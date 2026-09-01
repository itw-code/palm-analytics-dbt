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

<BigValue data={market_now} value=palm_oil_usd fmt="usd0" title="Palm oil (USD/t)"/>
<BigValue data={market_now} value=soybean_oil_usd fmt="usd0" title="Soybean oil (USD/t)"/>
<BigValue data={market_now} value=palm_soy_spread_usd fmt="usd0" title="Palm − Soy spread"/>
<BigValue data={market_now} value=usd_idr fmt="#,##0" title="USD/IDR"/>

## Palm vs soybean oil (USD/tonne)

<LineChart data={market} x=price_date y={['palm_oil_usd','soybean_oil_usd']} yAxisTitle="USD / tonne"/>

## Palm − soybean substitution spread

A negative spread means palm trades at a discount to soybean oil (palm looks attractive to buyers).

<LineChart data={market} x=price_date y=palm_soy_spread_usd yAxisTitle="USD / tonne"/>

## USD/IDR exchange rate

<LineChart data={market} x=price_date y=usd_idr yAxisTitle="IDR per USD"/>

## Governed metrics (dbt Semantic Layer)

These series are not hand-written SQL - they come from **one canonical definition** in the dbt metric registry (`_marts__semantic.yml`), compiled to the `sl_metrics_daily` view by `semantic/compile_metrics.py`. Dashboard, docs, and any future consumer must agree because there is only one place the math lives.

```sql sl_price
select metric_time, metric_value as palm_price_idr
from palm.sl_metrics_daily
where metric_name = 'avg_palm_price_idr'
order by metric_time
```

<LineChart data={sl_price} x=metric_time y=palm_price_idr yAxisTitle="IDR / tonne (governed metric)"/>

```sql sl_share
select metric_time, region_key, metric_value as harvest_share
from palm.sl_metrics_daily
where metric_name = 'effective_harvest_share'
order by metric_time
```

<LineChart data={sl_share} x=metric_time series=region_key y=harvest_share yAxisTitle="share of days that are effective harvest days"/>

Pricing, FX, operations value, and the harvest-day share all resolve to the same governed definitions - see the [Methodology](/methodology) for the registry → compiler → view pipeline.
