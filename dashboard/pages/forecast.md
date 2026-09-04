---
title: 7-Day Forward Planner
---

Prescriptive outlook for the next 7 days · Prakiraan 7 hari — not what *happened*, but what to *do next*. Forecast weather comes from **Open-Meteo Forecast** (or Historical-Forecast for deterministic CI), with the same agronomy rules as the historical planner. Prices are carried forward at the latest known value.

*Drill-down: [National](/) → [Region](/operations) → [Day](/operations) → **Operation · Tindakan** (this page: what to do next).*

```sql forecast_freshness
select min(forecast_date) as next_date, max(forecast_date) as end_date, count(*) as rows from palm.forecast
```

<Alert status="info">Showing forecast <Value data={forecast_freshness} column=next_date fmt="yyyy-mm-dd"/> → <Value data={forecast_freshness} column=end_date fmt="yyyy-mm-dd"/> (<Value data={forecast_freshness} column=rows/> region-days). Prices assumed flat at last known value.</Alert>

```sql regions_list
select region_key, region_name from palm.region order by region_name
```

<Dropdown name=region data={regions_list} value=region_key label=region_name title="Region" defaultValue="%">
    <DropdownOption valueLabel="All regions" value="%" />
</Dropdown>

```sql forecast_table
select
    f.forecast_date,
    r.region_name,
    f.horizon_days,
    round(f.precip_mm, 1) as precip_mm,
    round(f.humidity_pct, 0) as humidity,
    round(f.water_deficit_mm, 1) as water_deficit_mm,
    f.is_fertilize_favorable as fertilize,
    f.is_harvest_favorable as harvest,
    f.is_spray_favorable as spray,
    f.is_effective_harvest_day as effective_harvest,
    f.cpo_idr_per_tonne
from palm.forecast f
join palm.region r on f.region_key = r.region_key
where f.region_key like '${inputs.region.value}'
order by f.forecast_date
```

```sql forecast_summary
select
    count(*) filter (where is_effective_harvest_day) as effective_harvest_days,
    count(*) filter (where is_spray_favorable) as spray_days,
    count(*) filter (where is_fertilize_favorable) as fertilize_days
from palm.forecast
where region_key like '${inputs.region.value}'
```

<Grid cols=3>
  <BigValue data={forecast_summary} value=effective_harvest_days title="Effective harvest days · Hari panen"/>
  <BigValue data={forecast_summary} value=spray_days title="Spray days · Hari semprot"/>
  <BigValue data={forecast_summary} value=fertilize_days title="Fertilize days · Hari pupuk"/>
</Grid>

## Next 7 days — action table · Tabel tindakan

<DataTable data={forecast_table} rows=21>
    <Column id=forecast_date title="Date · Tgl"/>
    <Column id=region_name title="Region · Wilayah"/>
    <Column id=horizon_days title="H+"/>
    <Column id=precip_mm title="Precip (mm) · Hujan"/>
    <Column id=humidity title="Humidity (%) · Kelembapan" fmt="num0"/>
    <Column id=water_deficit_mm title="Deficit (mm) · Defisit"/>
    <Column id=cpo_idr_per_tonne title="CPO (IDR/t)" fmt="#,##0"/>
    <Column id=harvest title="Harvest · Panen" contentType=colorindicator/>
    <Column id=spray title="Spray · Semprot" contentType=colorindicator/>
    <Column id=fertilize title="Fertilize · Pupuk" contentType=colorindicator/>
    <Column id=effective_harvest title="Effective · Efektif" contentType=colorindicator/>
</DataTable>

## Forecast precipitation outlook · Prakiraan hujan

```sql forecast_precip
select forecast_date, avg(precip_mm) as avg_precip_mm
from palm.forecast
where region_key like '${inputs.region.value}'
group by forecast_date
order by forecast_date
```

<BarChart data={forecast_precip} x=forecast_date y=avg_precip_mm title="Average forecast precipitation by day" xAxisTitle="Date" yAxisTitle="mm / day"/>

*Forecast weather from Open-Meteo. Horizon H+1 is tomorrow. Use alongside the [Operations Planner](/operations) (historical) and [Market](/market) pages.*
