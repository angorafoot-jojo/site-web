"""Désactive le fondu (crossfade) sur les jingles de la station.

Le crossfade station (2s) fond chaque jingle des deux côtés : ~4s de son
dégradé, ce qui rend inaudibles les jingles courts (12 jingles ≤ 4s).
Ce script met fade_in / fade_out / fade_overlap à 0 sur tous les fichiers
du dossier Jingle/ : ils jouent alors sec, en entier.

Usage :
    AZURACAST_API_KEY=xxx python Radio/set_jingle_fades.py            # dry-run
    AZURACAST_API_KEY=xxx python Radio/set_jingle_fades.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys

import requests

BASE_URL = "https://parole-prophetique-fm.levangileduroyaume.com"
STATION_ID = 1
JINGLE_DIR = "Jingle/"
FADES = {"fade_in": 0, "fade_out": 0, "fade_overlap": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="applique (défaut : dry-run)")
    args = parser.parse_args()

    api_key = os.getenv("AZURACAST_API_KEY")
    if not api_key:
        print("ERREUR: variable d'environnement AZURACAST_API_KEY manquante.")
        return 2
    headers = {"X-API-Key": api_key}

    response = requests.get(f"{BASE_URL}/api/station/{STATION_ID}/files", headers=headers, timeout=300)
    response.raise_for_status()
    jingles = [f for f in response.json() if f["path"].startswith(JINGLE_DIR)]
    todo = [f for f in jingles if any(f.get(k) != v for k, v in FADES.items())]
    print(f"{len(jingles)} jingle(s), {len(todo)} à modifier (fade_in/out/overlap → 0).")
    for f in todo[:10]:
        print(f"  {int(f.get('length') or 0):3d}s  {f['path'].split('/')[-1]}")
    if len(todo) > 10:
        print(f"  ... + {len(todo) - 10} autres")

    if not args.apply:
        print("\n[DRY-RUN] Aucune modification envoyée. Relancer avec --apply.")
        return 0

    errors = 0
    for f in todo:
        r = requests.put(
            f"{BASE_URL}/api/station/{STATION_ID}/file/{f['id']}",
            headers=headers, json=FADES, timeout=60,
        )
        if not r.ok:
            errors += 1
            print(f"  ERREUR {r.status_code} sur {f['path']}")

    print(f"Terminé : {len(todo) - errors} modifié(s), {errors} erreur(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
