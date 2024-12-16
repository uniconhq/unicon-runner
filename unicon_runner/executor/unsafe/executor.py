import asyncio
import os
import shlex
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from unicon_runner.executor.base import Executor, ExecutorResult, Status
from unicon_runner.job import ComputeContext, Program


class UnsafeExecutor(Executor):
    """Uses uv to execute code"""

    env = Environment(
        loader=FileSystemLoader("unicon_runner/executor/unsafe/templates"),
        autoescape=select_autoescape(),
    )
    pyproject_template = env.get_template("pyproject.toml.jinja")
    CODE_FOLDER_NAME = "src"
    RUN_SCRIPT = "unicon_runner/executor/unsafe/scripts/run.sh"

    async def _execute(self, id: str, program: Program, cwd: Path, context: ComputeContext):
        # 1. Copy the uv files
        code_dir = cwd / self.CODE_FOLDER_NAME
        code_dir.mkdir()

        for file in program.files:
            with open(code_dir / file.file_name, "w") as f:
                f.write(file.content)

        with open(cwd / "pyproject.toml" "w") as f:
            pyproject_file = self.pyproject_template.render()
            f.write(pyproject_file)

        with open(code_dir / "__init__.py", "w") as f:
            f.write("")

        with open(cwd / "requirements.txt" "w") as f:
            if context.extra_options and "requirements" in context.extra_options:
                f.write(context.extra_options["requirements"])

        mem_limit_bytes: int = context.memory_limit_mb * 1024
        time_limit_secs: int = context.time_limit_ms * 1000

        python_version: str = "3.11.9"
        if context.extra_options:
            python_version = context.extra_options.get("version", python_version)

        # 2. Cd into temp folder and run uv sync && uv run entry
        exec_proc = await asyncio.create_subprocess_shell(
            shlex.join(
                [
                    self.RUN_SCRIPT,
                    str(cwd),
                    str(code_dir / program.entrypoint),
                    python_version,
                    str(mem_limit_bytes),
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
