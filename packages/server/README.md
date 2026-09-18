# creeper-server

Install the Creeper task server with Python 3.10+:

```sh
pip install creeper-server
creeper-server init
creeper-server --host 127.0.0.1 --port 11451 --tasks-dir config
```

Set `CREEPER_TOKEN` on both ends before binding to a network interface such as `0.0.0.0`. Workers connect using `creeper-client --server SERVER_IP`.

The server persists jobs in SQLite, assigns each pending job to one idle worker, requeues interrupted jobs, and collects results centrally. A browser is required only on workers.

Browse results with `creeper-server dashboard`, then open http://127.0.0.1:5000.
Run `creeper-server --help` for all options. The TCP protocol is intended for loopback or a trusted network; use a VPN/SSH tunnel across untrusted networks.

Documentation: https://github.com/YunyingTech/Creeper
License: GPL-3.0-only.
