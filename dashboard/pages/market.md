---
title: Pasar Sawit
description: Harga sawit vs minyak kedelai, selisih substitusi, dan kurs USD/IDR.
---

{@partial "lang_toggle.md"}

{#if inputs.lang.value == 'en'}

Palm oil does not trade in isolation — **soybean oil** is its closest substitute, so the palm-vs-soy spread drives buyer switching, and the USD/IDR rate decides what a USD-quoted price is actually worth to an Indonesian estate.

{:else}

Sawit itu nggak jalan sendirian — **minyak kedelai** itu saingan terdekatnya. Kalau selisihnya melebar, pembeli pindah ke kedelai. Terus kurs USD/IDR yang nentuin harga dolar itu jadinya berapa rupiah di tangan kebun.

{/if}

```sql market
select
    price_date,
    palm_oil_usd,
    soybean_oil_usd,
    palm_soy_spread_usd,
    usd_idr,
    palm_oil_idr
from palm.commodity
order by price_date
```

```sql market_now
select palm_oil_usd, soybean_oil_usd, palm_soy_spread_usd, usd_idr
from palm.commodity
order by price_date desc
limit 1
```

{#if inputs.lang.value == 'en'}

<Grid cols=2>
  <BigValue data={market_now} value=palm_oil_usd fmt="$#,##0" title="Palm oil (USD/t)"/>
  <BigValue data={market_now} value=soybean_oil_usd fmt="$#,##0" title="Soybean oil (USD/t)"/>
  <BigValue data={market_now} value=palm_soy_spread_usd fmt="$#,##0" title="Palm − Soy spread (USD/t)"/>
  <BigValue data={market_now} value=usd_idr fmt="#,##0" title="USD/IDR (IDR)"/>
</Grid>

## Palm vs soybean oil

<LineChart data={market} x=price_date y={['palm_oil_usd','soybean_oil_usd']} title="Palm vs soybean oil price" xAxisTitle="Date" yAxisTitle="USD / tonne" yFmt="$#,##0"/>

## Palm − soybean substitution spread

A negative spread means palm trades at a discount to soybean oil (palm looks attractive to buyers).

<LineChart data={market} x=price_date y=palm_soy_spread_usd title="Palm minus soybean spread" xAxisTitle="Date" yAxisTitle="USD / tonne" yFmt="$#,##0"/>

## USD/IDR exchange rate

<LineChart data={market} x=price_date y=usd_idr title="USD/IDR exchange rate" xAxisTitle="Date" yAxisTitle="IDR per USD" yFmt="#,##0"/>

## Governed metrics

These series are not hand-written SQL — they come from **one canonical definition** in the dbt metric registry (`_marts__semantic.yml`), compiled to the `sl_metrics_daily` view by `semantic/compile_metrics.py`. Dashboard, docs, and any future consumer must agree because there is only one place the math lives.

```sql sl_price
select metric_time, metric_value as palm_price_idr
from palm.sl_metrics_daily
where metric_name = 'avg_palm_price_idr'
order by metric_time
```

<LineChart data={sl_price} x=metric_time y=palm_price_idr title="Governed palm price (IDR per tonne)" xAxisTitle="Date" yAxisTitle="IDR / tonne"/>

```sql sl_share
select metric_time, region_key, metric_value as harvest_share
from palm.sl_metrics_daily
where metric_name = 'effective_harvest_share'
order by metric_time
```

<LineChart data={sl_share} x=metric_time series=region_key y=harvest_share title="Effective harvest-day share by region" xAxisTitle="Date" yAxisTitle="Share of days (0–1)" yFmt="num2"/>

Pricing, FX, operations value, and the harvest-day share all resolve to the same governed definitions — see the [Methodology](/methodology) for the registry → compiler → view pipeline.

{:else}

<Grid cols=2>
  <BigValue data={market_now} value=palm_oil_usd fmt="$#,##0" title="Sawit (USD/ton)"/>
  <BigValue data={market_now} value=soybean_oil_usd fmt="$#,##0" title="Kedelai (USD/ton)"/>
  <BigValue data={market_now} value=palm_soy_spread_usd fmt="$#,##0" title="Selisih sawit−kedelai (USD/ton)"/>
  <BigValue data={market_now} value=usd_idr fmt="#,##0" title="Kurs USD/IDR (Rp)"/>
</Grid>

## Sawit vs minyak kedelai

<LineChart data={market} x=price_date y={['palm_oil_usd','soybean_oil_usd']} title="Harga sawit vs minyak kedelai" xAxisTitle="Tanggal" yAxisTitle="USD / ton" yFmt="$#,##0"/>

## Selisih sawit − kedelai

Selisih minus = sawit lebih murah dari kedelai (pembeli ngelirik sawit, bagus buat kita).

<LineChart data={market} x=price_date y=palm_soy_spread_usd title="Selisih sawit minus kedelai" xAxisTitle="Tanggal" yAxisTitle="USD / ton" yFmt="$#,##0"/>

## Kurs USD/IDR

<LineChart data={market} x=price_date y=usd_idr title="Kurs USD/IDR" xAxisTitle="Tanggal" yAxisTitle="Rp per USD" yFmt="#,##0"/>

## Angka yang dipegang bareng

Grafik-grafik ini bukan SQL tulis tangan — semuanya dari **satu definisi baku** di dbt (`_marts__semantic.yml`), dikompilasi ke view `sl_metrics_daily`. Jadi dasbor, dokumen, dan siapapun yang pakai angkanya pasti sama karena rumusnya cuma ada di satu tempat.

<LineChart data={sl_price} x=metric_time y=palm_price_idr title="Harga sawit patokan (Rp per ton)" xAxisTitle="Tanggal" yAxisTitle="Rp / ton"/>

<LineChart data={sl_share} x=metric_time series=region_key y=harvest_share title="Porsi hari panen jalan per kebun" xAxisTitle="Tanggal" yAxisTitle="Porsi hari (0–1)" yFmt="num2"/>

Harga, kurs, nilai operasi, dan porsi hari panen semuanya ngacu ke definisi yang sama — dalemannya ada di [Cara Kerja](/methodology).

{/if}
