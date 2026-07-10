-- Reusable business logic: derive per-region-day agronomy suitability signals
-- from weather thresholds. This is the layer between staging and consumption -
-- the piece practitioners call "where the value is".
with weather as (
    select * from {{ ref('stg_weather') }}
)
select
    region,
    weather_date,
    temp_mean_c,
    precip_mm,
    wind_max_kmh,

    -- Fertilizing: favorable when soil is moist enough to dissolve nutrients but
    -- not so wet that runoff washes them away.
    (precip_mm between 5 and 25)                        as is_fertilize_favorable,

    -- Harvesting: favorable on drier days so fruit and roads stay accessible.
    (precip_mm < 10)                                    as is_harvest_favorable,

    -- Spraying: favorable when low wind (drift control) and low rain (wash-off).
    (wind_max_kmh < 12 and precip_mm < 5)               as is_spray_favorable
from weather
