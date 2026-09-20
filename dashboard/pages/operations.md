---
title: Operations Planner
description: Per-region daily operating guidance — effective harvest days, spray and fertilize windows.
---

Per-region daily operating guidance · Panduan operasi harian per wilayah. An **effective harvest day** is a harvest-favorable day that is not a weekend or an Indonesian public holiday (labour is available).

*Drill-down: [National](/ ) → **Region · Wilayah** (this page, filter below) → Day · Hari (table) → [Operation · Tindakan](/forecast).*

{@partial "ops_freshness.md"}

{@partial "region_filter.md"}

```sql planner
select
    o.operation_date,
    r.region_name,
    round(o.precip_mm, 1) as precip_mm,
    round(o.humidity_pct, 0) as humidity,
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

<Grid cols=3>
  <BigValue data={planner_summary} value=effective_harvest_days title="Effective harvest days · Hari panen efektif"/>
  <BigValue data={planner_summary} value=spray_days title="Spray days · Hari semprot"/>
  <BigValue data={planner_summary} value=fertilize_days title="Fertilize days · Hari pupuk"/>
</Grid>

*Showing dates through <Value data={freshness} column=as_of fmt="yyyy-mm-dd"/> — filter by region above.*

## Daily recommendations · Rekomendasi harian

<DataTable data={planner} rows=20 search sortable>
    <Column id=operation_date title="Date · Tgl"/>
    <Column id=region_name title="Region · Wilayah"/>
    <Column id=precip_mm title="Precip (mm) · Hujan"/>
    <Column id=humidity title="Humidity (%) · Kelembapan" fmt="num0"/>
    <Column id=water_deficit_mm title="Deficit (mm) · Defisit"/>
    <Column id=cpo_idr_per_tonne title="CPO (IDR/t)" fmt="#,##0"/>
    <Column id=harvest title="Harvest · Panen" contentType=colorindicator/>
    <Column id=spray title="Spray · Semprot" contentType=colorindicator/>
    <Column id=fertilize title="Fertilize · Pupuk" contentType=colorindicator/>
    <Column id=effective_harvest title="Effective · Efektif" contentType=colorindicator/>
</DataTable>

## Water deficit over time · Defisit air

Water deficit = ET0 − precipitation, in mm/day. Positive = drier than crop demand.

```sql deficit
select operation_date, avg(water_deficit_mm) as avg_water_deficit_mm
from palm.operations_daily
where region_key like '${inputs.region.value}'
group by operation_date
order by operation_date
```

<LineChart data={deficit} x=operation_date y=avg_water_deficit_mm title="Average water deficit by day" xAxisTitle="Date" yAxisTitle="mm / day"/>
