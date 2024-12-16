import asyncio
import os
import shlex
from pathlib import Path

from jinja2 import Environment, PackageLoader, Template, select_autoescape

from unicon_runner.constants import CONTY_PATH
from unicon_runner.executor.base import ExecutorResult
from unicon_runner.executor.unsafe import UnsafeExecutor
from unicon_runner.job import ComputeContext, Program

JINJA_ENV = Environment(
    loader=PackageLoader("unicon_runner.executor"), autoescape=select_autoescape()
)


class SandboxExecutor(UnsafeExecutor):
    on_slurm = True

    # Mounting sometimes fails if we try to spawn multiple sandboxes on xlog.
    lock = asyncio.Lock()

    RUN_SCRIPT_TEMPLATE: Template = JINJA_ENV.get_template("run_sandbox.sh.jinja")

    async def _execute(self, _: str, __: Program, cwd: Path, ___: ComputeContext) -> ExecutorResult:
        async with self.lock:
            exec_proc = await asyncio.create_subprocess_shell(
                shlex.join(
                    [
                        CONTY_PATH,
                        "--bind",
                        str(cwd.absolute()),
                        str(cwd),
                        "--ro-bind",
                        str(cwd / "run.sh"),
                        os.path.expanduser("~/run.sh"),
                        # NOTE: `uv` binary is assumed to be stored under `~/.cargo/bin/`
                        # We are using `uv` as the environment manager and program runner
                        "--ro-bind",
                        os.path.expanduser("~/.cargo/bin/uv"),
                        os.path.expanduser("~/.cargo/bin/uv"),
                        # NOTE: We need to bind the uv cache folder to access uv-managed python executables
                        "--ro-bind",
                        os.path.expanduser("~/.local/share/uv"),
                        os.path.expanduser("~/.local/share/uv"),
                        str(self.ENTRYPOINT),
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
