#!/usr/bin/env python3
"""
Réinitialise l'AutoDJ d'AzuraCast à minuit.

Déclenché chaque nuit à 00h00 UTC pour que toutes les playlists séquentielles
(BLOC_A/B/C/D) repartent de la position 1 (jingle → message).

Trois étapes, dans cet ordre :
  1. reshuffle de chaque bloc → réinitialise sa file séquentielle interne
     (champ `queue_reset_at`) à la position 1. ÉTAPE CLÉ, longtemps absente :
     ni `queue/clear` ni `backend/restart` ne touchent ce curseur, d'où un
     BLOC_A qui reprenait systématiquement au milieu (jamais sur le message).
  2. queue/clear → vide la file « à venir » de la station (restes de BLOC_D).
  3. backend/restart → Liquidsoap reconstruit sa file sur les blocs réinitialisés.

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
import urllib.error
import urllib.request


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Redémarre l'AutoDJ AzuraCast")
    parser.add_argument("--base-url", required=True, help="URL de base AzuraCast")
    parser.add_argument("--station-id", type=int, default=1, help="ID de la station")
    parser.add_argument("--dry-run", action="store_true",
                        help="n'appelle aucune action destructive ; affiche seulement ce qui serait fait")
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

    print("=== RESET TERMINÉ ===")


if __name__ == "__main__":
    main()
