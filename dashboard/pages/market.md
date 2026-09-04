---
title: Commodity Market
---

Palm oil does not trade in isolation - **soybean oil** is its closest substitute, so the palm-vs-soy spread drives buyer switching, and the USD/IDR rate decides what a USD-quoted price is actually worth to an Indonesian estate.

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

<Grid cols=2>
  <BigValue data={market_now} value=palm_oil_usd fmt="usd0" title="Palm oil · Minyak sawit (USD/t)"/>
  <BigValue data={market_now} value=soybean_oil_usd fmt="usd0" title="Soybean oil · Minyak kedelai (USD/t)"/>
  <BigValue data={market_now} value=palm_soy_spread_usd fmt="usd0" title="Palm − Soy spread · Selisih (USD/t)"/>
  <BigValue data={market_now} value=usd_idr fmt="#,##0" title="USD/IDR · Kurs (IDR)"/>
</Grid>

## Palm vs soybean oil · Sawit vs kedelai

<LineChart data={market} x=price_date y={['palm_oil_usd','soybean_oil_usd']} title="Palm vs soybean oil price" xAxisTitle="Date" yAxisTitle="USD / tonne"/>

## Palm − soybean substitution spread · Selisih substitusi

A negative spread means palm trades at a discount to soybean oil (palm looks attractive to buyers).

<LineChart data={market} x=price_date y=palm_soy_spread_usd title="Palm minus soybean spread" xAxisTitle="Date" yAxisTitle="USD / tonne"/>

## USD/IDR exchange rate · Kurs

<LineChart data={market} x=price_date y=usd_idr title="USD/IDR exchange rate" xAxisTitle="Date" yAxisTitle="IDR per USD"/>

## Governed metrics · Metrik tata kelola

These series are not hand-written SQL - they come from **one canonical definition** in the dbt metric registry (`_marts__semantic.yml`), compiled to the `sl_metrics_daily` view by `semantic/compile_metrics.py`. Dashboard, docs, and any future consumer must agree because there is only one place the math lives.

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

Pricing, FX, operations value, and the harvest-day share all resolve to the same governed definitions - see the [Methodology](/methodology) for the registry → compiler → view pipeline.
