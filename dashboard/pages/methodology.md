---
title: Methodology & Data Lineage
---

This dashboard is the serving layer of an end-to-end analytics-engineering pipeline. It is deliberately built with the industry-standard toolchain to demonstrate the full workflow, not just charts.

## Data sources (all free)

| Source | What it provides | Auth |
|---|---|---|
| Open-Meteo Archive | historical daily weather per region - temperature, precipitation, wind, soil moisture, ET0, humidity | keyless |
| Open-Meteo Forecast / Historical-Forecast | **7-day forward forecast** per region (same variables; forecast API when window is future, historical-forecast for deterministic CI) | keyless |
| Frankfurter (ECB) | USD → IDR daily reference rate | keyless |
| Nager.Date | Indonesia public-holiday calendar | keyless |
| World Bank Pink Sheet | monthly palm-oil & soybean-oil prices | keyless |

All ingestion attempts a live fetch with retries and falls back to deterministic synthetic data, so the pipeline and its CI are always reproducible offline. **In production the fallback is never silent:** `ingestion/load_raw.py` writes `ingestion_manifest.json` with per-source provenance (`live` vs `synthetic`) and the scheduled GitHub Actions job surfaces any synthetic fallback as a warning in the workflow summary — and optionally opens a GitHub issue. Pass `--require-live` to make the pipeline fail-fast instead of degrading. Commodity price is *always* synthetic today because the World Bank Pink Sheet parser is stubbed (known limitation, flagged explicitly in the manifest).

## Transformation layers (dbt)

- **raw layer (DuckLake)** - API payloads land in a DuckLake catalog (`palm_lake/`): open parquet data files with ACID snapshot metadata from DuckDB Labs. Each daily load commits as one immutable, point-in-time-queryable snapshot (the snapshot id is recorded in the ingestion manifest).
- **staging** (`stg_*`) - one cleaned, typed model per source
- **intermediate** (`int_*`) - reusable business logic: a date spine (historical + forecast), forward-filled daily FX and commodity prices (DuckDB ASOF joins), and the agronomy suitability rules via a shared `agronomy_signals` macro (DRY - one definition for historical and forecast)
- **forecast mart** (`fct_estate_forecast_7day`) - prescriptive 7-day forward planner per region (H+1..7) with carried-forward prices
- **semantic layer** - canonical metric definitions in the MetricFlow-compatible spec (`_marts__semantic.yml`), parsed by dbt-core into the manifest and compiled by `semantic/compile_metrics.py` into the governed `sl_metrics_daily` view (simple, derived, and cumulative metrics) - one definition of every number, consumed by this dashboard
- **marts** - a Kimball star: `dim_date` (with weekend + holiday flags), `dim_region` (enriched with a seeded estate profile), `fct_estate_operations_daily` (incremental), and `fct_commodity_price_daily` (contract-enforced column types)

## Engineering practices demonstrated

- 4 heterogeneous sources with **source freshness** checks (`warn` at 3 days for daily feeds / 35 days for monthly, `error` at 90 / 95 days)
- a **DuckLake lakehouse raw layer** (parquet + ACID snapshots) feeding a DuckDB warehouse - the production object-storage-lakehouse pattern without cloud dependency
- layered modelling (staging → intermediate → marts) with **seeds**
- an **incremental** (`delete+insert`) materialization and an **SCD2 snapshot** on commodity prices
- a **model contract** enforcing column types on the commodity mart
- data quality: `not_null`, `unique`, `relationships`, `accepted_values`, `accepted_range`, a **custom generic test** (`non_negative`), and **dbt unit tests** proving the ASOF forward-fill and business-rule boundaries
- **exposures** linking this dashboard back to the models it depends on
- CI/CD: `dbt build` on every push/PR + **daily 00:00 UTC scheduled refresh** (`pages.yml` runs ingest → dbt build → Evidence build → Pages deploy) with `concurrency.cancel-in-progress: false` so the cron queues behind manual pushes instead of cancelling them, plus workflow-summary and GitHub-Issue observability on failures

## 7-day forward planner

The dashboard's [7-Day Forward Planner](/forecast) extends the same agronomy rules into the forecast window (H+1 → H+7). Raw forecast lands in DuckLake as `raw_weather_forecast` alongside the historical archive, the date spine extends to cover it, and the forecast mart assumes prices flat at the latest known value - honest about what is forecast vs known. Check the decision with hindsight the next morning.

## The decision it supports

*Given today's weather and the palm price (in local currency), which estate operations - fertilize, harvest, spray - are favorable in each region, and what is a good harvest day worth?* An **effective harvest day** additionally requires that labour is available (not a weekend or public holiday).

## Automation & observability

- **Schedule:** both workflows run on `push`/`pull_request` and additionally on `schedule: cron '0 0 * * *'` (00:00 UTC) plus `workflow_dispatch` for manual reruns.
- **E2E on schedule:** the Pages workflow does the full pipeline — `pip install` → `dbt deps` → `python ingestion/load_raw.py` → `dbt build` → `dbt source freshness` → `cp palm.duckdb` → `npm run build` → deploy to `gh-pages`.
- **No conflict with manual pushes:** `concurrency.group: pages` with `cancel-in-progress: false` (and `dbt-ci-${ref}` for the build workflow) makes the cron queue rather than kill an in-progress deploy.
- **Observability:** every run appends the ingestion manifest and freshness status to the Actions *Summary*; on `schedule` failures a GitHub Issue is opened automatically (deduplicated). Diagnostics (`target/*.json`, `ingestion_manifest.json`) are uploaded as artifacts on failure.

Source: [github.com/itw-code/palm-analytics-dbt](https://github.com/itw-code/palm-analytics-dbt)
