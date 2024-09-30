from unicon_runner.runner.runner import Runner, RunnerType
from unicon_runner.runner.task.programming import ProgrammingTask

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

executor = Runner(RunnerType.PODMAN)


async def run_submission(programming_task: ProgrammingTask):
    result = await executor.run_programming_task(programming_task=programming_task)

    message = result.model_dump_json()
    output_channel.basic_publish(
        exchange=TASK_RUNNER_OUTPUT_QUEUE_NAME, routing_key="", body=message
    )
    print(f" [x] Sent {message}")


def retrieve_job(ch, method, properties, body):
    try:
        task = ProgrammingTask.model_validate_json(body)
        print(task)
    except Exception as e:
        print(body)
        print(e)
        print("fail")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return
    asyncio.run(run_submission(task))
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    """Worker queue to listen for execute jobs"""
    input_channel.basic_consume(
        queue=TASK_RUNNER_QUEUE_NAME, on_message_callback=retrieve_job
    )
    input_channel.start_consuming()


if __name__ == "__main__":
    main()
