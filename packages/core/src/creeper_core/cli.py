"""Helpers used by independently installed command-line packages."""

import argparse
from pathlib import Path

import yaml

from creeper_core.settings import DEFAULTS


def port(value):
    try:
        result = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 1 <= result <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return result


def initialize(directory, server=False):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "config.yaml"
    if path.exists():
        raise ValueError(f"Configuration already exists: {path}")
    config = dict(DEFAULTS)
    config["database-path"] = "data/server.sqlite3" if server else "data/client.sqlite3"
    config["server-config-dir"] = "config"
    config["auto-start"] = True
    path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
    if server:
        sites = directory / "config"
        sites.mkdir(exist_ok=True)
        sample = sites / "example.yaml"
        if not sample.exists():
            sample.write_text(
                yaml.safe_dump(
                    {
                        "name": "Example Domain",
                        "url": "https://example.com",
                        "collections": [{"name": "Heading", "xpath": "//h1"}],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
    print(f"Created {path}")
    return 0
