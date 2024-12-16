#!/bin/bash

# Change directory to the working directory
cd $1 

# Install required Python interpreter and dependencies
uv venv --python $2
uv add -r requirements.txt -q

# NOTE: Memory limit is set in kilobytes
# Reference: https://ss64.com/bash/ulimit.html
ulimit -v $3
# NOTE: Exit code is preserved if process is does not exceed time limit
# Reference: https://www.man7.org/linux/man-pages/man1/timeout.1.html
timeout $4 uv run $5

exit_code=$?
echo $exit_code > $1/exit_code