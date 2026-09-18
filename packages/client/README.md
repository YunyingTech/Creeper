# creeper-client

Install a Creeper collection worker with Python 3.10+:

```sh
pip install creeper-client
creeper-client --server 127.0.0.1 --port 11451
```

Set `CREEPER_TOKEN` to the same value as the server for authenticated connections. Install Chrome/Chromium on workers. Selenium Manager locates/downloads the compatible driver on first use.

The worker receives one job at a time, collects the configured fields, saves results locally, and sends successful results and failure details back to the server. No repository checkout is needed.

Run `creeper-client --help` for configuration and standalone collection options.

Documentation: https://github.com/YunyingTech/Creeper
License: GPL-3.0-only.
