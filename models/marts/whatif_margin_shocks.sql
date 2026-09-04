-- Price x FX shock grid on yesterday's harvested margin (keeps agronomy fixed so the
-- table reads as pure market sensitivity). Base price/FX come from the latest
-- fct_commodity_price_daily row; revenue uses each region's own cost seed and
-- yield/extraction rate, mirroring fct_estate_margin_daily, harvest-day branch.
with base as (
    select palm_oil_usd, usd_idr
    from {{ ref('fct_commodity_price_daily') }}
    order by price_date desc
    limit 1
),
shocks as (
    select * from (values
        ('palm_-20pct', 0.80, 1.00),
        ('palm_-10pct', 0.90, 1.00),
        ('base',        1.00, 1.00),
        ('palm_+10pct', 1.10, 1.00),
        ('palm_+20pct', 1.20, 1.00),
        ('idr_-10pct',  1.00, 0.90),
        ('idr_+10pct',  1.00, 1.10),
        ('palm+10_fx+10', 1.10, 1.10),
        ('palm-10_fx-10', 0.90, 0.90)
    ) as t(scenario, palm_mult, fx_mult)
),
region as (
    select * from {{ ref('dim_region') }}
),
cost as (
    select * from {{ ref('cost_assumptions') }}
)
select
    {{ dbt_utils.generate_surrogate_key(['region.region_key', 'shocks.scenario']) }} as whatif_key,
    region.region_key,
    shocks.scenario,
    shocks.palm_mult,
    shocks.fx_mult,
    round(base.palm_oil_usd * shocks.palm_mult, 2) as shocked_palm_usd,
    round(base.usd_idr * shocks.fx_mult, 0) as shocked_usd_idr,
    round(base.palm_oil_usd * shocks.palm_mult * base.usd_idr * shocks.fx_mult, 0) as shocked_cpo_idr,
    round(
        base.palm_oil_usd * shocks.palm_mult * base.usd_idr * shocks.fx_mult
            * region.yield_t_ha * cost.extraction_rate
        - cost.fertilizer_cost_idr_per_ha
        - cost.harvest_cost_idr_per_ha
        - region.yield_t_ha * cost.extraction_rate * cost.transport_cost_idr_per_tonne
    , 0) as shocked_margin_idr_per_ha
from shocks
cross join base
cross join region
join cost on region.region_key = cost.region_key
