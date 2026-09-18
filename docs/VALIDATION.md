# Local validation — 2026-09-18

Environment: Windows, Python 3.12.10, Chrome, Selenium 4.49.0.

| Check | Result |
| --- | --- |
| Default pytest suite | 58 passed; 1 opt-in Chrome test skipped |
| Opt-in Chrome integration test | 1 passed |
| Ruff lint / format | Passed |
| Three wheels and three source distributions | Built successfully; all passed `twine check` |
| Artifact/source comparison and SHA-256 manifest | Passed |
| Independent client-only and server-only virtual environments | Installed from local wheels; `pip check` passed |
| Installed-package end-to-end test | Passed: authenticated TCP task, real Chrome collection, local and central SQLite, dashboard HTML/CSS/JS and API |
| Two-node dispatch and directory reload | Passed; tasks assigned once and new configuration picked up without repeating the initial batch |

The browser tests use local HTTP fixtures, not external news sites. Existing third-party site selectors have been schema-validated but not verified against the live sites. MySQL integration and the Linux/Python 3.10 CI matrix have not been executed locally.

Packages built: `creeper-client==1.1.0`, `creeper-server==1.1.0`, `yunying-creeper-core==1.1.0`.

Publication is pending: no usable GitHub credential, PyPI environment credential, `.pypirc`, or PyPI keyring credential was present. No remote repository push, GitHub Release creation, or PyPI upload has been performed. The three PyPI project names returned 404 (available) when checked; availability can change before publication.

See [PUBLISHING.md](PUBLISHING.md) for trusted publisher setup, release commands, and reproducible installation verification.
