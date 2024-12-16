import shutil
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from unicon_runner.job import ComputeContext, Program


class Status(str, Enum):
    OK = "OK"
    MLE = "MLE"
    TLE = "TLE"
    RTE = "RTE"
    WA = "WA"


class ExecutorType(str, Enum):
    PODMAN = "podman"
    UNSAFE = "unsafe"
    SANDBOX = "sandbox"


class ExecutorResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    stdout: str | None
    stderr: str | None
    status: Status | None


class ExecutorCwd:
    def __init__(self, root_dir: Path, id: str):
        self._cwd = root_dir / id
        self._cwd.mkdir()

    def __enter__(self):
        return self._cwd

    def __exit__(self, type, value, traceback):
        shutil.rmtree(self._cwd)
        self._cwd.rmdir()


FileSystemMapping = list[tuple[Path, str]]


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

    async def run(self, program: Program, context: ComputeContext) -> ExecutorResult:
        _tracking_fields = program.model_extra or {}
        id: str = str(uuid.uuid4())  # Unique identifier for the program
        with ExecutorCwd(self.root_dir, id) as cwd:
            for path, content in self.get_filesystem_mapping(program, context):
                (cwd / path).write_text(content)
            result = await self._execute(id, program, cwd, context)

        return ExecutorResult.model_validate({**_tracking_fields, **result.model_dump()})
