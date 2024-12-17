from unicon_runner.executor.base import ExecutorType
from unicon_runner.executor.podman import PodmanExecutor
from unicon_runner.executor.sandbox import SandboxExecutor
from unicon_runner.executor.unsafe import UnsafeExecutor


def create_executor(executor_type: ExecutorType):
    match executor_type:
        case ExecutorType.PODMAN:
            return PodmanExecutor()
        case ExecutorType.SANDBOX:
            return SandboxExecutor()
        case ExecutorType.UNSAFE:
            return UnsafeExecutor()


__all__ = ["PodmanExecutor", "SandboxExecutor", "UnsafeExecutor"]
