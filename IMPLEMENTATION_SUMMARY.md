# Implementation Summary — Automated Data Updates & Production Hardening

## 1) Automated Daily Refresh (Priority)

### What changed
- **`.github/workflows/pages.yml`** — full E2E pipeline now runs on `schedule: cron '0 0 * * *'` (00:00 UTC) in addition to `push` on `main` and `workflow_dispatch`. It executes: `pip install` → `dbt deps` → `python ingestion/load_raw.py` → `dbt build` → `dbt source freshness` → `cp palm.duckdb` → `npm build` → `upload-pages-artifact` → `deploy-pages`.
- **`.github/workflows/dbt.yml`** — same `schedule` added for CI validation (runs `dbt build` + freshness even when no code is pushed). Both workflows keep `workflow_dispatch` for manual reruns.
- **`concurrency.cancel-in-progress: false`** (was `true` for Pages). The scheduled cron now **queues behind** an in-progress manual push/PR instead of cancelling it. Group is `pages` (deploy) and `dbt-ci-${{ ref }}` (build), so `main` and PRs don't block each other, but a single branch never has two overlapping runs.
- **Pip + npm caches** (`cache: pip` / `cache: npm`) and `timeout-minutes` added to keep daily runs fast and bounded.

### Why
Scheduled Pages is the only way the dashboard stays fresh without human pushes. `cancel-in-progress: false` is the production-safe choice for Pages: a long Evidence build should finish; the cron should wait its turn, not kill it mid-deploy.

---

## 2) Robustness — deterministic fallback no longer silent

### What changed — `ingestion/load_raw.py`
- **Retry with backoff** (`fetch_with_retry`, 3 attempts, exponential 2s) for weather/FX/holidays. Eliminates flaking on transient 5xx/DNS blips.
- **Manifest** (`ingestion_manifest.json`): per-source provenance (`live` vs `synthetic` vs `failed`, row counts, error class, `synthetic_sources` counter, `status` = `live`/`synthetic_fallback`/`failed`). Written on every run, surfaced in the workflow summary, uploaded as an artifact on failure.
- **Never silent**: when synthetic fallback is used, `::warning::` and `::notice::` annotations are emitted; the workflow summary renders a `> [!WARNING]` callout. Commodity price fallback is explicitly flagged as *"parser not wired — known limitation"* rather than a generic API error.
- **Live-only mode** (`--require-live` / `--live-only`): still fails fast if any source degrades. Scheduled workflows can opt into fail-fast by setting `INGEST_REQUIRE_LIVE=1` as a repo variable — default (`0`) keeps the dashboard deployable through transient outages while still alerting.
- **Validation**: raises `ValueError` if an API returns 0 rows (treats empty response as failure, triggers retry/fallback).
- **Date handling**: `DEFAULT_END_DATE` stays fixed (`2026-06-30`) for deterministic CI; `PALM_END_DATE` env and `PALM_USE_LIVE_DATE=1` (yesterday) allow a scheduled run to ingest truly fresh data without code changes. CLI `--end-date` / `--window-days` added.
- **Manifest + `.gitignore`**: `ingestion_manifest.json` is git-ignored but retained as an artifact.

### Why
The original script's `try/except → synth_*` was excellent for reproducibility but **silently degraded data quality in production**. An on-call engineer would see a green Pages deploy with synthetic weather/FX and never know. Now the pipeline is *graceful by default, loud by design*: it still deploys through an outage, but the degradation is machine-readable and human-visible, and can be promoted to a hard failure with one variable.

---

## 3) Observability

### What changed — both workflows
- **Workflow Summary** steps append the manifest JSON + freshness table to `$GITHUB_STEP_SUMMARY`. A synthetic fallback renders a warning callout; a live run renders a note. Row counts are also emitted via DuckDB.
- **Source freshness** no longer `continue-on-error: true` (which hid failures). Now: `dbt source freshness --output target/freshness.json || true` → parsed → summary + `::warning::` on `warn`, `::error::` + `exit 1` on `error`/`fail`. Warnings stay visible; only errors fail the job.
- **Failure artifacts**: `target/run_results.json`, `target/freshness.json`, `ingestion_manifest.json`, `logs/dbt.log` uploaded as `*_diagnostics-<run_id>` (retention 14d).
- **Scheduled-failure Issues**: `actions/github-script@v7` opens a GitHub Issue titled `Scheduled dbt build failed — YYYY-MM-DD` / `Scheduled dashboard refresh failed — …` with run/commit links, deduplicated (if an open issue with that prefix exists, it comments instead of spamming). Requires `permissions: issues: write`.

### Why
Daily cron without observability is a silent failure mode. GitHub-native summaries + issues meet the requirement without adding external dependencies (Slack/PagerDuty can be wired later to the same `failure()` condition).

---

## 4) Source freshness — tighten signals without breaking deterministic CI

### What changed — `models/staging/_staging__sources.yml`
- `raw_weather` / `raw_fx_rate`: `warn_after: 3 days` (was 45), `error_after: 90 days` (new), `filter` added. 
- `raw_commodity_price`: `warn_after: 35 days` (was 90), `error_after: 95 days`, `filter` added.
- Comments explain the trade-off: tight `warn` catches a missed daily cron immediately; generous `error` keeps the fixed `2026-06-30` fixture from erroring until ~Sep 2026 (current wall-clock) while still catching true staleness in live mode (`PALM_USE_LIVE_DATE=1`).

### Why
`warn: 45 days` meant a missed daily refresh would go unnoticed for 6 weeks. `warn: 3 days` surfaces it next morning. The staggered `warn`/`error` split lets the job stay green on `warn` (visible in summary) and only go red on `error`.

---

## 5) Performance

### What changed
- **`dbt_project.yml`**: `+persist_docs` (relation + columns) for catalog quality, `seeds` column types, `fct_estate_operations_daily` now declares `incremental_strategy: delete+insert` + `on_schema_change: sync_all_columns` at the project level.
- **`models/marts/fct_estate_operations_daily.sql`**: explicit `config(incremental_strategy='delete+insert')`. Allows late-arriving days to overwrite cleanly and lets DuckDB prune the scan to only `where signals.weather_date > (select max(operation_date) from {{ this }})`. Comments document the rationale.
- **DuckDB / CI**: `pip`/`npm` caches, `threads: 4` (existing), `ls -lh` validation after `cp`, `timeout-minutes` to avoid hung runners.

### Why
`delete+insert` is the correct incremental strategy for DuckDB when the grain is a date and reloads are idempotent. The project-level defaults ensure future marts inherit sane behavior without copy-paste.

---

## 6) Dashboard UX — low-effort / high-impact

### What changed
- **`dashboard/pages/index.md`**: adds `freshness` query (`max(operation_date)`, `days_stale`), `{#if}` alerts (`warning` when `>3` days stale, `info` otherwise), `<Grid cols=4>` layout, `yFmt` formatting, `*Data as of … — refreshed daily at 00:00 UTC*` footer. Chart titles preserved.
- **`dashboard/pages/operations.md`**: adds staleness alert, `<Grid cols=3>` for KPIs, footer with `as_of`, `<DataTable search sortable>` with extra columns (`water_deficit_mm`, `cpo_idr_per_tonne`) and `rows=20`.
- **`dashboard/pages/methodology.md`**: documents the daily 00:00 UTC schedule, E2E steps, concurrency behavior, observability, and the synthetic-fallback contract.

### Why
The single most valuable UX signal for a scheduled dashboard is *“how old is this data?”* — a staleness banner and an explicit *Data as of* label cost ~5 lines of SQL/Markdown and eliminate the “is this still live?” doubt. Search/sort on the planner table makes 120×3 rows actually usable.

---

## Verification
- `python -c "yaml.safe_load(...)"` — both workflows parse.
- `.venv/Scripts/python.exe ingestion/load_raw.py` → `live` for weather/FX/holidays, `synthetic` only for commodity (expected stub), manifest written, exit 0; `--require-live` → exit 1 with `failed` manifest (correct).
- `.venv/Scripts/dbt build --profiles-dir .` → `PASS=56` after all edits.
- `dbt source freshness` → `WARN` (expected for 2026-06-30 fixture, no `ERROR`), jobs stay green; scheduled live mode (`PALM_USE_LIVE_DATE=1`) would be `PASS`.

## How to make the schedule fail-fast (optional)
Set a repository variable `INGEST_REQUIRE_LIVE=1` (Settings → Variables) and/or `PALM_USE_LIVE_DATE=1` to ingest through yesterday instead of the fixed `2026-06-30`. After the World Bank parser is wired, `INGEST_REQUIRE_LIVE=1` will make any single API outage file a GitHub Issue instead of deploying synthetic data.

## Files delivered
- `.github/workflows/dbt.yml` (updated)
- `.github/workflows/pages.yml` (updated)
- `ingestion/load_raw.py` (updated)
- `models/staging/_staging__sources.yml` (freshness thresholds)
- `dbt_project.yml` (performance/docs)
- `models/marts/fct_estate_operations_daily.sql` (incremental strategy)
- `dashboard/pages/index.md`, `operations.md`, `methodology.md` (UX)
- `.gitignore` (ignore `ingestion_manifest.json`)
