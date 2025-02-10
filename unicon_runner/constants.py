import os

from dotenv import load_dotenv

load_dotenv()


def _get_env_var(name: str, default: str | None = None, required: bool = True):
    value = os.getenv(name, default) or default
    if (value is None) and required:
        raise ValueError(f"{name} environment variable not defined")
    return value


AMQP_URL: str = _get_env_var("AMQP_URL")
AMQP_EXCHANGE_NAME: str = _get_env_var("AMQP_EXCHANGE_NAME", "unicon")
AMQP_TASK_QUEUE_NAME: str = _get_env_var("AMQP_TASK_QUEUE_NAME", "unicon.tasks")
AMQP_RESULT_QUEUE_NAME: str = _get_env_var("AMQP_RESULT_QUEUE_NAME", "unicon.results")

DEFAULT_EXEC_PY_VERSION: str = _get_env_var("DEFAULT_EXEC_PY_VERSION", "3.11.9")

CONTY_PATH: str = _get_env_var("CONTY_PATH", "conty.sh")
CONTY_DOWNLOAD_URL: str = _get_env_var(
    "CONTY_DOWNLOAD_URL", "https://github.com/uniconhq/conty/releases/latest/download/conty.sh"
)
