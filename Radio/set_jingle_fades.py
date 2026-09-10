"""Désactive le fondu (crossfade) sur les jingles de la station.

POURQUOI
--------
Le crossfade station (2 s) fond chaque jingle des deux côtés : ~4 s de son
dégradé. Un jingle de 9 s ne dure alors que ~5 s à l'antenne, et l'AutoDJ
échoue à le lancer — il ressert un titre déjà en file. Ce script met
fade_in / fade_out / fade_overlap à 0 sur tous les fichiers du dossier
Jingle/ : ils jouent alors sec, en entier.

Un fichier fraîchement uploadé hérite du crossfade de la station : la
normalisation doit donc être rejouée après CHAQUE import de jingles.
C'est le rôle du workflow `radio-jingle-fades.yml` (quotidien, idempotent).

HISTORIQUE
----------
Lancé une seule fois à la main le 12/06/2026 sur les 40 jingles d'alors.
La banque ElevenLabs importée le 09-10/07/2026 n'a donc jamais été
normalisée : sur août 2026, ces jingles ont sauté 13 à 45 % du temps,
tandis que les jingles normalisés en juin (id_station_01/02/03) sautaient
0 à 6 % — à durée de fichier égale (9 s). Voir README §7.

Usage :
    AZURACAST_API_KEY=xxx python Radio/set_jingle_fades.py            # dry-run
    AZURACAST_API_KEY=xxx python Radio/set_jingle_fades.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import requests

BASE_URL = "https://parole-prophetique-fm.levangileduroyaume.com"
STATION_ID = 1
JINGLE_DIR = "Jingle/"
FADES = {"fade_in": 0, "fade_out": 0, "fade_overlap": 0}

# En dessous de cette durée *réelle à l'antenne*, l'AutoDJ échoue à lancer
# le fichier (mesuré en prod 07/2026, confirmé sur les 31 jours d'août).
# Un jingle non normalisé perd ~4 s : c'est ce seuil qu'il franchit.
RELIABLE_JINGLE_SECONDS = 9


def is_jingle(media: dict[str, Any], jingle_dir: str = JINGLE_DIR) -> bool:
    """Vrai si le fichier appartient au dossier des jingles."""
    return str(media.get("path", "")).startswith(jingle_dir)


def needs_fade_reset(media: dict[str, Any], fades: dict[str, int] = FADES) -> bool:
    """Vrai si au moins un champ de fondu n'est pas déjà à la valeur cible.

    Un champ à `None` signifie « hériter du crossfade de la station » : c'est
    précisément le cas à corriger. Un champ déjà à 0 (int ou float) est
    considéré conforme, ce qui rend le script idempotent.
    """
    for key, target in fades.items():
        current = media.get(key)
        if current is None or current != target:
            return True
    return False


def select_jingles_to_fix(
    files: list[dict[str, Any]],
    jingle_dir: str = JINGLE_DIR,
    fades: dict[str, int] = FADES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Retourne (jingles du dossier, jingles à normaliser)."""
    jingles = [f for f in files if is_jingle(f, jingle_dir)]
    todo = [f for f in jingles if needs_fade_reset(f, fades)]
    return jingles, todo


def format_media_line(media: dict[str, Any], fades: dict[str, int] = FADES) -> str:
    """Ligne de diagnostic : durée, durée utile estimée, fondus actuels."""
    length = int(media.get("length") or 0)
    current = {k: media.get(k) for k in fades}
    lost = sum(float(v) for v in current.values() if v)
    effective = max(0, length - int(lost))
    alert = "  ⚠️ indiffusable" if effective < RELIABLE_JINGLE_SECONDS else ""
    fades_txt = " ".join(f"{k.replace('fade_', '')}={current[k]}" for k in fades)
    name = str(media.get("path", "")).split("/")[-1]
    return f"  {length:3d}s → {effective:3d}s utiles   {fades_txt:<34} {name}{alert}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="applique (défaut : dry-run)")
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--station-id", type=int, default=STATION_ID)
    args = parser.parse_args(argv)

    api_key = os.getenv("AZURACAST_API_KEY")
    if not api_key:
        print("ERREUR: variable d'environnement AZURACAST_API_KEY manquante.")
        return 2
    headers = {"X-API-Key": api_key, "Authorization": f"Bearer {api_key}"}
    base = args.base_url.rstrip("/")

    response = requests.get(
        f"{base}/api/station/{args.station_id}/files", headers=headers, timeout=300
    )
    response.raise_for_status()
    jingles, todo = select_jingles_to_fix(response.json())

    print(f"{len(jingles)} jingle(s) dans {JINGLE_DIR}, {len(todo)} à normaliser (fondus → 0).")
    for media in todo:
        print(format_media_line(media))

    if not todo:
        print("RESULTAT: 0 jingle a normaliser — pool deja conforme.")
        return 0

    if not args.apply:
        print(f"\n[DRY-RUN] {len(todo)} jingle(s) à corriger. Relancer avec --apply.")
        print(f"RESULTAT: {len(todo)} jingle(s) a normaliser (dry-run, rien envoye).")
        return 0

    errors = 0
    for media in todo:
        resp = requests.put(
            f"{base}/api/station/{args.station_id}/file/{media['id']}",
            headers=headers, json=FADES, timeout=60,
        )
        if not resp.ok:
            errors += 1
            print(f"  ERREUR {resp.status_code} sur {media['path']}")

    fixed = len(todo) - errors
    print(f"Terminé : {fixed} normalisé(s), {errors} erreur(s).")
    print(f"RESULTAT: {fixed} jingle(s) normalise(s), {errors} erreur(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
