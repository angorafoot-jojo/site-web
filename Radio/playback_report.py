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

# Paliers de gravité des anomalies (secondes d'écart) : au même titre,
# un jingle décalé de 12 s et un trou d'antenne d'une heure ne pèsent
# pas pareil dans le bilan.
SEVERITY_SERIOUS_SECONDS = 60
SEVERITY_CRITICAL_SECONDS = 600

# Deux diffusions du message du jour espacées de moins de ça sont un
# « double rapproché » : l'auditeur entend le même message deux fois
# de suite (reboucle du bloc sortant + démarrage du bloc entrant).
MESSAGE_DOUBLE_WINDOW_SECONDS = 900

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
    severities = []  # écarts absolus (s) des anomalies, pour les paliers de gravité

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
                severities.append(-gap)
            elif gap > TOLERANCE_SECONDS:
                status, shown_gap = "⚠️ TROU APRÈS", f"{gap:+d}s"
                problems += 1
                severities.append(gap)
            else:
                status, shown_gap = "✅", f"{gap:+d}s"
            actual_str = fmt_duration(actual)
        else:
            actual_str, shown_gap, status = "?", "", "⏳ dernier titre (durée réelle inconnue)"

        lines.append(
            f"{started:%H:%M:%S} {playlist[:28]:28s} {fmt_duration(expected):>10s} "
            f"{actual_str:>10s} {shown_gap:>8s}  {status}  {title}"
        )

    bilan = (
        f"Bilan : {len(entries)} titres, {problems} anomalie(s) "
        f"(titre coupé de plus de {TOLERANCE_SECONDS}s ou trou d'antenne)."
    )
    if severities:
        minor = sum(1 for s in severities if s < SEVERITY_SERIOUS_SECONDS)
        serious = sum(1 for s in severities
                      if SEVERITY_SERIOUS_SECONDS <= s < SEVERITY_CRITICAL_SECONDS)
        critical = sum(1 for s in severities if s >= SEVERITY_CRITICAL_SECONDS)
        bilan += (
            f" Gravité : {minor} mineure(s) <1min · {serious} sérieuse(s) 1-10min"
            f" · {critical} critique(s) >10min."
        )
    lines += ["-" * 100, bilan]
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
    tot_plan = tot_match = tot_extra = tot_tail = 0
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
        opcodes = sm.get_opcodes()

        # Marge de fin de bloc : chaque plan embarque volontairement un surplus
        # au-delà de la fenêtre (anti-rebouclage). Le suffixe du plan qui suit
        # le dernier titre réellement joué n'a donc jamais été atteint — c'est
        # attendu, on le sort de la conformité et on le liste à part.
        tail: list[str] = []
        tail_seconds = 0
        if opcodes and opcodes[-1][0] == "delete" and opcodes[-1][2] == len(plan_norm):
            _, i1, i2, _, _ = opcodes[-1]
            tail = planned_titles[i1:i2]
            tail_seconds = sum(it.get("duration_seconds") or 0 for it in items[i1:i2])
            opcodes = opcodes[:-1]

        matched = 0
        skipped, extra = [], []
        for op, i1, i2, j1, j2 in opcodes:
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
        n_reach = n_plan - len(tail)
        conf = 100 * matched / n_reach if n_reach else 0
        tot_plan += n_reach
        tot_match += matched
        tot_extra += len(extra)
        tot_tail += len(tail)

        name = (block.get("block_name") or "").replace("_SERIE_DU_JOUR", "")
        lines.append("-" * 100)
        lines.append(
            f"{name:7s} ({window})  prévus {n_plan:>3} · atteignables {n_reach:>3} · "
            f"joués {len(actual_titles):>3} · conformité {conf:>3.0f}% · "
            f"sautés {len(skipped):>2} · en trop {len(extra):>2}"
        )
        if skipped:
            shown = " · ".join(skipped[:6])
            more = f"  …(+{len(skipped) - 6})" if len(skipped) > 6 else ""
            lines.append(f"   ⏭️  PRÉVU NON JOUÉ : {shown}{more}")
        if extra:
            shown = " · ".join(extra[:6])
            more = f"  …(+{len(extra) - 6})" if len(extra) > 6 else ""
            lines.append(f"   ➕  JOUÉ NON PRÉVU : {shown}{more}")
        if tail:
            shown = " · ".join(tail[:6])
            more = f"  …(+{len(tail) - 6})" if len(tail) > 6 else ""
            lines.append(
                f"   ⏸️  FIN DE BLOC NON ATTEINTE ({len(tail)} titres · ~{fmt_duration(tail_seconds)}) "
                f"— marge anti-rebouclage au-delà de la fenêtre, normal : {shown}{more}"
            )
            # Garde-fou : si la part non atteinte dépasse nettement le surplus
            # planifié, ce n'est plus la marge — un incident a amputé le bloc.
            window_seconds = (m1 - m0) * 60
            plan_seconds = sum(it.get("duration_seconds") or 0 for it in items)
            surplus = max(0, plan_seconds - window_seconds)
            if tail_seconds > surplus + 600:
                lines.append(
                    f"   ⚠️  part non atteinte (~{fmt_duration(tail_seconds)}) excède la marge prévue "
                    f"(~{fmt_duration(surplus)}) — reboucle ou coupure probable dans le bloc"
                )

    lines.append("-" * 100)
    global_conf = 100 * tot_match / tot_plan if tot_plan else 0
    lines.append(
        f"CONFORMITÉ GLOBALE : {tot_match}/{tot_plan} titres atteignables joués dans l'ordre "
        f"= {global_conf:.0f}%  ({tot_extra} titre(s) hors plan · "
        f"{tot_tail} non atteint(s) en fin de bloc, marge normale)"
    )
    return "\n".join(lines) + "\n"


def build_health_section(history: list[dict], day: date, plan: dict | None) -> str:
    """Section « CONTRÔLES APPROFONDIS » : les défauts que le tableau titre
    par titre ne montre pas — message du jour rejoué, jingles sautés, blocs
    débordant de leur fenêtre, bouche-trous, couverture début/fin de journée.
    Chaque contrôle correspond à un défaut réellement observé en prod
    (audits de juin-juillet 2026)."""
    head = ["", "=" * 100, "CONTRÔLES APPROFONDIS", "=" * 100]
    if not plan:
        head.append("Plan non disponible : contrôles approfondis impossibles pour ce jour.")
        return "\n".join(head) + "\n"

    entries = sorted(history, key=lambda e: e["played_at"])
    played = [
        {
            "dt": datetime.fromtimestamp(e["played_at"], tz=timezone.utc),
            "title": (e.get("song") or {}).get("title") or "?",
            "playlist": e.get("playlist") or "?",
            "duration": e.get("duration") or 0,
        }
        for e in entries
    ]
    for p in played:
        p["norm"] = norm_title(p["title"])

    blocks = [b for b in plan.get("blocks", []) if b.get("window") and b.get("items")]
    lines = list(head)

    # --- 1. Message du jour : combien de diffusions, et des doubles rapprochés ?
    message = plan.get("message") or {}
    msg_norm = norm_title(message.get("title", ""))
    planned_plays = sum(1 for b in blocks for it in b["items"] if it.get("type") == "message")
    if msg_norm and planned_plays:
        plays = [p for p in played if p["norm"] == msg_norm]
        doubles = 0
        for prev, cur in zip(plays, plays[1:]):
            prev_end = prev["dt"] + timedelta(
                seconds=prev["duration"] or message.get("duration_seconds") or 0)
            cur["double"] = (cur["dt"] - prev_end).total_seconds() < MESSAGE_DOUBLE_WINDOW_SECONDS
            doubles += cur["double"]
        verdict = "✅" if len(plays) == planned_plays and not doubles else "❌"
        lines.append(
            f"MESSAGE DU JOUR « {message.get('title', '?')} » : "
            f"{len(plays)} diffusion(s) pour {planned_plays} prévue(s) {verdict}"
        )
        for p in plays:
            mark = "  ⚠️ DOUBLE RAPPROCHÉ (rejoué juste après la diffusion précédente)" \
                if p.get("double") else ""
            lines.append(f"   {p['dt']:%H:%M:%S}  (étiquette {p['playlist']}){mark}")
        if len(plays) > planned_plays:
            lines.append(
                "   → diffusions en trop = reboucle d'un bloc avant la fin de sa fenêtre"
                " (l'étiquette playlist des fichiers partagés n'est pas fiable,"
                " se fier aux heures)."
            )

    # --- 2. Jingles : joués vs prévus, par bloc.
    jingle_lines, tot_played, tot_planned = [], 0, 0
    for block in blocks:
        m0, m1 = _window_bounds(block["window"])
        planned = sum(1 for it in block["items"] if it.get("type") == "jingle")
        in_window = [p for p in played
                     if m0 <= p["dt"].hour * 60 + p["dt"].minute < m1]
        played_jingles = sum(1 for p in in_window if p["norm"].startswith("jingle"))
        tot_planned += planned
        tot_played += played_jingles
        name = (block.get("block_name") or "").replace("_SERIE_DU_JOUR", "")
        jingle_lines.append(f"{name} {played_jingles}/{planned}")
    if tot_planned:
        pct = 100 * tot_played / tot_planned
        verdict = "✅" if tot_played >= tot_planned else "⚠️"
        lines.append(
            f"JINGLES : {tot_played} joués / {tot_planned} prévus ({pct:.0f}%) {verdict}"
            f"   ·   {' · '.join(jingle_lines)}"
        )

    # --- 3. Titres joués hors de la fenêtre de leur bloc (débordements).
    #     Seuls les titres présents dans UN seul bloc du plan sont testables :
    #     jingles et message sont partagés par les 4 blocs (étiquette non fiable).
    owner: dict[str, tuple[str, str, int, int]] = {}
    counts: dict[str, int] = {}
    for block in blocks:
        m0, m1 = _window_bounds(block["window"])
        name = (block.get("block_name") or "").replace("_SERIE_DU_JOUR", "")
        for it in block["items"]:
            n = norm_title(it.get("title", ""))
            counts[n] = counts.get(n, 0) + 1
            owner[n] = (name, block["window"], m0, m1)
    exclusive = {n: o for n, o in owner.items() if counts[n] == 1}
    all_windows = [_window_bounds(b["window"]) for b in blocks]
    overflow = []
    for p in played:
        info = exclusive.get(p["norm"])
        if not info:
            continue
        minute = p["dt"].hour * 60 + p["dt"].minute
        # Hors de toute fenêtre du plan (ex. 23h30-minuit = BLOC_E_LOUANGE_NUIT,
        # playlist statique volontairement hors plan) : rien à contrôler.
        if not any(w0 <= minute < w1 for (w0, w1) in all_windows):
            continue
        name, window, m0, m1 = info
        if not (m0 <= minute < m1):
            overflow.append(f"   {p['dt']:%H:%M:%S}  {p['title']} — prévu dans {name} ({window})")
    if overflow:
        lines.append(f"HORS FENÊTRE : {len(overflow)} titre(s) d'un bloc joués hors de sa plage ⚠️")
        lines += overflow[:8]
        if len(overflow) > 8:
            lines.append(f"   …(+{len(overflow) - 8})")
    else:
        lines.append("HORS FENÊTRE : aucun débordement de bloc détecté ✅")

    # --- 4. Bouche-trous : titres inconnus du plan ET sans playlist identifiée
    #     (« AzuraCast is Live! », titre « ? »… = l'AutoDJ a comblé un vide).
    plan_norms = set(owner)
    fillers = [p for p in played
               if p["norm"] not in plan_norms
               and (p["playlist"] == "?" or p["title"] == "?"
                    or p["norm"].startswith("azuracastislive"))]
    if fillers:
        lines.append(f"BOUCHE-TROUS : {len(fillers)} titre(s) hors plan sans playlist ⚠️")
        for p in fillers[:8]:
            lines.append(
                f"   {p['dt']:%H:%M:%S}  {p['title']}  ({fmt_duration(p['duration'])})")
    else:
        lines.append("BOUCHE-TROUS : aucun ✅")

    # --- 5. Couverture de la journée : l'antenne démarre-t-elle à minuit,
    #     et le dernier titre couvre-t-il la fin de journée ?
    #     (les trous à cheval sur minuit échappent au tableau titre par titre)
    if played:
        day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        start_gap = (played[0]["dt"] - day_start).total_seconds()
        last = played[-1]
        end_gap = (day_end - (last["dt"] + timedelta(seconds=last["duration"]))).total_seconds()
        start_txt = (f"premier titre à {played[0]['dt']:%H:%M:%S}"
                     + (f" ⚠️ trou de {fmt_duration(start_gap)} en début de journée"
                        if start_gap > 150 else " ✅"))
        end_txt = (f"dernier titre finit vers "
                   f"{(last['dt'] + timedelta(seconds=last['duration'])):%H:%M:%S} (estimé)"
                   + (f" ⚠️ fin de journée possiblement découverte ({fmt_duration(end_gap)})"
                      if end_gap > 150 else " ✅"))
        lines.append(f"COUVERTURE : {start_txt} · {end_txt}")

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

    plan = load_plan(day, args.plans_dir)
    report, problems = build_report(history, day)
    report += build_health_section(history, day, plan)
    report += build_plan_section(history, day, plan)

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
