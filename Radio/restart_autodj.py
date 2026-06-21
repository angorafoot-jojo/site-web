#!/usr/bin/env python3
"""
Redémarre l'AutoDJ d'AzuraCast et vide la file d'attente.

Déclenché chaque nuit à 00h00 UTC pour garantir que toutes les playlists
séquentielles (BLOC_A/B/C/D) repartent de la position 1 (jingle → message),
indépendamment de l'état du pointeur interne de Liquidsoap.

Usage:
    python Radio/restart_autodj.py --base-url URL [--station-id ID]

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


def api_post(url: str, api_key: str) -> dict:
    req = urllib.request.Request(
        url,
        method="POST",
        data=b"",
        headers={
            "Authorization": f"Bearer {api_key}",
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main() -> None:
    parser = argparse.ArgumentParser(description="Redémarre l'AutoDJ AzuraCast")
    parser.add_argument("--base-url", required=True, help="URL de base AzuraCast")
    parser.add_argument("--station-id", type=int, default=1, help="ID de la station")
    args = parser.parse_args()

    api_key = os.environ.get("AZURACAST_API_KEY", "").strip()
    if not api_key:
        print("ERREUR : variable AZURACAST_API_KEY manquante", file=sys.stderr)
        sys.exit(1)

    base = args.base_url.rstrip("/")
    sid = args.station_id

    print(f"=== RESTART AUTODJ (station {sid}) ===")

    restart_url = f"{base}/api/station/{sid}/backend/restart"
    print(f"POST {restart_url}")
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

    # Liquidsoap prend quelques secondes pour redémarrer avant d'accepter
    # la commande clear sur la file.
    time.sleep(8)

    clear_url = f"{base}/api/station/{sid}/queue/clear"
    print(f"POST {clear_url}")
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

    print("=== RESET TERMINÉ — pointeurs remis à la position 1 ===")


if __name__ == "__main__":
    main()
