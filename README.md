# 🌴 palm-analytics-dbt

An end-to-end **analytics engineering** portfolio project on a real-world domain: Indonesian palm-oil estate operations. It demonstrates the modern AE stack from raw ingestion to a tested, documented dimensional model, orchestrated and CI-checked.

```
Open-Meteo (weather) + World Bank (CPO price)
        │   ingestion/load_raw.py  (Python)
        ▼
   DuckDB  (palm.duckdb  ·  MotherDuck for the hosted demo)
        │   dbt build
        ▼
   dbt models:  sources → staging → intermediate → marts
        │        (+ tests, docs, exposures)
        ▼
   BI layer (Metabase / Evidence.dev)  ·  GitHub Actions runs dbt build + test on every PR
```

## Why this project
Analytics engineering is **modeling**, not tool-collecting. The centerpiece here is the layered dbt model:
- **staging** (`stg_`) — 1:1 cleaned, renamed, typed views over raw sources
- **intermediate** (`int_`) — reusable business logic (agronomy suitability signals)
- **marts** (`fct_` / `dim_`) — a Kimball-style star the BI layer consumes

## Quickstart
```bash
python -m venv .venv && . .venv/Scripts/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt

# 1. Ingest raw data into DuckDB (live APIs, with deterministic synthetic fallback)
python ingestion/load_raw.py

# 2. Build + test the whole model
dbt build --profiles-dir .

# 3. Explore docs / lineage
dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .
```

## Stack
| Layer | Tool |
|---|---|
| Ingestion | Python (`requests`) |
| Warehouse | DuckDB (local) → MotherDuck (hosted demo) |
| Transformation | **dbt** (`dbt-duckdb`) |
| Orchestration | Airflow + astronomer-cosmos *(next milestone)* |
| CI | GitHub Actions (`dbt build`) |
| BI | Metabase / Evidence.dev *(next milestone)* |

## Data model
See [models/](models/). The marts answer: *given the weather and CPO price on a given day in a given region, which estate operations (fertilize / harvest / spray) are favorable, and what is the estimated value at risk?*

## Notes
- Ingestion attempts live Open-Meteo + World Bank calls and falls back to **deterministic synthetic data** if offline, so `dbt build` and CI are always green. Swap in live-only mode via `--live-only`.
- `palm.duckdb` and secrets are git-ignored. To use MotherDuck, set `MOTHERDUCK_TOKEN` and point the `prod` target at `md:palm_analytics`.
