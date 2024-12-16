import asyncio
from pathlib import Path

from unicon_runner.executor.base import Executor, ExecutorResult, FileSystemMapping, Status
from unicon_runner.job import ComputeContext, Program


class PodmanExecutor(Executor):
    """Uses podman + Dockerfile in template to execute code"""

    def get_filesystem_mapping(self, program: Program, _: ComputeContext) -> FileSystemMapping:
        return [(Path(file.name), file.content) for file in program.files]

    async def _execute(self, id: str, program: Program, cwd: Path, context: ComputeContext):
        _IMAGE: str = "python:3.11.9"  # TEMP: Hardcoded base image

        proc = await asyncio.create_subprocess_shell(
            f"podman run --rm --name {id}_run "
            f"-m {context.memory_limit_mb}m "
            f"-v ./{cwd}:/run {_IMAGE} "
            f"timeout --verbose {context.time_limit_ms}s python run/{program.entrypoint}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # 3. Output raw result
        stdout, stderr = await proc.communicate()

        match proc.returncode:
            case 137:
                status = Status.MLE
            case 124:
                status = Status.TLE
            case 1:
                status = Status.RTE
            case _:
                status = Status.OK

        return ExecutorResult.model_validate(
            {
                "status": status.value,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
            }
        )
