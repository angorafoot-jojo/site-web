#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import requests


@dataclass
class Episode:
    series_name: str
    title: str
    path: str


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def flatten_episodes(config: dict[str, Any]) -> list[Episode]:
    episodes = []
    for serie in config["series"]:
        for ep in serie["episodes"]:
            episodes.append(Episode(serie["name"], ep["title"], ep["path"]))
    if not episodes:
        raise ValueError("Aucun épisode dans la configuration.")
    return episodes


def request_api(method: str, url: str, api_key: str, timeout: int = 30, **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {api_key}"
    headers["X-API-Key"] = api_key
    return requests.request(method, url, headers=headers, timeout=timeout, **kwargs)


def parse_json_or_explain(response: requests.Response) -> Any:
    try:
        return response.json()
    except Exception:
        raise RuntimeError(
            "AzuraCast n'a pas retourné du JSON.\n"
            f"Status HTTP: {response.status_code}\n"
            f"Content-Type: {response.headers.get('content-type')}\n"
            f"Réponse début:\n{response.text[:800]}"
        )


def find_playlist(base_url: str, station_id: int, api_key: str, name: str) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/station/{station_id}/playlists"
    response = request_api("GET", url, api_key)
    if not response.ok:
        raise RuntimeError(f"Impossible de lister les playlists. Status={response.status_code}\n{response.text[:800]}")
    playlists = parse_json_or_explain(response)
    for playlist in playlists:
        if playlist.get("name") == name:
            return playlist
    available = [p.get("name") for p in playlists]
    raise RuntimeError(f"Playlist cible introuvable: {name}. Disponibles: {available}")


def clear_playlist_contents(base_url: str, station_id: int, playlist_id: int, api_key: str, dry_run: bool) -> int:
    """Retire tous les fichiers de la playlist avant d'importer le nouvel épisode."""
    url = f"{base_url.rstrip('/')}/api/station/{station_id}/files"
    # Filtre par playlist si AzuraCast le supporte, timeout long car la librairie peut être grande
    response = request_api("GET", url, api_key, timeout=120, params={"playlist": playlist_id})
    if not response.ok:
        raise RuntimeError(f"Impossible de lister les fichiers. Status={response.status_code}\n{response.text[:800]}")

    data = parse_json_or_explain(response)
    all_files: list[dict] = data if isinstance(data, list) else data.get("rows", data.get("items", data.get("results", [])))

    # Si AzuraCast n'a pas filtré côté serveur, on filtre côté client


    files_in_playlist = [
        f for f in all_files
        if any(p.get("id") == playlist_id for p in f.get("playlists", []))
    ]

    count = len(files_in_playlist)
    print(f"Nettoyage de la playlist: {count} fichier(s) à retirer.")

    if dry_run:
        for f in files_in_playlist:
            print(f"  [DRY-RUN] Retirait: {f.get('path', f.get('title', '?'))}")
        return count

    for f in files_in_playlist:
        file_id = f["id"]
        remaining_playlists = [p["id"] for p in f.get("playlists", []) if p["id"] != playlist_id]
        update_url = f"{base_url.rstrip('/')}/api/station/{station_id}/file/{file_id}"
        resp = request_api("PUT", update_url, api_key, json={"playlists": remaining_playlists})
        if not resp.ok:
            raise RuntimeError(
                f"Impossible de retirer le fichier {file_id} de la playlist. "
                f"Status={resp.status_code}\n{resp.text[:400]}"
            )

    print(f"Playlist vidée ({count} fichier(s) retiré(s)).")
    return count


def import_single_episode(base_url: str, station_id: int, playlist_id: int, api_key: str, episode_path: str, dry_run: bool) -> int:
    """
    AzuraCast attend un upload multipart nommé playlist_file.
    On crée donc un mini fichier .m3u avec un seul chemin média.
    Retourne le nombre de fichiers trouvés et importés.
    """
    url = f"{base_url.rstrip('/')}/api/station/{station_id}/playlist/{playlist_id}/import"
    m3u_content = episode_path.strip() + "\n"

    if dry_run:
        print("[DRY-RUN] Import via playlist_file (.m3u temporaire)")
        print("URL:", url)
        print("playlist_file content:", repr(m3u_content))
        return 1

    files = {
        "playlist_file": ("serie_du_jour.m3u", m3u_content.encode("utf-8"), "audio/x-mpegurl")
    }

    response = request_api("POST", url, api_key, files=files)

    if not response.ok:
        raise RuntimeError(f"Import échoué. Status={response.status_code}\n{response.text[:1200]}")

    result = parse_json_or_explain(response)
    print("Réponse import:", json.dumps(result, ensure_ascii=False)[:800])

    # Extraire le nombre de fichiers trouvés — AzuraCast retourne import_results comme liste
    matched = 0
    if isinstance(result, dict):
        import_results = result.get("import_results", [])
        if isinstance(import_results, list):
            matched = len(import_results)
        if matched == 0:
            # Fallback sur d'autres formes de réponse possibles
            matched = (
                result.get("matched")
                or result.get("imported")
                or result.get("added")
                or (result.get("files") or {}).get("success")
                or 0
            )

    print(f"Import: {matched} fichier(s) trouvé(s) sur 1 attendu.")

    if matched != 1:
        raise RuntimeError(
            f"ERREUR: attendu 1 fichier importé, obtenu {matched}.\n"
            f"Vérifiez que ce chemin existe dans AzuraCast: {episode_path}"
        )

    return matched


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="azuracast_rotation_config_option_a.json")
    parser.add_argument("--state", default="azuracast_rotation_state.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-advance", action="store_true")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    state_path = Path(args.state)

    base_url = os.getenv("AZURACAST_BASE_URL") or config.get("azuracast_base_url")
    api_key = os.getenv("AZURACAST_API_KEY") or config.get("azuracast_api_key")
    station_id = int(config.get("station_id", 1))
    target_playlist_name = config.get("target_playlist_name", "SERIE_DU_JOUR")

    if not base_url:
        raise RuntimeError("azuracast_base_url manquant.")
    if not api_key or api_key == "REMPLACE_MOI":
        raise RuntimeError("Clé API manquante. Mets AZURACAST_API_KEY ou modifie le fichier config.")

    episodes = flatten_episodes(config)
    today = date.today().isoformat()

    if state_path.exists():
        state = load_json(state_path)
    else:
        state = {"episode_index": 0, "last_run_date": None}

    current_index = int(state.get("episode_index", 0))

    if state.get("last_run_date") == today and not args.force_advance:
        ep = episodes[current_index]
        print("Déjà exécuté aujourd'hui.")
        print(f"Épisode actif: {ep.series_name} — {ep.title}")
        return

    if state.get("last_run_date") is None:
        next_index = current_index
    else:
        next_index = (current_index + 1) % len(episodes)

    ep = episodes[next_index]

    print("Épisode du jour:")
    print(f"  Série: {ep.series_name}")
    print(f"  Titre: {ep.title}")
    print(f"  Chemin: {ep.path}")

    playlist = find_playlist(base_url, station_id, api_key, target_playlist_name)
    playlist_id = int(playlist["id"])
    print(f"Playlist cible: {target_playlist_name} / ID {playlist_id}")

    # Étape 1 : vider la playlist avant tout import
    clear_playlist_contents(base_url, station_id, playlist_id, api_key, args.dry_run)

    # Étape 2 : importer le nouvel épisode (lève une exception si 0 ou >1 fichier trouvé)
    import_single_episode(base_url, station_id, playlist_id, api_key, ep.path, args.dry_run)

    # Étape 3 : sauvegarder l'état seulement si les deux étapes ont réussi
    if not args.dry_run:
        save_json(state_path, {
            "episode_index": next_index,
            "last_run_date": today,
            "active_series": ep.series_name,
            "active_title": ep.title,
            "active_path": ep.path,
            "total_episodes": len(episodes),
        })
        print("État sauvegardé:", state_path)

    print("Terminé.")


if __name__ == "__main__":
    main()
