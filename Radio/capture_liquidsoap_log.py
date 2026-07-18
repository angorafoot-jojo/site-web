"""Capture horaire des événements du liquidsoap.log d'AzuraCast.

Le liquidsoap.log du serveur est un tampon glissant d'environ 24 h
(constaté le 18/07/2026 : 7 440 lignes couvrant ~28 h) : les causes des
anomalies (erreurs de décodage, échecs de fetch, fichiers sautés) ont
disparu avant que le rapport quotidien de 01h00 puisse les corréler.

Ce script est donc lancé toutes les heures par la CI : il récupère le
log via l'API, n'en garde que les lignes datées d'intérêt (erreurs,
avertissements, échecs, titres préparés) et les ajoute au fichier du
jour `Radio/logs/liquidsoap_events_<date>.log`. Le rapport de diffusion
peut ensuite chercher les causes dans ces archives.

Usage :
    AZURACAST_API_KEY=xxx python Radio/capture_liquidsoap_log.py

Idempotent : l'état (`liquidsoap_capture_state.json`, committé comme
azuracast_rotation_state.json) mémorise la position de lecture et
l'horodatage de la dernière ligne archivée — relancer le script
n'archive jamais deux fois la même ligne.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE_URL = "https://parole-prophetique-fm.levangileduroyaume.com"
STATION_ID = 1
LOG_KEY = "liquidsoap_log"

STATE_PATH = Path("Radio/liquidsoap_capture_state.json")
OUTPUT_DIR = Path("Radio/logs")

# Même politique que les rapports de diffusion (playback_report.py).
RETENTION_DAYS = 90

# Ligne datée du log Liquidsoap : « 2026/07/18 14:22:50 [source:niveau] texte ».
TIMESTAMPED_LINE = re.compile(r"^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) (.*)$")

# Lignes archivées (sur le texte après l'horodatage) :
# - niveaux 1 et 2 = erreurs/avertissements Liquidsoap (ex. decoder.id3:2) ;
# - échecs explicites (« Fetch failed: retry ») et mots-clés d'incident ;
# - « Prepared "chemin" » = le fichier que l'AutoDJ a mis en file — permet
#   de savoir si un jingle manquant a seulement été tenté ;
# - bascules de source (« switch ») utiles aux frontières de bloc.
# Les lignes non datées (bruit ffmpeg « [mp3float] ... ») sont inutilisables
# pour la corrélation et ne sont pas archivées.
KEEP_PATTERN = re.compile(
    r"(:[12]\] )|failed|error|skip|underrun|blank|Prepared \"|switch",
    re.IGNORECASE,
)


def fetch_log(api_key: str, position: int | None) -> dict:
    """GET /station/{id}/log/{key} — réponse {contents, eof, position}.

    `position` (offset de la lecture précédente) réduit la réponse aux
    octets nouveaux ; si le serveur l'ignore ou si le log a tourné, le
    filtrage par horodatage (extract_new_events) dédoublonne de toute
    façon — la position n'est qu'une optimisation.
    """
    url = f"{BASE_URL}/api/station/{STATION_ID}/log/{LOG_KEY}"
    if position:
        url += "?" + urllib.parse.urlencode({"position": position})
    request = urllib.request.Request(url, headers={"X-API-Key": api_key})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def extract_new_events(contents: str, last_ts: str) -> list[tuple[str, str]]:
    """[(horodatage, ligne complète)] des lignes d'intérêt strictement
    postérieures à `last_ts` (format « YYYY/MM/DD HH:MM:SS », comparable
    lexicographiquement). Limite assumée : plusieurs lignes dans la même
    seconde à cheval sur deux captures peuvent être perdues — sans enjeu
    à une capture par heure."""
    events = []
    for line in contents.splitlines():
        m = TIMESTAMPED_LINE.match(line)
        if not m:
            continue
        ts, text = m.group(1), m.group(2)
        if ts <= last_ts:
            continue
        if KEEP_PATTERN.search(text):
            events.append((ts, line))
    return events


def append_events(events: list[tuple[str, str]], output_dir: Path) -> dict[str, int]:
    """Ajoute chaque ligne au fichier du jour de SON horodatage (une capture
    à 00h17 porte des lignes de la veille et du jour). Renvoie {date: nb}."""
    output_dir.mkdir(parents=True, exist_ok=True)
    per_day: dict[str, list[str]] = {}
    for ts, line in events:
        day = ts[:10].replace("/", "-")
        per_day.setdefault(day, []).append(line)
    for day, lines in per_day.items():
        path = output_dir / f"liquidsoap_events_{day}.log"
        with path.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return {day: len(lines) for day, lines in per_day.items()}


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(path: Path, position: int, last_ts: str) -> None:
    path.write_text(
        json.dumps({"position": position, "last_ts": last_ts}, indent=2) + "\n",
        encoding="utf-8",
    )


def purge_old_events(output_dir: Path, today: date) -> None:
    cutoff = today - timedelta(days=RETENTION_DAYS)
    for log_file in sorted(output_dir.glob("liquidsoap_events_*.log")):
        try:
            file_day = date.fromisoformat(log_file.stem.removeprefix("liquidsoap_events_"))
        except ValueError:
            continue
        if file_day < cutoff:
            log_file.unlink()
            print(f"Archive supprimée (plus de {RETENTION_DAYS} jours) : {log_file}")


def main() -> int:
    api_key = os.getenv("AZURACAST_API_KEY")
    if not api_key:
        print("ERREUR: variable d'environnement AZURACAST_API_KEY manquante.")
        return 2

    state = load_state(STATE_PATH)
    last_ts = state.get("last_ts", "")
    position = state.get("position")

    data = fetch_log(api_key, position)
    contents = data.get("contents") or ""
    new_position = data.get("position") or 0

    # Log tourné (fichier plus petit que la position mémorisée) : la réponse
    # incrémentale est vide alors que du contenu existe — relire en entier,
    # le filtre par last_ts évite les doublons.
    if position and not contents.strip():
        data = fetch_log(api_key, None)
        contents = data.get("contents") or ""
        new_position = data.get("position") or 0

    events = extract_new_events(contents, last_ts)
    if events:
        counts = append_events(events, OUTPUT_DIR)
        for day, count in sorted(counts.items()):
            print(f"{count} événement(s) archivé(s) → {OUTPUT_DIR}/liquidsoap_events_{day}.log")
        last_ts = events[-1][0]
    else:
        print("Aucun nouvel événement d'intérêt dans le log.")

    save_state(STATE_PATH, new_position, last_ts)
    purge_old_events(OUTPUT_DIR, datetime.now(timezone.utc).date())
    return 0


if __name__ == "__main__":
    sys.exit(main())
