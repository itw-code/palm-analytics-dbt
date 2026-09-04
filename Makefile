# palm-analytics-dbt — common tasks and one-command repro.
#
# Local (inside activated .venv):
#   make repro        # ingest -> compile semantic layer -> dbt build -> docs
# Containerised (only Docker required):
#   docker build -t palm-analytics . && docker run --rm palm-analytics
#
# CI parity: .github/workflows/dbt.yml runs the same four steps as `repro`
# (plus freshness + diagnostics); the lint job proposal runs `make lint`.

PROFILE_DIR := .
DBT := dbt --profiles-dir $(PROFILE_DIR)

.PHONY: help setup ingest compile build freshness docs lint lint-yaml lint-sql repro clean

help:
	@echo "Targets: setup ingest compile build freshness docs lint repro clean"

# Install python deps, dbt packages, and the git hooks. Run inside your venv.
setup:
	python -m pip install -r requirements.txt
	$(DBT) deps
	python -m pip install pre-commit
	pre-commit install

# Rebuild raw layer (DuckLake) from live APIs w/ synthetic fallback.
ingest:
	python ingestion/load_raw.py

# Render models/marts/_marts__semantic.yml into the generated semantic model.
compile:
	$(DBT) parse
	python semantic/compile_metrics.py

# Run + test every model (seeds, snapshot, staging -> marts).
build:
	$(DBT) build

# Advisory source staleness report (never fails pinned-fixture runs by itself).
freshness:
	$(DBT) source freshness --output target/freshness.json || true

# Lineage artifacts for the hosted-docs proposal (target/manifest|catalog.json).
docs:
	$(DBT) docs generate

# Full pre-commit suite (sqlfluff + dbt-checkpoint + yamllint + hygiene).
lint:
	pre-commit run --show-diff-on-failure --color=always --all-files

lint-yaml:
	pre-commit run yamllint --all-files

lint-sql:
	pre-commit run sqlfluff-lint --all-files

# One-command warehouse repro: raw -> marts -> lineage artifacts.
repro: ingest compile build docs

clean:
	$(DBT) clean || true
