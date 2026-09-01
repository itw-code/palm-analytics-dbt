-- MetricFlow time spine: continuous daily calendar required by the semantic
-- layer spec. Tagged with metricflow_time_spine: true in _marts__semantic.yml.
-- Static generous range keeps the spine independent of lake freshness so the
-- metric graph can always resolve it.
select cast(unnest(
    generate_series(DATE '2020-01-01', DATE '2031-12-31', interval '1' day)
) as date) as date_day
