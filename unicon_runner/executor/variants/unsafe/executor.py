import asyncio
import os
import shlex

from jinja2 import Environment, FileSystemLoader, select_autoescape

from unicon_runner.executor.variants.base import Executor, ExecutorResult
from unicon_runner.schemas import Request, Status


class UnsafeExecutor(Executor):
    """Uses uv to execute code"""

    env = Environment(
        loader=FileSystemLoader("unicon_runner/executor/variants/unsafe/templates"),
        autoescape=select_autoescape(),
    )
    pyproject_template = env.get_template("pyproject.toml.jinja")
    CODE_FOLDER_NAME = "src"
    RUN_SCRIPT = "unicon_runner/executor/variants/unsafe/scripts/run.sh"

    async def _execute(self, request: Request, request_id: str, folder_path: str) -> ExecutorResult:
        # 1. Copy the uv files
        code_folder_path = os.path.join(folder_path, self.CODE_FOLDER_NAME)
        print(code_folder_path)
        os.mkdir(code_folder_path)

        for file in request.files:
            with open(os.path.join(code_folder_path, file.file_name), "w") as f:
                f.write(file.content)

        with open(os.path.join(folder_path, "pyproject.toml"), "w") as f:
            pyproject_file = self.pyproject_template.render()
            f.write(pyproject_file)

        with open(os.path.join(code_folder_path, "__init__.py"), "w") as f:
            f.write("")

        with open(os.path.join(folder_path, "requirements.txt"), "w") as f:
            if (
                request.environment.extra_options
                and "requirements" in request.environment.extra_options
            ):
                f.write(request.environment.extra_options["requirements"])

        mem_limit_mb: int = request.environment.memory_limit * 1024
        time_limit_secs: int = request.environment.time_limit

        python_version: str = "3.11.9"
        if request.environment.extra_options:
            python_version = request.environment.extra_options.get("python_version", python_version)

        # 2. Cd into temp folder and run uv sync && uv run entry
        exec_proc = await asyncio.create_subprocess_shell(
            shlex.join(
                [
                    self.RUN_SCRIPT,
                    folder_path,
                    f"{self.CODE_FOLDER_NAME}/{request.entrypoint}",
                    python_version,
                    str(mem_limit_mb),
                    str(time_limit_secs),
                ]
            ),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # NOTE: We need to unset VIRTUAL_ENV to prevent uv from using it
            env={**os.environ, "VIRTUAL_ENV": ""},
        )

        stdout, stderr = await exec_proc.communicate()

        match exec_proc.returncode:
            case 137:
                status = Status.MLE
            case 124:
                status = Status.TLE
            case 1:
                status = Status.RTE
            case _:
                status = Status.OK

        # 3. Return result
        return ExecutorResult.model_validate(
            {
                "status": status.value,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
            }
        )
