import asyncio
import os
import shutil

from jinja2 import Environment, FileSystemLoader, select_autoescape

from unicon_runner.executor.variants.base import Executor, ExecutorResult
from unicon_runner.schemas import Request, Status


class SandboxExecutor(Executor):
    """Uses conty"""

    env = Environment(
        loader=FileSystemLoader("unicon_runner/executor/variants/unsafe/templates"),
        autoescape=select_autoescape(),
    )
    pyproject_template = env.get_template("pyproject.toml.jinja")
    CODE_FOLDER_NAME = "src"
    INSTALL_SCRIPT = "unicon_runner/executor/variants/sandbox/scripts/install.sh"
    RUN_SCRIPT = "unicon_runner/executor/variants/sandbox/scripts/run.sh"
    CONTY = os.getenv("CONTY_PATH")

    def set_up_request(self, request_id: str) -> str:
        """
        All executors will be given a temporary folder named after the request id to work with.
        Returns path to this temporary folder.
        """
        folder_name = request_id
        folder_path = os.path.join("/tmp", folder_name)
        os.makedirs(folder_path)

        return folder_path

    # just adding these two functions too to test
    async def run_request(self, request: Request, request_id: str) -> ExecutorResult:
        folder_path = self.set_up_request(request_id)
        result = await self._execute(
            request,
            request_id,
            folder_path,
        )
        self.clean_up_folder(folder_path)
        return result

    def clean_up_folder(self, folder_path: str):
        """Cleans up the temporary folder"""
        shutil.rmtree(folder_path)

    async def _execute(self, request: Request, request_id: str, folder_path: str) -> ExecutorResult:
        # 1. Copy the uv files
        code_folder_path = os.path.join(folder_path, self.CODE_FOLDER_NAME)
        os.mkdir(code_folder_path)

        for file in request.files:
            with open(os.path.join(code_folder_path, file.file_name), "w") as f:
                f.write(file.content)

        with open(os.path.join(folder_path, "pyproject.toml"), "w") as f:
            pyproject_file = self.pyproject_template.render()
            f.write(pyproject_file)

        with open(os.path.join(code_folder_path, "__init__.py"), "w") as f:
            f.write("")

        with open(os.path.join(folder_path, "requirements.txt"), "w") as f:
            if "requirements" in request.environment.options:
                f.write(request.environment.options["requirements"])

        # 2. Cd into temp folder and run uv sync && uv run entry
        proc = await asyncio.create_subprocess_shell(
            f"UV_CONCURRENT_INSTALLS=1 {self.INSTALL_SCRIPT} {folder_path}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await proc.wait()

        proc = await asyncio.create_subprocess_shell(
            f"SANDBOX=1 SANDBOX_LEVEL=1 QUIET_MODE=1 UV_CONCURRENT_INSTALLS=1 {self.CONTY} "
            f"--bind {os.path.abspath(folder_path)} ~/{folder_path} "
            f"--ro-bind {os.path.abspath(self.RUN_SCRIPT)} ~/{self.RUN_SCRIPT} "
            # NOTE: `uv` binary is assumed to be stored under `~/.cargo/bin/`
            # We are using `uv` as the environment manager and program runner
            f"--ro-bind ~/.cargo ~/.cargo "
            f"./{self.RUN_SCRIPT} {folder_path} {self.CODE_FOLDER_NAME}/{request.entrypoint} {request.environment.memory_limit * 1024} {request.environment.time_limit}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        match proc.returncode:
            case 137:
                status = Status.MLE
            case 124:
                status = Status.TLE
            case 1:
                status = Status.RTE
            case _:
                status = Status.OK

        # 3. Return result
        return ExecutorResult.model_validate(
            {
                "status": status.value,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
            }
        )
