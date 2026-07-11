{% snapshot commodity_price_snapshot %}
{{
    config(
        target_schema='snapshots',
        unique_key='snapshot_id',
        strategy='check',
        check_cols=['usd_per_tonne']
    )
}}
-- SCD2 change tracking on monthly commodity prices: a new record is captured
-- whenever a month's published price is revised.
select
    commodity || '-' || cast(price_month as varchar) as snapshot_id,
    price_month,
    commodity,
    usd_per_tonne
from {{ ref('stg_commodity_price') }}
{% endsnapshot %}
