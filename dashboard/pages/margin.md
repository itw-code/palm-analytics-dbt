---
title: Margin per Hectare
---

P&L per hectare derived from the same price + yield + extraction rate that powers the operations planner, minus your seeded cost assumptions. On non-effective days you still carry fertilizer cost. Replace `seeds/cost_assumptions.csv` with your estate's actuals and every number recomputes.

```sql regions_list
select region_key, region_name from palm.region order by region_name
```

<Dropdown name=region data={regions_list} value=region_key label=region_name title="Region" defaultValue="%">
    <DropdownOption valueLabel="All regions" value="%" />
</Dropdown>

```sql margin_recent
select
    m.operation_date,
    r.region_name,
    m.revenue_idr_per_ha,
    m.margin_idr_per_ha,
    m.margin_total_idr,
    m.is_effective_harvest_day
from palm.margin m
join palm.region r on m.region_key = r.region_key
where m.region_key like '${inputs.region.value}'
order by m.operation_date desc
limit 30
```

<DataTable data={margin_recent} rows=15>
    <Column id=operation_date title="Date"/>
    <Column id=region_name title="Region"/>
    <Column id=revenue_idr_per_ha title="Revenue/ha (IDR)" fmt="#,##0"/>
    <Column id=margin_idr_per_ha title="Margin/ha (IDR)" fmt="#,##0"/>
    <Column id=margin_total_idr title="Margin total (IDR)" fmt="#,##0"/>
    <Column id=is_effective_harvest_day title="Harvest day" contentType=colorindicator/>
</DataTable>

```sql margin_trend
select operation_date, avg(margin_idr_per_ha) as avg_margin_ha
from palm.margin
where region_key like '${inputs.region.value}'
group by operation_date
order by operation_date
```

<LineChart data={margin_trend} x=operation_date y=avg_margin_ha yAxisTitle="Avg margin/ha (IDR)" yFmt="#,##0"/>

*Formula: `revenue = CPO_IDR * yield * extraction_rate` (only on effective harvest days); `margin_per_ha = revenue - fertilizer - harvest - transport`, else `-fertilizer`. Edit `cost_assumptions.csv` and the margin rebuilds everywhere.*
