-- Cleaned 1:1 view over raw CPO price.
with source as (
    select * from {{ source('raw', 'raw_cpo_price') }}
)
select
    cast(price_date as date)             as price_date,
    cast(cpo_usd_per_tonne as double)    as cpo_usd_per_tonne
from source
