-- Singular test: the governed metrics view must be unique at its declared grain.
-- (Written as a standalone test because the grain includes coalesce(region_key).)

select
    metric_name,
    metric_time,
    coalesce(region_key, '')  as region,
    count(*)                  as n
from {{ ref('sl_metrics_daily') }}
group by 1, 2, 3
having count(*) > 1
