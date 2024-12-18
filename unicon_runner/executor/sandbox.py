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

    def _cmd(self, cwd: Path) -> tuple[list[str], dict[str, str]]:
        # if not Path(CONTY_PATH).exists():
        #     raise RuntimeError(f"Conty binary not found at {CONTY_PATH}!")

        # NOTE: `uv` binary is assumed to be stored under `~/.cargo/bin/`
        # We are using `uv` as the environment manager and program runner
        uv_path = Path("~/.cargo/bin/uv").expanduser()
        # NOTE: We need to bind the uv cache folder to access uv-managed python executables
        uv_cache_path = Path("~/.local/share/uv").expanduser()

        return [
            CONTY_PATH,
            "--bind",
            str(cwd.absolute()),
            str(cwd),
            "--ro-bind",
            *([str(uv_path)] * 2),
            "--ro-bind",
            *([str(uv_cache_path)] * 2),
            str(cwd / self.ENTRYPOINT),
        ], {
            # Conty specific environment variables
            "SANDBOX": "1",
            "SANDBOX_LEVEL": "1",
            "QUIET_MODE": "1",
            # NOTE: We need to unset VIRTUAL_ENV to prevent uv from using the wrong base python interpreter
            "VIRTUAL_ENV": "''",
        }

    async def _collect(self, proc: asyncio.subprocess.Process) -> ExecutorResult:
        stdout, stderr = await proc.communicate()

        exit_code_file = self._root_dir / "exit_code"
        if not exit_code_file.exists():
            exit_code = 1
        else:
            with open(exit_code_file) as f:
                exit_code = int(f.read())

        return ExecutorResult(exit_code=exit_code, stdout=stdout.decode(), stderr=stderr.decode())
