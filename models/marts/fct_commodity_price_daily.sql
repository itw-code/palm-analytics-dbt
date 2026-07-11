-- Daily commodity fact (contract-enforced): palm & soybean oil, the substitution spread,
-- FX, and palm oil in local currency.
with comm as (
    select * from {{ ref('int_commodity_daily') }}
),
fx as (
    select * from {{ ref('int_fx_daily') }}
)
select
    comm.date_day                               as price_date,
    comm.palm_usd                               as palm_oil_usd,
    comm.soy_usd                                as soybean_oil_usd,
    comm.palm_soy_spread_usd,
    fx.usd_idr,
    round(comm.palm_usd * fx.usd_idr, 0)        as palm_oil_idr
from comm
left join fx on comm.date_day = fx.date_day
