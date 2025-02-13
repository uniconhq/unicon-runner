import os
from typing import Final

from dotenv import load_dotenv

load_dotenv()


def _get_env_var(name: str, default: str | None = None, required: bool = True):
    value = os.getenv(name, default) or default
    if (value is None) and required:
        raise ValueError(f"{name} environment variable not defined")
    return value


AMQP_URL: Final[str] = _get_env_var("AMQP_URL", required=False)
AMQP_EXCHANGE_NAME: Final[str] = _get_env_var("AMQP_EXCHANGE_NAME", "unicon")
AMQP_TASK_QUEUE_NAME: Final[str] = _get_env_var("AMQP_TASK_QUEUE_NAME", "unicon.tasks")
AMQP_RESULT_QUEUE_NAME: Final[str] = _get_env_var("AMQP_RESULT_QUEUE_NAME", "unicon.results")
AMQP_CONN_NAME: Final[str] = _get_env_var("AMQP_CONN_NAME", "unicon-runner")

DEFAULT_EXEC_PY_VERSION: Final[str] = _get_env_var("DEFAULT_EXEC_PY_VERSION", "3.11.9")
DEFAULT_SLURM_OPTS: Final[str] = _get_env_var("DEFAULT_SLURM_OPTS", "")

CONTY_PATH: Final[str] = _get_env_var("CONTY_PATH", "conty.sh")
CONTY_DOWNLOAD_URL: Final[str] = _get_env_var(
    "CONTY_DOWNLOAD_URL", "https://github.com/uniconhq/conty/releases/latest/download/conty.sh"
)
