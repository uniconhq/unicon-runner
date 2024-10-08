import asyncio
import os

from unicon_runner.executor.variants.base import Executor, ExecutorResult
from unicon_runner.schemas import Request, Status


class PodmanExecutor(Executor):
    """Uses podman + Dockerfile in template to execute code"""

    async def _execute(self, request: Request, request_id: str, folder_path: str) -> ExecutorResult:
        folder_name = request_id

        # 1. Create files
        for file in request.files:
            with open(os.path.join(folder_path, file.file_name), "w") as f:
                f.write(file.content)

        # 2. Spawn podman container

        _IMAGE: str = "python:3.11.9"  # TEMP: Hardcoded base image

        proc = await asyncio.create_subprocess_shell(
            f"podman run --rm --name {folder_name}_run "
            f"-m {request.environment.memory_limit}m "
            f"-v ./{folder_path}:/run {_IMAGE} "
            f"timeout --verbose {request.environment.time_limit}s python run/{request.entrypoint}",
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
