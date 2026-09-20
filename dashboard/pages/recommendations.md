---
title: Saran Panen
description: Hari panen peringkat terbaik, prakiraan harga 30 hari, simulasi margin, dan tanda anomali.
---

{@partial "lang_toggle.md"}

{#if inputs.lang.value == 'en'}

Ranked harvest-day guidance — which day to harvest, what could move the margin, and what looks anomalous. Powered by the Lane-2 decision marts.

{:else}

Hari apa paling cuan buat manen, apa yang bisa ngubah margin, dan apa yang kelihatan aneh. Ditenagai mart keputusan Lane-2.

{/if}

{@partial "region_filter.md"}

```sql best_days
select
    forecast_date,
    region_name,
    composite_score,
    recommendation
from palm.harvest_ranked
where region_key like '${inputs.region.value}'
  and is_best_day
order by forecast_date, region_name
```

{#if inputs.lang.value == 'en'}

## Best harvest days

<DataTable data={best_days} rows=15>
    <Column id=forecast_date fmt="yyyy-mm-dd"/>
    <Column id=region_name title="Estate"/>
    <Column id=composite_score fmt="0.00" title="Score"/>
    <Column id=recommendation title="Call"/>
</DataTable>

```sql ranked_detail
select
    forecast_date,
    region_name,
    weather_score,
    labour_score,
    price_score,
    composite_score,
    day_rank,
    recommendation
from palm.harvest_ranked
where region_key like '${inputs.region.value}'
order by forecast_date, day_rank
limit 60
```

## Score breakdown

Multiplicative score `weather x labour x price` — a hard blocker zeroes the day.

<DataTable data={ranked_detail} rows=15>
    <Column id=forecast_date fmt="yyyy-mm-dd"/>
    <Column id=region_name title="Estate"/>
    <Column id=weather_score fmt="0.00" title="Weather"/>
    <Column id=labour_score fmt="0.00" title="Labour"/>
    <Column id=price_score fmt="0.00" title="Price"/>
    <Column id=composite_score fmt="0.000" title="Composite"/>
    <Column id=day_rank fmt="#,##0" title="Rank"/>
    <Column id=recommendation title="Call"/>
</DataTable>

## 30-day CPO outlook

OLS trend on 60 days of prices, ±1.96σ band. Shallow slope is expected — monthly Pink-Sheet steps move slowly.

```sql forecast_band
select forecast_date, forecast_palm_usd, lower_usd, upper_usd
from palm.forecast30
order by forecast_date
```

<LineChart data={forecast_band} x=forecast_date y={['forecast_palm_usd','lower_usd','upper_usd']} title="CPO 30-day forecast" xAxisTitle="Date" yAxisTitle="USD / tonne" yFmt="$#,##0"/>

```sql shock_table
select
    scenario,
    region_name,
    palm_mult,
    fx_mult,
    shocked_palm_usd,
    shocked_usd_idr,
    shocked_cpo_idr,
    shocked_margin_idr_per_ha
from palm.whatif
where region_key like '${inputs.region.value}'
order by scenario, region_name
```

## Margin shocks

9 scenarios: palm price ±10/20% crossed with IDR ±10%.

<DataTable data={shock_table} rows=15>
    <Column id=scenario title="Scenario"/>
    <Column id=region_name title="Estate"/>
    <Column id=shocked_palm_usd fmt="$#,##0" title="Shocked palm (USD/t)"/>
    <Column id=shocked_usd_idr fmt="#,##0" title="Shocked USD/IDR"/>
    <Column id=shocked_cpo_idr fmt="#,##0" title="Shocked CPO (IDR/t)"/>
    <Column id=shocked_margin_idr_per_ha fmt="#,##0" title="Shocked margin (IDR/ha)"/>
</DataTable>

```sql anomaly_table
select
    operation_date,
    region_name,
    rain_14d_mm,
    deficit_14d_mm,
    is_rainfall_deficit,
    palm_mom_pct,
    is_price_spike
from palm.anomalies
where region_key like '${inputs.region.value}'
order by operation_date desc, region_name
limit 60
```

## Anomaly flags

Rainfall deficit (14-day rain below 20mm) and price spikes (MoM above 5%).

<DataTable data={anomaly_table} rows=15>
    <Column id=operation_date fmt="yyyy-mm-dd"/>
    <Column id=region_name title="Estate"/>
    <Column id=rain_14d_mm fmt="0.0" title="Rain 14d (mm)"/>
    <Column id=deficit_14d_mm fmt="0.0" title="Deficit (mm)"/>
    <Column id=palm_mom_pct fmt="0.0" title="Palm MoM (%)"/>
    <Column id=is_rainfall_deficit title="Rain deficit?"/>
    <Column id=is_price_spike title="Price spike?"/>
</DataTable>

{:else}

## Hari panen paling cuan

<DataTable data={best_days} rows=15>
    <Column id=forecast_date fmt="yyyy-mm-dd"/>
    <Column id=region_name title="Kebun"/>
    <Column id=composite_score fmt="0.00" title="Nilai"/>
    <Column id=recommendation title="Perintah"/>
</DataTable>

## Bedah nilainya

Nilainya kali-kalian `cuaca x tim x harga` — satu aja nol (misal tim libur), harinya langsung gugur.

<DataTable data={ranked_detail} rows=15>
    <Column id=forecast_date fmt="yyyy-mm-dd"/>
    <Column id=region_name title="Kebun"/>
    <Column id=weather_score fmt="0.00" title="Cuaca"/>
    <Column id=labour_score fmt="0.00" title="Tim"/>
    <Column id=price_score fmt="0.00" title="Harga"/>
    <Column id=composite_score fmt="0.000" title="Total"/>
    <Column id=day_rank fmt="#,##0" title="Urutan"/>
    <Column id=recommendation title="Perintah"/>
</DataTable>

## Prakiraan CPO 30 hari

Tren garis dari 60 hari harga, pita ±1.96σ. Landai itu wajar — harga Bank Dunia geraknya bulanan, pelan.

<LineChart data={forecast_band} x=forecast_date y={['forecast_palm_usd','lower_usd','upper_usd']} title="Prakiraan CPO 30 hari" xAxisTitle="Tanggal" yAxisTitle="USD / ton" yFmt="$#,##0"/>

## Simulasi margin

9 skenario: harga sawit ±10/20% disilang sama rupiah ±10%. Biar kebayang kalau pasar goyang, cuan ikut goyang seberapa.

<DataTable data={shock_table} rows=15>
    <Column id=scenario title="Skenario"/>
    <Column id=region_name title="Kebun"/>
    <Column id=shocked_palm_usd fmt="$#,##0" title="Sawit goyang (USD/ton)"/>
    <Column id=shocked_usd_idr fmt="#,##0" title="USD/IDR goyang"/>
    <Column id=shocked_cpo_idr fmt="#,##0" title="CPO goyang (Rp/ton)"/>
    <Column id=shocked_margin_idr_per_ha fmt="#,##0" title="Margin goyang (Rp/ha)"/>
</DataTable>

## Tanda aneh-aneh

Kekeringan (hujan 14 hari di bawah 20mm) sama lonjakan harga (naik di atas 5% sebulan).

<DataTable data={anomaly_table} rows=15>
    <Column id=operation_date fmt="yyyy-mm-dd"/>
    <Column id=region_name title="Kebun"/>
    <Column id=rain_14d_mm fmt="0.0" title="Hujan 14hr (mm)"/>
    <Column id=deficit_14d_mm fmt="0.0" title="Defisit (mm)"/>
    <Column id=palm_mom_pct fmt="0.0" title="Naik sebulan (%)"/>
    <Column id=is_rainfall_deficit title="Kering?"/>
    <Column id=is_price_spike title="Harga loncat?"/>
</DataTable>

{/if}
