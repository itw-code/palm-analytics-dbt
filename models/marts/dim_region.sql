-- Conformed region dimension.
with regions as (
    select distinct region from {{ ref('stg_weather') }}
)
select
    region                                              as region_key,
    array_to_string(
        list_transform(
            string_split(replace(region, '_', ' '), ' '),
            w -> upper(substr(w, 1, 1)) || substr(w, 2)
        ), ' ')                                          as region_name,
    case
        when region ilike '%kalimantan%' then 'Kalimantan'
        else 'Sumatra'
    end                                                 as island
from regions
