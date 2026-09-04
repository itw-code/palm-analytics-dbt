# PROPOSAL — Lane 5 Observability: Discord alerts + status.md upgrade + DQ trend mart

Scope: **scripts only + proposals**. No workflow or dashboard files were edited.
Deliverable script: `scripts/discord_alert.py` (written, verified). Everything
below is a copy-paste-ready proposal for the owning lanes to apply.

Related: `scripts/generate_status.py` (status_summary writer), workflows
`dbt.yml` / `pages.yml` (scheduled failure → deduped GitHub Issue, diagnostics
artifacts), `dashboard/pages/status.md` (current trust page), `target/freshness.json`
+ `ingestion_manifest.json` (the alert inputs).

---

## A. `scripts/discord_alert.py` — usage (DELIVERED, verified)

Stdlib only (`urllib`), dry-run by default, never fails the build.

```bash
# Safe local test — prints the payload it WOULD send, sends nothing
python scripts/discord_alert.py --dry-run
python scripts/discord_alert.py --job-status failure --dry-run

# CI — schedule-failure path (dbt.yml / pages.yml notify job)
python scripts/discord_alert.py \
  --event "$GITHUB_EVENT_NAME" --job-status "$JOB_STATUS" \
  --run-url "$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID" \
  --live
```

Severity: ERROR = job failure, dbt error>0, or freshness error/fail;
WARN = synthetic_sources>0, freshness warn, or missing artifact;
OK = green (skipped unless `--always`). `--live` without
`DISCORD_WEBHOOK_URL` warns and exits 0 — alerting never breaks the build.
The webhook comes only from the `DISCORD_WEBHOOK_URL` env var (repo secret);
the script never hardcodes or prints it (logs `webhook_configured=yes/no`).

### Proposed workflow step (add to `dbt.yml` + `pages.yml`, e.g. after the
freshness-summary step and inside the `notify-on-scheduled-failure` job)

```yaml
      - name: Discord alert (failure + synthetic/freshness warning)
        if: always() && (github.event_name == 'schedule' || github.event_name == 'workflow_dispatch')
        run: python scripts/discord_alert.py --event "${{ github.event_name }}" --job-status "${{ needs.build.result || job.status }}" --run-url "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}" --live
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
```

```text
# Redacted dry-run output (real repo artifacts, 2026-09-04; secret never printed)
[discord] severity=WARN dry_run=True webhook_configured=no
content: "🟡 palm-analytics manual run: WARN (1 synthetic fallback)"
fields: dbt=92/93 PASS (0 error, 0 warn) | freshness=raw_commodity_price: pass
(3.3d stale), raw_fx_rate: pass (1.3d stale), raw_weather_forecast: pass
(max +6.7d in future), raw_weather: pass (1.3d stale) | synthetic=1 (commodity)
| lake snapshot=1
# --job-status failure → severity=ERROR, title "🔴 ... ERROR (scheduled job failed)"
# empty-dir edge case → WARN "run_results.json missing / freshness.json missing", exit 0
```

---

## B. `status.md` upgrade proposal (freshness + days-stale + last green + test trend)

Requires one small change to `scripts/generate_status.py`: extend the
`status_summary` row with four columns — `freshness_days_stale_json`
(per-source `{"name": days}` from `max_loaded_at_time_ago_in_s / 86400`),
`generated_date`, `last_green_run_at` (max `generated_at` where
`dbt_error=0 AND freshness_status != 'error'`, read back from the existing
table before overwrite; NULL on first run), and `dbt_pass_rate_7d_json`
(append today's `{pass,total}` to the JSON list stored in the prior row,
keep last 7). All are best-effort with NULL/empty fallbacks so a missing
artifact never breaks the page.

Proposed `dashboard/pages/status.md` addition (after the existing alerts,
before the `<Grid>`):

```markdown
```sql freshness_detail
select
  generated_at,
  freshness_status,
  freshness_summary,
  freshness_days_stale_json,
  last_green_run_at,
  date_diff('day', cast(last_green_run_at as timestamp), current_timestamp) as days_since_green
from palm.status
```

```sql test_trend
select run_date, pass, total from palm.status_test_trend order by run_date
```

{#if freshness_detail[0].days_since_green > 2}
<Alert status="danger" title="No green run for {freshness_detail[0].days_since_green} days">Last green run: <Value data={freshness_detail} column=last_green_run_at/>. Check the Actions tab and open Issues.</Alert>
{/if}

## Freshness detail

| Source | Status | Days stale |
|---|---|---|
| raw_weather | <Value data={freshness_detail} column=freshness_status/> | <Value data={freshness_detail} column=freshness_days_stale_json/> |

Last green run: <Value data={freshness_detail} column=last_green_run_at/>

## Test trend (last 7 runs)

<LineChart data={test_trend} x=run_date y=pass title="dbt PASS per run"/>
```

---

## C. Data-quality trend proposal (PASS/WARN/ERROR per day → mart + chart)

New mart `models/marts/fct_dq_run_daily.sql` (one row per run day; appends via
the existing `generate_status.py` step or a `dbt run` of this model reading
`status_summary` — no new infra):

```sql
-- fct_dq_run_daily: one row per pipeline run for the DQ trend chart.
-- Grain: run_date. Source: status_summary written by scripts/generate_status.py.
{{
  config(
    materialized='incremental',
    unique_key='run_date',
    on_schema_change='append_new_columns'
  )
}}

select
  cast(current_date as date) as run_date,
  {{ var('dbt_pass', 0) }}   as tests_pass,
  {{ var('dbt_warn', 0) }}   as tests_warn,
  {{ var('dbt_error', 0) }}  as tests_error,
  {{ var('dbt_total', 0) }}  as tests_total,
  '{{ var("freshness_status", "unknown") }}' as freshness_status,
  {{ var('synthetic_sources', 0) }} as synthetic_sources
{% if is_incremental() %}
where cast(current_date as date) not in (select run_date from {{ this }})
{% endif %}
```

Simpler alternative (no vars plumbing): `generate_status.py` appends one row
per run into `main.dq_run_history(run_date, pass, warn, error, total,
freshness_status, synthetic_sources)` with `INSERT ... ON CONFLICT DO NOTHING`
semantics (delete-then-insert on `run_date`). Expose it to Evidence with a new
`dashboard/sources/palm/dq_trend.sql` → `select * from dq_run_history order by run_date`.

Chart query for `status.md`:

```markdown
```sql dq_trend
select run_date, tests_pass as PASS, tests_warn as WARN, tests_error as ERROR
from palm.dq_trend order by run_date
```

## Data-quality trend

<LineChart data={dq_trend} x=run_date y=["PASS","WARN","ERROR"] title="Tests per day: PASS / WARN / ERROR"/>
```
