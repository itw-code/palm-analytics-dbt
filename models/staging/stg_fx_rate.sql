-- Cleaned 1:1 view over raw USD->IDR FX (business-day series).
with source as (
    select * from {{ source('raw', 'raw_fx_rate') }}
)
select
    cast(rate_date as date)   as rate_date,
    cast(usd_idr as double)   as usd_idr
from source
