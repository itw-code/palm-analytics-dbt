-- Incremental daily fact: agronomy signals joined to commodity price + FX and the
-- holiday/weekend calendar, yielding local-currency value and an "effective harvest day".
{{ config(materialized='incremental', unique_key='operations_key', on_schema_change='sync_all_columns') }}

with signals as (
    select * from {{ ref('int_daily_agronomy_signals') }}
),
comm as (
    select * from {{ ref('int_commodity_daily') }}
),
fx as (
    select * from {{ ref('int_fx_daily') }}
),
dates as (
    select * from {{ ref('dim_date') }}
)
select
    {{ dbt_utils.generate_surrogate_key(['signals.region', 'signals.weather_date']) }} as operations_key,
    signals.region                                      as region_key,
    signals.weather_date                                as operation_date,
    signals.temp_mean_c,
    signals.precip_mm,
    signals.wind_max_kmh,
    signals.et0_mm,
    signals.humidity_pct,
    signals.soil_moisture,
    signals.water_deficit_mm,
    signals.is_fertilize_favorable,
    signals.is_harvest_favorable,
    signals.is_spray_favorable,
    d.is_holiday,
    d.is_weekend,
    (signals.is_harvest_favorable and not d.is_holiday and not d.is_weekend) as is_effective_harvest_day,
    comm.palm_usd                                       as cpo_usd_per_tonne,
    fx.usd_idr,
    round(comm.palm_usd * fx.usd_idr, 0)                as cpo_idr_per_tonne,
    case when signals.is_harvest_favorable
         then round(comm.palm_usd * fx.usd_idr, 0)
         else 0 end                                     as harvest_day_value_idr
from signals
left join comm on signals.weather_date = comm.date_day
left join fx   on signals.weather_date = fx.date_day
left join dates d on signals.weather_date = d.date_key
{% if is_incremental() %}
where signals.weather_date > (select max(operation_date) from {{ this }})
{% endif %}
