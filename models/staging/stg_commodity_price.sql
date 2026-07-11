-- Cleaned monthly commodity prices (palm oil, soybean oil).
with source as (
    select * from {{ source('raw', 'raw_commodity_price') }}
)
select
    cast(price_month as date)        as price_month,
    lower(commodity)                 as commodity,
    cast(usd_per_tonne as double)    as usd_per_tonne
from source
