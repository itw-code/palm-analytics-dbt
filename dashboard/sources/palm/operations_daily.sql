select
    region_key,
    operation_date,
    temp_mean_c,
    precip_mm,
    wind_max_kmh,
    is_fertilize_favorable,
    is_harvest_favorable,
    is_spray_favorable,
    cpo_usd_per_tonne
from fct_estate_operations_daily
