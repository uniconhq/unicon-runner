import asyncio
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel

from unicon_runner.executor.variants.base import Executor
from unicon_runner.schemas import (
    ProgrammingEnvironment,
    Request,
    TaskEvalResult,
    TaskEvalStatus,
)


class TaskType(str, Enum):
    PROGRAMMING = "PROGRAMMING_TASK"


class ProgrammingTask(BaseModel):
    submission_id: str
    environment: ProgrammingEnvironment
    programs: list[Request]

    async def run(self, executor: Executor) -> TaskEvalResult[list[Any]]:
        results_with_index: dict[int, any] = {}
        async with asyncio.TaskGroup() as tg:
            for index, request in enumerate(self.request):
                tg.create_task(self.run(executor, request, index, results_with_index))

        results = [results_with_index[i] for i in range(len(results_with_index))]

        return TaskEvalResult(
            submission_id=self.submission_id,
            status=TaskEvalStatus.SUCCESS,
            result=results,
        )

    async def run_testcase(
        self,
        executor: Executor,
        request: Request,
        index: int,
        results: dict,
    ):
        results[index] = await executor.run_request(request, str(uuid()))
