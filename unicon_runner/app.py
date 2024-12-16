import asyncio
from collections.abc import Awaitable, Callable
from functools import partial

import pika
import pika.spec
import typer
from pika.adapters.blocking_connection import BlockingChannel
from pika.exchange_type import ExchangeType

from unicon_runner.constants import EXCHANGE_NAME, RABBITMQ_URL, RESULT_QUEUE_NAME, TASK_QUEUE_NAME
from unicon_runner.executor import create_executor
from unicon_runner.executor.base import Executor, ExecutorType, ProgramResult
from unicon_runner.job import Job, JobResult, Program

app = typer.Typer()


def pull_job(
    in_ch: BlockingChannel,
    method: pika.spec.Basic.Deliver,
    _: pika.spec.BasicProperties,
    msg_body: bytes,
    run_job_and_push_result: Callable[[Job], Awaitable[None]],
) -> None:
    job = Job.model_validate_json(msg_body)
    in_ch.basic_ack(delivery_tag=method.delivery_tag)
    # TODO: We are running async procedures in a blocking context. This is not ideal.
    asyncio.run(run_job_and_push_result(job))  # type: ignore


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
    push_result(job_result)


def push_result(out_ch: BlockingChannel, job_result: JobResult) -> None:
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


@app.command()
def start(exec_type: ExecutorType):
    in_ch, out_ch = init_mq()

    executor = create_executor(exec_type)

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


if __name__ == "__main__":
    app()
