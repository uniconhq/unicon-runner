import asyncio
import os

import pika  # type: ignore
from pika.exchange_type import ExchangeType  # type: ignore

from unicon_runner.lib.constants import (
    EXCHANGE_NAME,
    RESULT_QUEUE_NAME,
    TASK_QUEUE_NAME,
)
from unicon_runner.runner.runner import Runner
from unicon_runner.runner.task.programming import ProgrammingTask

connection = pika.BlockingConnection(pika.URLParameters(os.getenv("RABBITMQ_URL")))

# Set up MQ channels
input_channel = connection.channel()
input_channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type=ExchangeType.topic)
input_channel.queue_declare(queue=TASK_QUEUE_NAME, durable=True)
input_channel.queue_bind(exchange=EXCHANGE_NAME, queue=TASK_QUEUE_NAME, routing_key=TASK_QUEUE_NAME)

input_channel.basic_qos(prefetch_count=1)

output_channel = connection.channel()
output_channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type=ExchangeType.topic)
output_channel.queue_declare(queue=RESULT_QUEUE_NAME, durable=True)
output_channel.queue_bind(
    exchange=EXCHANGE_NAME, queue=RESULT_QUEUE_NAME, routing_key=RESULT_QUEUE_NAME
)

executor = Runner(os.getenv("RUNNER_TYPE"))


async def run_submission(programming_task: ProgrammingTask):
    result = await executor.run_programming_task(programming_task=programming_task)

    message = result.model_dump_json()
    output_channel.basic_publish(exchange="", routing_key=RESULT_QUEUE_NAME, body=message)
    print(f" [x] Sent {message}")


def retrieve_job(ch, method, properties, body):
    try:
        task = ProgrammingTask.model_validate_json(body)
        print(task)
    except Exception as e:
        print(e)
        return
    asyncio.run(run_submission(task))
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    """Worker queue to listen for execute jobs"""
    input_channel.basic_consume(queue=TASK_QUEUE_NAME, on_message_callback=retrieve_job)
    input_channel.start_consuming()


if __name__ == "__main__":
    main()
