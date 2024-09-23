from http import HTTPStatus
import json
from uuid import uuid4
from fastapi import FastAPI, BackgroundTasks, Response
from contextlib import asynccontextmanager
from unicon_runner.executor.run import run_request
from unicon_runner.util.redis_connection import redis_conn
import os

from unicon_runner.schemas import Request


@asynccontextmanager
async def lifespan(app: FastAPI):
    if "temp" not in os.listdir():
        os.mkdir("temp")
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/submissions", status_code=HTTPStatus.ACCEPTED)
async def run_submission(request: Request, background_tasks: BackgroundTasks):
    request_id = str(uuid4()).replace("-", "")
    background_tasks.add_task(run_request, request, request_id)
    redis_conn.set(request_id, "")
    print(redis_conn.exists(request_id))
    return {"submission_id": request_id}


@app.get("/submissions/{id}")
async def get_submission(id, response: Response):
    if not redis_conn.exists(id):
        response.status_code = HTTPStatus.NOT_FOUND
        return
    result = redis_conn.get(id)
    if not result:
        response.status_code = HTTPStatus.ACCEPTED
    return json.loads(result)
