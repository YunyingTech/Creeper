"""Build all three distributions and verify their metadata. Run from any directory."""

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    for package in ("core", "client", "server"):
        subprocess.run(
            [sys.executable, "-m", "build", str(ROOT / "packages" / package), "--outdir", str(output)],
            check=True,
        )
    artifacts = sorted([*output.glob("*.whl"), *output.glob("*.tar.gz")])
    subprocess.run([sys.executable, "-m", "twine", "check", *map(str, artifacts)], check=True)
    checksums = "\n".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in artifacts
    )
    (output / "SHA256SUMS.txt").write_text(checksums + "\n", encoding="utf-8")
    print(f"Built and checked {len(artifacts)} release artifacts in {output}")


if __name__ == "__main__":
    main()
