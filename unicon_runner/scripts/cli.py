"""CLI script to run a programming task without rabbitmq"""

import asyncio
import json

from unicon_runner.constants import RUNNER_TYPE
from unicon_runner.runner.runner import Runner, RunnerType
from unicon_runner.runner.task.programming import ProgrammingTask

with open("unicon_runner/scripts/test_loop.json") as f:
    EXAMPLE = f.read()

executor = Runner(RunnerType(RUNNER_TYPE))


async def run_programming_task():
    task = EXAMPLE
    result = await executor.run_programming_task(
        programming_task=ProgrammingTask.model_validate_json(task)
    )
    message = result.model_dump()
    print(json.dumps(message))


if __name__ == "__main__":
    asyncio.run(run_programming_task())
