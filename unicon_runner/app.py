from enum import Enum
from typing import Any
from fastapi import FastAPI
from pydantic import BaseModel, model_validator


class File(BaseModel):
    file_name: str
    content: str


class ProgrammingLanguage(str, Enum):
    PYTHON = "PYTHON"


class ProgrammingEnvironment(BaseModel):
    language: ProgrammingLanguage
    options: dict[str, str] | None
    time_limit: int  # in seconds
    memory_limit: int  # in MB


class Request(BaseModel):
    files: list[File]
    environment: ProgrammingEnvironment
    entrypoint: str

    @model_validator(mode="after")
    def check_entrypoint_in_files(self):
        if (self.entrypoint not in [file.file_name for file in self.files]):
            raise ValueError("entrypoint not in files")


app = FastAPI()


@app.post("/submissions")
def run_submission(request: Request):
    return "success"
