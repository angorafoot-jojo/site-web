#!/usr/bin/env python3
"""
Réinitialise l'AutoDJ d'AzuraCast à minuit.

Déclenché chaque nuit à 00h00 UTC pour que toutes les playlists séquentielles
(BLOC_A/B/C/D) repartent de la position 1 (jingle → message).

Quatre étapes, dans cet ordre :
  1. reshuffle de chaque bloc → réinitialise sa file séquentielle interne
     (champ `queue_reset_at`) à la position 1. ÉTAPE CLÉ, longtemps absente :
     ni `queue/clear` ni `backend/restart` ne touchent ce curseur, d'où un
     BLOC_A qui reprenait systématiquement au milieu (jamais sur le message).
  2. queue/clear → vide la file « à venir » de la station (restes de BLOC_D).
  3. backend/restart → Liquidsoap reconstruit sa file sur les blocs réinitialisés.
  4. surveillance de la file post-restart → journalise un instantané (diagnostic)
     et supprime les doublons dos à dos. Audit 06-25→07-01 : le message du jour
     jouait EXACTEMENT 2× d'affilée à 00h01 (écart réel/fichier = 2,00×, 4 nuits
     sur 5) — la 2e lecture attend dans la file pendant la 1re, on la retire.

Usage:
    python Radio/restart_autodj.py --base-url URL [--station-id ID] [--dry-run]

Variables d'environnement:
    AZURACAST_API_KEY  Clé API AzuraCast (obligatoire)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def api_post(url: str, api_key: str, method: str = "POST") -> dict:
    req = urllib.request.Request(
        url,
        method=method,
        data=b"",
        headers={
            "Authorization": f"Bearer {api_key}",
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def api_get(url: str, api_key: str):
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}", "X-API-Key": api_key},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def reshuffle_blocks(base: str, sid: int, api_key: str, dry_run: bool) -> None:
    """Réinitialise la file séquentielle de chaque bloc à la position 1.

    Appelle l'action AzuraCast `/playlist/{id}/reshuffle` (→ `resetQueue()`) :
    pour une playlist séquentielle, la file repart du début de l'ordre défini
    (position 1 = jingle → message). C'est l'étape que `queue/clear` (file de
    la station) et `backend/restart` (Liquidsoap) NE font PAS.

    Échec d'un bloc = non bloquant : on continue, les étapes 2-3 ramènent quand
    même l'antenne à l'heure (au pire, comportement identique à avant).
    """
    try:
        playlists = api_get(f"{base}/api/station/{sid}/playlists", api_key)
    except Exception as e:  # noqa: BLE001 — non bloquant
        print(f"  AVERTISSEMENT : playlists illisibles ({e}) — reshuffle ignoré.", file=sys.stderr)
        return

    blocks = sorted(
        (p for p in playlists if str(p.get("name", "")).startswith("BLOC_")),
        key=lambda p: p.get("name", ""),
    )
    if not blocks:
        print("  AVERTISSEMENT : aucun bloc 'BLOC_*' trouvé — reshuffle ignoré.", file=sys.stderr)
        return

    for p in blocks:
        url = f"{base}/api/station/{sid}/playlist/{p['id']}/reshuffle"
        if dry_run:
            print(f"  [DRY-RUN] PUT {url}  ({p['name']})")
            continue
        try:
            # L'action AzuraCast ReshuffleAction est exposée en PUT (un POST
            # renvoie HTTP 405 Method Not Allowed — vérifié sur le reset du 27/06).
            res = api_post(url, api_key, method="PUT")
            msg = res.get("message", "") if isinstance(res, dict) else res
            print(f"  reshuffle {p['name']} (id {p['id']}) : OK {msg}")
        except urllib.error.HTTPError as e:  # noqa: BLE001 — non bloquant
            print(f"  AVERTISSEMENT reshuffle {p['name']} : HTTP {e.code} {e.read().decode()[:120]}",
                  file=sys.stderr)
        except Exception as e:  # noqa: BLE001 — non bloquant
            print(f"  AVERTISSEMENT reshuffle {p['name']} : {e}", file=sys.stderr)


def queue_dup_delete_urls(now_song_id: str | None, queue_items: list) -> list:
    """URLs DELETE des éléments de la file qui sont des doublons dos à dos.

    Parcourt la séquence [titre à l'antenne] + file « à venir » : tout élément
    dont la chanson est identique à celle de l'élément PRÉCÉDENT est une
    rediffusion immédiate (le bug « message joué 2× d'affilée »). Les copies
    non consécutives (ex. le message rejoué 6 h plus tard par le bloc suivant)
    sont légitimes et conservées.

    L'API queue n'expose pas d'id de ligne : la cible DELETE est `links.self`.
    `now_song_id` = None si le titre à l'antenne n'est pas fiable (démarré
    avant le restart) : on ne compare alors que la file avec elle-même.
    """
    urls = []
    prev = now_song_id
    for item in queue_items:
        if item.get("is_played"):
            continue
        song_id = (item.get("song") or {}).get("id")
        self_url = (item.get("links") or {}).get("self")
        if song_id and prev and song_id == prev and self_url:
            urls.append(self_url)
        prev = song_id
    return urls


def append_watch_log(log_path: Path, check: int, now_song: dict,
                      started_after_restart: bool, items: list) -> None:
    """Persiste un instantané de surveillance minuit (JSON Lines, append-only).

    Les 3 sondages nowplaying/queue de watch_and_dedup_queue() tombent chaque
    nuit à ~00h00:40/01:20/02:00 UTC — exactement la fenêtre du restart et de
    la playlist 000_TRANSITION, jusqu'ici seulement imprimée puis perdue dans
    le log GitHub Actions éphémère. Écriture non bloquante : un échec ici ne
    doit jamais faire échouer le restart (voir l'appel, protégé par try/except).
    """
    record = {
        "logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "check": check,
        "now_playing_title": now_song.get("text", "?"),
        "started_after_restart": started_after_restart,
        "queue_preview": [
            {
                "title": (item.get("song") or {}).get("text", "?"),
                "playlist": item.get("playlist", "?"),
                "sent_to_autodj": item.get("sent_to_autodj"),
                "is_played": item.get("is_played"),
            }
            for item in items[:8]
        ],
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def watch_and_dedup_queue(base: str, sid: int, api_key: str, restart_ts: float,
                          dry_run: bool, checks: int, wait_s: int,
                          log_path: Path | None = None) -> None:
    """Instantané de la file post-restart + suppression des doublons dos à dos.

    Entièrement non bloquant : le reset (étapes 1-3) a déjà réussi, cette étape
    ne doit jamais faire échouer le workflow. Le doublon reste en file pendant
    toute la 1re lecture du message (25 min à 1h48) : plusieurs passages
    espacés suffisent à le retirer avant qu'il ne parte à l'antenne.
    """
    for check in range(1, checks + 1):
        if not dry_run and wait_s:
            time.sleep(wait_s)
        try:
            np = api_get(f"{base}/api/nowplaying/{sid}", api_key)
            queue = api_get(f"{base}/api/station/{sid}/queue", api_key)
        except Exception as e:  # noqa: BLE001 — non bloquant
            print(f"  AVERTISSEMENT check {check}/{checks} : lecture file/antenne impossible ({e})",
                  file=sys.stderr)
            continue

        now = (np or {}).get("now_playing") or {}
        now_song = now.get("song") or {}
        played_at = now.get("played_at") or 0
        # Garde-fou : si le titre à l'antenne a démarré AVANT le restart
        # (info périmée / Liquidsoap pas encore relancé), le comparer à la file
        # supprimerait la lecture LÉGITIME du message → on l'ignore ce tour-ci.
        started_after_restart = played_at >= restart_ts - 5
        items = queue if isinstance(queue, list) else []

        if log_path is not None:
            try:
                append_watch_log(log_path, check, now_song, started_after_restart, items)
            except Exception as e:  # noqa: BLE001 — non bloquant, jamais faire échouer le restart
                print(f"  AVERTISSEMENT : écriture du log de surveillance impossible ({e})",
                      file=sys.stderr)

        print(f"  check {check}/{checks} — à l'antenne : « {now_song.get('text', '?')} » "
              f"(démarré {'après' if started_after_restart else 'AVANT'} le restart) ; "
              f"file : {len(items)} élément(s)")
        for pos, item in enumerate(items[:8], 1):
            song = item.get("song") or {}
            print(f"    {pos}. {song.get('text', '?')}"
                  f" | playlist={item.get('playlist', '?')}"
                  f" | sent_to_autodj={item.get('sent_to_autodj')}"
                  f" | is_played={item.get('is_played')}")

        dup_urls = queue_dup_delete_urls(
            now_song.get("id") if started_after_restart else None, items)
        if not dup_urls:
            print("    aucun doublon dos à dos dans la file.")
            continue
        for url in dup_urls:
            if dry_run:
                print(f"    [DRY-RUN] DELETE {url} (doublon dos à dos)")
                continue
            try:
                api_post(url, api_key, method="DELETE")
                print(f"    doublon dos à dos supprimé de la file ✅ ({url})")
            except Exception as e:  # noqa: BLE001 — non bloquant
                print(f"    AVERTISSEMENT : suppression impossible ({url}) : {e}",
                      file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Redémarre l'AutoDJ AzuraCast")
    parser.add_argument("--base-url", required=True, help="URL de base AzuraCast")
    parser.add_argument("--station-id", type=int, default=1, help="ID de la station")
    parser.add_argument("--dry-run", action="store_true",
                        help="n'appelle aucune action destructive ; affiche seulement ce qui serait fait")
    parser.add_argument("--queue-checks", type=int, default=3,
                        help="nombre de passages de surveillance de la file après le restart (défaut 3)")
    parser.add_argument("--queue-check-wait", type=int, default=40,
                        help="secondes d'attente avant chaque passage de surveillance (défaut 40)")
    parser.add_argument("--watch-log-dir", default="Radio/logs",
                        help="dossier où persister les instantanés de surveillance minuit "
                             "(fichier midnight_watch_<date>.log, JSON Lines) ; vide pour désactiver")
    args = parser.parse_args()

    api_key = os.environ.get("AZURACAST_API_KEY", "").strip()
    if not api_key:
        print("ERREUR : variable AZURACAST_API_KEY manquante", file=sys.stderr)
        sys.exit(1)

    base = args.base_url.rstrip("/")
    sid = args.station_id

    print(f"=== RESET AUTODJ (station {sid}){' [DRY-RUN]' if args.dry_run else ''} ===")

    # 1. Réinitialiser la file séquentielle interne de chaque bloc à la
    #    position 1. SANS ça, le curseur reste où le cycle précédent l'a laissé
    #    et BLOC_A démarre au milieu (le message en position 1 n'est jamais joué).
    print("1) Reshuffle des blocs (curseur séquentiel → position 1)")
    reshuffle_blocks(base, sid, api_key, args.dry_run)

    # 2. Vider la file « à venir » de la station — supprime les morceaux de
    #    BLOC_D encore en attente, construits depuis l'ancien curseur.
    clear_url = f"{base}/api/station/{sid}/queue/clear"
    if args.dry_run:
        print(f"2) [DRY-RUN] POST {clear_url}")
    else:
        print(f"2) POST {clear_url}")
        try:
            result = api_post(clear_url, api_key)
            if result.get("success"):
                print(f"  OK : {result.get('message', '')}")
            else:
                print(f"  ECHEC : {result}", file=sys.stderr)
                sys.exit(1)
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} : {e.read().decode()[:200]}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"  ERREUR : {e}", file=sys.stderr)
            sys.exit(1)

    # 3. Redémarrer Liquidsoap pour qu'il reconstruise sa file sur les blocs
    #    fraîchement réinitialisés. ATTENTION : le restart NE réinitialise PAS
    #    le curseur des playlists (c'est le reshuffle de l'étape 1 qui le fait).
    restart_url = f"{base}/api/station/{sid}/backend/restart"
    if args.dry_run:
        print(f"3) [DRY-RUN] POST {restart_url}")
    else:
        print(f"3) POST {restart_url}")
        try:
            result = api_post(restart_url, api_key)
            if result.get("success"):
                print(f"  OK : {result.get('message', '')}")
            else:
                print(f"  ECHEC : {result}", file=sys.stderr)
                sys.exit(1)
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} : {e.read().decode()[:200]}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"  ERREUR : {e}", file=sys.stderr)
            sys.exit(1)

    # 4. Surveiller la file reconstruite : instantané (diagnostic du bug
    #    « message 2× d'affilée ») + suppression des doublons dos à dos avant
    #    qu'ils ne partent à l'antenne. En dry-run : un seul passage immédiat,
    #    en lecture seule (valide le parsing sur l'API réelle sans rien toucher).
    restart_ts = time.time()
    checks = 1 if args.dry_run else max(0, args.queue_checks)
    if checks:
        print("4) Surveillance de la file post-restart (diagnostic + dédoublonnage)")
        watch_log_path = (
            Path(args.watch_log_dir) / f"midnight_watch_{datetime.now(timezone.utc):%Y-%m-%d}.log"
            if args.watch_log_dir and not args.dry_run else None
        )
        watch_and_dedup_queue(base, sid, api_key, restart_ts,
                              args.dry_run, checks, args.queue_check_wait,
                              log_path=watch_log_path)

    print("=== RESET TERMINÉ ===")


if __name__ == "__main__":
    main()
