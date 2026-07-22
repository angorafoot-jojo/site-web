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
from dataclasses import dataclass
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

# Section MONITEUR : fenêtre (secondes) autour d'une anomalie de diffusion dans
# laquelle un incident serveur (crash, échec réseau, silence, saut) est retenu
# comme « cause probable ». Le titre coupé et l'événement Liquidsoap qui l'a
# causé sont journalisés à quelques secondes d'écart (voir le crash de 00h01
# du 22/07/2026 : PANIC puis bascule error_jingle dans la même minute).
CORRELATION_WINDOW_SECONDS = 120

# Incidents serveur groupés en amas quand ils se suivent de près (un crash
# entraîne une rafale de lignes : PANIC + bascules + reprise).
INCIDENT_CLUSTER_SECONDS = 90

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
    # La fenêtre déborde de 15 min sur le lendemain : le dernier titre du jour
    # a besoin d'une entrée "suivante" pour calculer sa durée réelle (voir
    # build_report) — sans ça il reste pour toujours "durée inconnue".
    end = (datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
           + timedelta(minutes=15))
    params = urllib.parse.urlencode({
        "start": f"{day.isoformat()}T00:00:00Z",
        "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rowsPerPage": 1000,
    })
    url = f"{BASE_URL}/api/station/{STATION_ID}/history?{params}"
    request = urllib.request.Request(url, headers={"X-API-Key": api_key})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def iter_day_playback(history: list[dict], day: date):
    """Pour chaque titre joué le jour `day`, sa durée réelle (écart avec le
    lancement du titre suivant) comparée à la durée du fichier.

    Source unique partagée par `build_report` (affichage titre par titre) et
    par `playback_incidents` (corrélation du moniteur) — aucune détection de
    coupure/trou n'est dupliquée. `fetch_history` déborde de 15 min sur le
    lendemain : la 1re entrée du lendemain sert de référence de fin au dernier
    titre du jour mais n'est jamais restituée (filtre sur `day`)."""
    entries = sorted(history, key=lambda e: e["played_at"])
    for i, entry in enumerate(entries):
        started = datetime.fromtimestamp(entry["played_at"], tz=timezone.utc)
        if started.date() != day:
            continue
        base = {
            "dt": started,
            "expected": entry.get("duration") or 0,
            "title": (entry.get("song") or {}).get("title") or "?",
            "playlist": entry.get("playlist") or "?",
        }
        if i + 1 < len(entries):
            actual = entries[i + 1]["played_at"] - entry["played_at"]
            yield {**base, "actual": actual, "gap": actual - base["expected"],
                   "is_last": False}
        else:
            yield {**base, "actual": None, "gap": None, "is_last": True}


def build_report(history: list[dict], day: date) -> tuple[str, int]:
    plays = list(iter_day_playback(history, day))
    lines = [
        f"Rapport de diffusion — {day.isoformat()} (heures UTC)",
        f"{len(plays)} titres joués | tolérance ±{TOLERANCE_SECONDS}s",
        "=" * 100,
        f"{'HEURE':8s} {'PLAYLIST':28s} {'FICHIER':10s} {'RÉEL':>10s} {'ÉCART':>8s}  STATUT  TITRE",
        "-" * 100,
    ]
    problems = 0
    severities = []  # écarts absolus (s) des anomalies, pour les paliers de gravité

    for p in plays:
        expected = p["expected"]
        if p["is_last"]:
            actual_str, shown_gap, status = "?", "", "⏳ dernier titre (durée réelle inconnue)"
        else:
            gap = p["gap"]
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
            actual_str = fmt_duration(p["actual"])

        lines.append(
            f"{p['dt']:%H:%M:%S} {p['playlist'][:28]:28s} {fmt_duration(expected):>10s} "
            f"{actual_str:>10s} {shown_gap:>8s}  {status}  {p['title']}"
        )

    bilan = (
        f"Bilan : {len(plays)} titres, {problems} anomalie(s) "
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


def _message_matcher(plan: dict | None):
    """Prédicat « cette diffusion est le message du jour » : (norm, duration) -> bool.

    Le titre du plan est l'étiquette d'épisode de la config, alors que
    l'historique journalise le tag du fichier audio — ils peuvent ne rien
    partager (« PQE C1 » vs « 1-pqe c1 », « Tian Le pardon 1 » vs
    « La pardon », vu sur les rapports des 09-11/07/2026 où le message
    était compté 0 diffusion à tort). La durée, elle, vient du même média
    AzuraCast des deux côtés : elle sert de second critère, en écartant
    les titres qui appartiennent déjà au plan (un cantique planifié de
    même durée ne doit pas passer pour le message). Limite assumée : un
    titre HORS plan de même durée à ±2 s près serait compté à tort —
    improbable, et l'heure listée dans le rapport le rendrait visible."""
    message = (plan or {}).get("message") or {}
    msg_norm = norm_title(message.get("title", ""))
    msg_seconds = message.get("duration_seconds") or 0
    other_norms = {
        norm_title(it.get("title", ""))
        for b in (plan or {}).get("blocks", [])
        for it in b.get("items", [])
        if it.get("type") != "message"
    }

    def matches(norm: str, duration: float) -> bool:
        if not msg_norm:
            return False
        if norm == msg_norm:
            return True
        return bool(msg_seconds and duration
                    and abs(duration - msg_seconds) <= 2
                    and norm not in other_norms)

    return matches


def _message_plays(history: list[dict], day: date, plan: dict | None) -> list[dict]:
    """Diffusions du message du jour, horodatées, chacune marquée « double
    rapproché » si elle suit de moins de MESSAGE_DOUBLE_WINDOW_SECONDS la
    précédente (auditeur qui entend deux fois le même message).

    Source unique partagée par les contrôles approfondis (section 1) et par le
    moniteur, pour ne pas dupliquer le repérage du message (matching par titre
    OU durée, voir `_message_matcher`)."""
    message = (plan or {}).get("message") or {}
    if not norm_title(message.get("title", "")):
        return []
    matches_message = _message_matcher(plan)
    plays = []
    for e in _day_entries(history, day):
        duration = e.get("duration") or 0
        norm = norm_title((e.get("song") or {}).get("title") or "?")
        if matches_message(norm, duration):
            plays.append({
                "dt": datetime.fromtimestamp(e["played_at"], tz=timezone.utc),
                "duration": duration,
                "playlist": e.get("playlist") or "?",
                "double": False,
            })
    for prev, cur in zip(plays, plays[1:]):
        prev_end = prev["dt"] + timedelta(
            seconds=prev["duration"] or message.get("duration_seconds") or 0)
        cur["double"] = (cur["dt"] - prev_end).total_seconds() < MESSAGE_DOUBLE_WINDOW_SECONDS
    return plays


def _day_entries(history: list[dict], day: date) -> list[dict]:
    """Entrées de l'historique appartenant au jour, triées. fetch_history()
    déborde de 15 min sur le lendemain (durée réelle du dernier titre) :
    sans ce filtre, les titres de 00h00-00h15 du lendemain retombent dans
    la fenêtre de BLOC_A (le fenêtrage se fait sur l'heure du jour) — vu
    le 11/07/2026 : 3 jingles du 12/07 comptés dans BLOC_A, 9/9 au lieu
    de 6/9, et des bouche-trous du lendemain listés dans le rapport."""
    return [e for e in sorted(history, key=lambda e: e["played_at"])
            if datetime.fromtimestamp(e["played_at"], tz=timezone.utc).date() == day]


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

    entries = _day_entries(history, day)
    # Titre réel + heure de début + forme normalisée pour chaque diffusion.
    # Le message du jour est ramené au titre du plan quand le tag du fichier
    # diffère (voir _message_matcher) : sinon il compte à tort comme
    # « sauté » + « en trop » dans chacun des 4 blocs.
    matches_message = _message_matcher(plan)
    msg_norm = norm_title((plan.get("message") or {}).get("title", ""))
    played = []
    for e in entries:
        dt = datetime.fromtimestamp(e["played_at"], tz=timezone.utc)
        title = (e.get("song") or {}).get("title") or "?"
        n = norm_title(title)
        if matches_message(n, e.get("duration") or 0):
            n = msg_norm
        played.append((dt, title, n))

    lines = list(head)
    tot_plan = tot_match = tot_extra = tot_tail = 0
    for block in plan.get("blocks", []):
        window = block.get("window", "")
        items = block.get("items", [])
        if not window or not items:
            continue
        m0, m1 = _window_bounds(window)
        planned_titles = [it.get("title", "?") for it in items]
        in_win = [(t, n) for (dt, t, n) in played if m0 <= dt.hour * 60 + dt.minute < m1]
        actual_titles = [t for (t, n) in in_win]

        plan_norm = [norm_title(t) for t in planned_titles]
        act_norm = [n for (t, n) in in_win]
        sm = difflib.SequenceMatcher(None, plan_norm, act_norm, autojunk=False)
        opcodes = sm.get_opcodes()

        # Marge de fin de bloc : chaque plan embarque volontairement un surplus
        # au-delà de la fenêtre (anti-rebouclage). Le suffixe du plan qui suit
        # le dernier titre réellement joué n'a donc jamais été atteint — c'est
        # attendu, on le sort de la conformité et on le liste à part.
        # Le suffixe se présente en « delete » quand la fenêtre se termine sur
        # un titre du plan, ou en « replace » quand un artefact de frontière
        # (jingle rebouclé, bouche-trou) joue après le dernier titre atteint —
        # sans ce second cas, la marge entière passait pour « sautée » (vu les
        # 09 et 11/07/2026 : 8 faux sautés par bloc). La part « réel » du
        # replace reste comptée en trop.
        tail: list[str] = []
        tail_seconds = 0
        if opcodes and opcodes[-1][0] in ("delete", "replace") and opcodes[-1][2] == len(plan_norm):
            op, i1, i2, j1, j2 = opcodes[-1]
            tail = planned_titles[i1:i2]
            tail_seconds = sum(it.get("duration_seconds") or 0 for it in items[i1:i2])
            opcodes = opcodes[:-1]
            if op == "replace":
                opcodes.append(("insert", i2, i2, j1, j2))

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

    entries = _day_entries(history, day)
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
        plays = _message_plays(history, day, plan)
        doubles = sum(1 for p in plays if p["double"])
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


# ─────────────────────────────────────────────────────────────────────────────
# MONITEUR : corrélation des 3 rapports + plan en une seule vue.
#
# Le rapport de diffusion est le seul fichier qu'un humain ouvre quand la radio
# a un souci (README §8). Plutôt que de le forcer à croiser à la main les 3
# journaux, cette section rassemble en tête :
#   - les anomalies HORODATÉES de diffusion (coupures/trous/doubles),
#   - les incidents SERVEUR (liquidsoap_events : crash, réseau, silence, saut),
#   - les actions de RESET/GARDE (midnight/boundary_watch),
# puis rattache à chaque anomalie la cause serveur probable la plus proche.
# ─────────────────────────────────────────────────────────────────────────────

# Ligne datée du log Liquidsoap : « 2026/07/22 00:01:22 [source:niveau] texte ».
_SERVER_LINE = re.compile(r"^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) (.*)$")

# Étiquettes lisibles des catégories d'incident serveur retenues.
INCIDENT_LABELS = {
    "crash": "💥 crash Liquidsoap (redémarrage automatique)",
    "network": "🌐 échec réseau AzuraCast/Liquidsoap",
    "deadair": "🔇 bascule sur jingle d'erreur (silence potentiel)",
    "skip": "⏭️ fichier sauté par l'AutoDJ",
}


@dataclass
class ServerEvent:
    """Un événement d'intérêt du liquidsoap.log, daté et catégorisé."""
    dt: datetime
    category: str  # clé de INCIDENT_LABELS
    text: str


def classify_server_line(text: str) -> str:
    """Catégorise le texte d'une ligne Liquidsoap (après l'horodatage).

    Renvoie une clé de INCIDENT_LABELS pour les lignes d'incident, ou "" pour
    le bruit bénin (fins de décodage normales, avertissements de dépréciation,
    lignes « Prepared » qui ne servent que de contexte)."""
    low = text.lower()
    if "panic" in low or "crashed with exception" in low or "has crashed" in low:
        return "crash"
    if ("could not perform http request" in low or "fetch failed" in low
            or "curlexception" in low or "api djoff - error" in low):
        return "network"
    if "error_jingle" in low or "underrun" in low or "blank" in low:
        return "deadair"
    # « skip » réel de l'AutoDJ, mais pas les fins de décodage (End_of_file) ni
    # les avertissements de dépréciation qui contiennent d'autres mots-clés.
    if "skip" in low and "deprecated" not in low:
        return "skip"
    return ""


def parse_server_events(text: str, day: date) -> list[ServerEvent]:
    """Événements d'incident du jour extraits du texte de liquidsoap_events."""
    events = []
    for line in text.splitlines():
        m = _SERVER_LINE.match(line)
        if not m:
            continue
        try:
            dt = datetime.strptime(m.group(1), "%Y/%m/%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if dt.date() != day:
            continue
        category = classify_server_line(m.group(2))
        if category:
            events.append(ServerEvent(dt, category, m.group(2)))
    return events


def group_incidents(events: list[ServerEvent],
                    cluster_seconds: int = INCIDENT_CLUSTER_SECONDS) -> list[dict]:
    """Regroupe les incidents de même catégorie qui se suivent de près.

    Un crash produit une rafale de lignes (PANIC + bascules) : sans
    regroupement le moniteur listerait dix lignes pour un seul incident."""
    groups: list[dict] = []
    for ev in sorted(events, key=lambda e: e.dt):
        last = groups[-1] if groups else None
        if (last and last["category"] == ev.category
                and (ev.dt - last["last"]).total_seconds() <= cluster_seconds):
            last["count"] += 1
            last["last"] = ev.dt
        else:
            groups.append({"category": ev.category, "start": ev.dt,
                           "last": ev.dt, "count": 1})
    return groups


def playback_incidents(history: list[dict], day: date) -> list[dict]:
    """Anomalies horodatées du RÉEL : titres coupés et trous d'antenne.
    Réutilise `iter_day_playback` (même détection que le tableau titre par
    titre)."""
    out = []
    for p in iter_day_playback(history, day):
        if p["is_last"] or not p["expected"]:
            continue
        gap = p["gap"]
        if gap < -TOLERANCE_SECONDS:
            out.append({"kind": "COUPÉ", "dt": p["dt"], "severity": -gap, "title": p["title"]})
        elif gap > TOLERANCE_SECONDS:
            out.append({"kind": "TROU", "dt": p["dt"], "severity": gap, "title": p["title"]})
    return out


def parse_watch_records(text: str) -> list[dict]:
    """Instantanés JSON Lines d'un log de surveillance (midnight/boundary)."""
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    return records


def summarize_watch(records: list[dict]) -> dict | None:
    """Synthèse d'un log de surveillance : restart confirmé ? doublon vu en file ?

    Un doublon en file = un titre non joué qui apparaît deux fois dans un même
    instantané, ou identique au titre à l'antenne (motif du message « joué 2×
    d'affilée » que le dédoublonnage retire)."""
    if not records:
        return None
    dup_seen = False
    for r in records:
        now = (r.get("now_playing_title") or "").strip().lower()
        titles = [(i.get("title") or "").strip().lower()
                  for i in r.get("queue_preview", []) if not i.get("is_played")]
        titles = [t for t in titles if t]
        if len(titles) != len(set(titles)) or (now and now in titles):
            dup_seen = True
    return {
        "checks": len(records),
        "restart": any(r.get("started_after_restart") for r in records),
        "dup_seen": dup_seen,
        "first": (records[0].get("logged_at") or "")[11:19],
    }


def nearest_incident(dt: datetime, groups: list[dict],
                     window: int = CORRELATION_WINDOW_SECONDS) -> dict | None:
    """Amas d'incident serveur le plus proche de `dt` dans la fenêtre, ou None."""
    best = None
    for g in groups:
        if g["start"] <= dt <= g["last"]:
            distance = 0.0
        else:
            distance = min(abs((dt - g["start"]).total_seconds()),
                           abs((dt - g["last"]).total_seconds()))
        if distance <= window and (best is None or distance < best[0]):
            best = (distance, g)
    return best[1] if best else None


def load_sibling_logs(day: date, output_dir: str | Path) -> dict[str, str]:
    """Texte brut des 2 autres rapports du jour (serveur + surveillances).
    Tolère l'absence : une chaîne vide signale « archive indisponible »."""
    output_dir = Path(output_dir)

    def read(name: str) -> str:
        try:
            return (output_dir / name).read_text(encoding="utf-8")
        except OSError:
            return ""

    return {
        "server": read(f"liquidsoap_events_{day.isoformat()}.log"),
        "midnight": read(f"midnight_watch_{day.isoformat()}.log"),
        "boundary": read(f"boundary_watch_{day.isoformat()}.log"),
    }


def build_monitor_section(history: list[dict], day: date, plan: dict | None,
                          logs: dict[str, str]) -> str:
    """Section « MONITEUR » en tête du rapport : synthèse et corrélation des 3
    rapports + plan, pour ne plus avoir à chercher la cause dans 3 fichiers."""
    groups = group_incidents(parse_server_events(logs.get("server", ""), day))
    midnight = summarize_watch(parse_watch_records(logs.get("midnight", "")))
    boundary = summarize_watch(parse_watch_records(logs.get("boundary", "")))
    anomalies = playback_incidents(history, day)
    doubles = [p["dt"] for p in _message_plays(history, day, plan) if p["double"]]

    have_server = bool(logs.get("server", "").strip())
    n_server = sum(g["count"] for g in groups)
    n_diffusion = len(anomalies) + len(doubles)

    verdict = "✅ RAS" if not n_diffusion and not n_server else "❌ incident(s) détecté(s)"
    lines = [
        "=" * 100,
        f"MONITEUR RADIO — {day.isoformat()} (synthèse des 3 rapports + plan, heures UTC)",
        "=" * 100,
        f"État : {verdict}  ·  diffusion : {len(anomalies)} coupure(s)/trou(s), "
        f"{len(doubles)} double(s) message  ·  serveur : {n_server} incident(s)",
    ]

    # --- Incidents serveur (liquidsoap_events) ---
    if not have_server:
        lines.append("SERVEUR : archive liquidsoap_events absente pour ce jour "
                     "— causes serveur indisponibles.")
    elif not groups:
        lines.append("SERVEUR : aucun incident (ni crash, ni échec réseau, ni silence) ✅")
    else:
        lines.append("SERVEUR (liquidsoap_events) :")
        for g in groups[:12]:
            count = f"  (×{g['count']})" if g["count"] > 1 else ""
            lines.append(f"   {g['start']:%H:%M:%S}  {INCIDENT_LABELS[g['category']]}{count}")
        if len(groups) > 12:
            lines.append(f"   …(+{len(groups) - 12} autre(s))")

    # --- Reset minuit / garde de frontière (midnight/boundary_watch) ---
    if midnight is None and boundary is None:
        lines.append("RESET/GARDE : aucun instantané de surveillance pour ce jour.")
    else:
        if midnight:
            state = "restart confirmé" if midnight["restart"] else "restart NON confirmé ⚠️"
            queue = "⚠️ doublon vu dans la file" if midnight["dup_seen"] else "file saine ✅"
            lines.append(f"RESET MINUIT : {state} vers {midnight['first']} · "
                         f"{midnight['checks']} contrôle(s) · {queue}")
        if boundary:
            queue = "⚠️ doublon(s) vu(s) dans la file" if boundary["dup_seen"] else "aucun doublon"
            lines.append(f"GARDE DE FRONTIÈRE : {boundary['checks']} snapshot(s) · {queue}")

    # --- Corrélation anomalie ↔ cause serveur ---
    rows = [(a["kind"], a["dt"], a["severity"], a["title"]) for a in anomalies]
    rows += [("DOUBLE MESSAGE", dt, None, "message du jour rejoué") for dt in doubles]
    rows.sort(key=lambda r: r[1])
    if rows:
        lines.append("INCIDENTS CORRÉLÉS (anomalie de diffusion ↔ cause serveur probable) :")
        for kind, dt, severity, title in rows[:15]:
            sev = f" {int(round(severity))}s" if severity else ""
            lines.append(f"   {dt:%H:%M:%S}  {kind}{sev} « {title} »")
            group = nearest_incident(dt, groups) if have_server else None
            if group:
                lines.append(f"          ↳ cause probable {group['start']:%H:%M:%S} : "
                             f"{INCIDENT_LABELS[group['category']]}")
            elif have_server:
                lines.append("          ↳ aucune cause serveur à proximité "
                             "(voir CONTRÔLES APPROFONDIS et RÉEL vs PRÉVU ci-dessous)")
            else:
                lines.append("          ↳ archive serveur absente — cause non déterminable")
        if len(rows) > 15:
            lines.append(f"   …(+{len(rows) - 15} autre(s))")
    else:
        lines.append("INCIDENTS CORRÉLÉS : aucune anomalie de diffusion à corréler ✅")

    lines.append("(Détail titre par titre, contrôles approfondis et RÉEL vs PRÉVU ci-dessous.)")
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
    logs = load_sibling_logs(day, args.output_dir)
    # Le moniteur (synthèse + corrélation des 3 rapports) ouvre le fichier ;
    # viennent ensuite le détail titre par titre, les contrôles et le plan.
    body, problems = build_report(history, day)
    report = build_monitor_section(history, day, plan, logs)
    report += body
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
