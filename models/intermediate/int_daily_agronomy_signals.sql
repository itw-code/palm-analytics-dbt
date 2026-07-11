-- Reusable business logic: per-region-day agronomy suitability from expanded weather inputs.
with weather as (
    select * from {{ ref('stg_weather') }}
)
select
    region,
    weather_date,
    temp_mean_c,
    precip_mm,
    wind_max_kmh,
    et0_mm,
    humidity_pct,
    soil_moisture,
    round(et0_mm - precip_mm, 2)                                   as water_deficit_mm,

    -- Fertilize: enough moisture to dissolve nutrients, not so wet it runs off.
    (precip_mm between 5 and 25 and soil_moisture < 0.35)          as is_fertilize_favorable,

    -- Harvest: dry enough that fruit and roads stay accessible, lower humidity.
    (precip_mm < 10 and humidity_pct < 88)                         as is_harvest_favorable,

    -- Spray: low wind (drift) and low rain (wash-off).
    (wind_max_kmh < 12 and precip_mm < 5)                          as is_spray_favorable
from weather
