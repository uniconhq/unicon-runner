import asyncio
from pathlib import Path

from unicon_runner.executor.base import (
    Executor,
    ExecutorResult,
    FileSystemMapping,
)
from unicon_runner.job import ComputeContext, Program


class PodmanExecutor(Executor):
    """Uses podman + Dockerfile in template to execute code"""

    def get_filesystem_mapping(self, program: Program, _: ComputeContext) -> FileSystemMapping:
        return [(Path(file.name), file.content, False) for file in program.files]

    async def _execute(
        self, id: str, program: Program, cwd: Path, context: ComputeContext
    ) -> ExecutorResult:
        _IMAGE: str = "python:3.11.9"  # TEMP: Hardcoded base image

        proc = await asyncio.create_subprocess_shell(
            f"podman run --rm --name {id}_run "
            f"-m {context.memory_limit_mb}m "
            f"-v ./{cwd}:/run {_IMAGE} "
            f"timeout --verbose {context.time_limit_secs}s python run/{program.entrypoint}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()
        exit_code = proc.returncode if proc.returncode is not None else 1
        return ExecutorResult(exit_code=exit_code, stdout=stdout.decode(), stderr=stderr.decode())
