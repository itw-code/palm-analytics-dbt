---
title: Palm Estate Operations
---

Decision-support for Indonesian palm-oil estates: what operations are favorable by region, and what a good harvest day is worth in both USD and local currency. Data flows **Open-Meteo + Frankfurter + Nager.Date + World Bank → DuckDB → dbt → this dashboard**.

```sql freshness
select
    max(operation_date) as as_of,
    datediff('day', max(operation_date), current_date) as days_stale,
    max(cpo_usd_per_tonne) as cpo_usd,
    max(cpo_idr_per_tonne) as cpo_idr
from palm.operations_daily
```

```sql headline
select
    max(operation_date) as as_of,
    max(cpo_usd_per_tonne) as cpo_usd,
    max(cpo_idr_per_tonne) as cpo_idr
from palm.operations_daily
where operation_date = (select max(operation_date) from palm.operations_daily)
```

```sql favorable_counts
select
    count(*) filter (where is_effective_harvest_day) as effective_harvest_days,
    count(*) filter (where is_fertilize_favorable) as fertilize_days,
    count(*) filter (where is_spray_favorable) as spray_days
from palm.operations_daily
```

{#if freshness[0].days_stale > 3}
<Alert status="warning" title="Data may be stale">
  Last successful refresh was <Value data={freshness} column=as_of fmt="yyyy-mm-dd"/> — that's <Value data={freshness} column=days_stale/> days ago. Scheduled daily refresh runs at 00:00 UTC; check the <a href="https://github.com/itw-code/palm-analytics-dbt/actions">Actions</a> tab for failures.
</Alert>
{/if}

{#if freshness[0].days_stale <= 3}
<Alert status="info" title="Data freshness">
  Dashboard refreshed through <Value data={freshness} column=as_of fmt="yyyy-mm-dd"/> (updated daily at 00:00 UTC).
</Alert>
{/if}

<Grid cols=4>
  <BigValue data={headline} value=cpo_usd fmt="usd0" title="Palm price (USD/tonne)"/>
  <BigValue data={headline} value=cpo_idr fmt="#,##0" title="Palm price (IDR/tonne)"/>
  <BigValue data={favorable_counts} value=effective_harvest_days title="Effective harvest days"/>
  <BigValue data={favorable_counts} value=spray_days title="Spray-favorable days"/>
</Grid>

*Data as of <Value data={freshness} column=as_of fmt="yyyy-mm-dd"/> — refreshed daily at 00:00 UTC via GitHub Actions. Commodity price is synthetic until the World Bank parser is wired (see Methodology).*

## Palm price trend (local currency)

```sql price_trend
select distinct operation_date, cpo_idr_per_tonne
from palm.operations_daily
where cpo_idr_per_tonne is not null
order by operation_date
```

<LineChart data={price_trend} x=operation_date y=cpo_idr_per_tonne yAxisTitle="IDR / tonne" yFmt="#,##0"/>

## Favorable operation-days by region

```sql by_region
select
    r.region_name,
    count(*) filter (where o.is_fertilize_favorable) as fertilize,
    count(*) filter (where o.is_harvest_favorable) as harvest,
    count(*) filter (where o.is_spray_favorable) as spray
from palm.operations_daily o
join palm.region r on o.region_key = r.region_key
group by r.region_name
order by r.region_name
```

<BarChart data={by_region} x=region_name y={['fertilize','harvest','spray']} type=grouped yAxisTitle="favorable days"/>

Explore further: the [Operations Planner](/operations) for per-region daily guidance, or the [Commodity Market](/market) for the palm-vs-soybean price story. Methodology and data lineage are on the [Methodology](/methodology) page.
