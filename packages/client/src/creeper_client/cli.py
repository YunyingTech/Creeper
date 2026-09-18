"""Entry point installed by pip install creeper-client."""

import argparse
import json
import sys
from pathlib import Path

import yaml
from creeper_core.cli import initialize, port
from creeper_core.daemon import Daemon
from creeper_core.settings import load_settings, load_sites

from creeper_client import __version__
from creeper_client.client import Client


def main(argv=None):
    parser = argparse.ArgumentParser(description="Connect a Creeper worker to a task server")
    parser.add_argument("command", nargs="?", choices=["run", "init"], default="run")
    parser.add_argument("--version", action="version", version=f"creeper-client {__version__}")
    parser.add_argument(
        "--config", type=Path, help="Optional config.yaml; paths resolve relative to this file"
    )
    parser.add_argument("--directory", type=Path, default=Path.cwd(), help="Directory for init")
    parser.add_argument("--server", help="Server hostname or IP address")
    parser.add_argument("--port", type=port, help="Server TCP port (default: 11451)")
    parser.add_argument("--database", type=Path, help="Local SQLite result file")
    parser.add_argument("--single", action="store_true", help="Run local site configurations once")
    parser.add_argument("--config-dir", type=Path, help="Local site directory for --single / --validate")
    parser.add_argument("--validate", action="store_true", help="Validate local site YAML without Chrome")
    parser.add_argument("--output", type=Path, help="Single mode JSON result export")
    args = parser.parse_args(argv)
    if args.output and not args.single:
        parser.error("--output requires --single")
    try:
        if args.command == "init":
            return initialize(args.directory)
        settings = load_settings(args.config)
        if args.server:
            settings["server-ip"] = args.server
        if args.port:
            settings["server-port"] = args.port
        if args.database:
            settings["database-path"] = str(args.database.resolve())
        elif args.config is None and not Path("config.yaml").exists():
            settings["database-path"] = str(Path("data/client.sqlite3").resolve())
        if args.config_dir:
            settings["config-dir"] = str(args.config_dir.resolve())
        if args.validate:
            sites = load_sites(settings["config-dir"])
            print(f"Configuration OK: {len(sites)} sites")
            return 0
        if args.single:
            daemon = Daemon.from_settings(settings)
            results = daemon.creeper()
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
                )
            print(f"Completed: {len(results)} collections, {len(daemon.errors)} errors")
            return 1 if daemon.errors else 0
        client = Client(settings["server-ip"], settings["server-port"], settings=settings)
        try:
            return 0 if client.connect_to_server() else 1
        finally:
            client.close_socket()
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError, yaml.YAMLError) as error:
        print(f"Creeper client error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
