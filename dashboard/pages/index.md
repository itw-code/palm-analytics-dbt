---
title: Palm Estate Operations
---

Decision-support for Indonesian palm-oil estates: what operations are favorable by region, and what a good harvest day is worth in both USD and local currency. Data flows **Open-Meteo + Frankfurter + Nager.Date + World Bank → DuckDB → dbt → this dashboard**.

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

<BigValue data={headline} value=cpo_usd fmt="usd0" title="Palm price (USD/tonne)"/>
<BigValue data={headline} value=cpo_idr fmt="#,##0" title="Palm price (IDR/tonne)"/>
<BigValue data={favorable_counts} value=effective_harvest_days title="Effective harvest days"/>
<BigValue data={favorable_counts} value=spray_days title="Spray-favorable days"/>

## Palm price trend (local currency)

```sql price_trend
select distinct operation_date, cpo_idr_per_tonne
from palm.operations_daily
where cpo_idr_per_tonne is not null
order by operation_date
```

<LineChart data={price_trend} x=operation_date y=cpo_idr_per_tonne yAxisTitle="IDR / tonne"/>

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
