# 🌴 palm-analytics-dbt

[![dbt build](https://github.com/itw-code/palm-analytics-dbt/actions/workflows/dbt.yml/badge.svg)](https://github.com/itw-code/palm-analytics-dbt/actions/workflows/dbt.yml)
[![deploy dashboard](https://github.com/itw-code/palm-analytics-dbt/actions/workflows/pages.yml/badge.svg)](https://github.com/itw-code/palm-analytics-dbt/actions/workflows/pages.yml)

An end-to-end **analytics engineering** project on a real domain: Indonesian palm-oil estate operations. It ingests four free public data sources, models them with dbt into a tested, documented, contract-enforced star schema, and serves the result as an interactive Evidence.dev dashboard - all reproducibly, with CI.

**🔗 Live dashboard:** https://itw-code.github.io/palm-analytics-dbt/

```
Open-Meteo   Frankfurter   Nager.Date   World Bank
 (weather)   (USD→IDR)     (holidays)   (palm/soy price)
     └─────────────┴────── ingestion/load_raw.py ──────┴─────────────┐
                                                                      ▼
                                              DuckDB  (palm.duckdb · MotherDuck)
                                                                      │  dbt build
                                                                      ▼
                        sources → staging (stg_) → intermediate (int_) → marts (dim_/fct_)
                              + seeds · snapshot (SCD2) · contract · tests · exposures
                                                                      ▼
                             Evidence.dev dashboard        GitHub Actions CI
                        (Overview · Planner · Market)     (dbt build on every push)
```

## The question it answers
*Given today's weather and the palm-oil price (in local currency), which estate operations - fertilize, harvest, spray - are favorable in each region, and what is a good harvest day worth?* An **effective harvest day** also requires available labour (not a weekend or Indonesian public holiday).

## Data sources (all free, all keyless)
| Source | Provides |
|---|---|
| [Open-Meteo](https://open-meteo.com) | daily weather per region: temp, precip, wind, soil moisture, ET0, humidity |
| [Frankfurter](https://frankfurter.dev) (ECB) | USD→IDR daily reference rate |
| [Nager.Date](https://date.nager.at) | Indonesia public-holiday calendar |
| [World Bank Pink Sheet](https://www.worldbank.org/en/research/commodity-markets) | monthly palm-oil & soybean-oil prices |

Ingestion attempts a live fetch and falls back to deterministic synthetic data, so builds and CI are always reproducible offline.

## What this demonstrates
| Feature | Competency |
|---|---|
| 4 heterogeneous sources + `dbt source freshness` | ingestion & source management |
| `seeds/region_profile.csv` | reference-data seeds |
| staging → intermediate → marts layering | modular modeling |
| `dim_date` (weekend + holiday flags), `dim_region`, `fct_*` | Kimball dimensional modeling |
| forward-filled FX & prices via DuckDB **ASOF joins** | SQL depth |
| **incremental** `fct_estate_operations_daily` | scalable materialization |
| **SCD2 snapshot** on commodity price | change data capture |
| **model contract** on `fct_commodity_price_daily` | data governance |
| custom generic test `non_negative` + not_null/unique/relationships/accepted_range | data quality |
| **dbt unit tests** on ASOF forward-fill & business-rule boundaries | logic testing beyond data shape |
| **exposures** + `dbt docs` lineage | documentation |
| GitHub Actions: `dbt build` + Pages deploy | CI/CD |

Verified: `dbt build` → **PASS=59, 0 errors** (incl. 3 dbt unit tests); Evidence build renders 4 pages with no query errors.

## 🧠 Architectural & Design Decisions

Key engineering trade-offs evaluated during system design:

* **DuckDB over Postgres/Warehouse for local ELT**: Enables zero-infrastructure serverless analytical processing with vectorized columnar execution and seamless MotherDuck cloud scale-up, without container overhead or query latency bottlenecks.
* **ASOF Joins for Forward-Filling**: Instead of complex window functions or synthetic date cross joins to fill missing weekend commodity prices and exchange rates, DuckDB's native `ASOF` join aligns the most recent historical price to daily operational logs deterministically with `O(N log M)` performance.
* **SCD Type 2 (`commodity_price_snapshot`)**: Tracks historical revision adjustments in World Bank Pink Sheet price estimates without destructive updates, preserving point-in-time financial auditability.
* **Model Contracts on Core Marts**: Explicit schema contracts on `fct_commodity_price_daily` guarantee downstream dashboard stability by failing the dbt run before breaking consumer reports in Evidence.dev.
* **Evidence.dev over traditional BI tools**: Code-driven, SQL-native markdown reporting versioned in git and compiled into static web pages deployed via GitHub Pages—eliminating BI server hosting costs while providing sub-second load times.

## 🛠️ Development & Iteration Methodology

This project was built following modular analytics engineering lifecycle phases:
1. **Ingestion Layer**: Keyless multi-source Python extractors (`Open-Meteo`, `Frankfurter`, `Nager.Date`, `World Bank`) with deterministic fallback seeds for offline testing.
2. **Kimball Dimensional Modeling**: Staging (`stg_`) cleaning → Intermediate (`int_`) join/enrichment → Marts (`dim_`, `fct_`) with star schema design.
3. **Data Quality Rigor**: 59 checks — 42 generic/singular tests (`non_negative`, `accepted_range`, foreign keys, contracts) + **3 dbt unit tests** proving ASOF forward-fill and agronomy rule boundaries (mutation-verified).
4. **BI & Presentation**: Evidence.dev metrics definitions and static dashboard build.
5. **CI/CD Automation**: GitHub Actions running automated `dbt build` test suites on pull requests and automated deployments to GitHub Pages.

*(Note: Commit history has been consolidated into milestone releases for clean public showcase distribution).*

## Quickstart
```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python ingestion/load_raw.py          # ingest raw data into DuckDB
dbt deps && dbt build --profiles-dir . # build + test everything (seeds, snapshot, models)
dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .  # lineage
```

### Dashboard (Evidence.dev)
```bash
cp palm.duckdb dashboard/sources/palm/palm.duckdb
cd dashboard
npm install
npm run sources
npm run dev        # http://localhost:3000
```

## Stack
Python · DuckDB / MotherDuck · **dbt** (`dbt-duckdb`) · Evidence.dev · GitHub Actions
