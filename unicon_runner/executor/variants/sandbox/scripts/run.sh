#!/bin/bash

cd $1
ulimit -v $3
timeout $4 uv run $2

exit_code=$?
echo $exit_code > $1/exit_code