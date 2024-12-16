from enum import Enum
from typing import Self

from pathvalidate import is_valid_filename
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class Language(str, Enum):
    PYTHON = "PYTHON"


class File(BaseModel):
    file_name: str
    content: str

    @field_validator("file_name", mode="before")
    @classmethod
    def check_filename_is_safe(cls, v):
        if not is_valid_filename(v):
            raise ValueError(f"{v} is an invalid file name")
        return v


class ComputeContext(BaseModel):
    language: Language
    time_limit_ms: int
    memory_limit_mb: int

    extra_options: dict[str, str] | None


class Program(BaseModel):
    model_config = ConfigDict(extra="allow")

    entrypoint: str
    files: list[File]

    @model_validator(mode="after")
    def check_entrypoint_exists_in_files(self) -> Self:
        if not any(file.file_name == self.entrypoint for file in self.files):
            raise ValueError(f"Entrypoint {self.entrypoint} not found in Program files")
        return self


class Job(BaseModel):
    # NOTE: This is needed to allow extra fields in a `Job` (also applied at the `Program` level)
    # These extra fields are essential in helping retain "tracking fields" sent from the task scheduler (backend)
    # Tracking fields are used for reconciliation purposes by the task scheduler
    # The runner should not be concerned with these fields but should pass them along
    model_config = ConfigDict(extra="allow")

    context: ComputeContext
    programs: list[Program]


class JobResult[ProgramResult](BaseModel):
    model_config = ConfigDict(extra="allow")  # For passthrough of tracking fields

    success: bool
    error: str | None
    results: list[ProgramResult]
