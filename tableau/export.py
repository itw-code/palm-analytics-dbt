"""Export Tableau worksheet sources from palm.duckdb.

Read-only. Does not run dbt, does not write the warehouse, does not invent rows.
Each CSV is one dbt model at its native grain. Row counts are checked against
that model before the script exits 0.

Run from the repo root:

    .venv/Scripts/python.exe tableau/export.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "palm.duckdb"
OUT_DIR = Path(__file__).resolve().parent / "export"

# Grain columns are the dimension keys the quality gate treats as not-null
# and unique in combination. Column lists match DESCRIBE order on the
# warehouse this script was written against; a missing column fails the export
# rather than silently dropping a field.
EXTRACTS = (
    {
        "file": "fct_estate_margin_daily__region_date.csv",
        "model": "fct_estate_margin_daily",
        "grain": ("region_key", "operation_date"),
        "keys": ("operations_key", "region_key", "operation_date"),
        "order": ("region_key", "operation_date"),
    },
    {
        "file": "fct_commodity_price_daily__price_date.csv",
        "model": "fct_commodity_price_daily",
        "grain": ("price_date",),
        "keys": ("price_date",),
        "order": ("price_date",),
    },
    {
        "file": "forecast_cpo_30day__forecast_date.csv",
        "model": "forecast_cpo_30day",
        "grain": ("forecast_date",),
        "keys": ("forecast_date",),
        "order": ("forecast_date",),
    },
    {
        "file": "rec_anomaly_flags__region_date.csv",
        "model": "rec_anomaly_flags",
        "grain": ("region_key", "operation_date"),
        "keys": ("anomaly_key", "region_key", "operation_date"),
        "order": ("region_key", "operation_date"),
    },
    {
        "file": "whatif_margin_shocks__region_scenario.csv",
        "model": "whatif_margin_shocks",
        "grain": ("region_key", "scenario"),
        "keys": ("whatif_key", "region_key", "scenario"),
        "order": ("region_key", "scenario"),
    },
    {
        "file": "dim_region__region_key.csv",
        "model": "dim_region",
        "grain": ("region_key",),
        "keys": ("region_key",),
        "order": ("region_key",),
    },
)


def _connect() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        sys.exit(f"warehouse missing: {DB_PATH}")
    return duckdb.connect(str(DB_PATH), read_only=True)


def _columns(con: duckdb.DuckDBPyConnection, model: str) -> list[str]:
    rows = con.execute(f"describe {model}").fetchall()
    return [r[0] for r in rows]


def _export_one(con: duckdb.DuckDBPyConnection, spec: dict) -> dict:
    cols = _columns(con, spec["model"])
    missing = [k for k in spec["keys"] if k not in cols]
    if missing:
        sys.exit(f"{spec['model']} missing expected keys {missing}; columns={cols}")
    select_list = ", ".join(cols)
    order = ", ".join(spec["order"])
    dest = OUT_DIR / spec["file"]
    con.execute(
        f"""
        copy (
            select {select_list}
            from {spec['model']}
            order by {order}
        ) to '{dest.as_posix()}' (header true, delimiter ',', quote '"')
        """
    )
    mart_rows = con.execute(f"select count(*) from {spec['model']}").fetchone()[0]
    return {
        "file": spec["file"],
        "model": spec["model"],
        "grain": list(spec["grain"]),
        "keys": list(spec["keys"]),
        "columns": cols,
        "mart_rows": mart_rows,
    }


def _csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            sys.exit(f"{path.name} has no header")
        return list(reader.fieldnames), list(reader)


def _check_csv(spec: dict, meta: dict) -> dict:
    path = OUT_DIR / spec["file"]
    header, rows = _csv_rows(path)
    if header != meta["columns"]:
        sys.exit(f"{spec['file']} header {header} != model columns {meta['columns']}")
    nulls = {key: 0 for key in spec["keys"]}
    seen: dict[tuple[str, ...], int] = {}
    for row in rows:
        for key in spec["keys"]:
            if row[key] is None or row[key] == "":
                nulls[key] += 1
        grain = tuple(row[col] for col in spec["grain"])
        seen[grain] = seen.get(grain, 0) + 1
    dups = sum(1 for n in seen.values() if n > 1)
    problems = []
    if len(rows) != meta["mart_rows"]:
        problems.append(f"csv rows {len(rows)} != mart rows {meta['mart_rows']}")
    if any(nulls.values()):
        problems.append(f"null dimension keys {nulls}")
    if dups:
        problems.append(f"duplicated grain combinations {dups}")
    if problems:
        sys.exit(f"{spec['file']}: " + "; ".join(problems))
    return {
        **meta,
        "csv_rows": len(rows),
        "null_keys": nulls,
        "duplicate_grains": dups,
    }


def _profile(con: duckdb.DuckDBPyConnection) -> dict:
    def rows(sql: str) -> list[dict]:
        cur = con.execute(sql)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]

    def one(sql: str) -> dict:
        return rows(sql)[0]

    return {
        "margin_span": one(
            """
            select min(operation_date) as min_date,
                   max(operation_date) as max_date,
                   count(*) as n_rows,
                   count(distinct region_key) as n_regions,
                   count(distinct operation_date) as n_dates,
                   sum(case when is_effective_harvest_day then 1 else 0 end) as harvest_days
            from fct_estate_margin_daily
            """
        ),
        "margin_by_region": rows(
            """
            select region_key,
                   count(*) as n_rows,
                   round(sum(margin_idr_per_ha), 0) as period_margin_idr_per_ha,
                   sum(case when is_effective_harvest_day then 1 else 0 end) as harvest_days
            from fct_estate_margin_daily
            group by 1
            order by period_margin_idr_per_ha desc
            """
        ),
        "margin_by_month": rows(
            """
            select date_trunc('month', operation_date)::date as month_start,
                   region_key,
                   round(sum(margin_idr_per_ha), 0) as month_margin_idr_per_ha,
                   sum(case when is_effective_harvest_day then 1 else 0 end) as harvest_days,
                   count(*) as calendar_days
            from fct_estate_margin_daily
            group by 1, 2
            order by 1, 2
            """
        ),
        "price_span": one(
            """
            select min(price_date) as min_date,
                   max(price_date) as max_date,
                   count(*) as n_rows,
                   min(palm_oil_usd) as min_palm_usd,
                   max(palm_oil_usd) as max_palm_usd,
                   min(palm_oil_idr) as min_palm_idr,
                   max(palm_oil_idr) as max_palm_idr,
                   min(usd_idr) as min_usd_idr,
                   max(usd_idr) as max_usd_idr
            from fct_commodity_price_daily
            """
        ),
        "price_by_month": rows(
            """
            select date_trunc('month', price_date)::date as month_start,
                   count(*) as n_days,
                   min(palm_oil_usd) as palm_usd,
                   max(palm_oil_usd) as palm_usd_max,
                   min(soybean_oil_usd) as soy_usd,
                   max(soybean_oil_usd) as soy_usd_max,
                   min(palm_soy_spread_usd) as spread_usd,
                   max(palm_soy_spread_usd) as spread_usd_max,
                   min(usd_idr) as fx_min,
                   max(usd_idr) as fx_max,
                   min(palm_oil_idr) as idr_min,
                   max(palm_oil_idr) as idr_max
            from fct_commodity_price_daily
            group by 1
            order by 1
            """
        ),
        "forecast_health": one(
            """
            select count(*) as n_rows,
                   min(forecast_date) as min_date,
                   max(forecast_date) as max_date,
                   count(distinct forecast_palm_usd) as distinct_forecasts,
                   min(forecast_palm_usd) as forecast_usd,
                   max(forecast_palm_usd) as forecast_usd_max,
                   min(band_half_width_usd) as band_min,
                   max(band_half_width_usd) as band_max,
                   count(*) filter (
                       where forecast_date in (
                           select price_date from fct_commodity_price_daily
                       )
                   ) as overlap_days
            from forecast_cpo_30day
            """
        ),
        "latest_price": one(
            """
            select price_date, palm_oil_usd, usd_idr, palm_oil_idr
            from fct_commodity_price_daily
            order by price_date desc
            limit 1
            """
        ),
        "anomaly_by_region": rows(
            """
            select region_key,
                   count(*) as n_rows,
                   min(operation_date) as min_date,
                   max(operation_date) as max_date,
                   sum(case when is_rainfall_deficit then 1 else 0 end) as rainfall_deficit_days,
                   sum(case when is_price_spike then 1 else 0 end) as price_spike_days
            from rec_anomaly_flags
            group by 1
            order by 1
            """
        ),
        "anomaly_latest_day": rows(
            """
            select operation_date, region_key, is_rainfall_deficit, is_price_spike
            from rec_anomaly_flags
            where operation_date = (select max(operation_date) from rec_anomaly_flags)
            order by region_key
            """
        ),
        "whatif_price_only": rows(
            """
            select region_key, scenario, palm_mult, fx_mult,
                   shocked_cpo_idr, shocked_margin_idr_per_ha
            from whatif_margin_shocks
            where fx_mult = 1
            order by region_key, palm_mult
            """
        ),
        "plan_columns": rows(
            """
            select table_name, column_name
            from information_schema.columns
            where table_schema = 'main'
              and regexp_matches(
                    lower(column_name),
                    '(^|_)(plan|budget|target)($|_)'
                  )
            order by 1, 2
            """
        ),
    }

def _json_default(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, bool):
        return value
    return str(value)


def main() -> None:
    check_only = "--check" in sys.argv
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = _connect()
    metas = []
    if check_only:
        for spec in EXTRACTS:
            cols = _columns(con, spec["model"])
            mart_rows = con.execute(f"select count(*) from {spec['model']}").fetchone()[0]
            metas.append(_check_csv(spec, {
                "file": spec["file"],
                "model": spec["model"],
                "grain": list(spec["grain"]),
                "keys": list(spec["keys"]),
                "columns": cols,
                "mart_rows": mart_rows,
            }))
    else:
        for spec in EXTRACTS:
            meta = _export_one(con, spec)
            metas.append(_check_csv(spec, meta))
    profile = _profile(con)
    con.close()
    payload = {"extracts": metas, "profile": profile}
    manifest = OUT_DIR / "manifest.json"
    manifest.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
