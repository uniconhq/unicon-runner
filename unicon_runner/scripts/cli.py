"""CLI script to run a programming task without rabbitmq"""

from unicon_runner.app import executor
from unicon_runner.runner.task.programming import ProgrammingTask
from pprint import pprint
import asyncio

with open("unicon_runner/scripts/test.json") as f:
    EXAMPLE = f.read()


async def run_programming_task():
    task = EXAMPLE
    result = await executor.run_programming_task(
        programming_task=ProgrammingTask.model_validate_json(task)
    )
    message = result.model_dump()
    pprint(message)


if __name__ == "__main__":
    asyncio.run(run_programming_task())
