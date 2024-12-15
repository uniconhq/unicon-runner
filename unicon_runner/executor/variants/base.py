import os
import shutil
from abc import ABC, abstractmethod

from pydantic import BaseModel

from unicon_runner.schemas import Request, Status


class ExecutorResult(BaseModel):
    stdout: str
    stderr: str
    status: Status


class ExecutorResultWithId(ExecutorResult):
    id: int


class Executor(ABC):
    on_slurm = False

    async def run_request(self, request: Request, request_id: str) -> ExecutorResult:
        folder_path = self.set_up_request(request_id)
        result = await self._execute(
            request,
            request_id,
            folder_path,
        )
        self.clean_up_folder(folder_path)
        return result

    def set_up_request(self, request_id: str) -> str:
        """
        All executors will be given a temporary folder named after the request id to work with.
        Returns path to this temporary folder.
        """
        folder_name = request_id
        folder_path = os.path.join("/tmp" if self.on_slurm else "temp", folder_name)
        os.makedirs(folder_path)

        return folder_path

    def clean_up_folder(self, folder_path: str):
        """Cleans up the temporary folder"""
        shutil.rmtree(folder_path)

    @abstractmethod
    async def _execute(self, request: Request, request_id: str, folder_path: str):
        raise NotImplementedError
