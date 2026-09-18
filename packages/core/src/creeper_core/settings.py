"""Application and site configuration validation shared by all run modes."""

import math
import os
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

import yaml

ROOT = Path.cwd()
DEFAULTS = {
    "max_thread": 2,
    "delay": 1,
    "timeout": 15,
    "page-load-timeout": 45,
    "max-retries": 3,
    "headless": True,
    "config-dir": "config",
    "database-backend": "sqlite",
    "database-path": "data/creeper.sqlite3",
    "mysql-config": "database.yaml",
    "server-ip": "127.0.0.1",
    "server-port": 11451,
    "listen-host": "127.0.0.1",
    "listen-port": 11451,
    "max_connection": 16,
    "server-config-dir": "ServerConfig",
    "received-config-dir": "data/received-config",
    "auth-token": "",
    "auto-start": False,
    "dashboard-host": "127.0.0.1",
    "dashboard-port": 5000,
    "IP-pool": False,
    "IP-pool-list": [],
}


def number(value, name, minimum=0, integer=False):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < minimum
        or (integer and not isinstance(value, int))
    ):
        raise ValueError(f"{name} must be {'an integer' if integer else 'a number'} >= {minimum}")
    return value


def read_yaml(path):
    with Path(path).open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return data


def load_settings(path=None):
    explicit = path is not None
    path = Path(path or Path.cwd() / "config.yaml").resolve()
    settings = {**deepcopy(DEFAULTS), **(read_yaml(path) if explicit or path.exists() else {})}
    for key in ("max_thread", "max-retries", "max_connection"):
        number(settings[key], key, 1, integer=True)
    for key in ("timeout", "page-load-timeout"):
        number(settings[key], key, 0.1)
    number(settings["delay"], "delay")
    for key in ("server-port", "listen-port", "dashboard-port"):
        number(settings[key], key, 1, integer=True)
        if settings[key] > 65535:
            raise ValueError(f"{key} must be <= 65535")
    for key in ("headless", "auto-start", "IP-pool"):
        if not isinstance(settings[key], bool):
            raise ValueError(f"{key} must be true or false")
    if settings["database-backend"] not in ("sqlite", "mysql"):
        raise ValueError("database-backend must be sqlite or mysql")
    for key in ("server-ip", "listen-host", "dashboard-host"):
        if not isinstance(settings[key], str) or not settings[key].strip():
            raise ValueError(f"{key} must be a non-empty hostname")
    for key in ("config-dir", "database-path", "mysql-config", "server-config-dir", "received-config-dir"):
        value = settings[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty path")
        settings[key] = str((path.parent / value).resolve())
    if not isinstance(settings["IP-pool-list"], list) or not all(
        isinstance(item, str) and item.strip() for item in settings["IP-pool-list"]
    ):
        raise ValueError("IP-pool-list must be a list of paths")
    settings["IP-pool-list"] = [str((path.parent / item).resolve()) for item in settings["IP-pool-list"]]
    settings["auth-token"] = os.environ.get("CREEPER_TOKEN", settings["auth-token"])
    if not isinstance(settings["auth-token"], str):
        raise ValueError("auth-token must be a string")
    return settings


def validate_site(data, source="site configuration"):
    data = deepcopy(data)
    if not isinstance(data, dict):
        raise ValueError(f"{source}: expected a mapping")
    url = data.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError(f"{source}: url is required")
    if "://" not in url:
        url = "https://" + url
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"{source}: url must be an HTTP(S) URL")
    data["url"] = url
    data.setdefault("name", parsed.hostname)
    collections = data.get("collections")
    if not isinstance(collections, list) or not collections:
        raise ValueError(f"{source}: collections must be a non-empty list")
    for collection in collections:
        if not isinstance(collection, dict):
            raise ValueError(f"{source}: collection must be a mapping")
        for key in ("name", "xpath"):
            if not isinstance(collection.get(key), str) or not collection[key].strip():
                raise ValueError(f"{source}: collection {key} is required")
        kind = collection.get("type", "text")
        if kind not in ("text", "class", "tag", "css", "xpath", "target", "rel"):
            raise ValueError(f"{source}: unsupported collection type: {kind}")
        if kind != "text" and (not isinstance(collection.get("child"), str) or not collection["child"]):
            raise ValueError(f"{source}: {kind} requires child")
        if "attribute" in collection and (
            not isinstance(collection["attribute"], str) or not collection["attribute"]
        ):
            raise ValueError(f"{source}: attribute must be a non-empty string")
    operations = data.get("pre", [])
    if not isinstance(operations, list):
        raise ValueError(f"{source}: pre must be a list")
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError(f"{source}: pre operation must be a mapping")
        kind = operation.get("type")
        if kind not in ("wait", "click", "input", "scroll"):
            raise ValueError(
                f"{source}: pre.type must be wait/click/input/scroll (numeric types are ambiguous)"
            )
        number(operation.get("id", 0), "pre.id", integer=True)
        if kind in ("click", "input") and not isinstance(operation.get("xpath"), str):
            raise ValueError(f"{source}: {kind} requires xpath")
        if kind == "wait":
            number(operation.get("seconds", 1), "pre.seconds")
        if kind == "scroll":
            number(operation.get("pixels", 600), "pre.pixels")
        if kind == "input" and not isinstance(operation.get("text"), str):
            raise ValueError(f"{source}: input requires text")
    return data


def load_sites(directory, filenames=None):
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f"Site configuration directory does not exist: {directory}")
    paths = sorted(p for p in directory.iterdir() if p.suffix.lower() in (".yaml", ".yml") and p.is_file())
    if filenames is not None:
        paths = [p for p in paths if p.name in filenames]
        if len(paths) != len(set(filenames)):
            raise ValueError("One or more requested configuration files are missing")
    if not paths:
        raise ValueError(f"No YAML site configurations found in {directory}")
    return [validate_site(read_yaml(p), str(p)) for p in paths]
