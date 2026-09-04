# Case study: palm-analytics-dbt — an end-to-end analytics-engineering showcase

> Live: <https://itw-code.github.io/palm-analytics-dbt/> ·
> Freshness: <https://itw-code.github.io/palm-analytics-dbt/status> ·
> Repo: <https://github.com/itw-code/palm-analytics-dbt>

## 1. Problem

Estate managers in Indonesian palm-oil operations make daily go/no-go calls —
fertilize, harvest, spray — against moving inputs: weather, labour availability,
exchange rates, and commodity prices. Public data covers all of these, but it
arrives in four incompatible shapes (daily weather API, daily FX reference,
yearly holiday calendar, monthly price sheet), with gaps on weekends and
revisions after the fact.

The project asks: *given today's weather and the palm-oil price in local
currency, which operations are favorable in each region, and what is a good
harvest day worth?* — and answers it with a tested, documented pipeline plus a
dashboard a non-technical stakeholder can read.

## 2. Options considered

| Decision | Option A (chosen) | Option B | Why A |
|---|---|---|---|
| Warehouse | **DuckDB file + DuckLake raw** | Postgres / cloud warehouse | Zero infrastructure; file-based CI; vectorized OLAP; MotherDuck scale-up path |
| Raw layer | **DuckLake snapshots** (parquet + ACID) | Raw tables in warehouse schema | Immutable point-in-time ingestion history; small serving file; mirrors prod lakehouse pattern |
| Gap-filling | **ASOF joins** | Window-function / cross-join fill | One deterministic last-observation-carried-forward join, `O(N log M)` |
| Price revisions | **SCD2 snapshot** | Overwrite in place | Point-in-time auditability of Pink Sheet revisions |
| Mart safety | **Model contract** on price mart | Tests only | Fail the run before breaking consumers |
| BI | **Evidence.dev + GitHub Pages** | Hosted BI (Power BI / Looker) | Git-versioned SQL-native reporting; static deploy, no server cost |
| Flaky sources | **Loud synthetic fallback** | Fail-fast ingest | Pipeline never goes red on transient outages; degradation surfaced via manifest + `/status` |

## 3. What was built

- **Ingestion** (`ingestion/load_raw.py`): 4 keyless sources with retry, per-source
  live/synthetic recording in `ingestion_manifest.json`, one DuckLake ACID
  snapshot per load.
- **Modeling**: staging → intermediate (calendar spine, ASOF FX/price fill,
  shared agronomy-rules macro) → marts (`dim_date`, `dim_region`,
  `fct_estate_operations_daily` incremental, `fct_estate_forecast_7day`,
  `fct_estate_margin_daily`, contracted `fct_commodity_price_daily`, SCD2
  snapshot, MetricFlow-spec semantic layer compiled to `sl_metrics_daily`).
- **Quality**: 92 passing dbt checks — generic/singular tests
  (`non_negative`, ranges, relationships, contracts) plus 3 **mutation-verified
  unit tests** on ASOF fill and agronomy boundaries.
- **Serving**: Evidence.dev dashboard (Overview, 7-day Forecast planner, Market,
  Margin, **Status trust page**) deployed to GitHub Pages.
- **Operations**: GitHub Actions daily 00:00 UTC cron (ingest → build →
  freshness → deploy), concurrency-safe, auto-issues on scheduled failure.

## 4. Trade-offs (honest)

1. **Commodity prices are a synthetic fixture in CI by design.** The World Bank
   xlsx parser is intentionally stubbed so builds are deterministic offline.
   Consequence: margin figures demonstrate mechanics, not market truth.
2. **History is pinned to 2026-06-30 on push/PR builds** for stable tests; only
   scheduled runs ingest through yesterday. Freshness gates are asymmetric
   (wide `error_after` on fixtures) — easy to misread if you don't know this.
3. **DuckLake is single-writer.** Two concurrent ingests on one catalog file
   take an IO lock — fine for a daily cron, a real constraint at higher cadence.
4. **No auth, no RLS.** The dashboard is a public static site; fine for a
   showcase, not for commercially sensitive estate data.
5. **Cost assumptions are seeds** (`seeds/cost_assumptions.csv`) — placeholder
   economics a real customer would replace with actuals.

## 5. Results

- `dbt build`: **PASS=92, WARN=0, ERROR=0** on every green run.
- Dashboard deploys daily (~2m20s); forecast page always shows live
  *today+1…7* window; `/status` exposes provenance to end users.
- Cold bootstrap works: deleting `palm_lake/` + `palm.duckdb` reproduces
  everything from `load_raw.py` + `dbt build`.

## 6. With funding / next

1. **Live price feed + validation** — replace the synthetic commodity fixture
   with a contracted vendor feed (or a maintained parser), add price-anomaly
   alerts.
2. **Forecast accuracy backtest** — accumulate forecast-vs-observed pairs from
   daily runs; publish rolling skill scores on the dashboard.
3. **WhatsApp 06:00 WIB digest** — daily ops summary per region from the
   forecast + margin marts (credentials are the only blocker).
4. **Multi-estate tenancy** — bring-your-own-block CSV upload, per-estate cost
   books, Bahasa Indonesia toggle, Excel export for field staff.
5. **Lakehouse hygiene** — weekly snapshot expiry + compaction as history grows.
