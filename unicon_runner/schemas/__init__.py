from enum import Enum
from pydantic import BaseModel, field_validator, model_validator
from pathvalidate import is_valid_filename, sanitize_filepath


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
        if (self.entrypoint not in [file.file_name for file in self.files]):
            raise ValueError("entrypoint not in files")
        return self
