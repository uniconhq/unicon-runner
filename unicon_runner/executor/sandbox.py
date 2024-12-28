import asyncio
from pathlib import Path

from jinja2 import Template

from unicon_runner.constants import CONTY_PATH
from unicon_runner.executor.base import JINJA_ENV, ExecutorResult
from unicon_runner.executor.unsafe import UnsafeExecutor


class SandboxExecutor(UnsafeExecutor):
    on_slurm = True

    # Mounting sometimes fails if we try to spawn multiple sandboxes on xlog.
    lock = asyncio.Lock()

    RUN_SCRIPT_TEMPLATE: Template = JINJA_ENV.get_template("run_sandbox.sh.jinja")

    def __init__(self, root_dir: Path):
        if CONTY_PATH is None or not Path(CONTY_PATH).exists():
            raise RuntimeError(
                "Conty binary not found! Please verify the CONTY_PATH environment variable."
            )
        super().__init__(root_dir)

    def _cmd(self, cwd: Path) -> tuple[list[str], dict[str, str]]:
        assert CONTY_PATH is not None

        # NOTE: `uv` binary is assumed to be stored under `~/.cargo/bin/`
        # We are using `uv` as the environment manager and program runner
        uv_path = Path("~/.cargo/bin/uv").expanduser()
        # NOTE: We need to bind the uv cache folder to access uv-managed python executables
        uv_cache_path = Path("~/.local/share/uv").expanduser()

        # fmt: off
        return [
            CONTY_PATH,
            "--ro-bind", *(["/"] * 2),
            "--ro-bind", *([str(uv_path)] * 2),
            "--ro-bind", *([str(uv_cache_path)] * 2),
            # R/W bind to the root working directory
            "--bind", *([str(cwd.parents[0])] * 2),
            # NOTE: Mount `procfs` to allow access to process information
            # This seems be required for GPU workloads
            "--proc", "/proc",
            # Bind /dev to allow access to devices
            "--dev-bind", *(["/dev"] * 2),
            str(cwd / self.ENTRYPOINT),
        ], {
            # Conty specific environment variables
            "SANDBOX": "1", "SANDBOX_LEVEL": "1", "QUIET_MODE": "1",
            # NOTE: `conty` installs NVIDIA drivers in the sandbox, so we need to disable it
            "NVIDIA_HANDLER": "-1",
            # NOTE: We need to unset VIRTUAL_ENV to prevent uv from using the wrong base python interpreter
            "VIRTUAL_ENV": "''",
        }
        # fmt: off

    async def _collect(self, proc: asyncio.subprocess.Process) -> ExecutorResult:
        stdout, stderr = await proc.communicate()

        exit_code_file = self._root_dir / "exit_code"
        if not exit_code_file.exists():
            exit_code = 1
        else:
            with open(exit_code_file) as f:
                exit_code = int(f.read())

        return ExecutorResult(exit_code=exit_code, stdout=stdout.decode(), stderr=stderr.decode())
