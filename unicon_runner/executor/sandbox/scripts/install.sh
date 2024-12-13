#!/bin/bash

cd $1

uv venv --python $2
uv add -r requirements.txt -q