from enum import Enum
from fastapi import FastAPI

from unicon_runner.schemas import Request


app = FastAPI()


@app.post("/submissions")
def run_submission(request: Request):
    return "success"
