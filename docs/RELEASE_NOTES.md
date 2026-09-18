# Creeper 1.1.0

Creeper now ships independently installable worker and server packages:

- `pip install creeper-client` installs the `creeper-client` command.
- `pip install creeper-server` installs the `creeper-server` command.
- The shared `yunying-creeper-core` runtime is installed automatically.

Servers persist tasks in SQLite and assign one pending job to each idle worker. Workers return results to the server while keeping a local copy. Disconnected leases are retried up to three attempts, and server restarts recover unfinished tasks. Unchanged completed configurations are not automatically repeated; use `--repeat` to request another run. New or modified site configurations are picked up every five seconds.

Collection now uses isolated browsers, bounded concurrency, bounded retries, explicit waits, and deterministic cleanup. Legacy selector modes and XPath attribute extraction are supported. SQLite writes are parameterized and legacy tables migrate without deleting content.

The result dashboard includes search, pagination, empty/error states and JSON endpoints. Setup, configuration, standalone collection, distributed deployment, package building and trusted publishing are documented in the README.

Breaking changes: client/server must both use protocol version 1.1.0; the original broadcast protocol is replaced by task scheduling. The default backend is local SQLite. Numeric pre-operation types are rejected because the original project did not define their behavior. MySQL is optional for worker/standalone storage, while the scheduler and dashboard use SQLite.
