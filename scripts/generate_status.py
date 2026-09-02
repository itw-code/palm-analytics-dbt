#!/usr/bin/env python3
"""Generate a DuckDB table `status_summary` for the Evidence /status page.

Reads:
  - ingestion_manifest.json (lake snapshot, synthetic fallback)
  - target/run_results.json (dbt build PASS/FAIL)
  - target/freshness.json (source freshness warn/error)
  - palm_lake metadata via ducklake_snapshots (optional)

Writes:
  - palm.duckdb main.status_summary (single row, overwritten each run)
  - dashboard/static/status.json (for non-DuckDB consumers, optional)

This makes the observability that already exists in CI summaries also
visible to the dashboard user - the trust page.
"""
import json
import pathlib
import datetime as dt

import duckdb

MANIFEST = pathlib.Path("ingestion_manifest.json")
RUN_RESULTS = pathlib.Path("target/run_results.json")
FRESHNESS = pathlib.Path("target/freshness.json")
DB = pathlib.Path("palm.duckdb")
OUT_JSON = pathlib.Path("dashboard/static/status.json")

def load_json(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def main() -> int:
    manifest = load_json(MANIFEST) or {}
    run_results = load_json(RUN_RESULTS) or {}
    freshness = load_json(FRESHNESS) or {}

    # dbt run_results summary
    results = run_results.get("results", []) if isinstance(run_results, dict) else []
    counts = {"pass": 0, "warn": 0, "error": 0, "skip": 0}
    for r in results:
        s = (r.get("status") or "").lower()
        if s in counts:
            counts[s] += 1
        elif s == "success":
            counts["pass"] += 1
        elif s == "fail":
            counts["error"] += 1

    # freshness summary
    fresh = freshness.get("results", []) if isinstance(freshness, dict) else []
    fresh_summary = ", ".join(f"{(r.get('unique_id') or '').split('.')[-1]}:{r.get('status')}" for r in fresh) or "no freshness data"
    fresh_status = "ok"
    statuses = [r.get("status") for r in fresh]
    if "error" in statuses or "fail" in statuses:
        fresh_status = "error"
    elif "warn" in statuses:
        fresh_status = "warn"

    lake = manifest.get("lake", {}) if isinstance(manifest, dict) else {}
    row_counts = manifest.get("row_counts", {}) if isinstance(manifest, dict) else {}
    generated_at = manifest.get("generated_at") or dt.datetime.utcnow().isoformat() + "Z"
    warehouse = manifest.get("warehouse") or "ducklake"
    status = manifest.get("status") or "unknown"
    synthetic = manifest.get("synthetic_sources", 0)

    # lake snapshot via ducklake (best-effort, no hard dependency)
    lake_snapshot = lake.get("snapshot_id")
    if lake_snapshot is None:
        try:
            con = duckdb.connect()
            con.execute("LOAD ducklake")
            con.execute("ATTACH 'ducklake:palm_lake/palm.ducklake' AS palm_raw (DATA_PATH 'palm_lake/data')")
            lake_snapshot = con.execute("SELECT max(snapshot_id) FROM ducklake_snapshots('palm_raw')").fetchone()[0]
        except Exception:
            pass

    row = {
        "generated_at": generated_at,
        "warehouse": warehouse,
        "ingestion_status": status,
        "synthetic_sources": int(synthetic or 0),
        "lake_snapshot_id": lake_snapshot,
        "row_counts_json": json.dumps(row_counts),
        "dbt_pass": counts["pass"],
        "dbt_warn": counts["warn"],
        "dbt_error": counts["error"],
        "dbt_total": len(results),
        "freshness_summary": fresh_summary,
        "freshness_status": fresh_status,
    }

    # write to DuckDB for Evidence
    con = duckdb.connect(str(DB))
    con.execute("DROP TABLE IF EXISTS main.status_summary")
    con.execute("""
        CREATE TABLE main.status_summary (
            generated_at VARCHAR,
            warehouse VARCHAR,
            ingestion_status VARCHAR,
            synthetic_sources INTEGER,
            lake_snapshot_id INTEGER,
            row_counts_json VARCHAR,
            dbt_pass INTEGER,
            dbt_warn INTEGER,
            dbt_error INTEGER,
            dbt_total INTEGER,
            freshness_summary VARCHAR,
            freshness_status VARCHAR
        )
    """)
    con.execute("""
        INSERT INTO main.status_summary VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, [row[k] for k in ["generated_at","warehouse","ingestion_status","synthetic_sources","lake_snapshot_id","row_counts_json","dbt_pass","dbt_warn","dbt_error","dbt_total","freshness_summary","freshness_status"]])
    con.close()
    print(f"[status] wrote status_summary (pass={counts['pass']}/{len(results)}, freshness={fresh_status}, lake_snapshot={lake_snapshot}) -> {DB}")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(row, indent=2), encoding="utf-8")
    print(f"[status] wrote {OUT_JSON}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
