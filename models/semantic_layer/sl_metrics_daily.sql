-- !! GENERATED FILE - DO NOT EDIT !!
-- Produced by semantic/compile_metrics.py from the metric registry in
-- models/marts/_marts__semantic.yml. Edit the YAML and re-run the compiler:
--   dbt parse --profiles-dir . && python semantic/compile_metrics.py
-- Grain: (metric_name, metric_time, region_key). region_key is NULL for
-- semantic models without a categorical region dimension.

with base__commodity_prices as (
    select
        price_date as metric_time,
        cast(null as varchar) as region_key,
        avg(palm_oil_usd) as palm_oil_usd_avg,
        avg(soybean_oil_usd) as soybean_oil_usd_avg,
        avg(usd_idr) as usd_idr_avg
    from {{ ref('fct_commodity_price_daily') }}
    group by metric_time
),
base__estate_operations as (
    select
        operation_date as metric_time,
        region_key,
        sum(harvest_day_value_idr) as harvest_value_idr_sum,
        sum(case when is_effective_harvest_day then 1 else 0 end) as effective_harvest_days,
        count(distinct operations_key) as operation_days,
        avg(water_deficit_mm) as water_deficit_avg
    from {{ ref('fct_estate_operations_daily') }}
    group by metric_time, region_key
),
m__avg_palm_price_usd as (
    select metric_time, region_key, (palm_oil_usd_avg)::double as metric_value
    from base__commodity_prices
),
m__avg_soybean_price_usd as (
    select metric_time, region_key, (soybean_oil_usd_avg)::double as metric_value
    from base__commodity_prices
),
m__avg_usd_idr as (
    select metric_time, region_key, (usd_idr_avg)::double as metric_value
    from base__commodity_prices
),
m__avg_water_deficit_mm as (
    select metric_time, region_key, (water_deficit_avg)::double as metric_value
    from base__estate_operations
),
m__effective_harvest_days as (
    select metric_time, region_key, (effective_harvest_days)::double as metric_value
    from base__estate_operations
),
m__harvest_value_last_7_days as (
    select metric_time, region_key,
           sum(harvest_value_idr_sum) over (partition by region_key order by metric_time
               range between interval '6' day preceding and current row)::double as metric_value
    from base__estate_operations
),
m__operation_days_total as (
    select metric_time, region_key, (operation_days)::double as metric_value
    from base__estate_operations
),
m__total_harvest_value_idr as (
    select metric_time, region_key, (harvest_value_idr_sum)::double as metric_value
    from base__estate_operations
),
m__avg_palm_price_idr as (
    select metric_time, region_key, (palm_oil_usd_avg * usd_idr_avg)::double as metric_value
    from base__commodity_prices
),
m__effective_harvest_share as (
    select metric_time, region_key, (effective_harvest_days / nullif(operation_days, 0))::double as metric_value
    from base__estate_operations
)

select 'avg_palm_price_idr' as metric_name, metric_time, region_key, metric_value from m__avg_palm_price_idr
union all
select 'avg_palm_price_usd' as metric_name, metric_time, region_key, metric_value from m__avg_palm_price_usd
union all
select 'avg_soybean_price_usd' as metric_name, metric_time, region_key, metric_value from m__avg_soybean_price_usd
union all
select 'avg_usd_idr' as metric_name, metric_time, region_key, metric_value from m__avg_usd_idr
union all
select 'avg_water_deficit_mm' as metric_name, metric_time, region_key, metric_value from m__avg_water_deficit_mm
union all
select 'effective_harvest_days' as metric_name, metric_time, region_key, metric_value from m__effective_harvest_days
union all
select 'effective_harvest_share' as metric_name, metric_time, region_key, metric_value from m__effective_harvest_share
union all
select 'harvest_value_last_7_days' as metric_name, metric_time, region_key, metric_value from m__harvest_value_last_7_days
union all
select 'operation_days_total' as metric_name, metric_time, region_key, metric_value from m__operation_days_total
union all
select 'total_harvest_value_idr' as metric_name, metric_time, region_key, metric_value from m__total_harvest_value_idr
