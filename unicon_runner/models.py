from enum import Enum
from typing import Self

from pathvalidate import is_valid_filename
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class File(BaseModel):
    name: str
    content: str

    @field_validator("name", mode="before")
    @classmethod
    def check_filename_is_safe(cls, v):
        if not is_valid_filename(v):
            raise ValueError(f"{v} is an invalid file name")
        return v


class Language(str, Enum):
    PYTHON = "PYTHON"


class ExtraOptions(BaseModel):
    version: str | None = None
    requirements: list[str] = []


class ComputeContext(BaseModel):
    language: Language
    time_limit_secs: float
    memory_limit_mb: int

    slurm: bool = False
    # Additional options for `srun`
    # e.g. [--gpus", "1", "--cpus-per-task", "2"]
    slurm_options: list[str] = []
    # Use python interpreter present in the allocated slurm node
    # If true, ignores python version specified under `extra_options` and default fallback python version
    slurm_use_system_py: bool = False

    extra_options: ExtraOptions | None = None


class Program(BaseModel):
    model_config = ConfigDict(extra="allow")

    entrypoint: str
    files: list[File]

    @model_validator(mode="after")
    def check_entrypoint_exists_in_files(self) -> Self:
        if not any(file.name == self.entrypoint for file in self.files):
            raise ValueError(f"Entrypoint {self.entrypoint} not found in Program files")
        return self


class Status(str, Enum):
    OK = "OK"
    MLE = "MLE"
    TLE = "TLE"
    RTE = "RTE"
    WA = "WA"


class ProgramResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    stdout: str | None
    stderr: str | None
    status: Status | None

    elapsed_time_ns: int | None = None


class ExecutorPerf(BaseModel):
    create_venv_ns: int
    install_deps_ns: int
    program_ns: int


class ExecutorResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str

    perf: ExecutorPerf | None = None


class Job(BaseModel):
    # NOTE: This is needed to allow extra fields in a `Job` (also applied at the `Program` level)
    # These extra fields are essential in helping retain "tracking fields" sent from the task scheduler (backend)
    # Tracking fields are used for reconciliation purposes by the task scheduler
    # The runner should not be concerned with these fields but should pass them along
    model_config = ConfigDict(extra="allow")

    context: ComputeContext
    programs: list[Program]


class JobResult(BaseModel):
    model_config = ConfigDict(extra="allow")  # For passthrough of tracking fields

    success: bool
    error: str | None
    results: list[ProgramResult]
