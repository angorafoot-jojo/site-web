"""Réécrit les métadonnées (titre + artiste) des fichiers bibliques d'AzuraCast.

Problème résolu : 924 des 1189 fichiers bibliques partagent un titre générique
(« La Bible », « Job », « Jeremie »…). Conséquences :
  - l'historique AzuraCast ne journalise pas deux titres consécutifs identiques
    → faux « trous » dans les rapports de diffusion ;
  - le regroupement par livre de la rotation mélangeait des livres entiers
    dans un même paquet sans ordre de chapitre fiable.

Le nom de fichier est la source de vérité : « La bible/jérémie_033.mp3 »
devient titre « Jérémie 33 », artiste « La Bible ».

Usage :
    AZURACAST_API_KEY=xxx python Radio/retitle_bible_files.py            # dry-run
    AZURACAST_API_KEY=xxx python Radio/retitle_bible_files.py --apply    # applique

Après un --apply, migrer la progression biblique du state avec --print-mapping
(voir la sortie du script).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests

BASE_URL = "https://parole-prophetique-fm.levangileduroyaume.com"
STATION_ID = 1
BIBLE_DIR = "La bible/"
ARTIST = "La Bible"

# Mots à laisser en minuscule dans les noms de livres (« Cantique des Cantiques »)
LOWERCASE_WORDS = {"des", "de", "du", "la", "le", "les", "et"}


def title_from_path(path: str) -> str | None:
    """« La bible/cantique_des_cantiques_004.mp3 » → « Cantique des Cantiques 4 »."""
    base = path.split("/")[-1].removesuffix(".mp3")
    m = re.match(r"^(.+?)_(\d+)$", base)
    if not m:
        return None
    words = m.group(1).split("_")
    book = " ".join(
        w if (w in LOWERCASE_WORDS and i > 0) else w.capitalize()
        for i, w in enumerate(words)
    )
    return f"{book} {int(m.group(2))}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="applique les changements (défaut : dry-run)")
    args = parser.parse_args()

    api_key = os.getenv("AZURACAST_API_KEY")
    if not api_key:
        print("ERREUR: variable d'environnement AZURACAST_API_KEY manquante.")
        return 2
    headers = {"X-API-Key": api_key}

    response = requests.get(f"{BASE_URL}/api/station/{STATION_ID}/files", headers=headers, timeout=300)
    response.raise_for_status()
    bible_files = [f for f in response.json() if f["path"].startswith(BIBLE_DIR)]
    print(f"{len(bible_files)} fichiers bibliques trouvés.")

    # Mapping ancien libellé de livre → nouveau, pour migrer bible_progress
    sys.path.insert(0, str(Path(__file__).parent))
    from azuracast_rotation_4_blocs import extract_book_chapter

    changes, skipped, mapping = [], 0, {}
    for f in bible_files:
        new_title = title_from_path(f["path"])
        if new_title is None:
            print(f"  ⚠️ nom de fichier hors format, ignoré : {f['path']}")
            continue
        old_book = extract_book_chapter(f.get("title") or "", f["path"])[0]
        new_book = extract_book_chapter(new_title, f["path"])[0]
        mapping.setdefault(old_book, set()).add(new_book)
        if f.get("title") == new_title and f.get("artist") == ARTIST:
            skipped += 1
            continue
        changes.append((f["id"], f["path"], f.get("title"), new_title))

    print(f"{len(changes)} fichier(s) à modifier, {skipped} déjà conformes.")
    for fid, path, old, new in changes[:10]:
        print(f"  «{old}» → «{new}»  ({path})")
    if len(changes) > 10:
        print(f"  ... + {len(changes) - 10} autres")

    print("\nMigration bible_progress (ancien livre → nouveau) :")
    for old_book in sorted(mapping):
        targets = mapping[old_book]
        if {old_book} == targets:
            continue
        status = sorted(targets)[0] if len(targets) == 1 else f"AMBIGU {sorted(targets)} → remettre à zéro"
        print(f"  «{old_book}» → {status}")

    if not args.apply:
        print("\n[DRY-RUN] Aucune modification envoyée. Relancer avec --apply.")
        return 0

    errors = 0
    for i, (fid, path, old, new) in enumerate(changes, 1):
        r = requests.put(
            f"{BASE_URL}/api/station/{STATION_ID}/file/{fid}",
            headers=headers, json={"title": new, "artist": ARTIST}, timeout=60,
        )
        if not r.ok:
            errors += 1
            print(f"  ERREUR {r.status_code} sur {path}")
        if i % 100 == 0:
            print(f"  {i}/{len(changes)}...")

    print(f"Terminé : {len(changes) - errors} modifiés, {errors} erreur(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
