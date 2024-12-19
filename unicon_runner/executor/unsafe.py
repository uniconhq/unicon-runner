from pathlib import Path

from jinja2 import Template

from unicon_runner.constants import DEFAULT_EXEC_PY_VERSION
from unicon_runner.executor.base import JINJA_ENV, Executor, FileSystemMapping
from unicon_runner.models import ComputeContext, Program


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

        python_version: str = DEFAULT_EXEC_PY_VERSION
        if context.slurm:
            # NOTE: We need to use the system python interpreter for slurm jobs
            # This is because of filesystem restrictions in the slurm environment (more details in the docs)
            python_version = "/usr/bin/python"
        elif context.extra_options:
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

    def _cmd(self, cwd: Path) -> tuple[list[str], dict[str, str]]:
        # NOTE: We need to unset VIRTUAL_ENV to prevent uv from using the wrong base python interpreter
        return [str(cwd / self.ENTRYPOINT)], {"VIRTUAL_ENV": "''"}
