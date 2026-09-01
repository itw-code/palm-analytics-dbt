{% macro agronomy_signals(source_ref) %}
-- Shared business logic: agronomy suitability flags + water deficit.
-- Used by int_daily_agronomy_signals (historical) and int_forecast_signals (7-day ahead).
-- Source must expose: region, weather_date, temp_mean_c, precip_mm, wind_max_kmh,
-- et0_mm, humidity_pct, soil_moisture.
with weather as (
    select * from {{ source_ref }}
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
    round(et0_mm - precip_mm, 2)                                  as water_deficit_mm,
    (precip_mm between 5 and 25 and soil_moisture < 0.35)         as is_fertilize_favorable,
    (precip_mm < 10 and humidity_pct < 88)                        as is_harvest_favorable,
    (wind_max_kmh < 12 and precip_mm < 5)                         as is_spray_favorable
from weather
{% endmacro %}
