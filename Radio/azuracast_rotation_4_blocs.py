#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import re
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


@dataclass
class MediaItem:
    id: int
    path: str
    title: str
    length: int
    source: str


MUSIC_PLAYLIST_NAME = "001_LA_MUSIQUE"
BIBLE_PLAYLIST_NAME = "002_BIBLE AUDIO"
JINGLE_PLAYLIST_NAME = "014_Jingles"

BLOCK_PLAYLISTS = [
    "BLOC_A_SERIE_DU_JOUR",
    "BLOC_B_SERIE_DU_JOUR",
    "BLOC_C_SERIE_DU_JOUR",
    "BLOC_D_SERIE_DU_JOUR",
]

CYCLE_PLAN = [
    ("jingle", "avant_message"),
    ("message", None),
    ("jingle", "avant_bible"),
    ("bible", 60 * 60),
    ("jingle", "avant_louange"),
    ("music", 60 * 60),
    ("jingle", "avant_bible"),
    ("bible", 30 * 60),
    ("jingle", "avant_louange"),
    ("music", 60 * 60),
    ("jingle", "avant_bible"),
    ("bible", 45 * 60),
    ("jingle", "avant_louange"),
    ("music", 60 * 60),
    ("jingle", "avant_bible"),
    ("bible", 20 * 60),
    ("jingle", "avant_louange"),
    ("music", 25 * 60),
]


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


def seconds_to_hms(seconds: int) -> str:
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


def extract_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("rows") or data.get("items") or data.get("results") or []
    return []


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


def get_playlist_files(base_url: str, station_id: int, api_key: str, playlist_id: int, source_name: str) -> list[MediaItem]:
    url = f"{base_url.rstrip('/')}/api/station/{station_id}/files"
    response = request_api("GET", url, api_key, timeout=180, params={"playlist": playlist_id})
    if not response.ok:
        raise RuntimeError(f"Impossible de lister les fichiers playlist={playlist_id}. Status={response.status_code}\n{response.text[:800]}")
    rows = extract_rows(parse_json_or_explain(response))

    items = []
    for row in rows:
        playlists = row.get("playlists", [])
        if playlists and not any(p.get("id") == playlist_id for p in playlists):
            continue
        path = row.get("path")
        length = int(row.get("length") or 0)
        if not path or length <= 0:
            continue
        items.append(MediaItem(
            id=int(row["id"]),
            path=path,
            title=row.get("title") or row.get("text") or path,
            length=length,
            source=source_name,
        ))

    if not items:
        raise RuntimeError(f"Aucun fichier utilisable trouvé pour playlist_id={playlist_id} ({source_name}).")
    return items


def clear_playlist_contents(base_url: str, station_id: int, playlist_id: int, api_key: str, dry_run: bool) -> int:
    url = f"{base_url.rstrip('/')}/api/station/{station_id}/files"
    response = request_api("GET", url, api_key, timeout=120, params={"playlist": playlist_id})
    if not response.ok:
        raise RuntimeError(f"Impossible de lister les fichiers. Status={response.status_code}\n{response.text[:800]}")

    all_files = extract_rows(parse_json_or_explain(response))
    files_in_playlist = [
        f for f in all_files
        if any(p.get("id") == playlist_id for p in f.get("playlists", []))
    ]

    count = len(files_in_playlist)
    print(f"Nettoyage playlist ID {playlist_id}: {count} fichier(s) à retirer.")

    if dry_run:
        return count

    for f in files_in_playlist:
        file_id = f["id"]
        remaining_playlists = [p["id"] for p in f.get("playlists", []) if p["id"] != playlist_id]
        update_url = f"{base_url.rstrip('/')}/api/station/{station_id}/file/{file_id}"
        resp = request_api("PUT", update_url, api_key, json={"playlists": remaining_playlists})
        if not resp.ok:
            raise RuntimeError(f"Impossible de retirer le fichier {file_id}. Status={resp.status_code}\n{resp.text[:400]}")

    print(f"Playlist ID {playlist_id} vidée.")
    return count


def categorize_jingles(
    all_jingles: list[MediaItem],
    config_categories: dict[str, list[str]],
) -> dict[str, list[MediaItem]]:
    """Répartit les jingles en catégories selon les chemins définis dans la config."""
    path_to_item = {item.path: item for item in all_jingles}
    categorized: dict[str, list[MediaItem]] = {}

    categorized_paths: set[str] = set()
    for cat, paths in config_categories.items():
        items = [path_to_item[p] for p in paths if p in path_to_item]
        categorized[cat] = items
        categorized_paths.update(p for p in paths if p in path_to_item)

    uncategorized = [j for j in all_jingles if j.path not in categorized_paths]
    if uncategorized:
        categorized.setdefault("transition", []).extend(uncategorized)

    total = sum(len(v) for v in categorized.values())
    for cat, items in categorized.items():
        print(f"  Catégorie jingle '{cat}': {len(items)} fichier(s)")
    if not total:
        raise RuntimeError("Aucun jingle trouvé dans aucune catégorie.")
    return categorized


def pick_jingle_from_category(
    category: str,
    jingle_categories: dict[str, list[MediaItem]],
    used_jingles: set[str],
    previous_path: str | None,
) -> MediaItem:
    """Sélectionne un jingle dans la catégorie demandée, avec fallback sur 'transition' puis tout."""
    fallback_order = [category, "transition"] + [k for k in jingle_categories if k not in (category, "transition")]

    for cat in fallback_order:
        pool = jingle_categories.get(cat, [])[:]
        random.shuffle(pool)
        for item in pool:
            if item.path != previous_path and item.path not in used_jingles:
                used_jingles.add(item.path)
                return item

    # Dernière chance : ignorer used_jingles, juste éviter le précédent
    for cat in fallback_order:
        pool = jingle_categories.get(cat, [])[:]
        random.shuffle(pool)
        for item in pool:
            if item.path != previous_path:
                used_jingles.add(item.path)
                return item

    all_items = [j for lst in jingle_categories.values() for j in lst]
    if not all_items:
        raise RuntimeError("Aucun jingle disponible.")
    item = all_items[0]
    used_jingles.add(item.path)
    return item


def extract_book_chapter(title: str, path: str) -> tuple[str, int]:
    """
    Extrait le nom du livre et le numéro de chapitre depuis le titre ou le chemin.

    Formats supportés :
      - "Lévitique 21" / "Esther 5"   → ("Lévitique", 21)
      - "2 Chroniques 24"              → ("2 Chroniques", 24)
      - "Bible_fr_06_joshua_016"       → ("Joshua", 16)
      - "Bible_fr_01_gen_008"          → ("Gen", 8)
      - "Matthieu" / "1 Corinthiens"  → ("Matthieu", 0)  / ("1 Corinthiens", 0)
    """
    t = title.strip()

    # Format 1 : titre se termine par un espace + entier (ex. "Lévitique 21")
    m = re.match(r'^(.+?)\s+(\d+)$', t)
    if m:
        return m.group(1).strip(), int(m.group(2))

    # Format 2 : chemin/titre type "Bible_fr_06_bookname_NNN"
    base = path.split('/')[-1].replace('.mp3', '').lower()
    m2 = re.match(r'bible_fr_\d+_(.+?)_(\d+)$', base)
    if m2:
        book = m2.group(1).replace('_', ' ').title()
        return book, int(m2.group(2))
    # Même pattern mais dans le titre (le titre IS le nom du fichier)
    m3 = re.match(r'bible_fr_\d+_(.+?)_(\d+)$', t.lower().replace(' ', '_'))
    if m3:
        book = m3.group(1).replace('_', ' ').title()
        return book, int(m3.group(2))

    # Format 3 : livre entier, pas de numéro → chapitre 0
    return t, 0


def group_bible_by_book(bible_files: list[MediaItem]) -> dict[str, list[MediaItem]]:
    """
    Regroupe les fichiers Bible par livre et les trie par numéro de chapitre.
    Retourne {nom_livre: [MediaItem_ch1, MediaItem_ch2, ...]}.
    """
    buckets: dict[str, list[tuple[int, MediaItem]]] = {}
    for item in bible_files:
        book, chapter = extract_book_chapter(item.title, item.path)
        buckets.setdefault(book, []).append((chapter, item))

    return {
        book: [item for _, item in sorted(chapters, key=lambda x: x[0])]
        for book, chapters in buckets.items()
    }


def pick_bible_sequential(
    bible_books: dict[str, list[MediaItem]],
    target_seconds: int,
    used_books_cycle: set[str],
    avoid_paths: set[str],
) -> tuple[list[MediaItem], int, str]:
    """
    Choisit un livre Bible non encore utilisé ce cycle, puis lit ses chapitres
    dans l'ordre jusqu'à atteindre la durée cible.

    Si le livre se termine avant la cible, enchaîne avec un autre livre.
    Retourne (fichiers_sélectionnés, durée_totale, nom_du_premier_livre).
    """
    # Livres disponibles : préférer ceux non utilisés ce cycle
    preferred = [b for b in bible_books if b not in used_books_cycle]
    others    = [b for b in bible_books if b in used_books_cycle]

    random.shuffle(preferred)
    random.shuffle(others)
    book_order = preferred + others

    selected: list[MediaItem] = []
    total = 0
    first_book: str | None = None

    for book_name in book_order:
        chapters = bible_books[book_name]
        for item in chapters:
            if item.path in avoid_paths:
                continue
            selected.append(item)
            total += item.length
            if first_book is None:
                first_book = book_name
            if total >= target_seconds:
                return selected, total, first_book

    # Fallback : si toujours sous la cible, on ignore avoid_paths et on complète
    if total < target_seconds:
        used_paths = {i.path for i in selected}
        for book_name in book_order:
            for item in bible_books[book_name]:
                if item.path not in used_paths:
                    selected.append(item)
                    total += item.length
                    if first_book is None:
                        first_book = book_name
                    if total >= target_seconds:
                        return selected, total, first_book or "inconnue"

    if total < target_seconds:
        print(f"AVERTISSEMENT: Bible insuffisante: {seconds_to_hms(total)} / {seconds_to_hms(target_seconds)}")

    return selected, total, first_book or "inconnue"


def pick_until_duration(
    files: list[MediaItem],
    target_seconds: int,
    source_name: str,
    avoid_paths: set[str] | None = None,
):
    avoid_paths = avoid_paths or set()
    selected = []
    selected_paths = set()
    total = 0
    repeated_count = 0

    candidates = files[:]
    random.shuffle(candidates)

    for item in candidates:
        if item.path in selected_paths or item.path in avoid_paths:
            continue
        selected.append(item)
        selected_paths.add(item.path)
        total += item.length
        if total >= target_seconds:
            return selected, total, repeated_count

    candidates = files[:]
    random.shuffle(candidates)

    for item in candidates:
        if item.path in selected_paths:
            continue
        selected.append(item)
        selected_paths.add(item.path)
        total += item.length
        if item.path in avoid_paths:
            repeated_count += 1
        if total >= target_seconds:
            break

    if total < target_seconds:
        print(f"AVERTISSEMENT: bloc {source_name} sous la cible: {seconds_to_hms(total)} / {seconds_to_hms(target_seconds)}")

    return selected, total, repeated_count


def build_full_cycle(
    block_name: str,
    message: Episode,
    music_files: list[MediaItem],
    bible_books: dict[str, list[MediaItem]],
    jingle_categories: dict[str, list[MediaItem]],
    used_music_global: set[str],
    used_bible_global: set[str],
):
    playlist_paths = []
    debug_blocks = []
    used_music_cycle = set()
    used_bible_books_cycle: set[str] = set()   # livres déjà utilisés dans ce bloc
    used_jingles_cycle = set()
    previous_jingle = None
    total_duration_without_message = 0

    for block_type, param in CYCLE_PLAN:
        if block_type == "message":
            playlist_paths.append(message.path)
            debug_blocks.append({
                "type": "message",
                "title": message.title,
                "path": message.path,
                "duration": "inconnue dans config",
                "files": 1,
            })
            continue

        if block_type == "jingle":
            jingle_category = param  # "avant_message", "avant_bible" ou "avant_louange"
            item = pick_jingle_from_category(jingle_category, jingle_categories, used_jingles_cycle, previous_jingle)
            previous_jingle = item.path
            playlist_paths.append(item.path)
            total_duration_without_message += item.length
            debug_blocks.append({
                "type": "jingle",
                "category": jingle_category,
                "title": item.title,
                "path": item.path,
                "duration_seconds": item.length,
                "duration": seconds_to_hms(item.length),
                "files": 1,
            })
            continue

        if block_type == "bible":
            target_seconds = param
            avoid = used_bible_global | {message.path}
            selected, duration, starting_book = pick_bible_sequential(
                bible_books, target_seconds, used_bible_books_cycle, avoid
            )
            for item in selected:
                playlist_paths.append(item.path)
                used_bible_global.add(item.path)
            used_bible_books_cycle.add(starting_book)
            total_duration_without_message += duration
            books_in_slot = list(dict.fromkeys(
                extract_book_chapter(i.title, i.path)[0] for i in selected
            ))
            debug_blocks.append({
                "type": "bible",
                "target": seconds_to_hms(target_seconds),
                "duration_seconds": duration,
                "duration": seconds_to_hms(duration),
                "files": len(selected),
                "starting_book": starting_book,
                "books_in_slot": books_in_slot,
            })
            continue

        if block_type == "music":
            target_seconds = param
            avoid = used_music_global | used_music_cycle | {message.path}
            selected, duration, repeats = pick_until_duration(music_files, target_seconds, "music", avoid)
            for item in selected:
                playlist_paths.append(item.path)
                used_music_cycle.add(item.path)
                used_music_global.add(item.path)
            total_duration_without_message += duration
            debug_blocks.append({
                "type": "music",
                "target": seconds_to_hms(target_seconds),
                "duration_seconds": duration,
                "duration": seconds_to_hms(duration),
                "files": len(selected),
                "repetitions_in_block": 0,
                "repetitions_global": repeats,
            })
            continue

        raise ValueError(f"Type de bloc inconnu: {block_type}")

    debug = {
        "block_name": block_name,
        "message_series": message.series_name,
        "message_title": message.title,
        "message_path": message.path,
        "known_duration_without_message_seconds": total_duration_without_message,
        "known_duration_without_message": seconds_to_hms(total_duration_without_message),
        "total_files": len(playlist_paths),
        "blocks": debug_blocks,
    }
    return playlist_paths, debug


def print_debug_summary(debug: dict[str, Any]) -> None:
    print(f"\n========== RÉSUMÉ {debug['block_name']} ==========")
    print(f"Message: {debug['message_series']} — {debug['message_title']}")
    print(f"Durée connue hors message: {debug['known_duration_without_message']}")
    print(f"Nombre total fichiers: {debug['total_files']}")
    print("-------------------------------------")
    for idx, block in enumerate(debug["blocks"], start=1):
        if block["type"] == "message":
            print(f"{idx:02d}. MESSAGE | {block['title']} | durée {block['duration']}")
        elif block["type"] == "jingle":
            print(f"{idx:02d}. JINGLE  | {block['duration']} | {block['title']}")
        else:
            print(
                f"{idx:02d}. {block['type'].upper():7s} | cible {block['target']} | réel {block['duration']} "
                f"| fichiers {block['files']} | répétitions globales {block.get('repetitions_global', 0)}"
            )
    print("=====================================\n")


def import_playlist_paths(base_url: str, station_id: int, playlist_id: int, api_key: str, paths: list[str], dry_run: bool) -> int:
    url = f"{base_url.rstrip('/')}/api/station/{station_id}/playlist/{playlist_id}/import"
    m3u_content = "\n".join(paths).strip() + "\n"

    if dry_run:
        print("[DRY-RUN] Import du bloc")
        print("Nombre de chemins:", len(paths))
        print("Aperçu M3U:")
        print("\n".join(paths[:12]))
        if len(paths) > 12:
            print(f"... + {len(paths) - 12} autres")
        return len(paths)

    files = {"playlist_file": ("bloc_serie_du_jour.m3u", m3u_content.encode("utf-8"), "audio/x-mpegurl")}
    response = request_api("POST", url, api_key, files=files)

    if not response.ok:
        raise RuntimeError(f"Import échoué. Status={response.status_code}\n{response.text[:1500]}")

    result = parse_json_or_explain(response)
    import_results = result.get("import_results", []) if isinstance(result, dict) else []
    matched = sum(1 for item in import_results if item.get("match"))
    expected = len(paths)
    print(f"Import: {matched} fichier(s) trouvé(s) sur {expected} attendu(s).")

    if matched != expected:
        missing = [item.get("path", "?") for item in import_results if not item.get("match")]
        raise RuntimeError(
            f"ERREUR: attendu {expected}, obtenu {matched}.\n"
            f"Fichiers introuvables aperçu:\n" + "\n".join(missing[:20])
        )

    return matched


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="azuracast_rotation_config_option_a.example.json")
    parser.add_argument("--state", default="azuracast_rotation_state.json")
    parser.add_argument("--debug-output", default="azuracast_4_blocs_debug.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-advance", action="store_true")
    args = parser.parse_args()

    config = load_json(Path(args.config))
    state_path = Path(args.state)

    base_url = os.getenv("AZURACAST_BASE_URL") or config.get("azuracast_base_url")
    api_key = os.getenv("AZURACAST_API_KEY") or config.get("azuracast_api_key")
    station_id = int(config.get("station_id", 1))

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

    next_index = current_index if state.get("last_run_date") is None else (current_index + 1) % len(episodes)
    ep = episodes[next_index]

    print("Épisode du jour pour les 4 blocs:")
    print(f"  Série: {ep.series_name}")
    print(f"  Titre: {ep.title}")
    print(f"  Chemin: {ep.path}")

    print("Chargement des playlists de destination...")
    block_playlists = []
    for name in BLOCK_PLAYLISTS:
        playlist = find_playlist(base_url, station_id, api_key, name)
        block_playlists.append((name, int(playlist["id"])))
        print(f"  {name} -> ID {playlist['id']}")

    print("Chargement bibliothèque musique...")
    music_playlist = find_playlist(base_url, station_id, api_key, MUSIC_PLAYLIST_NAME)
    music_files = get_playlist_files(base_url, station_id, api_key, int(music_playlist["id"]), "music")
    print(f"  Musique: {len(music_files)} fichiers (ID {music_playlist['id']})")

    print("Chargement bibliothèque Bible...")
    bible_playlist = find_playlist(base_url, station_id, api_key, BIBLE_PLAYLIST_NAME)
    bible_files = get_playlist_files(base_url, station_id, api_key, int(bible_playlist["id"]), "bible")
    bible_books = group_bible_by_book(bible_files)
    print(f"  Bible: {len(bible_files)} fichiers → {len(bible_books)} livres détectés (ID {bible_playlist['id']})")
    for book, chapters in sorted(bible_books.items()):
        print(f"    {book}: {len(chapters)} fichier(s)")

    print("Chargement bibliothèque jingles...")
    jingle_playlist = find_playlist(base_url, station_id, api_key, JINGLE_PLAYLIST_NAME)
    all_jingles = get_playlist_files(base_url, station_id, api_key, int(jingle_playlist["id"]), "jingle")
    print(f"  Jingles: {len(all_jingles)} fichiers (ID {jingle_playlist['id']})")

    print("Catégorisation des jingles...")
    config_jingle_cats = config.get("jingle_categories", {})
    if not config_jingle_cats:
        print("  AVERTISSEMENT: aucune 'jingle_categories' dans la config — tous les jingles vont en 'transition'.")
        config_jingle_cats = {"transition": [j.path for j in all_jingles]}
    jingle_categories = categorize_jingles(all_jingles, config_jingle_cats)

    all_debug = {
        "date": today,
        "message_series": ep.series_name,
        "message_title": ep.title,
        "message_path": ep.path,
        "blocks": [],
    }

    used_music_global: set[str] = set()
    used_bible_global: set[str] = set()

    for block_name, playlist_id in block_playlists:
        print(f"\n===== Construction {block_name} =====")
        cycle_paths, debug = build_full_cycle(
            block_name=block_name,
            message=ep,
            music_files=music_files,
            bible_books=bible_books,
            jingle_categories=jingle_categories,
            used_music_global=used_music_global,
            used_bible_global=used_bible_global,
        )
        print_debug_summary(debug)
        all_debug["blocks"].append(debug)

        clear_playlist_contents(base_url, station_id, playlist_id, api_key, args.dry_run)
        import_playlist_paths(base_url, station_id, playlist_id, api_key, cycle_paths, args.dry_run)

    save_json(Path(args.debug_output), all_debug)
    print(f"Résumé debug sauvegardé: {args.debug_output}")

    if not args.dry_run:
        print("Redémarrage de l'AutoDJ pour remettre les blocs à zéro...")
        restart_url = f"{base_url.rstrip('/')}/api/station/{station_id}/backend/restart"
        restart_resp = request_api("POST", restart_url, api_key)
        if restart_resp.ok:
            print("AutoDJ redémarré. Les blocs repartent de la position 1.")
        else:
            print(f"AVERTISSEMENT: Redémarrage AutoDJ échoué (status {restart_resp.status_code}). Les blocs peuvent reprendre en cours de route.")

        save_json(state_path, {
            "episode_index": next_index,
            "last_run_date": today,
            "active_series": ep.series_name,
            "active_title": ep.title,
            "active_path": ep.path,
            "total_episodes": len(episodes),
            "block_playlists": BLOCK_PLAYLISTS,
        })
        print("État sauvegardé:", state_path)

    print("Terminé.")


if __name__ == "__main__":
    main()
