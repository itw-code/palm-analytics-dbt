-- Star-schema fact: one row per region per day, joining agronomy signals to the
-- CPO price so the BI layer can answer "what should we do today, and what is it worth?".
with signals as (
    select * from {{ ref('int_daily_agronomy_signals') }}
),
price as (
    select * from {{ ref('stg_cpo_price') }}
)
select
    {{ dbt_utils.generate_surrogate_key(['signals.region', 'signals.weather_date']) }} as operations_key,
    signals.region                                      as region_key,
    signals.weather_date                                as operation_date,
    signals.temp_mean_c,
    signals.precip_mm,
    signals.wind_max_kmh,
    signals.is_fertilize_favorable,
    signals.is_harvest_favorable,
    signals.is_spray_favorable,
    price.cpo_usd_per_tonne,
    -- Illustrative value-at-opportunity: harvest-favorable days scaled by CPO price.
    case when signals.is_harvest_favorable
         then round(price.cpo_usd_per_tonne * 1.0, 2)
         else 0 end                                     as harvest_day_value_usd_per_tonne
from signals
left join price
    on signals.weather_date = price.price_date
