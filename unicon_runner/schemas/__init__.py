from enum import Enum
from typing import Generic, TypeVar
from pathvalidate import is_valid_filename
from pydantic import BaseModel, field_validator, model_validator


class File(BaseModel):
    file_name: str
    content: str

    @field_validator("file_name", mode="before")
    @classmethod
    def check_filename_is_safe(cls, v):
        if not is_valid_filename(v):
            raise ValueError(f"{v} is an invalid file name")
        return v


class ProgrammingLanguage(str, Enum):
    PYTHON = "PYTHON"


class ProgrammingEnvironment(BaseModel):
    language: ProgrammingLanguage
    options: dict[str, str] | None
    time_limit: int  # in seconds
    memory_limit: int  # in MB


TaskUserInput = TypeVar("TaskUserInput")
TaskExpectedAnswer = TypeVar("TaskExpectedAnswer")
TaskResult = TypeVar("TaskResult")


class TaskEvalStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class TaskEvalResult(BaseModel, Generic[TaskResult]):
    status: TaskEvalStatus
    result: TaskResult | None
    error: str | None = None


class ProgrammingLanguage(str, Enum):
    PYTHON = "PYTHON"


class RunnerRequest(BaseModel):
    files: list[File]
    environment: ProgrammingEnvironment
    entrypoint: str

    @model_validator(mode="after")
    def check_entrypoint_in_files(self):
        if self.entrypoint not in [file.file_name for file in self.files]:
            raise ValueError("entrypoint not in files")
        return self


class Status(str, Enum):
    OK = "OK"
    MLE = "MLE"
    TLE = "TLE"
    RTE = "RTE"


class Request(BaseModel):
    files: list[File]
    environment: ProgrammingEnvironment
    entrypoint: str

    @model_validator(mode="after")
    def check_entrypoint_in_files(self):
        if self.entrypoint not in [file.file_name for file in self.files]:
            raise ValueError("entrypoint not in files")
        return self
