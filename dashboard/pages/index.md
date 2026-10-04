---
title: Hari Ini · Operasi Kebun Sawit
description: Keputusan pagi buat kebun sawit Indonesia — kapan mupuk, manen, atau nyemprot per wilayah, plus berapa cuan sehari panen yang bagus.
---

{@partial "lang_toggle.md"}

{#if inputs.lang.value == 'en'}

<div style="display:flex;gap:28px;align-items:center;flex-wrap:wrap;border-left:3px solid #1F7A80;padding-left:20px;margin:8px 0 4px 0;">
<div style="flex:1 1 320px;min-width:260px;">
<p style="letter-spacing:0.14em;font-size:12px;font-weight:700;color:#1F7A80;margin:0 0 8px 0;">PALM ESTATE OPERATIONS · INDONESIA</p>
<p style="font-family:Georgia,'Palatino Linotype',serif;font-size:clamp(24px,3.4vw,34px);line-height:1.25;font-weight:700;margin:0 0 10px 0;">Every morning at 06:00 WIB, an estate manager decides: fertilize, harvest, or spray — per region.</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 10px 0;">A wrong day wastes fertilizer, loses yield, and idles labour. This page turns today's weather, price, and labour availability into a go/no-go per region — and prices what a good harvest day is worth.</p>
<p style="font-size:13px;opacity:0.75;margin:0 0 14px 0;">Open-Meteo + Frankfurter + Nager.Date + World Bank → DuckDB → dbt → this page. Refreshed daily.</p>
<a href="/forecast" style="display:inline-block;background:#1F7A80;color:#F7F4EE;padding:10px 18px;border-radius:3px;text-decoration:none;font-weight:600;font-size:14px;">Open the 7-day plan →</a>
</div>
</div>

{:else}

<div style="display:flex;gap:28px;align-items:center;flex-wrap:wrap;border-left:3px solid #1F7A80;padding-left:20px;margin:8px 0 4px 0;">
<div style="flex:1 1 320px;min-width:260px;">
<p style="letter-spacing:0.14em;font-size:12px;font-weight:700;color:#1F7A80;margin:0 0 8px 0;">OPERASI KEBUN SAWIT · INDONESIA</p>
<p style="font-family:Georgia,'Palatino Linotype',serif;font-size:clamp(24px,3.4vw,34px);line-height:1.25;font-weight:700;margin:0 0 10px 0;">Tiap pagi jam 06:00 WIB, mandor putuskan: hari ini mupuk, manen, atau nyemprot — per kebun.</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 10px 0;">Salah hari = pupuk kebuang, buah kepanen jelek, tim nganggur dibayar. Halaman ini ngubah cuaca hari ini + harga + ketersediaan tim jadi lampu hijau/merah per kebun — plus ngitung sehari panen yang bagus itu cuannya berapa.</p>
<p style="font-size:13px;opacity:0.75;margin:0 0 14px 0;">Cuaca + kurs + hari libur + harga CPO → diolah dbt → jadi halaman ini. Update tiap hari.</p>
<a href="/forecast" style="display:inline-block;background:#1F7A80;color:#F7F4EE;padding:10px 18px;border-radius:3px;text-decoration:none;font-weight:600;font-size:14px;">Buka rencana 7 hari →</a>
</div>
<svg width="200" height="150" viewBox="0 0 200 150" fill="none" aria-hidden="true" style="flex:0 0 auto;opacity:0.4;">
<path d="M-5,25 Q50,12 105,24 T205,20" stroke="#1F7A80" stroke-width="1.5"/>
<path d="M-5,50 Q50,38 105,49 T205,45" stroke="#1F7A80" stroke-width="1.5"/>
<path d="M-5,75 Q50,63 105,74 T205,70" stroke="#8B5E34" stroke-width="1.5"/>
<path d="M-5,100 Q50,88 105,99 T205,95" stroke="#1F7A80" stroke-width="1.5"/>
<path d="M-5,125 Q50,113 105,124 T205,120" stroke="#8B5E34" stroke-width="1.5"/>
<ellipse cx="150" cy="52" rx="16" ry="10" stroke="#1F7A80" stroke-width="1.5"/>
<ellipse cx="150" cy="52" rx="7" ry="4" stroke="#1F7A80" stroke-width="1.5"/>
</svg>
</div>

{/if}

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

{#if inputs.lang.value == 'en'}

## How the call gets made

<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:4px 0 8px 0;">
<div style="border:1px solid rgba(127,127,127,.35);border-radius:10px;padding:12px 14px;">
<p style="font-weight:700;margin:0 0 4px 0;">1 · Weather</p>
<p style="font-size:13.5px;line-height:1.55;margin:0;">Daily weather plus a 7-day forecast per region — rain, humidity, water deficit. Same agronomy rules score history and forecast, so they can never disagree.</p>
</div>
<div style="border:1px solid rgba(127,127,127,.35);border-radius:10px;padding:12px 14px;">
<p style="font-weight:700;margin:0 0 4px 0;">2 · Labour</p>
<p style="font-size:13.5px;line-height:1.55;margin:0;">Weekends and Indonesian public holidays decide whether a harvest-favorable day is actually workable. That filter is what makes a day <em>effective</em>.</p>
</div>
<div style="border:1px solid rgba(127,127,127,.35);border-radius:10px;padding:12px 14px;">
<p style="font-weight:700;margin:0 0 4px 0;">3 · Money</p>
<p style="font-size:13.5px;line-height:1.55;margin:0;">World Bank palm/soy prices in USD, converted at the daily reference rate, priced per hectare against seeded estate costs.</p>
</div>
</div>

> **Today's call:** **<Value data={top_region} column=region_name/>** leads with **<Value data={top_region} column=eff_days/>** effective harvest days, and each good day is worth ≈ **Rp<Value data={harvest_value} column=avg_value_idr fmt="#,##0"/>/ha** — deploy labour there first, then work the day-by-day plan in the [7-day forecast](/forecast).

## At a glance

<Grid cols=3>
  <BigValue data={headline} value=cpo_idr fmt="#,##0" title="CPO price today (IDR/t)"/>
  <BigValue data={favorable_counts} value=effective_harvest_days title="Workable harvest days on record"/>
  <BigValue data={harvest_value} value=avg_value_idr fmt="#,##0" title="Avg value of a good day (Rp/ha)"/>
</Grid>

## Palm price trend

Pink Sheet prices move monthly — flat steps are correct, not missing data. The pipeline carries the last known price forward to daily grain.

```sql price_trend
select distinct operation_date, cpo_idr_per_tonne
from palm.operations_daily
where cpo_idr_per_tonne is not null
order by operation_date
```

<LineChart data={price_trend} x=operation_date y=cpo_idr_per_tonne title="CPO price per tonne (monthly steps carried forward)" xAxisTitle="Date" yAxisTitle="IDR / tonne" yFmt="#,##0"/>

## Workable days by region and operation

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

<BarChart data={by_region} x=region_name y={['fertilize','harvest','spray']} type=grouped title="Favorable days by operation and region" xAxisTitle="Region" yAxisTitle="Favorable days"/>

## Start here — six minutes

1. **What to do next (2 min)** — the [7-day forward plan](/forecast): prescriptive per-region actions, H+1 to H+7.
2. **What happened (2 min)** — the [operations planner](/operations): per-region daily history behind today's call.
3. **What it's worth (1 min)** — [margin per hectare](/margin) and the [palm-vs-soy market](/market): the price story in local currency.
4. **Why trust it (1 min)** — [methodology](/methodology) for the pipeline, [trust page](/status) for freshness, lake snapshot, and test counts.

{:else}

## Gimana keputusannya dibuat

<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:4px 0 8px 0;">
<div style="border:1px solid rgba(127,127,127,.35);border-radius:10px;padding:12px 14px;">
<p style="font-weight:700;margin:0 0 4px 0;">1 · Cuaca</p>
<p style="font-size:13.5px;line-height:1.55;margin:0;">Cuaca harian + ramalan 7 hari per kebun — hujan, kelembapan, defisit air. Aturan mainnya sama buat data kemarin dan ramalan besok, jadi nggak mungkin beda pendapat.</p>
</div>
<div style="border:1px solid rgba(127,127,127,.35);border-radius:10px;padding:12px 14px;">
<p style="font-weight:700;margin:0 0 4px 0;">2 · Tim panen</p>
<p style="font-size:13.5px;line-height:1.55;margin:0;">Sabtu-Minggu sama tanggal merah dicek dulu — cuaca bagus tapi tim libur ya percuma. Lolos filter ini baru namanya <em>hari panen efektif</em>.</p>
</div>
<div style="border:1px solid rgba(127,127,127,.35);border-radius:10px;padding:12px 14px;">
<p style="font-weight:700;margin:0 0 4px 0;">3 · Duit</p>
<p style="font-size:13.5px;line-height:1.55;margin:0;">Harga sawit/kedelai Bank Dunia (USD) dikali kurs hari itu, terus dihitung per hektar lawan biaya kebun.</p>
</div>
</div>

> **Keputusan hari ini:** **<Value data={top_region} column=region_name/>** paling gas — **<Value data={top_region} column=eff_days/>** hari panen efektif, sehari yang bagus cuannya ≈ **Rp<Value data={harvest_value} column=avg_value_idr fmt="#,##0"/>/ha**. Kirim tim ke sana dulu, detail hariannya cek di [ramalan 7 hari](/forecast).

## Sekilas

<Grid cols=3>
  <BigValue data={headline} value=cpo_idr fmt="#,##0" title="Harga CPO hari ini (Rp/ton)"/>
  <BigValue data={favorable_counts} value=effective_harvest_days title="Hari panen jalan tercatat"/>
  <BigValue data={harvest_value} value=avg_value_idr fmt="#,##0" title="Rata-rata cuan sehari bagus (Rp/ha)"/>
</Grid>

## Tren harga sawit

Harga Bank Dunia keluarnya bulanan — jadi grafiknya tangga datar itu normal, bukan data hilang. Sistem bawa harga terakhir maju ke tiap hari.

<LineChart data={price_trend} x=operation_date y=cpo_idr_per_tonne title="Harga CPO per ton (tangga bulanan dibawa maju)" xAxisTitle="Tanggal" yAxisTitle="Rp / ton" yFmt="#,##0"/>

## Hari bagus per kebun dan kerjaan

<BarChart data={by_region} x=region_name y={['fertilize','harvest','spray']} type=grouped title="Hari mendukung per kerjaan dan kebun" xAxisTitle="Kebun" yAxisTitle="Jumlah hari"/>

## Mulai dari sini — enam menit

1. **Mau ngapain besok (2 mnt)** — [rencana 7 hari](/forecast): kerjaan apa per kebun, H+1 sampai H+7.
2. **Kemarin gimana (2 mnt)** — [jadwal operasi](/operations): catatan harian per kebun yang jadi dasar keputusan hari ini.
3. **Cuannya berapa (1 mnt)** — [margin per hektar](/margin) dan [pasar sawit vs kedelai](/market): cerita harga dalam rupiah.
4. **Kok bisa dipercaya (1 mnt)** — [cara kerja](/methodology) buat daleman pipa datanya, [halaman pantauan](/status) buat kesegaran data dan hasil tes.

{/if}

{#if freshness[0].days_stale > 3}
{#if inputs.lang.value == 'en'}
<Alert status="warning" title="Data may be stale">
  Last successful refresh was <Value data={freshness} column=as_of fmt="yyyy-mm-dd"/> — that's <Value data={freshness} column=days_stale/> days ago. Scheduled daily refresh runs at 00:00 UTC; check the <a href="https://github.com/itw-code/palm-analytics-dbt/actions">Actions</a> tab for failures.
</Alert>
{:else}
<Alert status="warning" title="Data mungkin basi">
  Update terakhir <Value data={freshness} column=as_of fmt="yyyy-mm-dd"/> — sudah <Value data={freshness} column=days_stale/> hari lalu. Jadwal update tiap jam 00:00 UTC; cek tab <a href="https://github.com/itw-code/palm-analytics-dbt/actions">Actions</a> kalau ada yang gagal.
</Alert>
{/if}
{/if}

{#if inputs.lang.value == 'en'}
<p><em>Data as of <Value data={freshness} column=as_of fmt="yyyy-mm-dd"/> — refreshed daily at 00:00 UTC. Freshness, lake snapshot, and test counts live on the <a href="/status">trust page</a>.</em></p>
{:else}
<p><em>Data per <Value data={freshness} column=as_of fmt="yyyy-mm-dd"/> — update tiap hari jam 00:00 UTC. Kesegaran data dan hasil tes ada di <a href="/status">halaman pantauan</a>.</em></p>
{/if}
