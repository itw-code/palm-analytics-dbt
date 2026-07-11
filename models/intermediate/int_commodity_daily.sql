-- Forward-fill monthly palm & soybean oil prices to daily, then compute the substitution spread.
with cal as (
    select date_day from {{ ref('int_calendar') }}
),
palm as (
    select c.date_day, p.usd_per_tonne as palm_usd
    from cal c
    asof left join (
        select price_month, usd_per_tonne
        from {{ ref('stg_commodity_price') }}
        where commodity = 'palm_oil'
    ) p on c.date_day >= p.price_month
),
soy as (
    select c.date_day, s.usd_per_tonne as soy_usd
    from cal c
    asof left join (
        select price_month, usd_per_tonne
        from {{ ref('stg_commodity_price') }}
        where commodity = 'soybean_oil'
    ) s on c.date_day >= s.price_month
)
select
    palm.date_day,
    palm.palm_usd,
    soy.soy_usd,
    round(palm.palm_usd - soy.soy_usd, 2) as palm_soy_spread_usd
from palm
join soy using (date_day)
