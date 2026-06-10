"""Génère un rapport de diffusion quotidien de la radio AzuraCast.

Pour chaque titre joué dans la journée, compare la durée réellement
diffusée (écart entre son lancement et le lancement du titre suivant)
avec la durée du fichier audio. Signale les titres coupés trop tôt
et les trous d'antenne.

Usage :
    AZURACAST_API_KEY=xxx python Radio/playback_report.py --date 2026-06-09
    (sans --date : rapport sur la journée d'hier, UTC)

Le rapport est écrit dans Radio/logs/diffusion_YYYY-MM-DD.log
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Au-delà de cet écart entre durée réelle et durée du fichier,
# le titre est signalé (coupé ou suivi d'un trou d'antenne).
TOLERANCE_SECONDS = 10

BASE_URL = "https://parole-prophetique-fm.levangileduroyaume.com"
STATION_ID = 1


def fmt_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


def fetch_history(api_key: str, day: date) -> list[dict]:
    params = urllib.parse.urlencode({
        "start": f"{day.isoformat()}T00:00:00Z",
        "end": f"{day.isoformat()}T23:59:59Z",
        "rowsPerPage": 1000,
    })
    url = f"{BASE_URL}/api/station/{STATION_ID}/history?{params}"
    request = urllib.request.Request(url, headers={"X-API-Key": api_key})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def build_report(history: list[dict], day: date) -> tuple[str, int]:
    entries = sorted(history, key=lambda e: e["played_at"])
    lines = [
        f"Rapport de diffusion — {day.isoformat()} (heures UTC)",
        f"{len(entries)} titres joués | tolérance ±{TOLERANCE_SECONDS}s",
        "=" * 100,
        f"{'HEURE':8s} {'PLAYLIST':28s} {'FICHIER':10s} {'RÉEL':>10s} {'ÉCART':>8s}  STATUT  TITRE",
        "-" * 100,
    ]
    problems = 0

    for i, entry in enumerate(entries):
        started = datetime.fromtimestamp(entry["played_at"], tz=timezone.utc)
        expected = entry.get("duration") or 0
        title = (entry.get("song") or {}).get("title") or "?"
        playlist = entry.get("playlist") or "?"

        if i + 1 < len(entries):
            actual = entries[i + 1]["played_at"] - entry["played_at"]
            gap = actual - expected
            if expected == 0:
                status, shown_gap = "❔ durée inconnue", ""
            elif gap < -TOLERANCE_SECONDS:
                status, shown_gap = "❌ COUPÉ", f"{gap:+d}s"
                problems += 1
            elif gap > TOLERANCE_SECONDS:
                status, shown_gap = "⚠️ TROU APRÈS", f"{gap:+d}s"
                problems += 1
            else:
                status, shown_gap = "✅", f"{gap:+d}s"
            actual_str = fmt_duration(actual)
        else:
            actual_str, shown_gap, status = "?", "", "⏳ dernier titre (durée réelle inconnue)"

        lines.append(
            f"{started:%H:%M:%S} {playlist[:28]:28s} {fmt_duration(expected):>10s} "
            f"{actual_str:>10s} {shown_gap:>8s}  {status}  {title}"
        )

    lines += [
        "-" * 100,
        f"Bilan : {len(entries)} titres, {problems} anomalie(s) "
        f"(titre coupé de plus de {TOLERANCE_SECONDS}s ou trou d'antenne).",
    ]
    return "\n".join(lines) + "\n", problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Jour à analyser (YYYY-MM-DD), défaut : hier en UTC")
    parser.add_argument("--output-dir", default="Radio/logs")
    args = parser.parse_args()

    api_key = os.getenv("AZURACAST_API_KEY")
    if not api_key:
        print("ERREUR: variable d'environnement AZURACAST_API_KEY manquante.")
        return 2

    day = date.fromisoformat(args.date) if args.date else (
        datetime.now(timezone.utc).date() - timedelta(days=1)
    )

    history = fetch_history(api_key, day)
    if not history:
        print(f"Aucune diffusion trouvée pour le {day.isoformat()}.")
        return 0

    report, problems = build_report(history, day)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"diffusion_{day.isoformat()}.log"
    output_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"Rapport écrit : {output_path}")
    return 0


if __name__ == "__main__":
    main()
    sys.exit(0)
