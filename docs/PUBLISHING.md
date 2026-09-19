# Publishing

Release artifacts are built locally with:

```sh
python -m pip install -r requirements-dev.txt build twine
python -m pytest -q
ruff check .
ruff format --check .
python scripts/build_release.py
```

The output is three wheels, three source distributions and `dist/SHA256SUMS.txt`. All three packages have the same version; update `packages/*/pyproject.toml`, `packages/*/src/*/__init__.py`, the legacy entry point and version assertions together before a new release. PyPI versions cannot be overwritten.

## GitHub Actions trusted publishing

The workflow is `.github/workflows/release.yml`. Configure three pending publishers on PyPI for the initial publication:

| PyPI project | GitHub owner | Repository | Workflow | Environment |
|---|---|---|---|---|
| `yunying-creeper-core` | `YunyingTech` | `Creeper` | `release.yml` | `pypi` |
| `creeper-client` | `YunyingTech` | `Creeper` | `release.yml` | `pypi` |
| `creeper-server` | `YunyingTech` | `Creeper` | `release.yml` | `pypi` |

Create a GitHub environment named `pypi` in the repository. After configuring all three PyPI publishers, set the repository Actions variable `PYPI_PUBLISH_ENABLED` to `true` to enable PyPI uploads. Without that variable, the workflow publishes only the GitHub Release and attached packages. Push the reviewed source and a matching tag:

```sh
git add .
git commit -m "Ship installable client and server with persistent task scheduling"
git tag v1.1.0
git push origin HEAD
git push origin v1.1.0
```

The workflow tests and builds the source, optionally publishes the common dependency before the applications, and then creates a GitHub Release containing the artifacts. If PyPI publishing is enabled and fails, the release job waits for that failure to be resolved. If PyPI publishing is disabled, the release still provides directly installable wheels and clearly distinguishes them from PyPI availability. `workflow_dispatch` on a branch only validates and builds; dispatch on a matching tag also publishes.

Reference: https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/

## Manual publication

If trusted publishing is unavailable, configure `TWINE_USERNAME=__token__` and `TWINE_PASSWORD` locally with a PyPI API token. Do not commit the token or place it in README examples. Publish the shared runtime first:

```sh
python -m twine upload dist/yunying_creeper_core-1.1.0*
python -m twine upload dist/creeper_client-1.1.0* dist/creeper_server-1.1.0*
gh release create v1.1.0 dist/* --title "Creeper v1.1.0" --notes-file docs/RELEASE_NOTES.md --verify-tag
```

Both a GitHub credential with repository write/release access and a PyPI publishing credential (or configured trusted publisher) are needed. An available package name does not itself authorize publication.

## Verify wheels independently of the repository

Create separate clean environments and install each application from `dist` (the common wheel is resolved automatically):

```sh
python -m venv .verify-client
python -m venv .verify-server
.verify-client/bin/python -m pip install --find-links dist creeper-client==1.1.0
.verify-server/bin/python -m pip install --find-links dist creeper-server==1.1.0
python scripts/smoke_installed.py --client-python .verify-client/bin/python --server-python .verify-server/bin/python
```

On Windows replace `bin/python` with `Scripts/python.exe`. The smoke test starts a local HTTP fixture, launches independently installed server and worker commands from temporary working directories, uses real Chrome to collect text, checks centrally stored results, and requests the dashboard assets. Chrome is required for this opt-in test.
