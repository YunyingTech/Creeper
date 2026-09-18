"""Creeper command-line entry point; importing this module has no runtime side effects."""

import argparse
import json
import sys
from pathlib import Path

import yaml
from creeper_core.settings import ROOT, load_settings, load_sites

__version__ = "1.1.0"


def build_parser():
    parser = argparse.ArgumentParser(description="Creeper: configurable Selenium collection")
    parser.add_argument("--version", action="version", version=f"Creeper {__version__}")
    parser.add_argument("--mode", choices=("single", "server", "client", "dashboard"), default="single")
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml", help="Application YAML file")
    parser.add_argument(
        "--config-dir", type=Path, help="Override site directory (server: files to distribute)"
    )
    parser.add_argument(
        "--validate", action="store_true", help="Validate configuration without launching Chrome"
    )
    parser.add_argument(
        "--auto-start", action="store_true", help="Server: start each authenticated worker after transfer"
    )
    parser.add_argument("--output", type=Path, help="Single mode: export successful collections as JSON")
    parser.add_argument("--no-banner", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.auto_start and args.mode != "server":
        parser.error("--auto-start requires --mode server")
    if args.output and args.mode != "single":
        parser.error("--output requires --mode single")
    try:
        settings = load_settings(args.config)
        if args.config_dir:
            key = "server-config-dir" if args.mode == "server" else "config-dir"
            settings[key] = str(args.config_dir.resolve())
        if args.validate:
            key = "server-config-dir" if args.mode == "server" else "config-dir"
            sites = load_sites(settings[key])
            print(
                f"Configuration OK: {len(sites)} sites, {sum(len(s['collections']) for s in sites)} collections"
            )
            return 0
        if not args.no_banner:
            from Banner import banner

            banner()
        from creeper_core.logger import Logger

        logger = Logger()
        logger.info(f"Starting Creeper {__version__} ({args.mode})")
        if args.mode == "single":
            from creeper_core.daemon import Daemon

            daemon = Daemon.from_settings(settings)
            results = daemon.creeper()
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
                )
            logger.info(
                f"Completed: {len(results)} collections, "
                f"{sum(len(row['content']) for row in results)} records, {len(daemon.errors)} errors"
            )
            return 1 if daemon.errors else 0
        if args.mode == "server":
            from creeper_server.server import Server

            server = Server(
                settings["listen-port"],
                settings["max_connection"],
                host=settings["listen-host"],
                token=settings["auth-token"],
                config_dir=settings["server-config-dir"],
                auto_start=True,
                database_path=settings["database-path"],
            )
            server.start_server_socket()
        elif args.mode == "client":
            from creeper_client.client import Client

            client = Client(settings["server-ip"], settings["server-port"], settings=settings)
            try:
                return 0 if client.connect_to_server() else 1
            finally:
                client.close_socket()
        else:
            if settings["database-backend"] != "sqlite":
                raise ValueError("Dashboard currently supports SQLite only")
            from creeper_server.dashboard import Dashboard

            Dashboard(settings["database-path"]).run(settings["dashboard-host"], settings["dashboard-port"])
        return 0
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError, yaml.YAMLError) as error:
        print(f"Creeper error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
