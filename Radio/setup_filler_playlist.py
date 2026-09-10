"""Playlist de secours 015_REMPLISSAGE — comble les résidus de fin de bloc.

POURQUOI
--------
Un bloc s'arrête de jouer avant la fin de sa fenêtre quand l'item suivant du
plan est trop long pour le temps restant. AzuraCast lance tout ce qui tient
(d'où le jingle de 10 s juste avant), puis refuse le titre long : la file se
vide et Liquidsoap bascule sur son fichier de secours par défaut,
« AzuraCast is Live! », jusqu'à la seconde de bascule.

Mesuré sur août-septembre 2026 : 28 assèchements aux frontières 05h59, 11h59,
17h59, 23h29 et 23h59, de 1 à 55 s (médiane 30 s). Ce vide est aussi ce qui
provoque le double remplissage de la file au démarrage du bloc suivant — le
message du jour parti 2× d'affilée les 3, 4 et 5 août (README §7).

Ce n'est pas un manque de contenu : les blocs débordent de 12 à 40 min. Il
manque un item COURT à jouer dans le résidu.

COMMENT
-------
Une playlist en **rotation générale** (aucun créneau horaire) sert de filet :
les 4 blocs + BLOC_E + 000_TRANSITION couvrent 100 % de la journée, donc elle
ne peut jouer que lorsqu'aucune playlist planifiée ne fournit de titre —
c'est-à-dire précisément dans les résidus.

Contenu : les jingles de la station et les chapitres bibliques les plus courts
(Psaume 117 = 16 s…). Si un titre déborde un peu sur la frontière, c'est de la
Parole, pas la marque d'un tiers.

PRUDENCE — ne JAMAIS ajouter de fichier via `PUT /file/{id}` : cet endpoint
détruit puis recrée les lignes du fichier dans ses AUTRES playlists, en les
ré-appendant en fin (README §5). C'est ce qui avait fait sauter 85 % des
jingles le 02/07/2026. On passe donc exclusivement par l'import M3U, comme la
rotation. Corollaire : l'import n'écrase rien, il ajoute — d'où le filtrage
des chemins déjà présents pour rester idempotent.

Usage :
    AZURACAST_API_KEY=xxx python Radio/setup_filler_playlist.py            # dry-run
    AZURACAST_API_KEY=xxx python Radio/setup_filler_playlist.py --apply
    AZURACAST_API_KEY=xxx python Radio/setup_filler_playlist.py --disable  # rollback
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from azuracast_rotation_4_blocs import (
    BIBLE_PLAYLIST_NAME,
    JINGLE_PLAYLIST_NAME,
    MediaItem,
    find_playlist,
    get_playlist_files,
    import_playlist_paths,
    request_api,
)

BASE_URL = "https://parole-prophetique-fm.levangileduroyaume.com"
STATION_ID = 1

FILLER_PLAYLIST_NAME = "015_REMPLISSAGE"

# Le plus long résidu mesuré sur août-septembre 2026 est de 55 s. Un plafond à
# 90 s laisse de quoi le combler d'un seul titre sans déborder franchement sur
# le bloc suivant, tout en gardant assez de chapitres éligibles pour éviter la
# répétition.
MAX_FILLER_SECONDS = 90

# Même plancher que la rotation : en dessous, l'AutoDJ échoue à lancer le
# fichier et ressert un titre déjà en file (README §7).
MIN_FILLER_SECONDS = 9

# Réglages de la playlist. Ce qui rend une playlist planifiée dans cette
# version d'AzuraCast, c'est la présence de `schedule_items`, pas le `type` :
# 000_TRANSITION est elle aussi `type: default`, mais avec un créneau 00h00-00h02.
# Ici, AUCUN créneau — c'est délibéré et c'est tout l'intérêt : une playlist
# planifiée préempterait le bloc au lieu de le compléter.
# `order: shuffle` évite d'entendre toujours le même psaume à 17h59.
FILLER_SETTINGS: dict[str, Any] = {
    "name": FILLER_PLAYLIST_NAME,
    "type": "default",
    "source": "songs",
    "order": "shuffle",
    "is_enabled": True,
    "include_in_requests": False,
    "avoid_duplicates": True,
    "weight": 1,
}


def select_filler_items(
    jingles: list[MediaItem],
    bible: list[MediaItem],
    max_seconds: int = MAX_FILLER_SECONDS,
    min_seconds: int = MIN_FILLER_SECONDS,
) -> list[MediaItem]:
    """Jingles + chapitres bibliques courts, dédoublonnés, triés par durée.

    Le tri par durée n'a pas d'effet à la diffusion (la playlist est en
    aléatoire) mais rend le dry-run lisible : on voit d'un coup d'œil ce qui
    comblera un résidu de 15 s et ce qui comblera 55 s.
    """
    retenus: dict[str, MediaItem] = {}
    for item in list(jingles) + list(bible):
        if not (min_seconds <= item.length <= max_seconds):
            continue
        retenus.setdefault(item.path, item)
    return sorted(retenus.values(), key=lambda i: (i.length, i.path))


def missing_paths(desired: list[MediaItem], present: list[MediaItem]) -> list[str]:
    """Chemins à importer : ceux qui manquent. L'import M3U ajoute sans
    écraser, donc réimporter l'existant créerait des doublons de lignes."""
    deja = {item.path for item in present}
    return [item.path for item in desired if item.path not in deja]


def extra_paths(desired: list[MediaItem], present: list[MediaItem]) -> list[str]:
    """Chemins présents mais hors critères. Volontairement NON retirés : la
    suppression passerait par `PUT /file/{id}`, qui réordonnerait les blocs.
    Signalés pour décision humaine."""
    voulus = {item.path for item in desired}
    return sorted(item.path for item in present if item.path not in voulus)


# Réglages dont dépend tout le mécanisme. `POST /playlists` ignore certains
# champs (README §5) et l'interface AzuraCast permet de les modifier à la main :
# sans contrôle, la playlist pourrait devenir inopérante sans que rien ne le
# signale.
#
# Volontairement limité à ces trois-là. `include_in_automation` en faisait
# partie au départ : erreur. Le dump complet de 000_TRANSITION (10/09/2026,
# workflow radio-test-playlists) montre que l'API ne renvoie même pas ce
# champ pour cette station — la comparaison valait donc toujours None, soit
# un avertissement permanent, c'est-à-dire aucun avertissement. Ce champ
# désigne d'ailleurs la fonction « Automated Assignment » d'AzuraCast, qui
# redistribue les titres entre playlists : on n'en veut surtout pas ici.
CRITICAL_SETTINGS = ("type", "is_enabled", "order")


def _normalize(value: Any) -> Any:
    """Compare 1/True/'true' et 'Default'/'default' sans faux écart."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value) if value in (0, 1) else value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "1"):
            return True
        if low in ("false", "0"):
            return False
        return low
    return value


def settings_drift(playlist: dict[str, Any],
                   wanted: dict[str, Any] = FILLER_SETTINGS) -> list[str]:
    """Réglages critiques qui diffèrent de ce qui est demandé."""
    ecarts = []
    for key in CRITICAL_SETTINGS:
        attendu, reel = _normalize(wanted.get(key)), _normalize(playlist.get(key))
        if attendu != reel:
            ecarts.append(f"{key} : attendu {wanted.get(key)!r}, "
                          f"AzuraCast a {playlist.get(key)!r}")
    return ecarts


def find_or_create_playlist(base_url: str, station_id: int, api_key: str,
                            dry_run: bool) -> dict[str, Any] | None:
    """Playlist de secours, créée si absente. None en dry-run si elle manque."""
    try:
        return find_playlist(base_url, station_id, api_key, FILLER_PLAYLIST_NAME)
    except Exception:
        pass

    if dry_run:
        print(f"[DRY-RUN] La playlist {FILLER_PLAYLIST_NAME} serait créée :")
        for key, value in FILLER_SETTINGS.items():
            print(f"    {key} = {value!r}")
        return None

    url = f"{base_url.rstrip('/')}/api/station/{station_id}/playlists"
    resp = request_api("POST", url, api_key, json=FILLER_SETTINGS, timeout=60)
    if not resp.ok:
        raise RuntimeError(
            f"Création de {FILLER_PLAYLIST_NAME} refusée. Status={resp.status_code}\n"
            f"{resp.text[:400]}")
    print(f"Playlist {FILLER_PLAYLIST_NAME} créée.")
    return find_playlist(base_url, station_id, api_key, FILLER_PLAYLIST_NAME)


def set_enabled(base_url: str, station_id: int, api_key: str,
                playlist_id: int, enabled: bool) -> None:
    """Active ou désactive la playlist — rollback en une commande."""
    url = f"{base_url.rstrip('/')}/api/station/{station_id}/playlist/{playlist_id}"
    resp = request_api("PUT", url, api_key, json={"is_enabled": enabled}, timeout=60)
    if not resp.ok:
        raise RuntimeError(f"Bascule is_enabled={enabled} refusée. "
                           f"Status={resp.status_code}\n{resp.text[:300]}")
    print(f"{FILLER_PLAYLIST_NAME} : is_enabled = {enabled}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="applique (défaut : dry-run)")
    parser.add_argument("--disable", action="store_true",
                        help="désactive la playlist de secours (rollback)")
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--station-id", type=int, default=STATION_ID)
    args = parser.parse_args(argv)

    api_key = os.getenv("AZURACAST_API_KEY")
    if not api_key:
        print("ERREUR: variable d'environnement AZURACAST_API_KEY manquante.")
        return 2
    base, station = args.base_url, args.station_id

    if args.disable:
        playlist = find_playlist(base, station, api_key, FILLER_PLAYLIST_NAME)
        set_enabled(base, station, api_key, int(playlist["id"]), False)
        print("RESULTAT: playlist de secours desactivee.")
        return 0

    jingle_pl = find_playlist(base, station, api_key, JINGLE_PLAYLIST_NAME)
    bible_pl = find_playlist(base, station, api_key, BIBLE_PLAYLIST_NAME)
    jingles = get_playlist_files(base, station, api_key, int(jingle_pl["id"]), "jingle")
    bible = get_playlist_files(base, station, api_key, int(bible_pl["id"]), "bible")
    desired = select_filler_items(jingles, bible)

    n_jingles = sum(1 for i in desired if i.source == "jingle")
    print(f"Candidats : {len(desired)} titre(s) de {MIN_FILLER_SECONDS}-{MAX_FILLER_SECONDS}s "
          f"({n_jingles} jingle(s), {len(desired) - n_jingles} chapitre(s) biblique(s)).")
    for item in desired[:15]:
        print(f"  {item.length:3d}s  {item.path}")
    if len(desired) > 15:
        print(f"  ... + {len(desired) - 15} autre(s)")

    if not desired:
        print("RESULTAT: aucun titre eligible — playlist de secours inchangee.")
        return 1

    playlist = find_or_create_playlist(base, station, api_key, dry_run=not args.apply)
    if playlist is None:                       # dry-run, playlist pas encore créée
        print(f"\n[DRY-RUN] {len(desired)} titre(s) seraient importés.")
        print(f"RESULTAT: {len(desired)} titre(s) a importer (dry-run, rien envoye).")
        return 0

    # allow_empty : une playlist fraîchement créée est vide, ce qui est
    # l'état de départ normal ici — pas une anomalie comme pour les
    # bibliothèques sources.
    present = get_playlist_files(base, station, api_key, int(playlist["id"]), "filler",
                                 allow_empty=True)
    a_importer = missing_paths(desired, present)
    en_trop = extra_paths(desired, present)

    print(f"\nPlaylist {FILLER_PLAYLIST_NAME} (ID {playlist['id']}) : "
          f"{len(present)} titre(s) présent(s), {len(a_importer)} à importer.")

    ecarts = settings_drift(playlist)
    if ecarts:
        print("  AVERTISSEMENT: réglages critiques inattendus — le filet de secours "
              "peut être inopérant :")
        for ecart in ecarts:
            print(f"    {ecart}")
    else:
        print(f"  Réglages critiques conformes ({', '.join(CRITICAL_SETTINGS)}) ✅")
    for path in en_trop:
        print(f"  AVERTISSEMENT: hors critères, laissé en place (retrait manuel) : {path}")

    if not a_importer:
        print("RESULTAT: 0 titre a importer — playlist de secours deja conforme.")
        return 0

    if not args.apply:
        print(f"\n[DRY-RUN] {len(a_importer)} titre(s) seraient importés.")
        print(f"RESULTAT: {len(a_importer)} titre(s) a importer (dry-run, rien envoye).")
        return 0

    imported = import_playlist_paths(base, station, int(playlist["id"]), api_key,
                                     a_importer, dry_run=False)
    print(f"RESULTAT: {imported} titre(s) importe(s) dans {FILLER_PLAYLIST_NAME}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
