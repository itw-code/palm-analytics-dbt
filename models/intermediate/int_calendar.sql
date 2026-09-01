-- Date spine covering historical weather + 7-day forecast; backbone for dim_date and forward-fills.
select cast(unnest(generate_series(
    (select min(weather_date) from {{ ref('stg_weather') }}),
    (select max(weather_date) from {{ ref('stg_weather_forecast') }}),
    interval '1 day'
)) as date) as date_day
