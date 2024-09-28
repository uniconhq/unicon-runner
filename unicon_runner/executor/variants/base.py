from abc import ABC, abstractmethod

from pydantic import BaseModel

from unicon_runner.schemas import Request, Status


class Result(BaseModel):
    stdout: str
    stderr: str
    status: Status


class Executor(ABC):
    @abstractmethod
    async def run_request(self, request: Request, request_id: str) -> Result:
        raise NotImplementedError
