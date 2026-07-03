"""Vérifie que chaque chemin de la config de rotation existe dans la médiathèque AzuraCast.

Comparaison stricte octet pour octet (comme l'import M3U d'AzuraCast).
Sort avec le code 1 et la liste des chemins introuvables s'il y a un écart,
ce qui permet au workflow GitHub Actions d'alerter avant la rotation de 23h.

Usage :
    AZURACAST_API_KEY=xxx python Radio/validate_paths.py --config Radio/azuracast_rotation_config_option_a.example.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


def iter_config_paths(node: Any, key: str | None = None) -> Iterator[str]:
    if isinstance(node, dict):
        for k, v in node.items():
            yield from iter_config_paths(v, k)
    elif isinstance(node, list):
        for v in node:
            yield from iter_config_paths(v, key)
    elif key == "path" and isinstance(node, str):
        yield node


# Créneaux attendus (heures de la station UTC, format HHMM).
# 000_TRANSITION joue le jingle d'identification 00:00→00:02 juste après le
# restart de minuit ; BLOC_A enchaîne à 00:02. Toute dérive (planification
# vidée, playlist désactivée, option interrupt réactivée) fait échouer la
# validation → Issue GitHub avant la prochaine rotation.
EXPECTED_SLOTS = {
    "000_TRANSITION": (0, 2),
    "BLOC_A_SERIE_DU_JOUR": (2, 559),
    "BLOC_B_SERIE_DU_JOUR": (600, 1159),
    "BLOC_C_SERIE_DU_JOUR": (1200, 1759),
    # BLOC_D s'arrête à 23h29 : la rotation de 23h30 ne doit JAMAIS reconstruire
    # un bloc à l'antenne (sa file repartirait en position 1 → message du
    # lendemain en avant-première, coupé à minuit). BLOC_E_LOUANGE_NUIT
    # (statique, jamais touchée par la rotation) couvre 23h30→23h59.
    "BLOC_D_SERIE_DU_JOUR": (1800, 2329),
    "BLOC_E_LOUANGE_NUIT": (2330, 2359),
}


def validate_block_schedules(base_url: str, station_id: int, api_key: str) -> list[str]:
    url = f"{base_url.rstrip('/')}/api/station/{station_id}/playlists"
    request = urllib.request.Request(url, headers={"X-API-Key": api_key})
    with urllib.request.urlopen(request, timeout=120) as response:
        playlists = json.load(response)

    problems = []
    found = set()
    for p in playlists:
        name = p.get("name")
        if name not in EXPECTED_SLOTS:
            continue
        found.add(name)
        if not p.get("is_enabled"):
            problems.append(f"{name} : playlist désactivée")
        if "interrupt" in (p.get("backend_options") or []):
            problems.append(f"{name} : option 'interrupt' réactivée (bug AzuraCast #3254)")
        slots = [(s.get("start_time"), s.get("end_time")) for s in p.get("schedule_items", [])]
        if slots != [EXPECTED_SLOTS[name]]:
            problems.append(f"{name} : planification {slots} au lieu de [{EXPECTED_SLOTS[name]}]")
    for name in EXPECTED_SLOTS.keys() - found:
        problems.append(f"{name} : playlist introuvable")
    return problems


def validate_rotation_freshness(state_path: Path) -> list[str]:
    """La rotation tourne à 23h30 UTC et estampille `last_run_date` avec son JOUR
    d'exécution — c'est-à-dire la veille de la diffusion qu'elle prépare. À l'heure
    de cette validation (midi UTC), un système sain a donc un state daté d'HIER.
    On n'alerte que si le state est plus ancien (rotation ratée depuis plus de 24 h),
    auquel cas la radio rejoue un contenu périmé."""
    if not state_path.exists():
        return [f"fichier state introuvable : {state_path}"]
    state = json.loads(state_path.read_text(encoding="utf-8"))
    last_run = state.get("last_run_date")
    if not last_run:
        return ["state sans last_run_date — la rotation n'a jamais tourné"]
    try:
        last_run_date = date.fromisoformat(last_run)
    except ValueError:
        return [f"last_run_date illisible dans le state : {last_run!r}"]
    oldest_ok = datetime.now(timezone.utc).date() - timedelta(days=1)
    if last_run_date < oldest_ok:
        return [
            f"la rotation n'a pas tourné depuis plus de 24 h (state du {last_run}, "
            f"attendu ≥ {oldest_ok.isoformat()}) — la radio rejoue un contenu périmé"
        ]
    return []


def fetch_server_paths(base_url: str, station_id: int, api_key: str) -> set[str]:
    url = f"{base_url.rstrip('/')}/api/station/{station_id}/files"
    request = urllib.request.Request(url, headers={"X-API-Key": api_key})
    with urllib.request.urlopen(request, timeout=300) as response:
        files = json.load(response)
    return {f["path"] for f in files}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="Radio/azuracast_rotation_config_option_a.example.json")
    parser.add_argument("--state", default="Radio/azuracast_rotation_state.json")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    base_url = os.getenv("AZURACAST_BASE_URL") or config.get("azuracast_base_url")
    api_key = os.getenv("AZURACAST_API_KEY") or config.get("azuracast_api_key")
    station_id = int(config.get("station_id", 1))

    if not base_url or not api_key or api_key == "REMPLACE_MOI":
        print("ERREUR: azuracast_base_url ou clé API manquante (env AZURACAST_API_KEY).")
        return 2

    config_paths = list(iter_config_paths(config))
    server_paths = fetch_server_paths(base_url, station_id, api_key)
    missing = [p for p in config_paths if p not in server_paths]

    print(f"Chemins dans la config : {len(config_paths)}")
    print(f"Fichiers sur le serveur : {len(server_paths)}")

    schedule_problems = validate_block_schedules(base_url, station_id, api_key)
    freshness_problems = validate_rotation_freshness(Path(args.state))

    if missing:
        print(f"\n❌ {len(missing)} chemin(s) introuvable(s) sur AzuraCast :")
        for path in missing:
            print(f"  - {path}")
        print("\nLa prochaine rotation échouera si rien n'est corrigé.")

    if schedule_problems:
        print(f"\n❌ {len(schedule_problems)} problème(s) de planification des blocs :")
        for problem in schedule_problems:
            print(f"  - {problem}")
        print("\nSans planification correcte, les blocs jouent tous en même temps.")

    if freshness_problems:
        print("\n❌ Fraîcheur de la rotation :")
        for problem in freshness_problems:
            print(f"  - {problem}")

    if missing or schedule_problems or freshness_problems:
        return 1

    print("✅ Chemins valides, transition + 4 blocs planifiés, rotation du jour effectuée.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
