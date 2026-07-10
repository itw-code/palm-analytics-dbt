"""Ingest raw source data into DuckDB for the palm-analytics dbt project.

Sources:
  - Open-Meteo Archive API   -> daily weather per estate region
  - World Bank CPO price      -> monthly crude palm oil USD/tonne (forward-filled to daily)

Both attempt a live fetch and fall back to DETERMINISTIC synthetic data when offline,
so `dbt build` and CI are always reproducible. Pass --live-only to disable the fallback.

Writes two raw tables to palm.duckdb:  raw_weather, raw_cpo_price
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import sys

import duckdb
import requests

DB_PATH = "palm.duckdb"

# A few representative Indonesian palm-oil estate regions (Sumatra / Kalimantan).
REGIONS = {
    "riau":            (0.51, 101.45),
    "north_sumatra":   (3.59, 98.67),
    "central_kalimantan": (-1.68, 113.38),
}

WINDOW_DAYS = 120


def _date_range(days: int) -> list[dt.date]:
    end = dt.date(2026, 6, 30)  # fixed end date -> deterministic runs (no Date.now drift)
    return [end - dt.timedelta(days=i) for i in range(days - 1, -1, -1)]


def fetch_weather_live(region: str, lat: float, lon: float, dates: list[dt.date]) -> list[dict]:
    start, end = dates[0].isoformat(), dates[-1].isoformat()
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}&start_date={start}&end_date={end}"
        "&daily=temperature_2m_mean,precipitation_sum,wind_speed_10m_max"
        "&timezone=Asia%2FJakarta"
    )
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    d = r.json()["daily"]
    rows = []
    for i, day in enumerate(d["time"]):
        rows.append({
            "region": region,
            "obs_date": day,
            "temp_mean_c": d["temperature_2m_mean"][i],
            "precip_mm": d["precipitation_sum"][i],
            "wind_max_kmh": d["wind_speed_10m_max"][i],
        })
    return rows


def synth_weather(region: str, seed_offset: int, dates: list[dt.date]) -> list[dict]:
    """Deterministic tropical-climate synthetic weather (no randomness -> reproducible)."""
    rows = []
    for i, day in enumerate(dates):
        phase = (day.timetuple().tm_yday + seed_offset) / 365 * 2 * math.pi
        temp = 27.0 + 2.5 * math.sin(phase)
        precip = max(0.0, 8.0 + 12.0 * math.sin(phase + region_hash(region)))
        wind = 6.0 + 4.0 * abs(math.sin(phase * 2))
        rows.append({
            "region": region,
            "obs_date": day.isoformat(),
            "temp_mean_c": round(temp, 2),
            "precip_mm": round(precip, 2),
            "wind_max_kmh": round(wind, 2),
        })
    return rows


def region_hash(region: str) -> float:
    return (sum(ord(c) for c in region) % 10) / 10.0


def fetch_cpo_live(dates: list[dt.date]) -> list[dict] | None:
    """World Bank commodity 'Pink Sheet' is not a clean JSON API; live mode is a
    placeholder hook. Returns None so the caller uses the synthetic series unless
    a real endpoint is wired in here."""
    return None


def synth_cpo(dates: list[dt.date]) -> list[dict]:
    """Deterministic CPO price random-walk-free series around ~950 USD/tonne."""
    rows = []
    base = 950.0
    for i, day in enumerate(dates):
        drift = 60.0 * math.sin(i / 30.0)
        seasonal = 25.0 * math.sin(day.timetuple().tm_yday / 365 * 2 * math.pi)
        rows.append({
            "price_date": day.isoformat(),
            "cpo_usd_per_tonne": round(base + drift + seasonal, 2),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live-only", action="store_true", help="Fail instead of using synthetic fallback")
    args = ap.parse_args()

    dates = _date_range(WINDOW_DAYS)
    weather_rows: list[dict] = []
    for offset, (region, (lat, lon)) in enumerate(REGIONS.items()):
        try:
            weather_rows += fetch_weather_live(region, lat, lon, dates)
            print(f"[weather] live OK: {region}")
        except Exception as e:  # network/DNS/ratelimit
            if args.live_only:
                print(f"[weather] live FAILED for {region}: {e}", file=sys.stderr)
                return 1
            weather_rows += synth_weather(region, offset, dates)
            print(f"[weather] synthetic fallback: {region} ({e.__class__.__name__})")

    cpo_rows = fetch_cpo_live(dates)
    if cpo_rows is None:
        if args.live_only:
            print("[cpo] live source not wired and --live-only set", file=sys.stderr)
            return 1
        cpo_rows = synth_cpo(dates)
        print("[cpo] synthetic series")

    con = duckdb.connect(DB_PATH)
    con.execute("CREATE OR REPLACE TABLE raw_weather (region VARCHAR, obs_date DATE, temp_mean_c DOUBLE, precip_mm DOUBLE, wind_max_kmh DOUBLE)")
    con.executemany(
        "INSERT INTO raw_weather VALUES (?, ?, ?, ?, ?)",
        [(r["region"], r["obs_date"], r["temp_mean_c"], r["precip_mm"], r["wind_max_kmh"]) for r in weather_rows],
    )
    con.execute("CREATE OR REPLACE TABLE raw_cpo_price (price_date DATE, cpo_usd_per_tonne DOUBLE)")
    con.executemany(
        "INSERT INTO raw_cpo_price VALUES (?, ?)",
        [(r["price_date"], r["cpo_usd_per_tonne"]) for r in cpo_rows],
    )
    n_w = con.execute("SELECT count(*) FROM raw_weather").fetchone()[0]
    n_c = con.execute("SELECT count(*) FROM raw_cpo_price").fetchone()[0]
    con.close()
    print(f"[duckdb] wrote raw_weather={n_w} rows, raw_cpo_price={n_c} rows -> {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
