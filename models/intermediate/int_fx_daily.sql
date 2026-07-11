-- Forward-fill business-day FX to every calendar day (DuckDB ASOF join = latest rate on/before).
select
    c.date_day,
    f.usd_idr
from {{ ref('int_calendar') }} c
asof left join {{ ref('stg_fx_rate') }} f
    on c.date_day >= f.rate_date
