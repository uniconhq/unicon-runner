#!/bin/bash

cd $1
ulimit -v $3
timeout $4 uv run $2