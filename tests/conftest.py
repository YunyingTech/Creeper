from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from creeper_core.settings import DEFAULTS


@pytest.fixture
def site():
    return {
        "name": "fixture",
        "url": "http://127.0.0.1:8000",
        "collections": [{"name": "news", "xpath": "//a"}],
    }


@pytest.fixture
def settings(tmp_path):
    config = deepcopy(DEFAULTS)
    for key in ("config-dir", "server-config-dir", "received-config-dir"):
        config[key] = str(tmp_path / key)
        Path(config[key]).mkdir()
    config["database-path"] = str(tmp_path / "results.sqlite3")
    config["delay"] = 0
    config["timeout"] = 0.01
    return config


@pytest.fixture
def write_site(site):
    def write(directory, filename="site.yaml", data=None):
        path = Path(directory) / filename
        path.write_text(yaml.safe_dump(data or site, allow_unicode=True), encoding="utf-8")
        return path

    return write
