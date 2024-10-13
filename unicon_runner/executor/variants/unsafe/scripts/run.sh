cd $1
ulimit -v $3
uv sync -q
uv add -r requirements.txt -q
timeout $4 uv run $2