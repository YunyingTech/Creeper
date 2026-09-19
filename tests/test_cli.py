import subprocess
import sys
import sysconfig
from pathlib import Path

from creeper_client.cli import main as client_main
from creeper_server.cli import main as server_main


def test_installed_entry_points():
    executable_dir = Path(sysconfig.get_path("scripts"))
    suffix = ".exe" if sys.platform == "win32" else ""
    for name in ("creeper-client", "creeper-server"):
        output = subprocess.run(
            [str(executable_dir / (name + suffix)), "--version"], check=True, capture_output=True, text=True
        )
        assert "1.1.0" in output.stdout


def test_init_validate_and_existing_config_preserved(tmp_path, monkeypatch):
    assert server_main(["init", "--directory", str(tmp_path)]) == 0
    before = (tmp_path / "config.yaml").read_bytes()
    assert server_main(["init", "--directory", str(tmp_path)]) == 1
    assert (tmp_path / "config.yaml").read_bytes() == before
    monkeypatch.chdir(tmp_path.parent)
    assert server_main(["--config", str(tmp_path / "config.yaml"), "--validate"]) == 0
    assert client_main(["--config", str(tmp_path / "config.yaml"), "--validate"]) == 0


def test_client_init_in_fresh_directory(tmp_path):
    assert client_main(["init", "--directory", str(tmp_path)]) == 0
    assert (tmp_path / "config.yaml").is_file()
