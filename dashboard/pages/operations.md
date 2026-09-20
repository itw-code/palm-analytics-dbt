---
title: Jadwal Operasi Harian
description: Panduan kerja harian per kebun — kapan hari panen efektif, kapan waktunya nyemprot dan mupuk.
---

{@partial "lang_toggle.md"}

{#if inputs.lang.value == 'en'}

Daily operating guidance per estate. An **effective harvest day** is a harvest-favorable day that is not a weekend or an Indonesian public holiday (the crew is actually available).

*Drill-down: [Today](/) → **Region** (this page, filter below) → Day (table) → [Action](/forecast).*

{:else}

Panduan kerja harian per kebun. **Hari panen efektif** itu gini: cuaca mendukung panen DAN timnya masuk — bukan Sabtu-Minggu, bukan tanggal merah.

*Alur: [Hari ini](/) → **Kebun** (halaman ini, pilih di bawah) → Tanggal (tabel) → [Kerjaan](/forecast).*

{/if}

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

{#if inputs.lang.value == 'en'}

<Grid cols=3>
  <BigValue data={planner_summary} value=effective_harvest_days title="Effective harvest days"/>
  <BigValue data={planner_summary} value=spray_days title="Spray days"/>
  <BigValue data={planner_summary} value=fertilize_days title="Fertilize days"/>
</Grid>

*Showing dates through <Value data={freshness} column=as_of fmt="yyyy-mm-dd"/> — filter by region above.*

## Daily recommendations

<DataTable data={planner} rows=20 search sortable>
    <Column id=operation_date title="Date"/>
    <Column id=region_name title="Estate"/>
    <Column id=precip_mm title="Rain (mm)"/>
    <Column id=humidity title="Humidity (%)" fmt="num0"/>
    <Column id=water_deficit_mm title="Deficit (mm)"/>
    <Column id=cpo_idr_per_tonne title="CPO (IDR/t)" fmt="#,##0"/>
    <Column id=harvest title="Harvest" contentType=colorindicator/>
    <Column id=spray title="Spray" contentType=colorindicator/>
    <Column id=fertilize title="Fertilize" contentType=colorindicator/>
    <Column id=effective_harvest title="Effective" contentType=colorindicator/>
</DataTable>

## Water deficit over time

Water deficit = ET0 − rain, in mm/day. Positive = drier than the crop wants.

```sql deficit
select operation_date, avg(water_deficit_mm) as avg_water_deficit_mm
from palm.operations_daily
where region_key like '${inputs.region.value}'
group by operation_date
order by operation_date
```

<LineChart data={deficit} x=operation_date y=avg_water_deficit_mm title="Average water deficit by day" xAxisTitle="Date" yAxisTitle="mm / day"/>

{:else}

<Grid cols=3>
  <BigValue data={planner_summary} value=effective_harvest_days title="Hari panen jalan"/>
  <BigValue data={planner_summary} value=spray_days title="Hari nyemprot"/>
  <BigValue data={planner_summary} value=fertilize_days title="Hari mupuk"/>
</Grid>

*Tanggal sampai <Value data={freshness} column=as_of fmt="yyyy-mm-dd"/> — ganti kebun di pilihan atas.*

## Saran harian

Ijo = gas, merah = tunda dulu. Kolom "Jalan" itu hasil akhirnya: cuaca oke + tim masuk.

<DataTable data={planner} rows=20 search sortable>
    <Column id=operation_date title="Tanggal"/>
    <Column id=region_name title="Kebun"/>
    <Column id=precip_mm title="Hujan (mm)"/>
    <Column id=humidity title="Lembap (%)" fmt="num0"/>
    <Column id=water_deficit_mm title="Defisit (mm)"/>
    <Column id=cpo_idr_per_tonne title="CPO (Rp/ton)" fmt="#,##0"/>
    <Column id=harvest title="Panen" contentType=colorindicator/>
    <Column id=spray title="Semprot" contentType=colorindicator/>
    <Column id=fertilize title="Pupuk" contentType=colorindicator/>
    <Column id=effective_harvest title="Jalan" contentType=colorindicator/>
</DataTable>

## Defisit air dari waktu ke waktu

Defisit air = penguapan (ET0) − hujan, satuannya mm/hari. Plus = lebih kering dari maunya sawit, daun bisa stres.

<LineChart data={deficit} x=operation_date y=avg_water_deficit_mm title="Rata-rata defisit air per hari" xAxisTitle="Tanggal" yAxisTitle="mm / hari"/>

{/if}
