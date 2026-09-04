# Lane 1 — Data Reality: provenance badges + backfill runbook

## What landed (tracked edit)

`ingestion/load_raw.py` — live World Bank Pink Sheet parser:
- `_parse_pink_workbook()` parses the "Monthly Prices" sheet (header row 5
  located by name, `$/mt` units = USD/tonne, `YYYYMmm` periods, `...` skip).
- `fetch_commodity_live()` tries `PALM_PINK_SHEET_URL` override, then pinned
  2026 edition, then 2025 edition, each with `fetch_with_retry`.
- `resolve_window_days()` — `PALM_START_DATE=YYYY-MM-DD` overrides
  `--window-days` for multi-year backfill.
- Caller + manifest messages updated: no more "parser not wired" stub text.
  Commodity is `live` when any URL parses, `synthetic` (loud) only when all
  URLs are unreachable, `failed` with `--require-live`.

## Backfill runbook

```bash
# ~5.5y backfill (weather/FX/holidays + full commodity months in range)
PALM_START_DATE=2020-01-01 PALM_END_DATE=2026-06-30 \
  .venv/Scripts/python.exe ingestion/load_raw.py

# Live scheduled mode (fresh through yesterday)
PALM_USE_LIVE_DATE=1 .venv/Scripts/python.exe ingestion/load_raw.py

# One-off Pink Sheet URL override (new edition released)
PALM_PINK_SHEET_URL=https://thedocs.worldbank.org/.../CMO-Historical-Data-Monthly.xlsx \
  .venv/Scripts/python.exe ingestion/load_raw.py --require-live
```

Note: Open-Meteo archive + Frankfurter history support multi-year ranges;
Nager.Date is per-year (looped). A 5y backfill pulls ~5.5k weather rows.

## Proposal A — provenance badges in dashboard footer (copy-paste)

`scripts/generate_status.py` already writes `status_summary`; add one column
`commodity_mode` from `ingestion_manifest.json`
(`provenance["sources"]["commodity"]["mode"]`). Then in
`dashboard/pages/index.md` footer query:

```sql
prov
select
  max(operation_date) as as_of,
  (select commodity_mode from palm.status_summary) as commodity_mode
from palm.fct_estate_operations_daily
```

```markdown
{#if prov[0].commodity_mode == 'live'}
<Alert status="success" title="Commodity prices: LIVE World Bank Pink Sheet" />
{:else}
<Alert status="warning" title="Commodity prices: synthetic fallback — Pink Sheet unreachable" />
{/if}
```

## Proposal B — status page per-source table (copy-paste)

Extend `status_summary` with `provenance_json` (dump of
`provenance["sources"]`), then in `dashboard/pages/status.md`:

```sql
prov
select
  key as source,
  value:mode::varchar as mode,
  value:rows::int as rows
from palm.status_summary,
lateral flatten(input => provenance_json::variant)
```

Renders a per-source LIVE/SYNTHETIC badge table next to the freshness panel.
