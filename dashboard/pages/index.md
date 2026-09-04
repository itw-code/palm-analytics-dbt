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

```sql top_region
select
    r.region_name,
    count(*) filter (where o.is_effective_harvest_day) as eff_days,
    count(*) as total_days
from palm.operations_daily o
join palm.region r on o.region_key = r.region_key
group by r.region_name
order by eff_days desc
limit 1
```

```sql harvest_value
select round(avg(harvest_day_value_idr), 0) as avg_value_idr
from palm.operations_daily
where is_effective_harvest_day
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

## At a glance · Sekilas

<Grid cols=2>
  <BigValue data={headline} value=cpo_usd fmt="usd0" title="CPO price · Harga CPO (USD/t)"/>
  <BigValue data={headline} value=cpo_idr fmt="#,##0" title="CPO price · Harga CPO (IDR/t)"/>
  <BigValue data={favorable_counts} value=effective_harvest_days title="Effective harvest days · Hari panen efektif"/>
  <BigValue data={favorable_counts} value=spray_days title="Spray-favorable days · Hari semprot"/>
</Grid>

> **Insight · Wawasan:** **<Value data={top_region} column=region_name/>** leads with **<Value data={top_region} column=eff_days/>** effective harvest days, and each good harvest day is worth ≈ **Rp<Value data={harvest_value} column=avg_value_idr fmt="#,##0"/>/ha** — deploy labour there first, then check the day-by-day plan in the [Operations Planner](/operations).

*Data as of <Value data={freshness} column=as_of fmt="yyyy-mm-dd"/> — refreshed daily at 00:00 UTC via GitHub Actions. Commodity prices are live World Bank Pink Sheet data (see Methodology).*

## Drill-down path · Alur telaah

1. **National · Nasional** (this page) — hero KPIs and price trend above.
2. **Region · Wilayah** — the chart below, then the [Operations Planner](/operations) filtered per region.
3. **Day · Hari** — the daily recommendations table in Operations.
4. **Operation · Tindakan** — what to do next in the [7-Day Forward Planner](/forecast), and what it is worth in [Margin](/margin).

## Palm price trend · Tren harga CPO

```sql price_trend
select distinct operation_date, cpo_idr_per_tonne
from palm.operations_daily
where cpo_idr_per_tonne is not null
order by operation_date
```

<LineChart data={price_trend} x=operation_date y=cpo_idr_per_tonne title="CPO price per tonne" xAxisTitle="Date" yAxisTitle="IDR / tonne" yFmt="#,##0"/>

## Favorable operation-days by region · Hari operasi per wilayah

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

<BarChart data={by_region} x=region_name y={['fertilize','harvest','spray']} type=grouped title="Favorable days by operation and region" xAxisTitle="Region · Wilayah" yAxisTitle="Favorable days"/>

Explore further: the [7-Day Forward Planner](/forecast) for prescriptive next-week actions, the [Operations Planner](/operations) for per-region daily guidance, or the [Commodity Market](/market) for the palm-vs-soybean price story. Methodology and data lineage are on the [Methodology](/methodology) page.
