---
title: Palm Estate Operations
---

Daily operational guidance for Indonesian palm-oil estates - which activities are favorable by region, alongside the crude palm oil (CPO) price that sets the value of a good harvest day. Data flows Open-Meteo + World Bank → DuckDB → dbt → this dashboard.

```sql latest_price
select operation_date, max(cpo_usd_per_tonne) as cpo_usd_per_tonne
from palm.operations_daily
group by operation_date
order by operation_date desc
limit 1
```

```sql favorable_counts
select
    count(*) filter (where is_harvest_favorable) as harvest_days,
    count(*) filter (where is_fertilize_favorable) as fertilize_days,
    count(*) filter (where is_spray_favorable) as spray_days
from palm.operations_daily
```

<BigValue data={latest_price} value=cpo_usd_per_tonne fmt="usd0" title="Latest CPO price (USD/tonne)"/>
<BigValue data={favorable_counts} value=harvest_days title="Harvest-favorable region-days"/>
<BigValue data={favorable_counts} value=spray_days title="Spray-favorable region-days"/>

## CPO price trend

```sql cpo_trend
select distinct operation_date, cpo_usd_per_tonne
from palm.operations_daily
order by operation_date
```

<LineChart data={cpo_trend} x=operation_date y=cpo_usd_per_tonne yAxisTitle="USD / tonne"/>

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

## Recent daily detail

```sql recent
select
    o.operation_date,
    r.region_name,
    round(o.temp_mean_c, 1) as temp_c,
    round(o.precip_mm, 1) as precip_mm,
    o.is_harvest_favorable as harvest_ok,
    o.is_spray_favorable as spray_ok,
    round(o.cpo_usd_per_tonne, 0) as cpo_usd
from palm.operations_daily o
join palm.region r on o.region_key = r.region_key
order by o.operation_date desc, r.region_name
limit 30
```

<DataTable data={recent} rows=10/>
