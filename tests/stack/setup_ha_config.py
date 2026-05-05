"""Pre-seed a Home Assistant config directory with this integration loaded.

Writes:
  - configuration.yaml with the bare minimum for HA to start
  - .storage/core.config_entries containing one ghostfolio config entry
  - custom_components/ghostfolio/ as a copy of the integration in this repo

Usage:
    python setup_ha_config.py --config-dir ha_config --url URL --token TOKEN
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_SRC = REPO_ROOT / "custom_components" / "ghostfolio"


CONFIGURATION_YAML = """\
default_config:

logger:
  default: info
  logs:
    custom_components.ghostfolio: debug
"""


def write_config_entries(config_dir: Path, url: str, token: str) -> None:
    storage_dir = config_dir / ".storage"
    storage_dir.mkdir(parents=True, exist_ok=True)

    entry_id = uuid.uuid4().hex
    payload = {
        "version": 1,
        "minor_version": 1,
        "key": "core.config_entries",
        "data": {
            "entries": [
                {
                    "entry_id": entry_id,
                    "version": 1,
                    "minor_version": 1,
                    "domain": "ghostfolio",
                    "title": f"Ghostfolio ({url})",
                    "data": {
                        "url": url,
                        "access_token": token,
                        "verify_ssl": False,
                    },
                    "options": {},
                    "pref_disable_new_entities": False,
                    "pref_disable_polling": False,
                    "source": "user",
                    "unique_id": url,
                    "disabled_by": None,
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "modified_at": "2024-01-01T00:00:00+00:00",
                    "discovery_keys": {},
                }
            ]
        },
    }
    (storage_dir / "core.config_entries").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def copy_integration(config_dir: Path) -> None:
    dest = config_dir / "custom_components" / "ghostfolio"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(INTEGRATION_SRC, dest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--token", required=True)
    args = parser.parse_args()

    config_dir = Path(args.config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "configuration.yaml").write_text(CONFIGURATION_YAML, encoding="utf-8")

    copy_integration(config_dir)
    write_config_entries(config_dir, args.url, args.token)

    print(f"Staged Home Assistant config at {config_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
