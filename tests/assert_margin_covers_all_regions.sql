-- Singular test: every region in the operations fact must have margin coverage.
-- A new estate added to region_profile.csv without a matching cost_assumptions.csv
-- row would otherwise vanish from the margin mart silently (inner join drops it).
-- This fails the build loudly instead, telling the user exactly what to add.

with ops_regions as (
    select distinct region_key from {{ ref('fct_estate_operations_daily') }}
),
margin_regions as (
    select distinct region_key from {{ ref('fct_estate_margin_daily') }}
)
select o.region_key
from ops_regions o
left join margin_regions m on o.region_key = m.region_key
where m.region_key is null
