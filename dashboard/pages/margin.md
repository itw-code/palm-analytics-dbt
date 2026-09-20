---
title: Cuan per Hektar
description: Laba-rugi per hektar per kebun per hari — pemasukan, biaya, dan margin dari harga dan rendemen.
---

{@partial "lang_toggle.md"}

{#if inputs.lang.value == 'en'}

P&L per hectare, derived from the same price + yield + extraction rate that powers the operations planner, minus seeded cost assumptions. On non-effective days you still carry fertilizer cost. Replace `seeds/cost_assumptions.csv` with your estate's actuals and every number recomputes.

*Drill-down: [Today](/) → [Region](/operations) → [Day](/operations) → **Margin value** (this page).*

{:else}

Laba-rugi per hektar — dari harga + tonase + rendemen yang sama kayak di jadwal operasi, dikurangi biaya kebun. Hari nggak panen pun biaya pupuk tetap jalan. Ganti `seeds/cost_assumptions.csv` sama angka kebunmu sendiri, semua angka ngikut berubah.

*Alur: [Hari ini](/) → [Kebun](/operations) → [Tanggal](/operations) → **Cuan** (halaman ini).*

{/if}

{@partial "region_filter.md"}

```sql margin_recent
select
    m.operation_date,
    r.region_name,
    m.revenue_idr_per_ha,
    m.margin_idr_per_ha,
    m.margin_total_idr,
    m.is_effective_harvest_day
from palm.margin m
join palm.region r on m.region_key = r.region_key
where m.region_key like '${inputs.region.value}'
order by m.operation_date desc
limit 30
```

{#if inputs.lang.value == 'en'}

<DataTable data={margin_recent} rows=15>
    <Column id=operation_date title="Date"/>
    <Column id=region_name title="Estate"/>
    <Column id=revenue_idr_per_ha title="Revenue/ha (IDR)" fmt="#,##0"/>
    <Column id=margin_idr_per_ha title="Margin/ha (IDR)" fmt="#,##0"/>
    <Column id=margin_total_idr title="Margin total (IDR)" fmt="#,##0"/>
    <Column id=is_effective_harvest_day title="Harvest day" contentType=colorindicator/>
</DataTable>

## Margin trend

```sql margin_trend
select operation_date, avg(margin_idr_per_ha) as avg_margin_ha
from palm.margin
where region_key like '${inputs.region.value}'
group by operation_date
order by operation_date
```

<LineChart data={margin_trend} x=operation_date y=avg_margin_ha title="Average margin per hectare by day" xAxisTitle="Date" yAxisTitle="IDR / ha" yFmt="#,##0"/>

*Formula: `revenue = CPO_IDR * yield * extraction_rate` (only on effective harvest days); `margin_per_ha = revenue - fertilizer - harvest - transport`, else `-fertilizer`. Edit `cost_assumptions.csv` and the margin rebuilds everywhere.*

{:else}

<DataTable data={margin_recent} rows=15>
    <Column id=operation_date title="Tanggal"/>
    <Column id=region_name title="Kebun"/>
    <Column id=revenue_idr_per_ha title="Masuk/ha (Rp)" fmt="#,##0"/>
    <Column id=margin_idr_per_ha title="Bersih/ha (Rp)" fmt="#,##0"/>
    <Column id=margin_total_idr title="Bersih total (Rp)" fmt="#,##0"/>
    <Column id=is_effective_harvest_day title="Panen" contentType=colorindicator/>
</DataTable>

## Tren cuan

<LineChart data={margin_trend} x=operation_date y=avg_margin_ha title="Rata-rata cuan per hektar per hari" xAxisTitle="Tanggal" yAxisTitle="Rp / ha" yFmt="#,##0"/>

*Rumusnya: `masuk = CPO_Rp * tonase * rendemen` (cuma jalan pas hari panen efektif); `bersih_per_ha = masuk - pupuk - panen - angkut`, kalau nggak panen ya `-pupuk`. Ubah `cost_assumptions.csv`, margin ngitung ulang semua.*

{/if}
