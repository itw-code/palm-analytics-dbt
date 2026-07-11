-- Cleaned Indonesia public holidays, deduplicated to one row per date.
with source as (
    select * from {{ source('raw', 'raw_holidays') }}
)
select
    cast(holiday_date as date)              as holiday_date,
    max(holiday_name)                       as holiday_name
from source
group by 1
