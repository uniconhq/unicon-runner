from collections.abc import Mapping
from enum import Enum

from unicon_runner.executor.variants.base import Executor, ExecutorResult
from unicon_runner.executor.variants.podman.executor import PodmanExecutor
from unicon_runner.executor.variants.sandbox.executor import SandboxExecutor
from unicon_runner.executor.variants.unsafe.executor import UnsafeExecutor
from unicon_runner.runner.task.programming import ProgrammingTask
from unicon_runner.schemas import Request


class RunnerType(str, Enum):
    PODMAN = "podman"
    UNSAFE = "unsafe"
    SANDBOX = "sandbox"


RUNNER_MAP: Mapping[RunnerType, type[Executor]] = {
    RunnerType.PODMAN: PodmanExecutor,
    RunnerType.UNSAFE: UnsafeExecutor,
    RunnerType.SANDBOX: SandboxExecutor,
}


class Runner:
    """
    The runner is the general interface used to execute code.
    It uses an executor, which is the method of running the code. (e.g. Podman, Unsafe)
    """

    executor: Executor

    def __init__(self, runner_type: RunnerType):
        self.executor = RUNNER_MAP[runner_type]()

    async def run_request(self, request: Request, request_id: str) -> ExecutorResult:
        return await self.executor.run_request(request, request_id)

    async def run_programming_task(self, programming_task: ProgrammingTask):
        return await programming_task.run(self.executor)
