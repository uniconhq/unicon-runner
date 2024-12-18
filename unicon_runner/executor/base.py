import shutil
import stat
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

from unicon_runner.models import ComputeContext, ExecutorResult, Program, ProgramResult, Status


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
    on_slurm = False

    @property
    def root_dir(self) -> Path:
        return Path("/tmp" if self.on_slurm else "temp")

    @abstractmethod
    def get_filesystem_mapping(
        self, program: Program, context: ComputeContext
    ) -> FileSystemMapping:
        """
        Mapping of files (path, content) to be written to the working directory of the executor
        """
        raise NotImplementedError

    @abstractmethod
    async def _execute(
        self, id: str, program: Program, cwd: Path, context: ComputeContext
    ) -> ExecutorResult:
        raise NotImplementedError

    async def run(self, program: Program, context: ComputeContext) -> ProgramResult:
        _tracking_fields = program.model_extra or {}
        id: str = str(uuid.uuid4())  # Unique identifier for the program
        with ExecutorCwd(self.root_dir, id) as cwd:
            for path, content, is_exec in self.get_filesystem_mapping(program, context):
                file_path = cwd / path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)
                if is_exec:
                    file_path.chmod(file_path.stat().st_mode | stat.S_IEXEC)

            result = await self._execute(id, program, cwd, context)

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
