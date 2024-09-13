from enum import Enum
from fastapi import FastAPI
from contextlib import asynccontextmanager
from unicon_runner.executor.run import run_request
import os

from unicon_runner.schemas import Request


@asynccontextmanager
async def lifespan(app: FastAPI):
    if "temp" not in os.listdir():
        os.mkdir("temp")
    yield

app = FastAPI(lifespan=lifespan)


@app.post("/submissions")
def run_submission(request: Request):
    return run_request(request)
