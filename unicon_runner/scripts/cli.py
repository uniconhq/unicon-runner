"""CLI script to run a programming task without rabbitmq"""

import os
from unicon_runner.runner.runner import Runner
from unicon_runner.runner.task.programming import ProgrammingTask
from pprint import pprint
import asyncio

with open("unicon_runner/scripts/test.json") as f:
    EXAMPLE = f.read()
# noqa: F821
executor = Runner(os.getenv("RUNNER_TYPE"))  # noqa: F821


async def run_programming_task():
    task = EXAMPLE
    result = await executor.run_programming_task(
        programming_task=ProgrammingTask.model_validate_json(task)
    )
    message = result.model_dump()
    pprint(message)


if __name__ == "__main__":
    asyncio.run(run_programming_task())
