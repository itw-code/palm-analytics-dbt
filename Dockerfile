# palm-analytics-dbt — one-command warehouse repro.
# Build + run (only Docker required):
#   docker build -t palm-analytics . && docker run --rm palm-analytics
# The container rebuilds the DuckLake raw layer (live APIs with synthetic
# fallback) and runs ingest -> semantic compile -> dbt build -> docs generate,
# i.e. the same steps as `make repro` / the dbt.yml CI job.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt packages.yml dbt_project.yml profiles.yml ./
RUN pip install -r requirements.txt \
    && dbt deps

COPY . ./

CMD ["make", "repro"]
