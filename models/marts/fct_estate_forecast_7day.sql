-- Forward 7-day planner: forecast agronomy signals joined to latest commodity/FX
-- and holiday calendar. Price is carried forward (assume latest known).
-- Not incremental - 7 rows per region, rebuilt every run.
with signals as (
    select * from {{ ref('int_forecast_signals') }}
),
-- same forward-filled daily prices used by historical fact
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
    {{ dbt_utils.generate_surrogate_key(['signals.region', 'signals.weather_date']) }} as forecast_key,
    signals.region                                      as region_key,
    signals.weather_date                                as forecast_date,
    row_number() over (partition by signals.region order by signals.weather_date) as horizon_days,
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
    (signals.is_harvest_favorable and not coalesce(d.is_holiday, false) and not coalesce(d.is_weekend, false)) as is_effective_harvest_day,
    comm.palm_usd                                       as cpo_usd_per_tonne,
    fx.usd_idr,
    round(comm.palm_usd * fx.usd_idr, 0)                as cpo_idr_per_tonne
from signals
left join comm on signals.weather_date = comm.date_day
left join fx   on signals.weather_date = fx.date_day
left join dates d on signals.weather_date = d.date_key
