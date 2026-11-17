# One command rebuilds everything from raw data: `make all`
.PHONY: all test lint ingest build power freeze estimate falsify revenue decide report

all:
	uv run transitcap all

test:
	uv run pytest -q

lint:
	uv run ruff check src tests

ingest build power freeze estimate falsify revenue decide report:
	uv run transitcap $@
