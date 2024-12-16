import asyncio
import os
import shlex
from pathlib import Path

from unicon_runner.constants import CONTY_PATH
from unicon_runner.executor.base import ExecutorResult
from unicon_runner.executor.unsafe.executor import UnsafeExecutor
from unicon_runner.job import ComputeContext, Program


class SandboxExecutor(UnsafeExecutor):
    on_slurm = True

    # Mounting sometimes fails if we try to spawn multiple sandboxes on xlog.
    lock = asyncio.Lock()

    async def _execute(
        self, _: str, program: Program, cwd: Path, context: ComputeContext
    ) -> ExecutorResult:
        mem_limit_bytes: int = context.memory_limit_mb * 1024
        time_limit_secs: int = context.time_limit_ms * 1000

        python_version: str = "3.11.9"
        if context.extra_options:
            python_version = context.extra_options.get("version", python_version)

        async with self.lock:
            exec_proc = await asyncio.create_subprocess_shell(
                shlex.join(
                    [
                        CONTY_PATH,
                        "--bind",
                        str(cwd.absolute()),
                        str(cwd),
                        "--ro-bind",
                        str(self.RUN_SCRIPT),
                        os.path.expanduser(f"~/{self.RUN_SCRIPT.name}"),
                        # NOTE: `uv` binary is assumed to be stored under `~/.cargo/bin/`
                        # We are using `uv` as the environment manager and program runner
                        "--ro-bind",
                        os.path.expanduser("~/.cargo/bin/uv"),
                        os.path.expanduser("~/.cargo/bin/uv"),
                        # NOTE: We need to bind the uv cache folder to access uv-managed python executables
                        "--ro-bind",
                        os.path.expanduser("~/.local/share/uv"),
                        os.path.expanduser("~/.local/share/uv"),
                        f"./{self.RUN_SCRIPT.name}",
                        str(cwd),
                        python_version,
                        str(mem_limit_bytes),
                        str(time_limit_secs),
                        str(cwd / "src" / program.entrypoint),
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

        with open(cwd / "exit_code") as f:
            exit_code = int(f.read())

        return ExecutorResult(exit_code=exit_code, stdout=stdout.decode(), stderr=stderr.decode())
