from copy import deepcopy

import pytest
import yaml
from creeper_core.settings import ROOT, load_settings, load_sites, validate_site

from main import main


@pytest.mark.parametrize("directory", ["config", "ServerConfig", "examples/sites"])
def test_bundled_site_configs(directory):
    assert load_sites(ROOT / directory)


def test_paths_resolve_from_config_location(tmp_path, monkeypatch):
    path = tmp_path / "custom.yaml"
    path.write_text("config-dir: sites\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path.parent)
    monkeypatch.setenv("CREEPER_TOKEN", "test-token")
    settings = load_settings(path)
    assert settings["config-dir"] == str(tmp_path / "sites")
    assert settings["auth-token"] == "test-token"


@pytest.mark.parametrize(
    "data",
    [
        "max_thread: 0",
        "max_thread: true",
        "delay: .nan",
        "timeout: -1",
        "server-port: 65536",
        "headless: nope",
        "IP-pool-list: bad",
        "database-backend: unknown",
        "config-dir: null",
        "auth-token: 12",
    ],
)
def test_invalid_settings(tmp_path, data, monkeypatch):
    monkeypatch.delenv("CREEPER_TOKEN", raising=False)
    path = tmp_path / "bad.yaml"
    path.write_text(data, encoding="utf-8")
    with pytest.raises(ValueError):
        load_settings(path)


@pytest.mark.parametrize(
    "patch",
    [
        {"url": "file:///etc/passwd"},
        {"collections": []},
        {"pre": [{"type": 0}]},
        {"collections": [{"name": "missing xpath"}]},
        {"pre": [{"type": "wait", "seconds": -1}]},
    ],
)
def test_invalid_sites(site, patch):
    with pytest.raises(ValueError):
        validate_site({**site, **patch})


def test_site_normalization_does_not_mutate_input(site):
    site["url"] = "example.com"
    before = deepcopy(site)
    assert validate_site(site)["url"] == "https://example.com"
    assert site == before


def test_validate_cli_does_not_launch_browser(capsys):
    assert main(["--validate", "--no-banner"]) == 0
    assert "13 sites" in capsys.readouterr().out


def test_invalid_yaml_cli(tmp_path, capsys):
    path = tmp_path / "bad.yaml"
    path.write_text("broken: [", encoding="utf-8")
    assert main(["--config", str(path), "--validate"]) == 1
    assert "Creeper error" in capsys.readouterr().err


def test_safe_yaml_only(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("!!python/object:builtins.object {}", encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        load_settings(path)
