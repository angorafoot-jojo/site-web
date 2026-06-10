"""Vérifie que chaque chemin de la config de rotation existe dans la médiathèque AzuraCast.

Comparaison stricte octet pour octet (comme l'import M3U d'AzuraCast).
Sort avec le code 1 et la liste des chemins introuvables s'il y a un écart,
ce qui permet au workflow GitHub Actions d'alerter avant la rotation de 23h.

Usage :
    AZURACAST_API_KEY=xxx python Radio/validate_paths.py --config Radio/azuracast_rotation_config_option_a.example.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any, Iterator


def iter_config_paths(node: Any, key: str | None = None) -> Iterator[str]:
    if isinstance(node, dict):
        for k, v in node.items():
            yield from iter_config_paths(v, k)
    elif isinstance(node, list):
        for v in node:
            yield from iter_config_paths(v, key)
    elif key == "path" and isinstance(node, str):
        yield node


def fetch_server_paths(base_url: str, station_id: int, api_key: str) -> set[str]:
    url = f"{base_url.rstrip('/')}/api/station/{station_id}/files"
    request = urllib.request.Request(url, headers={"X-API-Key": api_key})
    with urllib.request.urlopen(request, timeout=300) as response:
        files = json.load(response)
    return {f["path"] for f in files}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="Radio/azuracast_rotation_config_option_a.example.json")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    base_url = os.getenv("AZURACAST_BASE_URL") or config.get("azuracast_base_url")
    api_key = os.getenv("AZURACAST_API_KEY") or config.get("azuracast_api_key")
    station_id = int(config.get("station_id", 1))

    if not base_url or not api_key or api_key == "REMPLACE_MOI":
        print("ERREUR: azuracast_base_url ou clé API manquante (env AZURACAST_API_KEY).")
        return 2

    config_paths = list(iter_config_paths(config))
    server_paths = fetch_server_paths(base_url, station_id, api_key)
    missing = [p for p in config_paths if p not in server_paths]

    print(f"Chemins dans la config : {len(config_paths)}")
    print(f"Fichiers sur le serveur : {len(server_paths)}")

    if missing:
        print(f"\n❌ {len(missing)} chemin(s) introuvable(s) sur AzuraCast :")
        for path in missing:
            print(f"  - {path}")
        print("\nLa rotation de 23h UTC échouera si rien n'est corrigé.")
        return 1

    print("✅ Tous les chemins de la config existent sur le serveur.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
