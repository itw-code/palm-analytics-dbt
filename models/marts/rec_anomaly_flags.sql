-- Anomaly flags, one row per (region, day) for the last 60 days.
-- Rainfall deficit: 14-day rainfall under 20mm with a positive 14-day mean water
-- deficit (dry spell that the deficit confirms is not just a timing gap) OR a
-- 14-day mean deficit above 4.0mm (~90th pctile of history: 4.59).
-- Price spike: monthly palm USD jumps > 5% MoM (> 2x the largest observed step,
-- 2.41%) OR the daily IDR price breaches its trailing-90d max. UNDO: tighten or
-- loosen the 20/4.0/5% constants here - no downstream model depends on them.
with ops as (
    select
        region_key,
        operation_date,
        precip_mm,
        water_deficit_mm,
        is_harvest_favorable
    from {{ ref('fct_estate_operations_daily') }}
    where operation_date > (select max(operation_date) from {{ ref('fct_estate_operations_daily') }}) - interval 60 days
),
rolled as (
    select
        region_key,
        operation_date,
        precip_mm,
        water_deficit_mm,
        is_harvest_favorable,
        sum(precip_mm) over (
            partition by region_key order by operation_date
            rows between 13 preceding and current row) as rain_14d_mm,
        avg(water_deficit_mm) over (
            partition by region_key order by operation_date
            rows between 13 preceding and current row) as deficit_14d_mm
    from ops
),
px as (
    select
        price_month,
        usd_per_tonne,
        100 * (usd_per_tonne / lag(usd_per_tonne) over (order by price_month) - 1) as mom_pct
    from {{ ref('stg_commodity_price') }}
    where commodity = 'palm_oil'
),
daily as (
    select
        price_date,
        palm_oil_usd,
        palm_oil_idr,
        max(palm_oil_idr) over (
            order by price_date rows between 90 preceding and 1 preceding) as trailing90_max_idr
    from {{ ref('fct_commodity_price_daily') }}
)
select
    {{ dbt_utils.generate_surrogate_key(['rolled.region_key', 'rolled.operation_date']) }} as anomaly_key,
    rolled.region_key,
    rolled.operation_date,
    round(rolled.rain_14d_mm, 1) as rain_14d_mm,
    round(rolled.deficit_14d_mm, 2) as deficit_14d_mm,
    (rolled.rain_14d_mm < 20 and rolled.deficit_14d_mm > 0) or rolled.deficit_14d_mm > 4.0 as is_rainfall_deficit,
    px.mom_pct as palm_mom_pct,
    (coalesce(px.mom_pct, 0) > 5) or (daily.palm_oil_idr > coalesce(daily.trailing90_max_idr, 0)
        and daily.trailing90_max_idr is not null) as is_price_spike
from rolled
left join daily on rolled.operation_date = daily.price_date
left join px on date_trunc('month', rolled.operation_date) = px.price_month
