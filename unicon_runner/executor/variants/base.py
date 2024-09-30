import os
import shutil
import time
from abc import ABC, abstractmethod

from pydantic import BaseModel

from unicon_runner.schemas import Request, Status


class Result(BaseModel):
    stdout: str
    stderr: str
    status: Status


class Executor(ABC):
    async def run_request(self, request: Request, request_id: str) -> Result:
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
        folder_path = os.path.join("temp", folder_name)
        os.mkdir(folder_path)

        return folder_path

    def clean_up_folder(self, folder_path: str):
        """Cleans up the temporary folder"""
        time.sleep(5)
        shutil.rmtree(folder_path)

    @abstractmethod
    async def _execute(self, request: Request, request_id: str, folder_path: str):
        raise NotImplementedError
