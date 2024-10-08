"""CLI script to run a programming task without rabbitmq"""

import asyncio
from pprint import pprint

from unicon_runner.lib.constants import RUNNER_TYPE
from unicon_runner.runner.runner import Runner, RunnerType
from unicon_runner.runner.task.programming import ProgrammingTask

with open("unicon_runner/scripts/test.json") as f:
    EXAMPLE = f.read()

executor = Runner(RunnerType(RUNNER_TYPE))


async def run_programming_task():
    task = EXAMPLE
    result = await executor.run_programming_task(
        programming_task=ProgrammingTask.model_validate_json(task)
    )
    message = result.model_dump()
    pprint(message)


if __name__ == "__main__":
    asyncio.run(run_programming_task())
