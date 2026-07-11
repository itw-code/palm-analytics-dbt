-- Conformed region dimension, enriched with seeded estate profile (planted ha, yield, manager).
with regions as (
    select distinct region from {{ ref('stg_weather') }}
),
profile as (
    select * from {{ ref('region_profile') }}
)
select
    r.region                                            as region_key,
    array_to_string(
        list_transform(
            string_split(replace(r.region, '_', ' '), ' '),
            w -> upper(substr(w, 1, 1)) || substr(w, 2)
        ), ' ')                                         as region_name,
    case
        when r.region ilike '%kalimantan%' then 'Kalimantan'
        else 'Sumatra'
    end                                                 as island,
    p.planted_hectares,
    p.yield_t_ha,
    p.estate_manager
from regions r
left join profile p on r.region = p.region_key
