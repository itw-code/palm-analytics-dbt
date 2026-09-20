---
title: Rencana 7 Hari ke Depan
description: Acuan kerja 7 hari ke depan — kebun mana kerjain apa, plus hari panen yang paling cuan.
---

{@partial "lang_toggle.md"}

{#if inputs.lang.value == 'en'}

Prescriptive outlook for the next 7 days — not what *happened*, but what to *do next*. Forecast weather comes from **Open-Meteo Forecast**, scored with the same agronomy rules as history. Prices are carried forward at the latest known value.

*Drill-down: [Today](/) → [Region](/operations) → [Day](/operations) → **Action** (this page: what to do next).*

{:else}

Bukan cerita kemarin — ini **perintah kerja 7 hari ke depan**. Ramalan cuaca dari **Open-Meteo**, aturannya sama persis kayak data kemarin jadi nggak bisa beda. Harga dianggap jalan di tempat (harga terakhir yang ketahuan).

*Alur: [Hari ini](/) → [Kebun](/operations) → [Tanggal](/operations) → **Kerjaan** (halaman ini: besok ngapain).*

{/if}

```sql forecast_freshness
select min(forecast_date) as next_date, max(forecast_date) as end_date, count(*) as rows from palm.forecast
```

{#if inputs.lang.value == 'en'}
<Alert status="info">Showing forecast <Value data={forecast_freshness} column=next_date fmt="yyyy-mm-dd"/> → <Value data={forecast_freshness} column=end_date fmt="yyyy-mm-dd"/> (<Value data={forecast_freshness} column=rows/> region-days). Prices assumed flat at last known value.</Alert>
{:else}
<Alert status="info">Ramalan <Value data={forecast_freshness} column=next_date fmt="yyyy-mm-dd"/> → <Value data={forecast_freshness} column=end_date fmt="yyyy-mm-dd"/> (<Value data={forecast_freshness} column=rows/> hari-kebun). Harga dianggap stagnan di angka terakhir.</Alert>
{/if}

{@partial "region_filter.md"}

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

{#if inputs.lang.value == 'en'}

<Grid cols=3>
  <BigValue data={forecast_summary} value=effective_harvest_days title="Effective harvest days"/>
  <BigValue data={forecast_summary} value=spray_days title="Spray days"/>
  <BigValue data={forecast_summary} value=fertilize_days title="Fertilize days"/>
</Grid>

## Next 7 days — action table

<DataTable data={forecast_table} rows=21>
    <Column id=forecast_date title="Date"/>
    <Column id=region_name title="Estate"/>
    <Column id=horizon_days title="H+"/>
    <Column id=precip_mm title="Rain (mm)"/>
    <Column id=humidity title="Humidity (%)" fmt="num0"/>
    <Column id=water_deficit_mm title="Deficit (mm)"/>
    <Column id=cpo_idr_per_tonne title="CPO (IDR/t)" fmt="#,##0"/>
    <Column id=harvest title="Harvest" contentType=colorindicator/>
    <Column id=spray title="Spray" contentType=colorindicator/>
    <Column id=fertilize title="Fertilize" contentType=colorindicator/>
    <Column id=effective_harvest title="Effective" contentType=colorindicator/>
</DataTable>

## Forecast rain outlook

```sql forecast_precip
select forecast_date, avg(precip_mm) as avg_precip_mm
from palm.forecast
where region_key like '${inputs.region.value}'
group by forecast_date
order by forecast_date
```

<BarChart data={forecast_precip} x=forecast_date y=avg_precip_mm title="Average forecast rain by day" xAxisTitle="Date" yAxisTitle="mm / day"/>

*Forecast weather from Open-Meteo. Horizon H+1 is tomorrow. Use alongside the [Operations Planner](/operations) (history) and [Market](/market) pages.*

{:else}

<Grid cols=3>
  <BigValue data={forecast_summary} value=effective_harvest_days title="Hari panen jalan"/>
  <BigValue data={forecast_summary} value=spray_days title="Hari nyemprot"/>
  <BigValue data={forecast_summary} value=fertilize_days title="Hari mupuk"/>
</Grid>

## Tabel kerja 7 hari ke depan

H+1 itu besok. Ijo = kerjain, merah = skip dulu.

<DataTable data={forecast_table} rows=21>
    <Column id=forecast_date title="Tanggal"/>
    <Column id=region_name title="Kebun"/>
    <Column id=horizon_days title="H+"/>
    <Column id=precip_mm title="Hujan (mm)"/>
    <Column id=humidity title="Lembap (%)" fmt="num0"/>
    <Column id=water_deficit_mm title="Defisit (mm)"/>
    <Column id=cpo_idr_per_tonne title="CPO (Rp/ton)" fmt="#,##0"/>
    <Column id=harvest title="Panen" contentType=colorindicator/>
    <Column id=spray title="Semprot" contentType=colorindicator/>
    <Column id=fertilize title="Pupuk" contentType=colorindicator/>
    <Column id=effective_harvest title="Jalan" contentType=colorindicator/>
</DataTable>

## Ramalan hujan

<BarChart data={forecast_precip} x=forecast_date y=avg_precip_mm title="Rata-rata ramalan hujan per hari" xAxisTitle="Tanggal" yAxisTitle="mm / hari"/>

*Ramalan cuaca dari Open-Meteo. H+1 = besok. Sandingkan sama [Jadwal Operasi](/operations) (catatan kemarin) dan [Pasar](/market).*

{/if}
