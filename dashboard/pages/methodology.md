---
title: Methodology & Data Lineage
---

This dashboard is the serving layer of an end-to-end analytics-engineering pipeline. It is deliberately built with the industry-standard toolchain to demonstrate the full workflow, not just charts.

## Data sources (all free)

| Source | What it provides | Auth |
|---|---|---|
| Open-Meteo Archive | daily weather per region - temperature, precipitation, wind, soil moisture, evapotranspiration (ET0), humidity | keyless |
| Frankfurter (ECB) | USD → IDR daily reference rate | keyless |
| Nager.Date | Indonesia public-holiday calendar | keyless |
| World Bank Pink Sheet | monthly palm-oil & soybean-oil prices | keyless |

All ingestion attempts a live fetch and falls back to deterministic synthetic data, so the pipeline and its CI are always reproducible offline.

## Transformation layers (dbt)

- **staging** (`stg_*`) - one cleaned, typed model per source
- **intermediate** (`int_*`) - reusable business logic: a date spine, forward-filled daily FX and commodity prices (DuckDB ASOF joins), and the agronomy suitability rules
- **marts** - a Kimball star: `dim_date` (with weekend + holiday flags), `dim_region` (enriched with a seeded estate profile), `fct_estate_operations_daily` (incremental), and `fct_commodity_price_daily` (contract-enforced column types)

## Engineering practices demonstrated

- 4 heterogeneous sources with **source freshness** checks
- layered modelling (staging → intermediate → marts) with **seeds**
- an **incremental** materialization and an **SCD2 snapshot** on commodity prices
- a **model contract** enforcing column types on the commodity mart
- data quality: `not_null`, `unique`, `relationships`, `accepted_values`, `accepted_range`, and a **custom generic test** (`non_negative`)
- **exposures** linking this dashboard back to the models it depends on
- CI: `dbt build` runs on every push

## The decision it supports

*Given today's weather and the palm price (in local currency), which estate operations - fertilize, harvest, spray - are favorable in each region, and what is a good harvest day worth?* An **effective harvest day** additionally requires that labour is available (not a weekend or public holiday).

Source: [github.com/itw-code/palm-analytics-dbt](https://github.com/itw-code/palm-analytics-dbt)
