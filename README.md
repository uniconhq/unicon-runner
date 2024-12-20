# Unicon 🦄 Runner

Starting a long-running process that listens to the task queue:

```bash
uv run unicon_runner/app.py \
    start [unsafe | sandbox | podman] <root-working-dir>
```
> [!NOTE]
`RABBITMQ_URL` needs to be set either in the `.env` file or as an environment variable.

> `<root-working-dir>` is the root directory where working directories for each program execution will be created. This directory should be writable by the user running the runner.

Test the runner with a sample program:

```bash
uv run unicon_runner/app.py \
    test [unsafe | sandbox | podman] <root-working-dir> \
    <job-json-file> \
    [--slurm] \
    [--slurm_opt <slurm-option>]

# Example of running a job with the sandbox executor that 
# requires runtime dependencies on a Slurm cluster and (also a GPU just for fun)
uv run unicon_runner/app.py \
    test sandbox ./temp \
    examples/runtime_deps.json \
    --slurm \
    --slurm_opt "--gpus=1"
```

> Example job files can be found in the `/examples` directory.

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