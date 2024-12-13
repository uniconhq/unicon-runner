"""CLI script to run a programming task without rabbitmq"""

import asyncio
from pprint import pprint

from unicon_runner.constants import RUNNER_TYPE
from unicon_runner.runner.base import Runner, RunnerType
from unicon_runner.schemas import Request

with open("unicon_runner/scripts/test2.json") as f:
    EXAMPLE = f.read()

executor = Runner(RunnerType(RUNNER_TYPE))


async def run_programming_task():
    task = EXAMPLE
    result = await executor.run_request(Request.model_validate_json(task), "test")
    message = result.model_dump()
    pprint(message)


if __name__ == "__main__":
    asyncio.run(run_programming_task())
