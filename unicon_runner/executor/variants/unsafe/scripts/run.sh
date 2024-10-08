cd $1
ulimit -v $3
timeout $4 uv run --no-project $2