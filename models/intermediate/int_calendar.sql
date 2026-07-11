-- Date spine covering the weather window; the backbone for dim_date and daily forward-fills.
with bounds as (
    select min(weather_date) as d0, max(weather_date) as d1
    from {{ ref('stg_weather') }}
)
select cast(unnest(generate_series(d0, d1, interval '1 day')) as date) as date_day
from bounds
