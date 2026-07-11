---
title: Operations Planner
---

Per-region daily operating guidance. An **effective harvest day** is a harvest-favorable day that is not a weekend or an Indonesian public holiday (labour is available).

```sql regions_list
select region_key, region_name from palm.region order by region_name
```

<Dropdown name=region data={regions_list} value=region_key label=region_name title="Region" defaultValue="%">
    <DropdownOption valueLabel="All regions" value="%" />
</Dropdown>

```sql planner
select
    o.operation_date,
    r.region_name,
    round(o.precip_mm, 1) as precip_mm,
    round(o.humidity_pct, 0) as humidity_pct,
    round(o.water_deficit_mm, 1) as water_deficit_mm,
    o.is_fertilize_favorable as fertilize,
    o.is_harvest_favorable as harvest,
    o.is_spray_favorable as spray,
    o.is_effective_harvest_day as effective_harvest,
    o.cpo_idr_per_tonne
from palm.operations_daily o
join palm.region r on o.region_key = r.region_key
where o.region_key like '${inputs.region.value}'
order by o.operation_date desc
```

```sql planner_summary
select
    count(*) filter (where is_effective_harvest_day) as effective_harvest_days,
    count(*) filter (where is_spray_favorable) as spray_days,
    count(*) filter (where is_fertilize_favorable) as fertilize_days
from palm.operations_daily
where region_key like '${inputs.region.value}'
```

<BigValue data={planner_summary} value=effective_harvest_days title="Effective harvest days"/>
<BigValue data={planner_summary} value=spray_days title="Spray days"/>
<BigValue data={planner_summary} value=fertilize_days title="Fertilize days"/>

## Daily recommendations

<DataTable data={planner} rows=15>
    <Column id=operation_date title="Date"/>
    <Column id=region_name title="Region"/>
    <Column id=precip_mm title="Precip (mm)"/>
    <Column id=humidity_pct title="Humidity (%)"/>
    <Column id=harvest contentType=colorindicator/>
    <Column id=spray contentType=colorindicator/>
    <Column id=fertilize contentType=colorindicator/>
    <Column id=effective_harvest contentType=colorindicator/>
</DataTable>

## Water deficit (ET0 − precipitation) over time

```sql deficit
select operation_date, avg(water_deficit_mm) as avg_water_deficit_mm
from palm.operations_daily
where region_key like '${inputs.region.value}'
group by operation_date
order by operation_date
```

<LineChart data={deficit} x=operation_date y=avg_water_deficit_mm yAxisTitle="mm (positive = drier than crop demand)"/>
