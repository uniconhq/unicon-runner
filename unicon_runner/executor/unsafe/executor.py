import asyncio
import os
import shlex
from importlib import resources
from pathlib import Path

from jinja2 import Environment, PackageLoader, Template, select_autoescape

from unicon_runner.executor.base import Executor, ExecutorResult, FileSystemMapping, Status
from unicon_runner.executor.unsafe import scripts
from unicon_runner.job import ComputeContext, Program

UNSAFE_SCRIPTS = resources.files(scripts)


class UnsafeExecutor(Executor):
    """Uses uv to execute code"""

    PYPROJECT_TEMPLATE: Template = Environment(
        loader=PackageLoader("unicon_runner.executor.unsafe"), autoescape=select_autoescape()
    ).get_template("pyproject.toml.jinja")

    PACKAGE_DIR = Path("src")
    RUN_SCRIPT = UNSAFE_SCRIPTS / "run.sh"

    def get_filesystem_mapping(
        self, program: Program, context: ComputeContext
    ) -> FileSystemMapping:
        requirements: str = (
            context.extra_options.get("requirements", "") if context.extra_options else ""
        )
        return [
            *[(self.PACKAGE_DIR / file.name, file.content) for file in program.files],
            (Path("pyproject.toml"), self.PYPROJECT_TEMPLATE.render()),
            (Path("__init__.py"), ""),
            (Path("requirements.txt"), requirements),
        ]

    async def _execute(self, _: str, program: Program, cwd: Path, context: ComputeContext):
        mem_limit_bytes: int = context.memory_limit_mb * 1024
        time_limit_secs: int = context.time_limit_ms * 1000

        python_version: str = "3.11.9"
        if context.extra_options:
            python_version = context.extra_options.get("version", python_version)

        # 2. Cd into temp folder and run uv sync && uv run entry
        exec_proc = await asyncio.create_subprocess_shell(
            shlex.join(
                [
                    str(self.RUN_SCRIPT),
                    str(cwd),
                    str(self.PACKAGE_DIR / program.entrypoint),
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
