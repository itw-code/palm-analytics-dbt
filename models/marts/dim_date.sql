-- Calendar dimension: spine + weekend + Indonesian public-holiday flags.
with cal as (
    select date_day from {{ ref('int_calendar') }}
),
holidays as (
    select holiday_date, holiday_name from {{ ref('stg_holidays') }}
)
select
    c.date_day                                          as date_key,
    extract(year from c.date_day)                       as year,
    extract(month from c.date_day)                      as month,
    extract(day from c.date_day)                        as day_of_month,
    extract(dow from c.date_day)                        as day_of_week,
    (extract(dow from c.date_day) in (0, 6))            as is_weekend,
    (h.holiday_date is not null)                        as is_holiday,
    h.holiday_name
from cal c
left join holidays h on c.date_day = h.holiday_date
