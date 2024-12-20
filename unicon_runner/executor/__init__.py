from pathlib import Path

from unicon_runner.executor.base import ExecutorType
from unicon_runner.executor.podman import PodmanExecutor
from unicon_runner.executor.sandbox import SandboxExecutor
from unicon_runner.executor.unsafe import UnsafeExecutor


def create_executor(executor_type: ExecutorType, root_wd_dir: Path):
    match executor_type:
        case ExecutorType.PODMAN:
            return PodmanExecutor(root_wd_dir)
        case ExecutorType.SANDBOX:
            return SandboxExecutor(root_wd_dir)
        case ExecutorType.UNSAFE:
            return UnsafeExecutor(root_wd_dir)


__all__ = ["PodmanExecutor", "SandboxExecutor", "UnsafeExecutor"]
