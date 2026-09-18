"""Entry point installed by pip install creeper-server."""

import argparse
import sys
from pathlib import Path

import yaml
from creeper_core.cli import initialize, port
from creeper_core.settings import load_settings, load_sites

from creeper_server import __version__
from creeper_server.dashboard import Dashboard
from creeper_server.server import Server


def main(argv=None):
    parser = argparse.ArgumentParser(description="Distribute persistent Creeper tasks to connected workers")
    parser.add_argument("command", nargs="?", choices=["run", "init", "dashboard"], default="run")
    parser.add_argument("--version", action="version", version=f"creeper-server {__version__}")
    parser.add_argument("--config", type=Path, help="Optional configuration file")
    parser.add_argument("--directory", type=Path, default=Path.cwd(), help="Directory for init")
    parser.add_argument("--host", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=port, help="TCP port (11451) or dashboard HTTP port (5000)")
    parser.add_argument("--tasks-dir", type=Path, help="Directory of site YAML tasks")
    parser.add_argument("--database", type=Path, help="Server task and result SQLite file")
    parser.add_argument(
        "--repeat", action="store_true", help="Enqueue a new run even for unchanged completed tasks"
    )
    parser.add_argument("--validate", action="store_true", help="Validate tasks without starting the server")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            return initialize(args.directory, server=True)
        settings = load_settings(args.config)
        if args.database:
            settings["database-path"] = str(args.database.resolve())
        elif args.config is None and not Path("config.yaml").exists():
            settings["database-path"] = str(Path("data/server.sqlite3").resolve())
            settings["server-config-dir"] = str(Path("config").resolve())
        if args.tasks_dir:
            settings["server-config-dir"] = str(args.tasks_dir.resolve())
        if args.validate:
            sites = load_sites(settings["server-config-dir"])
            print(f"Configuration OK: {len(sites)} tasks")
            return 0
        if args.command == "dashboard":
            Dashboard(settings["database-path"]).run(
                args.host or settings["dashboard-host"], args.port or settings["dashboard-port"]
            )
            return 0
        server = Server(
            args.port or settings["listen-port"],
            settings["max_connection"],
            host=args.host or settings["listen-host"],
            token=settings["auth-token"],
            config_dir=settings["server-config-dir"],
            database_path=settings["database-path"],
            repeat=args.repeat,
            auto_start=True,
        )
        server.start_server_socket()
        return 0
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError, yaml.YAMLError) as error:
        print(f"Creeper server error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
