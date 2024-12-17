import asyncio
import os
import shlex
from pathlib import Path

from jinja2 import Environment, PackageLoader, Template, select_autoescape

from unicon_runner.executor.base import Executor, ExecutorResult, FileSystemMapping
from unicon_runner.models import ComputeContext, Program

JINJA_ENV = Environment(
    loader=PackageLoader("unicon_runner.executor"), autoescape=select_autoescape()
)


class UnsafeExecutor(Executor):
    PYPROJECT_TEMPLATE: Template = JINJA_ENV.get_template("pyproject.toml.jinja")
    RUN_SCRIPT_TEMPLATE: Template = JINJA_ENV.get_template("run_unsafe.sh.jinja")

    ENTRYPOINT: Path = Path("run.sh")

    def get_filesystem_mapping(
        self, program: Program, context: ComputeContext
    ) -> FileSystemMapping:
        package_dir = Path("src")

        requirements: str = (
            context.extra_options.get("requirements", "") if context.extra_options else ""
        )

        mem_limit_kb: int = context.memory_limit_mb * 1024
        time_limit_secs: int = context.time_limit_secs * 1000

        python_version: str = "3.11.9"
        if context.extra_options:
            python_version = context.extra_options.get("version", python_version)

        run_script = self.RUN_SCRIPT_TEMPLATE.render(
            python_version=python_version,
            memory_limit_kb=mem_limit_kb,
            time_limit=time_limit_secs,
            entry_point=str(package_dir / program.entrypoint),
        )

        return [
            *[(package_dir / file.name, file.content, False) for file in program.files],
            (package_dir / "__init__.py", "", False),
            (Path("pyproject.toml"), self.PYPROJECT_TEMPLATE.render(), False),
            (Path("requirements.txt"), requirements, False),
            (self.ENTRYPOINT, run_script, True),
        ]

    async def _execute(self, _: str, __: Program, cwd: Path, ___: ComputeContext) -> ExecutorResult:
        proc = await asyncio.create_subprocess_shell(
            shlex.join([str(cwd / self.ENTRYPOINT)]),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # NOTE: We need to unset VIRTUAL_ENV to prevent uv from using it
            env={**os.environ, "VIRTUAL_ENV": ""},
        )

        stdout, stderr = await proc.communicate()
        exit_code = proc.returncode if proc.returncode is not None else 1
        return ExecutorResult(exit_code=exit_code, stdout=stdout.decode(), stderr=stderr.decode())
