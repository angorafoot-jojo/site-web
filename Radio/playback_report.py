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
import difflib
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Au-delà de cet écart entre durée réelle et durée du fichier,
# le titre est signalé (coupé ou suivi d'un trou d'antenne).
TOLERANCE_SECONDS = 10

# Les rapports plus vieux que ça sont supprimés à chaque exécution.
RETENTION_DAYS = 90

BASE_URL = "https://parole-prophetique-fm.levangileduroyaume.com"
STATION_ID = 1

# Dossier où la rotation archive le plan ordonné du jour (réel vs prévu).
PLANS_DIR = "Radio/plans"


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


def load_plan(day: date, plans_dir: str = PLANS_DIR) -> dict | None:
    """Charge l'instantané de plan archivé par la rotation pour ce jour, ou None."""
    path = Path(plans_dir) / f"plan_{day.isoformat()}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def norm_title(title: str) -> str:
    """Forme normalisée d'un titre pour comparer plan et historique
    (insensible aux accents, à la casse, à la ponctuation et aux espaces).

    Les espaces sont SUPPRIMÉS, pas réduits : le plan stocke « PQE J 1 »
    quand l'historique journalise « pqe j1 » — avec des espaces conservés,
    le message était compté à tort « prévu non joué » + « joué non prévu »
    dans chaque bloc (conformité sous-estimée, vu sur les rapports de
    fin juin 2026)."""
    t = unicodedata.normalize("NFKD", title or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def _window_bounds(window: str) -> tuple[int, int]:
    """'06:00-12:00' -> (360, 720). Minutes UTC depuis minuit, fin exclusive.
    Précision à la minute requise depuis que BLOC_D s'arrête à 23h30
    (BLOC_E_LOUANGE_NUIT couvre 23h30-minuit, hors plan)."""
    start, end = window.split("-")
    return (int(start[:2]) * 60 + int(start[3:5]),
            int(end[:2]) * 60 + int(end[3:5]))


def build_plan_section(history: list[dict], day: date, plan: dict | None) -> str:
    """Section « RÉEL vs PRÉVU » : aligne, bloc par bloc, les titres réellement
    joués sur l'ordre théorique archivé lors de la rotation."""
    head = ["", "=" * 100, "RÉEL vs PRÉVU — ce qui a joué vs ce que le plan prévoyait", "=" * 100]
    if not plan:
        head.append(
            f"Plan non disponible pour le {day.isoformat()} "
            f"(aucun {PLANS_DIR}/plan_{day.isoformat()}.json). "
            "Les instantanés sont générés à chaque rotation à partir de leur mise en place."
        )
        return "\n".join(head) + "\n"

    entries = sorted(history, key=lambda e: e["played_at"])
    # Titre réel + heure de début pour chaque diffusion.
    played = [
        (datetime.fromtimestamp(e["played_at"], tz=timezone.utc),
         (e.get("song") or {}).get("title") or "?")
        for e in entries
    ]

    lines = list(head)
    tot_plan = tot_match = tot_extra = 0
    for block in plan.get("blocks", []):
        window = block.get("window", "")
        items = block.get("items", [])
        if not window or not items:
            continue
        m0, m1 = _window_bounds(window)
        planned_titles = [it.get("title", "?") for it in items]
        actual_titles = [t for (dt, t) in played if m0 <= dt.hour * 60 + dt.minute < m1]

        plan_norm = [norm_title(t) for t in planned_titles]
        act_norm = [norm_title(t) for t in actual_titles]
        sm = difflib.SequenceMatcher(None, plan_norm, act_norm, autojunk=False)

        matched = skipped_idx = extra_idx = 0
        skipped, extra = [], []
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "equal":
                matched += i2 - i1
            elif op == "delete":
                skipped += planned_titles[i1:i2]
            elif op == "insert":
                extra += actual_titles[j1:j2]
            elif op == "replace":
                skipped += planned_titles[i1:i2]
                extra += actual_titles[j1:j2]

        n_plan = len(planned_titles)
        conf = 100 * matched / n_plan if n_plan else 0
        tot_plan += n_plan
        tot_match += matched
        tot_extra += len(extra)

        name = (block.get("block_name") or "").replace("_SERIE_DU_JOUR", "")
        lines.append("-" * 100)
        lines.append(
            f"{name:7s} ({window})  prévus {n_plan:>3} · joués {len(actual_titles):>3} · "
            f"conformité {conf:>3.0f}% · sautés {len(skipped):>2} · en trop {len(extra):>2}"
        )
        if skipped:
            shown = " · ".join(skipped[:6])
            more = f"  …(+{len(skipped) - 6})" if len(skipped) > 6 else ""
            lines.append(f"   ⏭️  PRÉVU NON JOUÉ : {shown}{more}")
        if extra:
            shown = " · ".join(extra[:6])
            more = f"  …(+{len(extra) - 6})" if len(extra) > 6 else ""
            lines.append(f"   ➕  JOUÉ NON PRÉVU : {shown}{more}")

    lines.append("-" * 100)
    global_conf = 100 * tot_match / tot_plan if tot_plan else 0
    lines.append(
        f"CONFORMITÉ GLOBALE : {tot_match}/{tot_plan} titres prévus joués dans l'ordre "
        f"= {global_conf:.0f}%  ({tot_extra} titre(s) hors plan)"
    )
    return "\n".join(lines) + "\n"


def purge_old_reports(output_dir: Path, today: date) -> None:
    cutoff = today - timedelta(days=RETENTION_DAYS)
    for log_file in sorted(output_dir.glob("diffusion_*.log")):
        try:
            file_day = date.fromisoformat(log_file.stem.removeprefix("diffusion_"))
        except ValueError:
            continue
        if file_day < cutoff:
            log_file.unlink()
            print(f"Rapport supprimé (plus de {RETENTION_DAYS} jours) : {log_file}")


def purge_old_plans(plans_dir: Path, today: date) -> None:
    cutoff = today - timedelta(days=RETENTION_DAYS)
    if not plans_dir.exists():
        return
    for plan_file in sorted(plans_dir.glob("plan_*.json")):
        try:
            file_day = date.fromisoformat(plan_file.stem.removeprefix("plan_"))
        except ValueError:
            continue
        if file_day < cutoff:
            plan_file.unlink()
            print(f"Plan supprimé (plus de {RETENTION_DAYS} jours) : {plan_file}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Jour à analyser (YYYY-MM-DD), défaut : hier en UTC")
    parser.add_argument("--output-dir", default="Radio/logs")
    parser.add_argument("--plans-dir", default=PLANS_DIR,
                        help="dossier des instantanés de plan (réel vs prévu)")
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
    report += build_plan_section(history, day, load_plan(day, args.plans_dir))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"diffusion_{day.isoformat()}.log"
    output_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"Rapport écrit : {output_path}")

    purge_old_reports(output_dir, datetime.now(timezone.utc).date())
    purge_old_plans(Path(args.plans_dir), datetime.now(timezone.utc).date())
    return 0


if __name__ == "__main__":
    main()
    sys.exit(0)
