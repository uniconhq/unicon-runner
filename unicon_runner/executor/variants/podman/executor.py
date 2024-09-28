from unicon_runner.executor.variants.base import Executor, Result
from unicon_runner.schemas import Request
import asyncio
import os
from unicon_runner.schemas import Status

from jinja2 import Environment, FileSystemLoader, select_autoescape


class PodmanExecutor(Executor):
    """Uses podman + Dockerfile in template to execute code"""

    env = Environment(
        loader=FileSystemLoader("unicon_runner/executor/variants/podman/templates"),
        autoescape=select_autoescape(),
    )
    dockerfile_template = env.get_template("Dockerfile.jinja")

    async def _execute(
        self, request: Request, request_id: str, folder_path: str
    ) -> Result:
        folder_name = request_id

        # 1. Create files
        for file in request.files:
            with open(os.path.join(folder_path, file.file_name), "w") as f:
                f.write(file.content)

        with open(os.path.join(folder_path, "Dockerfile"), "w") as f:
            dockerfile = self.dockerfile_template.render(
                entrypoint=request.entrypoint, time_limit=request.environment.time_limit
            )
            f.write(dockerfile)

        # 2. Spawn podman container
        proc = await asyncio.create_subprocess_shell(
            f"podman build {folder_path} -t {folder_name}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await proc.wait()

        proc = await asyncio.create_subprocess_shell(
            f"podman run --name {folder_name}_run -m {request.environment.memory_limit}m {folder_name}",
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

        return Result.model_validate(
            {
                "status": status.value,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
            }
        )
