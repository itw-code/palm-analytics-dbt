-- Margin per hectare on every effective harvest day.
-- Revenue per ha = CPO price (IDR/t) * yield (t/ha) * extraction rate.
-- On non-effective days revenue is 0 and you still carry fertilizer cost.
-- Costs are seed-assumed (cost_assumptions.csv) - replace with your actuals.

with ops as (
    select * from {{ ref('fct_estate_operations_daily') }}
),
cost as (
    select * from {{ ref('cost_assumptions') }}
),
region as (
    select * from {{ ref('dim_region') }}
)
select
    ops.operations_key,
    ops.region_key,
    ops.operation_date,
    ops.is_effective_harvest_day,
    ops.cpo_idr_per_tonne,
    region.planted_hectares,
    region.yield_t_ha,
    cost.fertilizer_cost_idr_per_ha,
    cost.harvest_cost_idr_per_ha,
    cost.transport_cost_idr_per_tonne,
    cost.extraction_rate,
    -- revenue per ha only when you actually harvest
    case when ops.is_effective_harvest_day
         then round(ops.cpo_idr_per_tonne * region.yield_t_ha * cost.extraction_rate, 0)
         else 0 end as revenue_idr_per_ha,
    -- transport is per tonne of CPO actually harvested
    case when ops.is_effective_harvest_day
         then round(region.yield_t_ha * cost.extraction_rate * cost.transport_cost_idr_per_tonne, 0)
         else 0 end as transport_cost_idr_per_ha,
    case when ops.is_effective_harvest_day
         then round(
            ops.cpo_idr_per_tonne * region.yield_t_ha * cost.extraction_rate
            - cost.fertilizer_cost_idr_per_ha
            - cost.harvest_cost_idr_per_ha
            - region.yield_t_ha * cost.extraction_rate * cost.transport_cost_idr_per_tonne
         , 0)
         else -cost.fertilizer_cost_idr_per_ha
    end as margin_idr_per_ha,
    case when ops.is_effective_harvest_day
         then round(
            (ops.cpo_idr_per_tonne * region.yield_t_ha * cost.extraction_rate
            - cost.fertilizer_cost_idr_per_ha
            - cost.harvest_cost_idr_per_ha
            - region.yield_t_ha * cost.extraction_rate * cost.transport_cost_idr_per_tonne)
            * region.planted_hectares
         , 0)
         else round(-cost.fertilizer_cost_idr_per_ha * region.planted_hectares, 0)
    end as margin_total_idr
from ops
join region on ops.region_key = region.region_key
join cost on ops.region_key = cost.region_key
