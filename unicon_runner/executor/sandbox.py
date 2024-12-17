import asyncio
import os
import shlex
from pathlib import Path

from jinja2 import Environment, PackageLoader, Template, select_autoescape

from unicon_runner.constants import CONTY_PATH
from unicon_runner.executor.base import ExecutorResult
from unicon_runner.executor.unsafe import UnsafeExecutor
from unicon_runner.models import ComputeContext, Program

JINJA_ENV = Environment(
    loader=PackageLoader("unicon_runner.executor"), autoescape=select_autoescape()
)


class SandboxExecutor(UnsafeExecutor):
    on_slurm = True

    # Mounting sometimes fails if we try to spawn multiple sandboxes on xlog.
    lock = asyncio.Lock()

    RUN_SCRIPT_TEMPLATE: Template = JINJA_ENV.get_template("run_sandbox.sh.jinja")

    async def _execute(self, _: str, __: Program, cwd: Path, ___: ComputeContext) -> ExecutorResult:
        if not Path(CONTY_PATH).exists():
            raise RuntimeError(f"Conty binary not found at {CONTY_PATH}!")

        # NOTE: `uv` binary is assumed to be stored under `~/.cargo/bin/`
        # We are using `uv` as the environment manager and program runner
        uv_path = Path("~/.cargo/bin/uv").expanduser()
        # NOTE: We need to bind the uv cache folder to access uv-managed python executables
        uv_cache_path = Path("~/.local/share/uv").expanduser()

        async with self.lock:
            exec_proc = await asyncio.create_subprocess_shell(
                shlex.join(
                    [
                        CONTY_PATH,
                        "--bind",
                        str(cwd.absolute()),
                        str(cwd),
                        "--ro-bind",
                        *([str(uv_path)] * 2),
                        "--ro-bind",
                        *([str(uv_cache_path)] * 2),
                        str(cwd / self.ENTRYPOINT),
                    ]
                ),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    **os.environ,
                    # Conty specific environment variables
                    "SANDBOX": "1",
                    "SANDBOX_LEVEL": "1",
                    "QUIET_MODE": "1",
                    # NOTE: We need to unset VIRTUAL_ENV to prevent uv from using it
                    "VIRTUAL_ENV": "",
                },
            )

            stdout, stderr = await exec_proc.communicate()

        exit_code_file = cwd / "exit_code"
        if not exit_code_file.exists():
            exit_code = 1
        else:
            with open(exit_code_file) as f:
                exit_code = int(f.read())

        return ExecutorResult(exit_code=exit_code, stdout=stdout.decode(), stderr=stderr.decode())
