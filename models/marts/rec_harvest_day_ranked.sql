-- Ranked harvest-day recommender: composite = weather * labour * price.
-- Multiplicative (not additive) so any hard blocker zeroes the day: crews do not
-- work public holidays, heavy rain or saturated air makes roads/blocks impassable,
-- and the 0.05 price floor keeps a soft market from ever outranking field reality.
with feats as (
    select * from {{ ref('rec_harvest_features') }}
),
scored as (
    select
        feats.*,
        round(feats.weather_score * feats.labour_score * feats.price_score, 3) as composite_score,
        case
            when feats.weather_score * feats.labour_score * feats.price_score >= 0.50 then 'harvest'
            when feats.weather_score * feats.labour_score * feats.price_score >= 0.20 then 'conditional'
            else 'stand_down'
        end as recommendation
    from feats
)
select
    forecast_key,
    region_key,
    forecast_date,
    horizon_days,
    weather_score,
    labour_score,
    price_score,
    composite_score,
    recommendation,
    rank() over (partition by region_key order by composite_score desc, forecast_date) as day_rank,
    case when rank() over (partition by region_key order by composite_score desc, forecast_date) = 1
        then true else false end as is_best_day
from scored
