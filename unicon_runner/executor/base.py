import asyncio
import logging
import os
import shlex
import shutil
import stat
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from unicon_runner.models import ComputeContext, ExecutorResult, Program, ProgramResult, Status

logger = logging.getLogger("unicon_runner")

JINJA_ENV = Environment(
    loader=PackageLoader("unicon_runner.executor"), autoescape=select_autoescape()
)


class ExecutorCwd:
    def __init__(self, root_dir: Path, id: str):
        self._cwd = root_dir / id
        self._cwd.mkdir(parents=True)

    def __enter__(self):
        return self._cwd

    def __exit__(self, type, value, traceback):
        if (type, value, traceback) == (None, None, None):
            # Only clean up if there was no exception when exiting the context
            # Else we propagate the exception
            shutil.rmtree(self._cwd)


# list[(<file_path>, <file_content>, <is_executable>)]
FileSystemMapping = list[tuple[Path, str, bool]]


class ExecutorType(str, Enum):
    PODMAN = "podman"
    UNSAFE = "unsafe"
    SANDBOX = "sandbox"


class Executor(ABC):
    def __init__(self, root_dir: Path):
        self._root_dir = root_dir

    @abstractmethod
    def get_filesystem_mapping(
        self, program: Program, context: ComputeContext
    ) -> FileSystemMapping:
        """
        Mapping of files (path, content) to be written to the working directory of the executor
        """
        raise NotImplementedError

    @abstractmethod
    def _cmd(self, cwd: Path) -> tuple[list[str], dict[str, str]]:
        raise NotImplementedError

    async def _collect(self, proc: asyncio.subprocess.Process) -> ExecutorResult:
        stdout, stderr = await proc.communicate()
        exit_code = proc.returncode if proc.returncode is not None else 1
        return ExecutorResult(exit_code=exit_code, stdout=stdout.decode(), stderr=stderr.decode())

    async def run(self, program: Program, context: ComputeContext) -> ProgramResult:
        _tracking_fields = program.model_extra or {}
        id: str = str(uuid.uuid4())  # Unique identifier for the program
        with ExecutorCwd(self._root_dir, id) as cwd:
            for path, content, is_exec in self.get_filesystem_mapping(program, context):
                logger.info(f"Writing file: [magenta]{path}[/]")
                file_path = cwd / path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)
                if is_exec:
                    file_path.chmod(file_path.stat().st_mode | stat.S_IEXEC)

            cmd: list[str]
            env_vars: dict[str, str]

            if context.slurm:
                # NOTE: For `slurm` execution, the working directory needs to be in NFS
                # There will be 2 working directories:
                # 1. NFS working directory (where the setup is done)
                # 2. Slurm working directory (where the program is executed)
                #   - This is hardcoded to `/tmp` for now
                #   - A possible improvement is to introduce staging and execution directories
                exec_dir = Path("/tmp") / id
                prog_cmd, prog_env_vars = self._cmd(exec_dir)

                # Assemble the script that copies files from NFS to Slurm working directory
                slurm_script = JINJA_ENV.get_template("slurm.sh.jinja").render(
                    staging_dir=str(cwd),
                    exec_dir=str(exec_dir),
                    exec_export_env_vars="\n".join(
                        [f"export {key}={value}" for key, value in prog_env_vars.items()]
                    ),
                    run_script=shlex.join(prog_cmd),
                )
                slurm_script_path = cwd / "slurm.sh"
                slurm_script_path.write_text(slurm_script)
                slurm_script_path.chmod(slurm_script_path.stat().st_mode | stat.S_IEXEC)

                cmd = ["srun", *context.slurm_options, str(slurm_script_path)]
                env_vars = {}
            else:
                cmd, env_vars = self._cmd(cwd)

            logger.info(f"Process command: {cmd}")
            logger.info(f"Env vars: {env_vars}")

            result = await self._collect(
                await asyncio.create_subprocess_shell(
                    shlex.join(cmd),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={**os.environ, **env_vars},
                )
            )

        match result.exit_code:
            case 137:
                status = Status.MLE
            case 124:
                status = Status.TLE
            case 1:
                status = Status.RTE
            case _:
                status = Status.OK

        return ProgramResult.model_validate(
            {
                **_tracking_fields,
                "status": status.value,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
