import asyncio
from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
from typing import Annotated

import pika
import pika.spec
import typer
from pika.adapters.blocking_connection import BlockingChannel
from pika.exchange_type import ExchangeType

from unicon_runner.constants import EXCHANGE_NAME, RABBITMQ_URL, RESULT_QUEUE_NAME, TASK_QUEUE_NAME
from unicon_runner.executor import create_executor
from unicon_runner.executor.base import Executor, ExecutorType, ProgramResult
from unicon_runner.models import Job, JobResult, Program

app = typer.Typer()


def pull_job(
    in_ch: BlockingChannel,
    method: pika.spec.Basic.Deliver,
    _: pika.spec.BasicProperties,
    msg_body: bytes,
    run_job_and_push_result: Callable[[Job], Awaitable[None]],
) -> None:
    logger.info(f"Received message: {len(msg_body)} bytes")
    job = Job.model_validate_json(msg_body)
    logger.info(f"Received job: {job.model_extra}")
    # TODO: We are running async procedures in a blocking context. This is not ideal.
    asyncio.run(run_job_and_push_result(job=job))  # type: ignore
    in_ch.basic_ack(delivery_tag=method.delivery_tag)


async def run_job_and_push_result(
    push_result: Callable[[JobResult], None], executor: Executor, job: Job
) -> None:
    async def _run_program(program: Program) -> ProgramResult:
        return await executor.run(program, job.context)

    async with asyncio.TaskGroup() as tg:
        program_tasks = [tg.create_task(_run_program(program)) for program in job.programs]

    _tracking_fields = job.model_extra or {}
    job_result = JobResult(
        success=True,
        error=None,
        results=[program_task.result() for program_task in program_tasks],
        **_tracking_fields,
    )
    push_result(job_result=job_result)  # type: ignore


def push_result(out_ch: BlockingChannel, job_result: JobResult) -> None:
    logger.info(f"Pushed result: {job_result.model_extra}")
    out_ch.basic_publish(
        exchange=EXCHANGE_NAME, routing_key=RESULT_QUEUE_NAME, body=job_result.model_dump_json()
    )


def init_mq() -> tuple[BlockingChannel, BlockingChannel]:
    conn = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))

    in_ch, out_ch = conn.channel(), conn.channel()
    for ch in [in_ch, out_ch]:
        ch.exchange_declare(exchange=EXCHANGE_NAME, exchange_type=ExchangeType.topic)

    in_ch.queue_declare(queue=TASK_QUEUE_NAME, durable=True)
    in_ch.queue_bind(TASK_QUEUE_NAME, EXCHANGE_NAME, TASK_QUEUE_NAME)

    out_ch.queue_declare(queue=RESULT_QUEUE_NAME, durable=True)
    out_ch.queue_bind(RESULT_QUEUE_NAME, EXCHANGE_NAME, RESULT_QUEUE_NAME)

    return in_ch, out_ch


RootWorkingDirectory = Annotated[
    Path,
    typer.Argument(
        exists=True,
        writable=True,
        readable=True,
        help="Root path for executor's working directory",
    ),
]


@app.command()
def start(exec_type: ExecutorType, root_wd_dir: RootWorkingDirectory) -> None:
    in_ch, out_ch = init_mq()
    logger.info("Initialized task and result queues")

    executor = create_executor(exec_type, root_wd_dir)
    logger.info(f"Created executor: [bold green]{executor.__class__.__name__}[/]")
    logger.info(f"Root working directory: [bold green]{root_wd_dir.absolute()}[/]")

    in_ch.basic_qos(prefetch_count=1)
    in_ch.basic_consume(
        TASK_QUEUE_NAME,
        on_message_callback=partial(
            pull_job,
            run_job_and_push_result=partial(
                run_job_and_push_result,
                push_result=partial(push_result, out_ch=out_ch),
                executor=executor,
            ),
        ),
        auto_ack=False,
    )

    try:
        in_ch.start_consuming()  # NOTE: This is a blocking call (runs forever)
    except KeyboardInterrupt:
        in_ch.stop_consuming()


@app.command()
def test(
    exec_type: ExecutorType,
    root_wd_dir: RootWorkingDirectory,
    job_file: Annotated[Path, typer.Argument(exists=True, readable=True)],
    slurm: bool = False,
    slurm_opt: list[str] | None = None,
) -> None:
    # Dynamically set the slurm flag
    import json

    job_json = json.loads(job_file.read_text())
    if "context" in job_json:
        job_json["context"]["slurm"] = slurm
        job_json["context"]["slurm_options"] = slurm_opt or []

    job = Job.model_validate(job_json)
    executor = create_executor(exec_type, root_wd_dir)

    from rich.console import Console
    from rich.table import Table

    _console = Console()

    async def _run_job(program: Program) -> ProgramResult:
        # Since this is a test, we don't want to clean up the working directory
        # This is so that we can easily inspect the files written and replay the execution
        return await executor.run(program, job.context, cleanup=False)

    for i, program in enumerate(job.programs):
        prog_result = asyncio.run(_run_job(program))

        tbl = Table(title=f"Program Result #{i + 1}", highlight=True)
        tbl.add_column("status", style="magenta")
        tbl.add_column("stdout")
        tbl.add_column("stderr", style="red")
        tbl.add_row(prog_result.status, prog_result.stdout, prog_result.stderr)
        _console.print(tbl)


if __name__ == "__main__":
    import logging

    from rich.logging import RichHandler

    logging.basicConfig(
        level="INFO",
        format="[magenta]%(funcName)s[/] - %(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(markup=True)],
    )
    logging.getLogger("asyncio").setLevel(logging.INFO)
    logging.getLogger("pika").setLevel(logging.WARN)

    logger = logging.getLogger("unicon_runner")

    app()
