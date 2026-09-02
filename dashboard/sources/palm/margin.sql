select
    region_key,
    operation_date,
    revenue_idr_per_ha,
    transport_cost_idr_per_ha,
    margin_idr_per_ha,
    margin_total_idr,
    is_effective_harvest_day
from fct_estate_margin_daily
