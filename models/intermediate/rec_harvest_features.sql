-- Lane 2 decision-grade features for the 7-day harvest-day recommender.
-- One row per (region, forecast date). Scores:
--   weather_score: continuous 0-1 mirror of macros/agronomy_rules.sql harvest
--     thresholds (precip_mm < 10 ideal, humidity_pct < 88); linear decay to 0
--     at 25mm (the fertilize-window upper bound - beyond that blocks are waterlogged).
--   labour_score: 1.0 weekday, 0.4 weekend (reduced crew), 0.0 public holiday (no crew).
--   price_score: latest CPO IDR placed on its trailing-90d min-max range, floored
--     at 0.05 so a soft market tilts the ranking but never vetoes a workable day.
with fc as (
    select * from {{ ref('fct_estate_forecast_7day') }}
),
px as (
    select
        min(palm_oil_idr) as min_idr,
        max(palm_oil_idr) as max_idr
    from {{ ref('fct_commodity_price_daily') }}
    where price_date > (select max(price_date) from {{ ref('fct_commodity_price_daily') }}) - interval 90 days
)
select
    fc.forecast_key,
    fc.region_key,
    fc.forecast_date,
    fc.horizon_days,
    fc.precip_mm,
    fc.humidity_pct,
    fc.is_harvest_favorable,
    fc.is_holiday,
    fc.is_weekend,
    fc.cpo_idr_per_tonne,
    round(
        greatest(0, least(1, 1 - fc.precip_mm / 25.0))
        * case when fc.humidity_pct < 88 then 1.0 else 0.5 end
    , 3) as weather_score,
    case
        when coalesce(fc.is_holiday, false) then 0.0
        when coalesce(fc.is_weekend, false) then 0.4
        else 1.0
    end as labour_score,
    round(
        greatest(0.05, least(1.0,
            (fc.cpo_idr_per_tonne - px.min_idr) / nullif(px.max_idr - px.min_idr, 0)
        ))
    , 3) as price_score
from fc
cross join px
