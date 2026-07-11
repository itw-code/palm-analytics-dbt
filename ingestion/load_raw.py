"""Ingest raw source data into DuckDB for the palm-analytics dbt project.

Heterogeneous free sources (all keyless):
  - Open-Meteo Archive      -> daily weather per region (temp, precip, wind, soil moisture, ET0, humidity)
  - Frankfurter (ECB)       -> USD->IDR daily FX
  - Nager.Date              -> Indonesia public holidays
  - World Bank Pink Sheet    -> palm oil + soybean oil monthly prices (best-effort xlsx; synthetic fallback)

Every source attempts a live fetch and falls back to DETERMINISTIC synthetic data when
offline, so `dbt build` and CI are always reproducible. Pass --live-only to disable fallback.

Writes raw tables: raw_weather, raw_fx_rate, raw_holidays, raw_commodity_price
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import sys

import duckdb
import requests

DB_PATH = "palm.duckdb"

REGIONS = {
    "riau":                (0.51, 101.45),
    "north_sumatra":       (3.59, 98.67),
    "central_kalimantan": (-1.68, 113.38),
}

END_DATE = dt.date(2026, 6, 30)   # fixed -> deterministic (no wall-clock drift)
WINDOW_DAYS = 120


def date_range(days: int) -> list[dt.date]:
    return [END_DATE - dt.timedelta(days=i) for i in range(days - 1, -1, -1)]


def region_hash(region: str) -> float:
    return (sum(ord(c) for c in region) % 10) / 10.0


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


# --------------------------------------------------------------------------- FX (Frankfurter)
def fetch_fx_live(dates) -> list[dict]:
    start, end = dates[0].isoformat(), dates[-1].isoformat()
    url = f"https://api.frankfurter.dev/v1/{start}..{end}?base=USD&symbols=IDR"
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    rates = r.json()["rates"]  # business-day series -> forward-filled in dbt
    return [{"rate_date": d, "usd_idr": v["IDR"]} for d, v in sorted(rates.items())]


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
    ap.add_argument("--live-only", action="store_true")
    args = ap.parse_args()

    dates = date_range(WINDOW_DAYS)
    years = sorted({d.year for d in dates})
    months = month_starts(dates)

    # weather
    weather = []
    for offset, (region, (lat, lon)) in enumerate(REGIONS.items()):
        try:
            weather += fetch_weather_live(region, lat, lon, dates); print(f"[weather] live OK: {region}")
        except Exception as e:
            if args.live_only:
                print(f"[weather] live FAILED {region}: {e}", file=sys.stderr); return 1
            weather += synth_weather(region, offset, dates); print(f"[weather] synthetic: {region} ({e.__class__.__name__})")

    # fx
    try:
        fx = fetch_fx_live(dates); print(f"[fx] live OK ({len(fx)} rows)")
    except Exception as e:
        if args.live_only:
            print(f"[fx] live FAILED: {e}", file=sys.stderr); return 1
        fx = synth_fx(dates); print(f"[fx] synthetic ({e.__class__.__name__})")

    # holidays
    try:
        holidays = fetch_holidays_live(years); print(f"[holidays] live OK ({len(holidays)} rows)")
    except Exception as e:
        if args.live_only:
            print(f"[holidays] live FAILED: {e}", file=sys.stderr); return 1
        holidays = synth_holidays(years); print(f"[holidays] synthetic ({e.__class__.__name__})")

    # commodity
    commodity = fetch_commodity_live(months)
    if commodity is None:
        if args.live_only:
            print("[commodity] live source not wired and --live-only set", file=sys.stderr); return 1
        commodity = synth_commodity(months); print(f"[commodity] synthetic ({len(commodity)} rows)")
    else:
        print(f"[commodity] live OK ({len(commodity)} rows)")

    con = duckdb.connect(DB_PATH)
    con.execute("""CREATE OR REPLACE TABLE raw_weather (
        region VARCHAR, obs_date DATE, temp_mean_c DOUBLE, precip_mm DOUBLE, wind_max_kmh DOUBLE,
        et0_mm DOUBLE, humidity_pct DOUBLE, soil_moisture DOUBLE)""")
    con.executemany("INSERT INTO raw_weather VALUES (?,?,?,?,?,?,?,?)",
        [(r["region"], r["obs_date"], r["temp_mean_c"], r["precip_mm"], r["wind_max_kmh"],
          r["et0_mm"], r["humidity_pct"], r["soil_moisture"]) for r in weather])

    con.execute("CREATE OR REPLACE TABLE raw_fx_rate (rate_date DATE, usd_idr DOUBLE)")
    con.executemany("INSERT INTO raw_fx_rate VALUES (?,?)", [(r["rate_date"], r["usd_idr"]) for r in fx])

    con.execute("CREATE OR REPLACE TABLE raw_holidays (holiday_date DATE, holiday_name VARCHAR)")
    con.executemany("INSERT INTO raw_holidays VALUES (?,?)", [(r["holiday_date"], r["holiday_name"]) for r in holidays])

    con.execute("CREATE OR REPLACE TABLE raw_commodity_price (price_month DATE, commodity VARCHAR, usd_per_tonne DOUBLE)")
    con.executemany("INSERT INTO raw_commodity_price VALUES (?,?,?)",
        [(r["price_month"], r["commodity"], r["usd_per_tonne"]) for r in commodity])

    counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
              for t in ("raw_weather", "raw_fx_rate", "raw_holidays", "raw_commodity_price")}
    con.close()
    print(f"[duckdb] {counts} -> {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
