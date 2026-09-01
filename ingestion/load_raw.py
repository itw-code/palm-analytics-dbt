"""Ingest raw source data into DuckDB for the palm-analytics dbt project.

Heterogeneous free sources (all keyless):
  - Open-Meteo Archive      -> daily weather per region (temp, precip, wind, soil moisture, ET0, humidity)
  - Frankfurter (ECB)       -> USD->IDR daily FX
  - Nager.Date              -> Indonesia public holidays
  - World Bank Pink Sheet    -> palm oil + soybean oil monthly prices (best-effort xlsx; synthetic fallback)

Every source attempts a live fetch with retries and falls back to DETERMINISTIC
synthetic data when offline, so `dbt build` and CI are always reproducible.
Pass --live-only / --require-live to disable fallback (recommended for scheduled
production runs). When synthetic fallback is used, a machine-readable manifest
(ingestion_manifest.json) is written and a prominent WARNING is emitted so the
degradation is never silent.

Raw tables land in a DuckLake catalog (palm_lake/): open parquet data files with
ACID snapshot metadata from DuckDB Labs. Every run creates a new lake snapshot,
so the raw layer is point-in-time queryable ("what did the API return on March
3?") - the manifest records the snapshot id for auditability.

Writes lake tables: palm_raw.main.raw_weather, raw_weather_forecast, raw_fx_rate, raw_holidays, raw_commodity_price
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import time

import duckdb
import requests

LAKE_DIR = "palm_lake"
LAKE_META = f"{LAKE_DIR}/palm.ducklake"
LAKE_DATA = f"{LAKE_DIR}/data"
LAKE_ALIAS = "palm_raw"
MANIFEST_DEFAULT = "ingestion_manifest.json"

REGIONS = {
    "riau":                (0.51, 101.45),
    "north_sumatra":       (3.59, 98.67),
    "central_kalimantan": (-1.68, 113.38),
}

# Fixed end-date keeps CI fully deterministic. Override with PALM_END_DATE=YYYY-MM-DD
# or --end-date for a live scheduled run (e.g. yesterday).
DEFAULT_END_DATE = dt.date(2026, 6, 30)
WINDOW_DAYS = 120
FORECAST_WINDOW = 7
FORECAST_DAILY_VARS = "temperature_2m_mean,precipitation_sum,wind_speed_10m_max,et0_fao_evapotranspiration,relative_humidity_2m_mean,soil_moisture_0_to_10cm_mean"


def resolve_end_date(cli_end_date: str | None) -> dt.date:
    if cli_end_date:
        return dt.date.fromisoformat(cli_end_date)
    env = os.getenv("PALM_END_DATE")
    if env:
        return dt.date.fromisoformat(env)
    # When running on a schedule in production you want fresh data up to yesterday.
    # Set PALM_USE_LIVE_DATE=1 in the scheduled workflow to opt in.
    if os.getenv("PALM_USE_LIVE_DATE") == "1":
        return dt.date.today() - dt.timedelta(days=1)
    return DEFAULT_END_DATE


def date_range(days: int, end_date: dt.date) -> list[dt.date]:
    return [end_date - dt.timedelta(days=i) for i in range(days - 1, -1, -1)]


def region_hash(region: str) -> float:
    return (sum(ord(c) for c in region) % 10) / 10.0


# --------------------------------------------------------------------------- retry helper
def fetch_with_retry(fn, *, retries: int = 3, backoff: float = 2.0, label: str = ""):
    """Call fn() up to retries times with exponential backoff. Re-raises last error."""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt == retries:
                break
            sleep_s = backoff * attempt
            print(f"[{label}] attempt {attempt}/{retries} failed ({e.__class__.__name__}: {e}) — retrying in {sleep_s:.0f}s",
                  file=sys.stderr)
            time.sleep(sleep_s)
    assert last_exc is not None
    raise last_exc


# --------------------------------------------------------------------------- weather
def fetch_weather_live(region, lat, lon, dates) -> list[dict]:
    start, end = dates[0].isoformat(), dates[-1].isoformat()
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}&start_date={start}&end_date={end}"
        "&daily=temperature_2m_mean,precipitation_sum,wind_speed_10m_max,"
        "et0_fao_evapotranspiration,relative_humidity_2m_mean,soil_moisture_0_to_7cm_mean"
        "&timezone=Asia%2FJakarta"
    )
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    d = r.json()["daily"]

    def col(name):
        return d.get(name) or [None] * len(d["time"])

    temp, precip, wind = col("temperature_2m_mean"), col("precipitation_sum"), col("wind_speed_10m_max")
    et0, hum, soil = col("et0_fao_evapotranspiration"), col("relative_humidity_2m_mean"), col("soil_moisture_0_to_7cm_mean")
    rows = []
    for i, day in enumerate(d["time"]):
        rows.append({
            "region": region, "obs_date": day,
            "temp_mean_c": temp[i], "precip_mm": precip[i], "wind_max_kmh": wind[i],
            "et0_mm": et0[i], "humidity_pct": hum[i], "soil_moisture": soil[i],
        })
    if not rows:
        raise ValueError("Open-Meteo returned 0 rows")
    return rows


def synth_weather(region, seed_offset, dates) -> list[dict]:
    rows = []
    for i, day in enumerate(dates):
        phase = (day.timetuple().tm_yday + seed_offset) / 365 * 2 * math.pi
        temp = 27.0 + 2.5 * math.sin(phase)
        precip = max(0.0, 8.0 + 12.0 * math.sin(phase + region_hash(region)))
        wind = 6.0 + 4.0 * abs(math.sin(phase * 2))
        et0 = 3.5 + 1.2 * math.sin(phase + 1)
        humidity = 78.0 + 10.0 * math.sin(phase + 0.5)
        soil = round(0.28 + 0.08 * math.sin(phase + region_hash(region)), 3)
        rows.append({
            "region": region, "obs_date": day.isoformat(),
            "temp_mean_c": round(temp, 2), "precip_mm": round(precip, 2), "wind_max_kmh": round(wind, 2),
            "et0_mm": round(et0, 2), "humidity_pct": round(humidity, 1), "soil_moisture": soil,
        })
    return rows


def fetch_forecast_live(region, lat, lon, dates) -> list[dict]:
    """Fetch 7-day forecast from Open-Meteo.
    Chooses forecast vs historical-forecast endpoint based on whether the window
    is in the future (today is the pivot). Historical-forecast covers past dates
    so deterministic CI with a fixed END_DATE keeps working offline."""
    start, end = dates[0].isoformat(), dates[-1].isoformat()
    today = dt.date.today().isoformat()
    if end < today:
        base = "https://historical-forecast-api.open-meteo.com/v1/forecast"
    elif start >= today:
        base = "https://api.open-meteo.com/v1/forecast"
    else:
        base = "https://api.open-meteo.com/v1/forecast"
    url = (
        f"{base}?latitude={lat}&longitude={lon}&start_date={start}&end_date={end}"
        f"&daily={FORECAST_DAILY_VARS}&timezone=Asia%2FJakarta"
    )
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    d = r.json()["daily"]

    def col(name):
        return d.get(name) or [None] * len(d["time"])

    temp, precip, wind = col("temperature_2m_mean"), col("precipitation_sum"), col("wind_speed_10m_max")
    et0, hum, soil = col("et0_fao_evapotranspiration"), col("relative_humidity_2m_mean"), col("soil_moisture_0_to_10cm_mean")
    rows = []
    for i, day in enumerate(d["time"]):
        rows.append({
            "region": region, "obs_date": day,
            "temp_mean_c": temp[i], "precip_mm": precip[i], "wind_max_kmh": wind[i],
            "et0_mm": et0[i], "humidity_pct": hum[i], "soil_moisture": soil[i],
        })
    if not rows:
        raise ValueError("Forecast API returned 0 rows")
    return rows


# --------------------------------------------------------------------------- FX (Frankfurter)
def fetch_fx_live(dates) -> list[dict]:
    start, end = dates[0].isoformat(), dates[-1].isoformat()
    url = f"https://api.frankfurter.dev/v1/{start}..{end}?base=USD&symbols=IDR"
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    rates = r.json()["rates"]  # business-day series -> forward-filled in dbt
    rows = [{"rate_date": d, "usd_idr": v["IDR"]} for d, v in sorted(rates.items())]
    if not rows:
        raise ValueError("Frankfurter returned 0 rows")
    return rows


def synth_fx(dates) -> list[dict]:
    rows = []
    for i, day in enumerate(dates):
        if day.weekday() >= 5:  # mimic ECB: business days only
            continue
        rate = 16000 + 400 * math.sin(i / 45.0)
        rows.append({"rate_date": day.isoformat(), "usd_idr": round(rate, 2)})
    return rows


# --------------------------------------------------------------------------- holidays (Nager.Date)
def fetch_holidays_live(years) -> list[dict]:
    rows = []
    for y in years:
        r = requests.get(f"https://date.nager.at/api/v3/PublicHolidays/{y}/ID", timeout=25)
        r.raise_for_status()
        for h in r.json():
            rows.append({"holiday_date": h["date"], "holiday_name": h.get("name", "")})
    if not rows:
        raise ValueError("Nager.Date returned 0 rows")
    return rows


def synth_holidays(years) -> list[dict]:
    # Deterministic subset of well-known Indonesian public holidays.
    fixed = {"01-01": "New Year's Day", "05-01": "Labour Day", "06-01": "Pancasila Day",
             "08-17": "Independence Day", "12-25": "Christmas Day"}
    rows = []
    for y in years:
        for md, name in fixed.items():
            rows.append({"holiday_date": f"{y}-{md}", "holiday_name": name})
    return rows


# --------------------------------------------------------------------------- commodity (World Bank)
WB_XLSX = "https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/related/CMO-Historical-Data-Monthly.xlsx"


def fetch_commodity_live(months) -> list[dict] | None:
    """Best-effort World Bank Pink Sheet (monthly xlsx). Returns None on any failure
    (unstable URL / no openpyxl) so the caller uses the synthetic series."""
    try:
        import io
        import openpyxl  # optional dependency
        r = requests.get(WB_XLSX, timeout=30)
        r.raise_for_status()
        wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True, data_only=True)
        # Parsing the multi-header Monthly Prices sheet is intentionally left as a hook;
        # returning None keeps the pipeline deterministic until a parser is wired.
        return None
    except Exception:
        return None


def synth_commodity(months) -> list[dict]:
    rows = []
    for i, m in enumerate(months):
        palm = 950 + 70 * math.sin(i / 3.0)
        soy = 1040 + 55 * math.sin(i / 3.0 + 0.6)   # soybean oil, the key substitute
        rows.append({"price_month": m.isoformat(), "commodity": "palm_oil", "usd_per_tonne": round(palm, 2)})
        rows.append({"price_month": m.isoformat(), "commodity": "soybean_oil", "usd_per_tonne": round(soy, 2)})
    return rows


def month_starts(dates) -> list[dt.date]:
    seen, out = set(), []
    for d in dates:
        k = (d.year, d.month)
        if k not in seen:
            seen.add(k)
            out.append(dt.date(d.year, d.month, 1))
    return out


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live-only", action="store_true", help="Fail instead of using synthetic fallback (alias for --require-live)")
    ap.add_argument("--require-live", action="store_true", help="Fail if any source must fall back to synthetic")
    ap.add_argument("--allow-synthetic", action="store_true", default=True, help="Allow synthetic fallback (default: true, disable with --require-live)")
    ap.add_argument("--manifest", default=MANIFEST_DEFAULT, help="Path to write ingestion manifest JSON")
    ap.add_argument("--end-date", default=None, help="Override end date (YYYY-MM-DD); default 2026-06-30 or PALM_END_DATE / PALM_USE_LIVE_DATE")
    ap.add_argument("--window-days", type=int, default=WINDOW_DAYS, help="Number of days to ingest")
    args = ap.parse_args()

    require_live = args.live_only or args.require_live
    # --require-live takes precedence over --allow-synthetic
    allow_synthetic = not require_live

    end_date = resolve_end_date(args.end_date)
    dates = date_range(args.window_days, end_date)
    forecast_dates = [end_date + dt.timedelta(days=i) for i in range(1, FORECAST_WINDOW + 1)]
    years = sorted({d.year for d in dates} | {d.year for d in forecast_dates})
    months = month_starts(dates)

    provenance: dict = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "end_date": end_date.isoformat(),
        "window_days": args.window_days,
        "require_live": require_live,
        "sources": {},
    }
    synth_count = 0

    # weather
    weather = []
    for offset, (region, (lat, lon)) in enumerate(REGIONS.items()):
        try:
            rows = fetch_with_retry(lambda r=region, la=lat, lo=lon: fetch_weather_live(r, la, lo, dates),
                                    label=f"weather:{region}")
            weather += rows
            print(f"[weather] live OK: {region} ({len(rows)} rows)")
            provenance["sources"].setdefault("weather", {})[region] = {"mode": "live", "rows": len(rows)}
        except Exception as e:
            if not allow_synthetic:
                print(f"[weather] live FAILED {region}: {e}", file=sys.stderr)
                provenance["sources"].setdefault("weather", {})[region] = {"mode": "failed", "error": f"{e.__class__.__name__}: {e}"}
                _write_manifest(args.manifest, provenance, synth_count, status="failed")
                return 1
            rows = synth_weather(region, offset, dates)
            weather += rows
            synth_count += 1
            print(f"[weather] synthetic fallback: {region} ({e.__class__.__name__}: {e})", file=sys.stderr)
            provenance["sources"].setdefault("weather", {})[region] = {"mode": "synthetic", "rows": len(rows), "error": f"{e.__class__.__name__}: {e}"}

    # forecast (7 days ahead) - prescriptive, not just retrospective
    forecast = []
    for offset, (region, (lat, lon)) in enumerate(REGIONS.items()):
        try:
            rows = fetch_with_retry(lambda r=region, la=lat, lo=lon: fetch_forecast_live(r, la, lo, forecast_dates),
                                    label=f"forecast:{region}")
            forecast += rows
            print(f"[forecast] live OK: {region} ({len(rows)} rows)")
            provenance["sources"].setdefault("forecast", {})[region] = {"mode": "live", "rows": len(rows)}
        except Exception as e:
            if not allow_synthetic:
                print(f"[forecast] live FAILED {region}: {e}", file=sys.stderr)
                provenance["sources"].setdefault("forecast", {})[region] = {"mode": "failed", "error": f"{e.__class__.__name__}: {e}"}
                _write_manifest(args.manifest, provenance, synth_count, status="failed")
                return 1
            rows = synth_weather(region, offset + 10, forecast_dates)
            forecast += rows
            synth_count += 1
            print(f"[forecast] synthetic fallback: {region} ({e.__class__.__name__}: {e})", file=sys.stderr)
            provenance["sources"].setdefault("forecast", {})[region] = {"mode": "synthetic", "rows": len(rows), "error": f"{e.__class__.__name__}: {e}"}

    # fx
    try:
        fx = fetch_with_retry(lambda: fetch_fx_live(dates), label="fx")
        print(f"[fx] live OK ({len(fx)} rows)")
        provenance["sources"]["fx"] = {"mode": "live", "rows": len(fx)}
    except Exception as e:
        if not allow_synthetic:
            print(f"[fx] live FAILED: {e}", file=sys.stderr)
            provenance["sources"]["fx"] = {"mode": "failed", "error": f"{e.__class__.__name__}: {e}"}
            _write_manifest(args.manifest, provenance, synth_count, status="failed")
            return 1
        fx = synth_fx(dates)
        synth_count += 1
        print(f"[fx] synthetic fallback ({e.__class__.__name__}: {e})", file=sys.stderr)
        provenance["sources"]["fx"] = {"mode": "synthetic", "rows": len(fx), "error": f"{e.__class__.__name__}: {e}"}

    # holidays
    try:
        holidays = fetch_with_retry(lambda: fetch_holidays_live(years), label="holidays")
        print(f"[holidays] live OK ({len(holidays)} rows)")
        provenance["sources"]["holidays"] = {"mode": "live", "rows": len(holidays)}
    except Exception as e:
        if not allow_synthetic:
            print(f"[holidays] live FAILED: {e}", file=sys.stderr)
            provenance["sources"]["holidays"] = {"mode": "failed", "error": f"{e.__class__.__name__}: {e}"}
            _write_manifest(args.manifest, provenance, synth_count, status="failed")
            return 1
        holidays = synth_holidays(years)
        synth_count += 1
        print(f"[holidays] synthetic fallback ({e.__class__.__name__}: {e})", file=sys.stderr)
        provenance["sources"]["holidays"] = {"mode": "synthetic", "rows": len(holidays), "error": f"{e.__class__.__name__}: {e}"}

    # commodity
    commodity = fetch_commodity_live(months)
    if commodity is None:
        if require_live:
            print("[commodity] live source not wired (parser stub) and --require-live set", file=sys.stderr)
            provenance["sources"]["commodity"] = {"mode": "failed", "error": "parser not wired - World Bank xlsx parsing stub returns None"}
            _write_manifest(args.manifest, provenance, synth_count, status="failed")
            return 1
        commodity = synth_commodity(months)
        synth_count += 1
        # Distinguish known stub limitation from transient API failure
        print("[commodity] synthetic (World Bank parser stub - known limitation; synthetic series used)", file=sys.stderr)
        provenance["sources"]["commodity"] = {"mode": "synthetic", "rows": len(commodity), "error": "parser not wired - synthetic fallback (known limitation)"}
    else:
        print(f"[commodity] live OK ({len(commodity)} rows)")
        provenance["sources"]["commodity"] = {"mode": "live", "rows": len(commodity)}

    con = _open_lake()
    # One ACID transaction for the whole load: either every raw table lands or
    # none does (a mid-run crash leaves the previous snapshot readable), and we
    # get ONE new snapshot instead of hundreds (each autocommit batch otherwise
    # commits its own snapshot + parquet file).
    con.execute("BEGIN TRANSACTION")
    con.execute(f"DROP TABLE IF EXISTS {LAKE_ALIAS}.main.raw_weather")
    con.execute(f"""CREATE TABLE {LAKE_ALIAS}.main.raw_weather (
        region VARCHAR, obs_date DATE, temp_mean_c DOUBLE, precip_mm DOUBLE, wind_max_kmh DOUBLE,
        et0_mm DOUBLE, humidity_pct DOUBLE, soil_moisture DOUBLE)""")
    con.executemany(f"INSERT INTO {LAKE_ALIAS}.main.raw_weather VALUES (?,?,?,?,?,?,?,?)",
        [(r["region"], r["obs_date"], r["temp_mean_c"], r["precip_mm"], r["wind_max_kmh"],
          r["et0_mm"], r["humidity_pct"], r["soil_moisture"]) for r in weather])

    con.execute(f"DROP TABLE IF EXISTS {LAKE_ALIAS}.main.raw_weather_forecast")
    con.execute(f"""CREATE TABLE {LAKE_ALIAS}.main.raw_weather_forecast (
        region VARCHAR, forecast_date DATE, temp_mean_c DOUBLE, precip_mm DOUBLE, wind_max_kmh DOUBLE,
        et0_mm DOUBLE, humidity_pct DOUBLE, soil_moisture DOUBLE)""")
    con.executemany(f"INSERT INTO {LAKE_ALIAS}.main.raw_weather_forecast VALUES (?,?,?,?,?,?,?,?)",
        [(r["region"], r["obs_date"], r["temp_mean_c"], r["precip_mm"], r["wind_max_kmh"],
          r["et0_mm"], r["humidity_pct"], r["soil_moisture"]) for r in forecast])

    con.execute(f"DROP TABLE IF EXISTS {LAKE_ALIAS}.main.raw_fx_rate")
    con.execute(f"CREATE TABLE {LAKE_ALIAS}.main.raw_fx_rate (rate_date DATE, usd_idr DOUBLE)")
    con.executemany(f"INSERT INTO {LAKE_ALIAS}.main.raw_fx_rate VALUES (?,?)", [(r["rate_date"], r["usd_idr"]) for r in fx])

    con.execute(f"DROP TABLE IF EXISTS {LAKE_ALIAS}.main.raw_holidays")
    con.execute(f"CREATE TABLE {LAKE_ALIAS}.main.raw_holidays (holiday_date DATE, holiday_name VARCHAR)")
    con.executemany(f"INSERT INTO {LAKE_ALIAS}.main.raw_holidays VALUES (?,?)", [(r["holiday_date"], r["holiday_name"]) for r in holidays])

    con.execute(f"DROP TABLE IF EXISTS {LAKE_ALIAS}.main.raw_commodity_price")
    con.execute(f"CREATE TABLE {LAKE_ALIAS}.main.raw_commodity_price (price_month DATE, commodity VARCHAR, usd_per_tonne DOUBLE)")
    con.executemany(f"INSERT INTO {LAKE_ALIAS}.main.raw_commodity_price VALUES (?,?,?)",
        [(r["price_month"], r["commodity"], r["usd_per_tonne"]) for r in commodity])

    counts = {t: con.execute(f"SELECT count(*) FROM {LAKE_ALIAS}.main.{t}").fetchone()[0]
              for t in ("raw_weather", "raw_weather_forecast", "raw_fx_rate", "raw_holidays", "raw_commodity_price")}
    con.execute("COMMIT")

    # ACID snapshot id of this load - recorded in the manifest for point-in-time audits
    lake_snapshot = None
    try:
        lake_snapshot = con.execute(f"SELECT max(snapshot_id) FROM ducklake_snapshots('{LAKE_ALIAS}')").fetchone()[0]
    except Exception as e:
        print(f"[lake] snapshot id lookup failed (non-fatal): {e}", file=sys.stderr)
    con.close()
    print(f"[ducklake] {counts} snapshot={lake_snapshot} -> {LAKE_META}")

    status = "synthetic_fallback" if synth_count > 0 else "live"
    prov = provenance
    prov_lake = {"catalog": LAKE_META, "data_path": LAKE_DATA, "snapshot_id": lake_snapshot}
    _write_manifest(args.manifest, prov, synth_count, status=status, counts=counts, lake=prov_lake)

    if synth_count > 0:
        # Never silent: emit a banner that survives in logs and is detectable by CI.
        print(f"\n::warning::[ingestion] {synth_count} source(s) used SYNTHETIC fallback - see {args.manifest} for provenance. "
              "In production (scheduled runs) this should be investigated; pass --require-live to fail-fast.", file=sys.stderr)
        # Also surface commodity stub note
        if provenance["sources"].get("commodity", {}).get("mode") == "synthetic":
            print("::notice::[ingestion] commodity price is ALWAYS synthetic until World Bank parser is wired (known limitation).", file=sys.stderr)

    return 0


def _open_lake():
    """Open a DuckDB connection with the DuckLake catalog attached as `palm_raw`.
    The ducklake extension auto-installs on first use (needs network on cold CI runners)."""
    os.makedirs(LAKE_DIR, exist_ok=True)
    con = duckdb.connect()          # ephemeral; the lake + parquet files are the state
    try:
        con.execute("INSTALL ducklake")
        con.execute("LOAD ducklake")
    except Exception as e:
        raise SystemExit(
            f"[lake] FATAL: ducklake extension unavailable ({e.__class__.__name__}: {e}). "
            "Cold runner needs network for extension install; re-run or pin duckdb>=1.2."
        )
    con.execute(
        f"ATTACH 'ducklake:{LAKE_META}' AS {LAKE_ALIAS} (DATA_PATH '{LAKE_DATA}')"
    )
    return con


def _write_manifest(path: str, provenance: dict, synth_count: int, status: str = "live", counts: dict | None = None, lake: dict | None = None):
    provenance["synthetic_sources"] = synth_count
    provenance["status"] = status
    provenance["warehouse"] = "ducklake"
    if lake:
        provenance["lake"] = lake
    if counts:
        provenance["row_counts"] = counts
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(provenance, f, indent=2)
        print(f"[manifest] wrote {path} (status={status}, synthetic={synth_count})")
    except Exception as e:
        print(f"[manifest] FAILED to write {path}: {e}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
