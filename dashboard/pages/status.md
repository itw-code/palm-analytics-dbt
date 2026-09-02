---
title: Trust & Data Health
---

How this dashboard is built, tested, and monitored — the trust ledger. Updated on every run.

```sql status
select * from palm.status
```

{#if status[0].freshness_status == 'error'}
<Alert status="danger" title="Source freshness: ERROR">Some raw sources are stale beyond the error threshold. Check the freshness summary below and the Actions tab.</Alert>
{:else if status[0].freshness_status == 'warn'}
<Alert status="warning" title="Source freshness: WARN">At least one source is past its warn threshold (expected in CI with the pinned fixture). Live deploys are fresh — see generated_at.</Alert>
{:else}
<Alert status="info" title="Freshness OK">Raw sources are within their freshness window.</Alert>
{/if}

{#if status[0].synthetic_sources > 0}
<Alert status="warning" title="Synthetic fallback active">`synthetic_sources = {status[0].synthetic_sources}` — at least one API fell back to deterministic synthetic data. Commodity is always synthetic until the World Bank parser is wired. See ingestion manifest.</Alert>
{/if}

<Grid cols=3>
  <BigValue data={status} value=dbt_pass title="dbt PASS"/>
  <BigValue data={status} value=dbt_total title="dbt total checks"/>
  <BigValue data={status} value=lake_snapshot_id title="Lake snapshot"/>
</Grid>

| Field | Value |
|---|---|
| Generated at | <Value data={status} column=generated_at/> |
| Warehouse | <Value data={status} column=warehouse/> |
| Ingestion status | <Value data={status} column=ingestion_status/> |
| Synthetic sources | <Value data={status} column=synthetic_sources/> |
| Freshness | <Value data={status} column=freshness_summary/> |
| Row counts (raw) | <Value data={status} column=row_counts_json/> |
| dbt | <Value data={status} column=dbt_pass/> / <Value data={status} column=dbt_total/> PASS (<Value data={status} column=dbt_error/> error, <Value data={status} column=dbt_warn/> warn) |

*Every scheduled run appends this same ledger to the GitHub Actions Summary and, on failure, opens a deduplicated Issue. Lake snapshots are queryable at any past `snapshot_id` via DuckLake time travel.*

## Margin assumptions

The margin mart uses `seeds/cost_assumptions.csv` — fertilizer, harvest and transport costs per region plus extraction rate. Replace those seed values with your estate's actuals and the margin recomputes everywhere. Formula per effective harvest day:

`revenue_per_ha = CPO_IDR_per_tonne * yield_t_ha * extraction_rate`

`margin_per_ha = revenue_per_ha - fertilizer - harvest - transport` ; otherwise `-fertilizer` (you still fertilize even when you don't harvest).

See [7-Day Forecast](/forecast) for prescriptive outlook and [Operations](/operations) for historical planner.
