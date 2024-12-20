import os

from dotenv import load_dotenv

load_dotenv()


def _get_env_var(name: str, default: str | None = None, required: bool = True):
    value = os.getenv(name, default) or default
    if (value is None) and required:
        raise ValueError(f"{name} environment variable not defined")
    return value


RABBITMQ_URL: str = _get_env_var("RABBITMQ_URL", required=False)
CONTY_PATH: str = _get_env_var("CONTY_PATH", required=False)

EXCHANGE_NAME = _get_env_var("EXCHANGE_NAME", "unicon")
TASK_QUEUE_NAME = _get_env_var("WORK_QUEUE_NAME", "unicon.tasks")
RESULT_QUEUE_NAME = _get_env_var("RESULT_QUEUE_NAME", "unicon.results")

DEFAULT_EXEC_PY_VERSION = "3.11.9"
