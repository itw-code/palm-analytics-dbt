-- Cleaned 1:1 view over raw weather: typed, renamed, expanded agronomy inputs.
with source as (
    select * from {{ source('raw', 'raw_weather') }}
)
select
    lower(region)                      as region,
    cast(obs_date as date)             as weather_date,
    cast(temp_mean_c as double)        as temp_mean_c,
    cast(precip_mm as double)          as precip_mm,
    cast(wind_max_kmh as double)       as wind_max_kmh,
    cast(et0_mm as double)             as et0_mm,
    cast(humidity_pct as double)       as humidity_pct,
    cast(soil_moisture as double)      as soil_moisture
from source
