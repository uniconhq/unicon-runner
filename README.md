# Unicon 🦄 Runner

Starting the runner and connecting to the work/task queue:

```bash
RABBITMQ_URL="<ampq-url>" EXECUTOR_TYPE="[podman | sandbox | unsafe]" uv run unicon-runner/app.py
```

## Executors

All program executors depend on [`uv`](https://github.com/astral-sh/uv) as the environment manager and program executor (via `uv run`). As such, it is required to have `uv` installed on the host system that is running `sandbox` and `unsafe` typed executors (for container-based executors like `podman`, we handle the installation of `uv` in the container image).

### `podman`

Ensure that host has [`podman`](https://podman.io/docs/installation) installed.

### `sandbox`

We are using [`conty`](https://github.com/Kron4ek/Conty) for sandboxing. Ensure that the host has `conty.sh` (regular version) installed. The latest tested version is `1.26.2`.

> [!IMPORTANT]
When using `sandbox` executor, the environment variable `CONTY_PATH` should be set to the path of `conty.sh` on the host system.

### `unsafe`

As the name suggests, this executor does not provide any sandboxing or host isolation. It runs programs directly on the host system. This executor is not recommended for untrusted code.