-- 30-day CPO trend outlook: OLS slope fitted on the last 60 observed USD prices,
-- projected forward; the band is +/- 1.96 * residual stddev (constant-width, honest
-- about being a naive trend, not a volatility model). Flat monthly Pink-Sheet price
-- steps mean the slope is shallow by construction - confirm on the chart.
with hist as (
    select
        price_date,
        palm_oil_usd,
        row_number() over (order by price_date) as t
    from {{ ref('fct_commodity_price_daily') }}
),
windowed as (
    select * from hist
    where price_date > (select max(price_date) from hist) - interval 60 days
),
fit as (
    select
        count(*) as n,
        avg(t * 1.0) as mean_t,
        avg(palm_oil_usd) as mean_p,
        covar_pop(t * 1.0, palm_oil_usd) as cv,
        var_pop(t * 1.0) as vx,
        max(price_date) as last_date,
        max_by(palm_oil_usd, price_date) as last_price
    from windowed
),
resid as (
    select stddev_pop(
        w.palm_oil_usd - (f.mean_p + case when f.vx = 0 then 0 else f.cv / f.vx end * (w.t - f.mean_t))
    ) as sigma
    from windowed w cross join fit f
),
days as (
    select cast(range(1, 31) as int[]) as arr
),
exploded as (
    select unnest(arr) as horizon_days from days
)
select
    (select last_date from fit) + cast(e.horizon_days as int) as forecast_date,
    e.horizon_days,
    round((select last_price from fit)
        + case when (select vx from fit) = 0 then 0
               else (select cv / vx from fit) end * e.horizon_days, 2) as forecast_palm_usd,
    round(1.96 * coalesce((select sigma from resid), 0), 2) as band_half_width_usd,
    round((select last_price from fit)
        + case when (select vx from fit) = 0 then 0
               else (select cv / vx from fit) end * e.horizon_days
        - 1.96 * coalesce((select sigma from resid), 0), 2) as lower_usd,
    round((select last_price from fit)
        + case when (select vx from fit) = 0 then 0
               else (select cv / vx from fit) end * e.horizon_days
        + 1.96 * coalesce((select sigma from resid), 0), 2) as upper_usd
from exploded e
