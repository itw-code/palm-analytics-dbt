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
