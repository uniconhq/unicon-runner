import json
from uuid import uuid4
from unicon_runner.executor.run import run_request

from unicon_runner.schemas import Request

import pika
import asyncio

TASK_RUNNER_QUEUE_NAME = "task_runner"
TASK_RUNNER_OUTPUT_QUEUE_NAME = "task_runner_results"

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))

# Set up MQ channels
input_channel = connection.channel()
input_channel.queue_declare(queue=TASK_RUNNER_QUEUE_NAME, durable=True)
input_channel.basic_qos(prefetch_count=1)

output_channel = connection.channel()
output_channel.exchange_declare(
    exchange=TASK_RUNNER_OUTPUT_QUEUE_NAME, exchange_type="fanout"
)


async def run_submission(request: Request):
    request_id = str(uuid4()).replace("-", "")
    result = await run_request(request, request_id)

    message = json.dumps(result)
    output_channel.basic_publish(
        exchange=TASK_RUNNER_OUTPUT_QUEUE_NAME, routing_key="", body=message
    )
    print(f" [x] Sent {message}")


def retrieve_job(ch, method, properties, body):
    asyncio.run(run_submission(Request.model_validate_json(body)))
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    """Worker queue to listen for execute jobs"""
    input_channel.basic_consume(
        queue=TASK_RUNNER_QUEUE_NAME, on_message_callback=retrieve_job
    )
    input_channel.start_consuming()


if __name__ == "__main__":
    main()
