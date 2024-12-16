from unicon_runner.executor.base import ExecutorType
from unicon_runner.executor.podman.executor import PodmanExecutor
from unicon_runner.executor.sandbox.executor import SandboxExecutor
from unicon_runner.executor.unsafe.executor import UnsafeExecutor


def create_executor(executor_type: ExecutorType):
    match executor_type:
        case ExecutorType.PODMAN:
            return PodmanExecutor()
        case ExecutorType.SANDBOX:
            return SandboxExecutor()
        case ExecutorType.UNSAFE:
            return UnsafeExecutor()


__all__ = ["PodmanExecutor", "SandboxExecutor", "UnsafeExecutor"]
