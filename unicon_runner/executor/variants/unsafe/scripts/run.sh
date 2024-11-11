#!/bin/bash

cd $1

uv venv --python $3
uv add -r requirements.txt -q

ulimit -v $4
timeout $5 uv run $2