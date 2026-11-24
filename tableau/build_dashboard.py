"""Build self-contained HTML/SVG analytical workbench from certified Tableau CSV extracts.

Reads exclusively from ``tableau/export/*.csv`` and ``tableau/export/manifest.json``
without modifying dbt models, DuckDB state, or CSV extracts.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EXPORT_DIR = HERE / "export"
OUT_HTML = HERE / "dashboard.html"


def _read_csv(filename: str) -> list[dict[str, str]]:
    path = EXPORT_DIR / filename
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _to_bool(val: str) -> bool:
    return str(val).strip().lower() == "true"


def _to_float(val: str) -> float:
    return float(val) if val not in ("", None) else 0.0


def build_payload() -> dict[str, Any]:
    """Assemble verified JSON payload directly from CSV extracts and manifest."""
    manifest = json.loads((EXPORT_DIR / "manifest.json").read_text(encoding="utf-8"))
    regions_raw = _read_csv("dim_region__region_key.csv")
    margin_raw = _read_csv("fct_estate_margin_daily__region_date.csv")
    ops_raw = _read_csv("fct_estate_operations_daily__region_date.csv")
    price_raw = _read_csv("fct_commodity_price_daily__price_date.csv")
    anomaly_raw = _read_csv("rec_anomaly_flags__region_date.csv")
    whatif_raw = _read_csv("whatif_margin_shocks__region_scenario.csv")
    forecast_raw = _read_csv("forecast_cpo_30day__forecast_date.csv")

    ops_index = {
        (r["region_key"], r["operation_date"]): r
        for r in ops_raw
    }
    anom_index = {
        (r["region_key"], r["operation_date"]): r
        for r in anomaly_raw
    }

    order = ["central_kalimantan", "lampung", "north_sumatra", "riau"]
    colors = {
        "central_kalimantan": "#7A5F28",
        "lampung": "#8C4A6B",
        "north_sumatra": "#3F6B52",
        "riau": "#1F7A80",
    }
    dark_colors = {
        "central_kalimantan": "#D4B46A",
        "lampung": "#C489A4",
        "north_sumatra": "#8FBF9C",
        "riau": "#7EB8BC",
    }

    regions: dict[str, dict[str, Any]] = {}
    names: dict[str, str] = {}
    managers: dict[str, str] = {}
    for r in regions_raw:
        rk = r["region_key"]
        names[rk] = r["region_name"]
        managers[rk] = r["estate_manager"]
        regions[rk] = {
            "region_key": rk,
            "region_name": r["region_name"],
            "island": r["island"],
            "planted_hectares": _to_float(r["planted_hectares"]),
            "yield_t_ha": _to_float(r["yield_t_ha"]),
            "estate_manager": r["estate_manager"],
        }

    months = ["2026-03", "2026-04", "2026-05", "2026-06"]
    monthly: dict[str, dict[str, float]] = {m: {rk: 0.0 for rk in order} for m in months}
    monthly_total: dict[str, dict[str, float]] = {m: {rk: 0.0 for rk in order} for m in months}
    harvest: dict[str, dict[str, int]] = {m: {rk: 0 for rk in order} for m in months}
    period: dict[str, float] = {rk: 0.0 for rk in order}
    period_total: dict[str, float] = {rk: 0.0 for rk in order}
    harvest_period: dict[str, int] = {rk: 0 for rk in order}

    daily_ops: list[dict[str, Any]] = []
    for mrow in margin_raw:
        rk = mrow["region_key"]
        dt = mrow["operation_date"]
        mo = dt[:7]
        orow = ops_index[(rk, dt)]
        arow = anom_index.get((rk, dt), {})

        eff = _to_bool(mrow["is_effective_harvest_day"])
        harv_fav = _to_bool(orow["is_harvest_favorable"])
        is_hol = _to_bool(orow["is_holiday"])
        is_wknd = _to_bool(orow["is_weekend"])
        margin_ha = _to_float(mrow["margin_idr_per_ha"])
        margin_tot = _to_float(mrow["margin_total_idr"])
        rev_ha = _to_float(mrow["revenue_idr_per_ha"])
        fert_ha = _to_float(mrow["fertilizer_cost_idr_per_ha"])
        harv_cost_ha = _to_float(mrow["harvest_cost_idr_per_ha"]) if eff else 0.0
        transp_ha = _to_float(mrow["transport_cost_idr_per_ha"])

        if eff:
            status = "harvest"
        elif harv_fav and is_hol:
            status = "holiday"
        elif harv_fav and is_wknd:
            status = "weekend"
        else:
            status = "weather"

        monthly[mo][rk] += margin_ha
        monthly_total[mo][rk] += margin_tot
        period[rk] += margin_ha
        period_total[rk] += margin_tot
        if eff:
            harvest[mo][rk] += 1
            harvest_period[rk] += 1

        daily_ops.append({
            "r": rk,
            "d": dt,
            "st": status,
            "eff": eff,
            "m": round(margin_ha, 0),
            "mt": round(margin_tot, 0),
            "rev": round(rev_ha, 0),
            "fc": round(fert_ha, 0),
            "hc": round(harv_cost_ha, 0),
            "tc": round(transp_ha, 0),
            "pr": round(_to_float(orow["precip_mm"]), 1),
            "sm": round(_to_float(orow["soil_moisture"]), 3),
            "r14": round(_to_float(arow["rain_14d_mm"]), 1) if arow else None,
            "d14": round(_to_float(arow["deficit_14d_mm"]), 2) if arow else None,
            "rd": _to_bool(arow["is_rainfall_deficit"]) if arow else False,
            "ps": _to_bool(arow["is_price_spike"]) if arow else False,
        })

    unit_econ = {
        row["region_key"]: row
        for row in manifest["profile"]["unit_economics_by_region"]
    }
    blocking = {
        row["region_key"]: row
        for row in manifest["profile"]["operations_blocking_by_region"]
    }

    rain: list[dict[str, str]] = []
    price_spike_dates: list[str] = []
    seen_spikes: set[str] = set()
    for arow in anomaly_raw:
        if _to_bool(arow["is_rainfall_deficit"]):
            rain.append({"region_key": arow["region_key"], "operation_date": arow["operation_date"]})
        if _to_bool(arow["is_price_spike"]) and arow["operation_date"] not in seen_spikes:
            seen_spikes.add(arow["operation_date"])
            price_spike_dates.append(arow["operation_date"])
    price_spike_dates.sort()

    discount: list[dict[str, Any]] = []
    for prow in price_raw:
        palm = _to_float(prow["palm_oil_usd"])
        soy = _to_float(prow["soybean_oil_usd"])
        spread = _to_float(prow["palm_soy_spread_usd"])
        discount.append({
            "date": prow["price_date"],
            "pct": spread / soy,
            "spread": spread,
            "palm": palm,
            "soy": soy,
            "fx": _to_float(prow["usd_idr"]),
            "idr": _to_float(prow["palm_oil_idr"]),
            "spike": prow["price_date"] in seen_spikes,
        })

    whatif_all: list[dict[str, Any]] = []
    whatif_price_only: list[dict[str, Any]] = []
    for wrow in whatif_raw:
        pm = _to_float(wrow["palm_mult"])
        fm = _to_float(wrow["fx_mult"])
        entry = {
            "region_key": wrow["region_key"],
            "scenario": wrow["scenario"],
            "palm_mult": pm,
            "fx_mult": fm,
            "palm_usd": _to_float(wrow["shocked_palm_usd"]),
            "usd_idr": _to_float(wrow["shocked_usd_idr"]),
            "cpo": _to_float(wrow["shocked_cpo_idr"]),
            "margin": _to_float(wrow["shocked_margin_idr_per_ha"]),
        }
        whatif_all.append(entry)
        if abs(fm - 1.0) < 1e-9:
            whatif_price_only.append({
                "region_key": entry["region_key"],
                "scenario": entry["scenario"],
                "palm_mult": pm,
                "margin": entry["margin"],
                "cpo": entry["cpo"],
            })

    return {
        "months": months,
        "order": order,
        "colors": colors,
        "dark_colors": dark_colors,
        "names": names,
        "managers": managers,
        "regions": regions,
        "monthly": monthly,
        "monthly_total": monthly_total,
        "harvest": harvest,
        "period": period,
        "period_total": period_total,
        "harvest_period": harvest_period,
        "unit_econ": unit_econ,
        "blocking": blocking,
        "daily_ops": daily_ops,
        "rain": rain,
        "price_spike_dates": price_spike_dates,
        "discount": discount,
        "whatif": whatif_price_only,
        "whatif_all": whatif_all,
        "shocks": [-20, -10, 0, 10, 20],
        "audit": {
            "extracts": [
                {
                    "file": e["file"],
                    "model": e["model"],
                    "rows": e["csv_rows"],
                    "nulls": sum(e["null_keys"].values()),
                    "dups": e["duplicate_grains"],
                }
                for e in manifest["extracts"]
            ],
            "forecast_rows": len(forecast_raw),
            "forecast_health": manifest["profile"]["forecast_health"],
            "plan_columns": manifest["profile"]["plan_columns"],
            "price_span": manifest["profile"]["price_span"],
        },
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Palm estate operations and margin workbench</title>
<style>
  :root {
    color-scheme: light;
    --bg: #F7F4EE;
    --surface: #FDFBF7;
    --inset: #EFECE4;
    --ink: #14191F;
    --ink-2: #434C54;
    --muted: #5B636B;
    --line: #DDD6C8;
    --grid: #E6DFD2;
    --accent: #1F7A80;
    --alert: #C2410C;
    --halo: #FDFBF7;
    --weather: #94A3B8;
    --weekend: #D6CFC2;
    --holiday: #7A5F28;
    --font-display: Georgia, "Iowan Old Style", "Palatino Linotype", Palatino, serif;
    --font-sans: Inter, system-ui, -apple-system, "Segoe UI", sans-serif;
    --font-mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    --shadow-tip: 0 8px 24px rgba(20, 25, 31, 0.10);
  }
  [data-theme="dark"] {
    color-scheme: dark;
    --bg: #0F141A;
    --surface: #161D26;
    --inset: #1C2531;
    --ink: #ECE8DF;
    --ink-2: #C2C8CE;
    --muted: #9BA4AC;
    --line: #25303D;
    --grid: #222C38;
    --accent: #7EB8BC;
    --alert: #E09A94;
    --halo: #161D26;
    --weather: #516173;
    --weekend: #323D4B;
    --holiday: #D4B46A;
    --shadow-tip: 0 10px 28px rgba(0, 0, 0, 0.40);
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font: 400 14px/1.5 var(--font-sans);
    font-variant-numeric: tabular-nums;
    -webkit-font-smoothing: antialiased;
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  a:focus-visible, button:focus-visible, select:focus-visible, summary:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  /* Quiet workbench header */
  .topbar {
    position: relative;
    background: var(--bg);
    border-bottom: 1px solid var(--line);
  }
  .topbar-inner {
    max-width: 1440px;
    margin: 0 auto;
    padding: 12px 24px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px 20px;
  }
  .brand-block { min-width: 260px; }
  .brand-title {
    margin: 0;
    font: 600 20px/1.2 var(--font-display);
    letter-spacing: -0.01em;
    color: var(--ink);
  }
  .brand-meta {
    margin: 4px 0 0;
    font: 400 12px/1.3 var(--font-mono);
    color: var(--muted);
  }
  .controls-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
  }
  .seg-group {
    display: inline-flex;
    align-items: center;
    background: var(--inset);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 2px;
    gap: 2px;
  }
  .seg-btn {
    border: 0;
    background: transparent;
    color: var(--ink-2);
    font: 500 12px/1.2 var(--font-sans);
    padding: 6px 10px;
    border-radius: 4px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
    transition: background-color 140ms ease, color 140ms ease;
  }
  .seg-btn:hover { color: var(--ink); background: var(--surface); }
  .seg-btn[aria-pressed="true"] {
    background: var(--surface);
    color: var(--ink);
    box-shadow: inset 0 0 0 1px var(--line);
  }
  .swatch {
    width: 8px;
    height: 8px;
    border-radius: 2px;
    display: inline-block;
    flex: 0 0 auto;
  }
  .nav-links {
    display: inline-flex;
    align-items: center;
    gap: 12px;
    font-size: 12px;
    color: var(--muted);
  }
  .nav-links a { color: var(--ink-2); font-weight: 500; }

  .shell {
    max-width: 1440px;
    margin: 0 auto;
    padding: 20px 24px 48px;
  }

  /* Stat strip — pure typography, no sparklines or decorative icons */
  .kpi-strip {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }
  .kpi-tile {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 16px 20px;
  }
  .kpi-label {
    font: 500 12px/1.3 var(--font-sans);
    color: var(--muted);
    margin: 0 0 8px;
  }
  .kpi-value {
    font: 600 28px/1.15 var(--font-display);
    color: var(--ink);
    margin: 0 0 6px;
    font-variant-numeric: tabular-nums;
  }
  .kpi-note {
    font: 400 12px/1.4 var(--font-sans);
    color: var(--ink-2);
    margin: 0;
  }

  /* Section & Card framing */
  .section {
    margin-bottom: 32px;
  }
  .section-head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px 16px;
    margin-bottom: 12px;
  }
  .section-title {
    margin: 0;
    font: 600 20px/1.25 var(--font-display);
    color: var(--ink);
  }
  .grain-tag {
    font: 400 11px/1.3 var(--font-mono);
    color: var(--muted);
  }
  .verdict-rail {
    border-left: 3px solid var(--accent);
    padding: 4px 0 4px 16px;
    margin: 0 0 16px;
    font: 400 14px/1.55 var(--font-sans);
    color: var(--ink-2);
    max-width: 96ch;
  }
  .verdict-rail strong { font-weight: 600; color: var(--ink); }

  .card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 20px;
  }
  .card-title {
    margin: 0 0 4px;
    font: 600 16px/1.3 var(--font-sans);
    color: var(--ink);
  }
  .card-sub {
    margin: 0 0 14px;
    font: 400 13px/1.45 var(--font-sans);
    color: var(--muted);
  }
  .card-caption {
    margin: 10px 0 0;
    font: 400 12px/1.45 var(--font-sans);
    color: var(--muted);
  }

  /* Asymmetric Editorial Grids */
  .grid-5-7 { display: grid; grid-template-columns: 5fr 7fr; gap: 16px; }
  .grid-7-5 { display: grid; grid-template-columns: 7fr 5fr; gap: 16px; }
  .grid-6-6 { display: grid; grid-template-columns: 6fr 6fr; gap: 16px; }
  .stack-16 { display: grid; gap: 16px; }
  .mt-16 { margin-top: 16px; }

  /* Interactive buttons inside charts */
  .estate-list {
    display: grid;
    gap: 4px;
    margin-top: 12px;
  }
  button.row {
    width: 100%;
    padding: 8px 10px;
    border-radius: 6px;
    border: 1px solid var(--line);
    background: var(--bg);
    color: var(--ink);
    font: 500 12px/1.2 var(--font-sans);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    text-align: left;
    transition: background-color 140ms ease, border-color 140ms ease;
  }
  button.row:hover { background: var(--inset); }
  button.row[aria-pressed="true"] {
    background: var(--inset);
    border-color: var(--accent);
  }
  .row-left { display: inline-flex; align-items: center; gap: 8px; }
  .row-meta { font: 400 12px/1.2 var(--font-mono); color: var(--muted); }

  button.shock {
    min-width: 64px;
    padding: 8px 12px;
    border-radius: 6px;
    border: 1px solid var(--line);
    background: var(--bg);
    color: var(--ink);
    font: 500 13px/1.2 var(--font-mono);
    cursor: pointer;
    transition: background-color 140ms ease, border-color 140ms ease, color 140ms ease;
  }
  button.shock:hover { background: var(--inset); }
  button.shock[aria-pressed="true"] {
    background: var(--ink);
    color: var(--bg);
    border-color: var(--ink);
  }
  button.linkish {
    background: none;
    border: 0;
    padding: 0;
    font: 500 12px/1.3 var(--font-sans);
    color: var(--accent);
    text-decoration: underline;
    cursor: pointer;
  }
  .status-line {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    margin-top: 10px;
    font: 400 12px/1.4 var(--font-mono);
    color: var(--ink-2);
  }
  .inline-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 8px 12px;
    margin-bottom: 12px;
  }
  .pill-select {
    font: 500 12px/1.2 var(--font-sans);
    color: var(--ink);
    background: var(--inset);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 6px 10px;
  }

  /* Legend row */
  .legend-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px 16px;
    margin: 0 0 12px;
    font: 400 12px/1.3 var(--font-sans);
    color: var(--ink-2);
  }
  .legend-item { display: inline-flex; align-items: center; gap: 6px; }

  /* SVG typography & geometry */
  svg { display: block; width: 100%; height: auto; overflow: visible; }
  .axis {
    fill: var(--muted);
    font-family: var(--font-mono);
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }
  .axis-ink {
    fill: var(--ink);
    font-family: var(--font-sans);
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }
  .axis-mono {
    fill: var(--ink);
    font-family: var(--font-mono);
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }
  .gridline { stroke: var(--grid); stroke-width: 1; }
  .avg { stroke: #5C6570; stroke-dasharray: 4 3; fill: none; stroke-width: 1.5; }
  [data-theme="dark"] .avg { stroke: #9BA4AC; }
  .series { fill: none; stroke-width: 2; }
  .flag { fill: var(--alert); }

  /* Tables & Heatmap Matrix */
  .table-wrap { overflow-x: auto; }
  table.ledger {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
  }
  table.ledger th {
    text-align: left;
    font: 500 11.5px/1.3 var(--font-sans);
    color: var(--muted);
    padding: 8px 8px;
    border-bottom: 1px solid var(--line);
    white-space: nowrap;
  }
  table.ledger th.num, table.ledger td.num {
    text-align: right;
    font-family: var(--font-mono);
  }
  table.ledger td {
    padding: 9px 8px;
    border-bottom: 1px solid var(--line);
    color: var(--ink);
    vertical-align: middle;
  }
  table.ledger tbody tr.clickable { cursor: pointer; transition: background-color 120ms ease; }
  table.ledger tbody tr.clickable:hover { background: var(--inset); }
  table.ledger tbody tr.selected-row { background: var(--inset); }
  table.ledger tbody tr.selected-row td:first-child { box-shadow: inset 3px 0 0 var(--accent); }
  .matrix-cell {
    border-radius: 4px;
    padding: 6px 8px;
    text-align: right;
    font-family: var(--font-mono);
  }
  .matrix-sub { display: block; font-size: 10px; color: var(--muted); }
  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 99px;
    display: inline-block;
    margin-right: 6px;
  }

  /* Audit collapse */
  details.audit {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 16px 20px;
  }
  details.audit summary {
    cursor: pointer;
    font: 500 14px/1.3 var(--font-sans);
    color: var(--ink);
  }
  .audit-grid {
    display: grid;
    grid-template-columns: 7fr 5fr;
    gap: 16px;
    margin-top: 16px;
  }
  .callout-box {
    background: var(--inset);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 12px;
    line-height: 1.5;
    color: var(--ink-2);
  }

  /* Floating tooltip */
  .tooltip {
    position: fixed;
    z-index: 90;
    pointer-events: none;
    background: var(--surface);
    color: var(--ink);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 10px 12px;
    box-shadow: var(--shadow-tip);
    font: 400 12px/1.4 var(--font-sans);
    font-variant-numeric: tabular-nums;
    max-width: 280px;
    opacity: 0;
    transform: translateY(4px);
    transition: opacity 100ms ease, transform 100ms ease;
  }
  .tooltip.open { opacity: 1; transform: translateY(0); }
  .tooltip-head { font-weight: 600; margin-bottom: 4px; color: var(--ink); }
  .tooltip-mono { font-family: var(--font-mono); font-size: 11px; color: var(--ink-2); }

  .footer {
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid var(--line);
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 8px 16px;
    font: 400 12px/1.4 var(--font-mono);
    color: var(--muted);
  }

  @media (max-width: 1100px) {
    .kpi-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .grid-5-7, .grid-7-5, .grid-6-6, .audit-grid { grid-template-columns: 1fr; }
  }
  @media (max-width: 640px) {
    .topbar-inner, .shell { padding-left: 16px; padding-right: 16px; }
    .kpi-strip { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
<header class="topbar">
  <div class="topbar-inner">
    <div class="brand-block">
      <h1 class="brand-title">Palm estate operations and margin workbench</h1>
      <p class="brand-meta">3 Mar–30 Jun 2026 operations · 27 Sep 2026 commodity base · dbt PASS=129 · <a href="https://public.tableau.com/app/profile/ihsan.tri.wanda/viz/palm_estate_margin_workbench/PalmEstateOperationsMarginWorkbench" target="_blank" rel="noopener">Tableau Public workbook</a></p>
    </div>
    <div class="controls-bar">
      <div class="seg-group" id="global-estate-pills" role="group" aria-label="Filter by estate"></div>
      <div class="seg-group" id="unit-basis-toggle" role="group" aria-label="Metric unit basis">
        <button type="button" class="seg-btn" data-unit="per_ha" aria-pressed="true">Per hectare (bn IDR/ha)</button>
        <button type="button" class="seg-btn" data-unit="total" aria-pressed="false">Estate total (Rp Tn)</button>
      </div>
      <nav class="nav-links" aria-label="Sections">
        <a href="#drift">Drift</a>
        <a href="#diagnostics">Diagnostics</a>
        <a href="#commodity">Commodity</a>
        <a href="#shock">Stress test</a>
        <a href="#ledger">Ledger</a>
      </nav>
      <button type="button" class="seg-btn" id="theme-toggle" style="border:1px solid var(--line);background:var(--surface);" aria-pressed="false">Dark mode</button>
    </div>
  </div>
</header>

<main class="shell">
  <section class="kpi-strip" id="kpi-strip" aria-label="Executive metrics"></section>

  <!-- Section 1: Margin Drift & Cross-Filtered Ranking (BUILD.md Sheet 1, Sheet 3, Cumulative) -->
  <section class="section" id="drift">
    <div class="section-head">
      <h2 class="section-title">Where margin is drifting, March–June 2026</h2>
      <span class="grain-tag">fct_estate_margin_daily · 480 rows · grain (region_key, operation_date)</span>
    </div>
    <p class="verdict-rail"><strong>Operational cadence, not agronomic yield, decides the period table.</strong> Riau earns the highest profit per harvest day (90.0 m IDR/ha) and the largest estate total (Rp 60.1 T), yet Lampung leads per-hectare margin (5.36 vs 4.80 bn IDR/ha) by logging 10 extra harvest days. Central Kalimantan loses 82 of 120 days to rain and stays last every month.</p>

    <div class="grid-5-7">
      <article class="card">
        <h3 class="card-title" id="rank-title">Lampung leads period margin per hectare; only Riau has an estate-specific flag, and it is closed</h3>
        <p class="card-sub" id="rank-sub">Bars show the 3 Mar–30 Jun sum across the same 120 days per estate. The amber mark flags Riau's two May rainfall-deficit days; both flags read false on 30 Jun.</p>
        <div id="rank"></div>
      </article>

      <article class="card">
        <h3 class="card-title">Central Kalimantan is last on margin per hectare in every month; there is no plan to judge drift against</h3>
        <p class="card-sub">Sum of daily margin across 3 Mar–30 Jun 2026 (March starts 3 Mar across all estates). Dashed line marks the four-estate FIXED mean and stays visible when filtering to one estate.</p>
        <div id="trend"></div>
        <div class="status-line">
          <span id="filter-status">Filter: all estates</span>
          <button class="linkish" id="clear-filter" type="button">Show all estates</button>
        </div>
        <p class="card-caption">Central Kalimantan hits a May trough of 0.12 bn IDR/ha across only 2 effective harvest days and recovers to 0.72 bn in June, remaining fourth in all four months.</p>
      </article>
    </div>

    <article class="card mt-16">
      <div class="inline-bar">
        <div>
          <h3 class="card-title">Daily cumulative margin trajectory and idle fertilizer burn</h3>
          <p class="card-sub" style="margin-bottom:0;">Running cumulative sum across 120 calendar days. Flat or negative slopes reflect non-harvest days paying daily fertilizer cost without FFB revenue.</p>
        </div>
        <span class="grain-tag" id="cum-hover-readout">Hover chart to inspect daily cumulative margin</span>
      </div>
      <div id="cumulative"></div>
    </article>
  </section>

  <!-- Section 2: Diagnostic Root-Cause Analysis -->
  <section class="section" id="diagnostics">
    <div class="section-head">
      <h2 class="section-title">Diagnostic root cause: weather throughput vs estate scale</h2>
      <span class="grain-tag">fct_estate_operations_daily · 480 rows · dim_region · 44,900 ha</span>
    </div>
    <p class="verdict-rail"><strong>Stranded land sits in Central Kalimantan.</strong> Central Kalimantan operates the largest footprint (15,200 ha, 33.9% of portfolio area) but harvests only 26 of 120 days due to 82 weather-blocked days (11.8 mm/day average rain), absorbing 86.5 m IDR/ha of idle fertilizer drag.</p>

    <div class="grid-7-5">
      <article class="card">
        <h3 class="card-title">120-day operational weather and labour calendar matrix</h3>
        <p class="card-sub">Every day per estate classified by agronomy and labour gate. Hover any cell for exact rainfall, soil moisture, and daily margin.</p>
        <div class="legend-row" id="cal-legend"></div>
        <div id="ops-calendar"></div>
      </article>

      <article class="card">
        <h3 class="card-title">120-day harvest blocking decomposition</h3>
        <p class="card-sub">Share of calendar days turning into effective harvest vs weather, weekend, and public-holiday blocks.</p>
        <div id="blocking-mix"></div>
        <p class="card-caption">Effective harvest days vs total calendar: Lampung 64/120 (53.3%), Riau 54/120 (45.0%), North Sumatra 48/120 (40.0%), Central Kalimantan 26/120 (21.7%).</p>
      </article>
    </div>

    <div class="grid-6-6 mt-16">
      <article class="card">
        <div class="inline-bar">
          <div>
            <h3 class="card-title">Margin variance bridge vs Lampung benchmark</h3>
            <p class="card-sub" style="margin-bottom:0;">Exact decomposition into harvest volume, unit rate, and idle drag (0.00 residual).</p>
          </div>
          <select id="bridge-target" class="pill-select" aria-label="Compare estate against Lampung">
            <option value="central_kalimantan" selected>vs Central Kalimantan (1.78 bn)</option>
            <option value="riau">vs Riau (4.80 bn)</option>
            <option value="north_sumatra">vs North Sumatra (3.90 bn)</option>
          </select>
        </div>
        <div id="variance-bridge"></div>
      </article>

      <article class="card">
        <h3 class="card-title">Footprint vs harvest productivity quadrant</h3>
        <p class="card-sub">Zoomed view: X starts at 20 harvest days, Y starts at 65 m IDR/ha. Circle area scales with planted hectares (7,400–15,200 ha).</p>
        <div id="quadrant"></div>
      </article>
    </div>
  </section>

  <!-- Section 3: Commodity, FX & Operational Anomaly Intelligence -->
  <section class="section" id="commodity">
    <div class="section-head">
      <h2 class="section-title">Commodity spread, local CPO pricing, and anomaly signals</h2>
      <span class="grain-tag">fct_commodity_price_daily · 209 rows · rec_anomaly_flags · 240 rows</span>
    </div>
    <p class="verdict-rail"><strong>Single-axis small multiples replace dual-axis clutter.</strong> CPO widened from a 25.7% discount to soybean oil in March to 36.6% by June, while Rupiah weakness (peaking at 18,151 IDR/USD) triggered six market-wide IDR trailing-high flags in May.</p>

    <div class="grid-6-6">
      <article class="card">
        <h3 class="card-title">Palm's discount to soybean oil widened from 25.7% in March to 36.6% by June, then froze</h3>
        <p class="card-sub">Discount = (palm − soy) / soy. USD spread peaked in May (−645 USD/t); percent discount widened through June (−36.6%). Jul–Sep repeats the June Pink Sheet print.</p>
        <p class="grain-tag" id="discount-hover" style="margin:0 0 8px;">Latest print 2026-09-27 · Discount −36.6% · Spread −$636/t · Palm $1,104/t · Soy $1,740/t</p>
        <div id="discount"></div>
        <p class="card-caption">No forecast band shown: forecast_cpo_30day covers 2026-09-28..2026-10-27 with 0 overlap days, constant 1,104 USD/t, and 0.00 band half-width.</p>
      </article>

      <div class="stack-16">
        <article class="card">
          <h3 class="card-title">Local CPO price in IDR and May trailing-high spike flags</h3>
          <p class="card-sub">Zoomed single axis: starts at 18.0 m IDR/t. Red markers denote the 6 market-wide IDR trailing-high dates (15, 18, 19, 26, 27, 28 May; FX range 16,855–18,151 IDR/USD).</p>
          <div id="cpo-idr-chart"></div>
        </article>

        <article class="card">
          <h3 class="card-title">14-day rolling rainfall across estates (May–June anomaly window)</h3>
          <p class="card-sub">Single axis from zero. Only Riau breached the rainfall-deficit threshold on 2–3 May (0.8 mm over 14 days; 3.81 mm/day deficit), resolving cleanly before 30 Jun.</p>
          <div id="rain-14d-chart"></div>
        </article>
      </div>
    </div>
  </section>

  <!-- Section 4: 2D Price x FX Stress-Test Engine (BUILD.md Sheet 4 preserved + full 9-scenario matrix) -->
  <section class="section" id="shock">
    <div class="section-head">
      <h2 class="section-title">Harvest-day margin under a palm-price and FX stress test</h2>
      <span class="grain-tag">whatif_margin_shocks · 36 rows · base print 2026-09-27 (1,104 USD/t · 17,903 IDR/USD)</span>
    </div>
    <p class="verdict-rail"><strong>Fixed costs amplify commodity shocks by 1.025x.</strong> A −20% CPO shock cuts Riau's harvest-day margin by −20.5% (72.6 vs 91.3 m IDR/ha) because daily fertilizer, harvest, and transport outlays remain fixed in Rupiah.</p>

    <div class="grid-5-7">
      <article class="card">
        <h3 class="card-title">On a harvest day Riau clears the most per hectare at every palm-price shock; Central Kalimantan stays last</h3>
        <p class="card-sub">Set the palm-price shock parameter (FX held at 1.00). Price-only grid excludes FX scenarios per build spec; compare FX scenarios in the matrix at right.</p>
        <div id="ladder" style="display:flex;flex-wrap:wrap;gap:6px;" role="group" aria-label="Price shock %"></div>
        <p class="status-line" id="shock-status"></p>
        <div style="margin-top:12px;">
          <p class="grain-tag" style="margin:0 0 6px;">Set the palm-price shock (four-estate mean, m IDR/ha)</p>
          <div id="ladder-chart"></div>
        </div>
        <div style="margin-top:14px;">
          <p class="grain-tag" style="margin:0 0 6px;">Harvest-day margin at the selected shock (m IDR/ha)</p>
          <div id="shock-bars"></div>
        </div>
      </article>

      <article class="card">
        <h3 class="card-title">Full 9-scenario Price × FX stress matrix</h3>
        <p class="card-sub">Every scenario in whatif_margin_shocks (palm_mult × fx_mult). Notice palm_+10pct and idr_+10pct yield identical CPO IDR (21,741,403 IDR/t) because revenue scales linearly with the product.</p>
        <div class="table-wrap" id="stress-matrix"></div>
      </article>
    </div>
  </section>

  <!-- Section 5: Estate Unit Economics Ledger & Governance Audit -->
  <section class="section" id="ledger">
    <div class="section-head">
      <h2 class="section-title">Estate unit economics and agronomy ledger</h2>
      <span class="grain-tag">Click any estate row to cross-filter charts above</span>
    </div>
    <article class="card" style="margin-bottom:16px;">
      <div class="table-wrap" id="ledger-table"></div>
    </article>

    <details class="audit" id="governance-audit">
      <summary>dbt warehouse &amp; CSV extract governance audit (7 certified tables, 0 null keys, 0 duplicate grains)</summary>
      <div class="audit-grid" id="audit-body"></div>
    </details>
  </section>

  <footer class="footer">
    <span>Source extracts: fct_estate_margin_daily · fct_estate_operations_daily · fct_commodity_price_daily · rec_anomaly_flags · whatif_margin_shocks · dim_region</span>
    <span><a href="https://public.tableau.com/app/profile/ihsan.tri.wanda/viz/palm_estate_margin_workbench/PalmEstateOperationsMarginWorkbench" target="_blank" rel="noopener">Open published Tableau Public workbook</a> · Rebuilt via tableau/build_dashboard.py</span>
  </footer>
</main>

<div class="tooltip" id="tooltip" role="status" aria-live="polite"></div>

<script id="data" type="application/json">__PAYLOAD_JSON__</script>
<script>
const D = JSON.parse(document.getElementById("data").textContent);
const state = {
  region: null,
  shock: 0,
  unit: "per_ha",
  bridgeTarget: "central_kalimantan",
  theme: "light",
};

const tipEl = document.getElementById("tooltip");
function showTip(ev, html) {
  tipEl.innerHTML = html;
  tipEl.classList.add("open");
  const pad = 14;
  const rect = tipEl.getBoundingClientRect();
  let x = ev.clientX + pad;
  let y = ev.clientY + pad;
  if (x + rect.width > window.innerWidth - 12) x = ev.clientX - rect.width - pad;
  if (y + rect.height > window.innerHeight - 12) y = ev.clientY - rect.height - pad;
  tipEl.style.left = Math.max(8, x) + "px";
  tipEl.style.top = Math.max(8, y) + "px";
}
function hideTip() { tipEl.classList.remove("open"); }

const bn = (v) => (v / 1e9).toFixed(2);
const tn = (v) => (v / 1e12).toFixed(2);
const mn = (v) => (v / 1e6).toFixed(1);
const fmtInt = (v) => Math.round(v).toLocaleString("en-US");
const signedPct = (v) => {
  const n = v * 100;
  const body = Math.abs(n).toFixed(1) + "%";
  if (n > 0.0001) return "+" + body;
  if (n < -0.0001) return "−" + body;
  return "0.0%";
};
const estateColor = (key) => (state.theme === "dark" ? D.dark_colors[key] : D.colors[key]);
const isPerHa = () => state.unit === "per_ha";
const metricPeriod = (key) => (isPerHa() ? D.period[key] : D.period_total[key]);
const metricMonth = (m, key) => (isPerHa() ? D.monthly[m][key] : D.monthly_total[m][key]);
const formatMetric = (v) => (isPerHa() ? bn(v) : tn(v));
const unitSuffix = () => (isPerHa() ? "bn IDR/ha" : "Rp Tn");

function svgEl(name, attrs) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  return el;
}

function rightRoundedBar(x, y, w, h, r) {
  if (w <= 0) return `M ${x} ${y} h 0 v ${h} h 0 Z`;
  const rr = Math.min(r, w / 2, h / 2);
  return `M ${x} ${y} H ${x + w - rr} Q ${x + w} ${y} ${x + w} ${y + rr} V ${y + h - rr} Q ${x + w} ${y + h} ${x + w - rr} ${y + h} H ${x} Z`;
}

function leftRoundedBar(xEnd, y, w, h, r) {
  if (w <= 0) return `M ${xEnd} ${y} h 0 v ${h} h 0 Z`;
  const x0 = xEnd - w;
  const rr = Math.min(r, w / 2, h / 2);
  return `M ${xEnd} ${y} H ${x0 + rr} Q ${x0} ${y} ${x0} ${y + rr} V ${y + h - rr} Q ${x0} ${y + h} ${x0 + rr} ${y + h} H ${xEnd} Z`;
}

function haloText(parent, attrs, text) {
  const t = svgEl("text", attrs);
  t.setAttribute("stroke", "var(--halo)");
  t.setAttribute("stroke-width", "3");
  t.setAttribute("paint-order", "stroke");
  t.textContent = text;
  parent.appendChild(t);
  return t;
}

function monthAvg(m) {
  const vals = D.order.map((k) => metricMonth(m, k));
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

function toggleRegion(key) {
  state.region = state.region === key ? null : key;
  renderAll();
}

function renderTopControls() {
  const host = document.getElementById("global-estate-pills");
  host.replaceChildren();
  const mkBtn = (label, active, color, onClick) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "seg-btn";
    b.setAttribute("aria-pressed", String(active));
    if (color) {
      const sw = document.createElement("span");
      sw.className = "swatch";
      sw.style.background = color;
      b.appendChild(sw);
    }
    b.appendChild(document.createTextNode(label));
    b.addEventListener("click", onClick);
    return b;
  };
  host.appendChild(mkBtn("All 4", state.region === null, null, () => { state.region = null; renderAll(); }));
  for (const key of ["lampung", "riau", "north_sumatra", "central_kalimantan"]) {
    const shortName = key === "central_kalimantan" ? "C. Kalimantan" : (key === "north_sumatra" ? "N. Sumatra" : D.names[key]);
    host.appendChild(mkBtn(shortName, state.region === key, estateColor(key), () => toggleRegion(key)));
  }
  document.querySelectorAll("#unit-basis-toggle button").forEach((btn) => {
    btn.setAttribute("aria-pressed", String(btn.dataset.unit === state.unit));
  });
  const tBtn = document.getElementById("theme-toggle");
  tBtn.setAttribute("aria-pressed", String(state.theme === "dark"));
  tBtn.textContent = state.theme === "dark" ? "Paper mode" : "Dark mode";
}

function renderKpis() {
  const host = document.getElementById("kpi-strip");
  host.replaceChildren();
  const totalPortfolioTn = D.order.reduce((s, k) => s + D.period_total[k], 0);
  const totalHa = D.order.reduce((s, k) => s + D.regions[k].planted_hectares, 0);
  const totalWeatherBlocked = D.order.reduce((s, k) => s + D.blocking[k].weather_blocked_days, 0);
  const totalEff = D.order.reduce((s, k) => s + D.blocking[k].effective_harvest_days, 0);
  const lastPrice = D.discount[D.discount.length - 1];

  const cards = [
    {
      label: "Portfolio total margin (44,900 ha)",
      value: "Rp " + tn(totalPortfolioTn) + " T",
      note: "192 effective harvest estate-days across 480 scheduled days",
    },
    {
      label: isPerHa() ? "Per-hectare leader (Lampung)" : "Total estate leader (Riau)",
      value: isPerHa() ? "5.36 bn/ha" : "Rp 60.06 T",
      note: isPerHa()
        ? "64 harvest days; Riau leads scale at Rp 60.06 T (12,500 ha)"
        : "36.4% of portfolio margin across 12,500 ha (2nd per ha at 4.80 bn)",
    },
    {
      label: "Weather throughput loss",
      value: totalWeatherBlocked + " / 480 days",
      note: "Central Kalimantan loses 82 of 120 days to rain (11.8 mm/day mean)",
    },
    {
      label: "Palm discount to soybean oil",
      value: signedPct(lastPrice.pct),
      note: "Flat Jun–Sep; 0 open anomaly flags on 30 Jun (2 closed in Riau)",
    },
  ];
  for (const c of cards) {
    const tile = document.createElement("div");
    tile.className = "kpi-tile";
    tile.innerHTML = `<p class="kpi-label">${c.label}</p><p class="kpi-value">${c.value}</p><p class="kpi-note">${c.note}</p>`;
    host.appendChild(tile);
  }
}

function renderRank() {
  const host = document.getElementById("rank");
  host.replaceChildren();
  const titleEl = document.getElementById("rank-title");
  const subEl = document.getElementById("rank-sub");
  if (isPerHa()) {
    titleEl.textContent = "Lampung leads period margin per hectare; only Riau has an estate-specific flag, and it is closed";
    subEl.textContent = "Bars show the 3 Mar–30 Jun sum across the same 120 days per estate. The amber mark flags Riau's two May rainfall-deficit days; both flags read false on 30 Jun.";
  } else {
    titleEl.textContent = "Riau leads total estate margin at Rp 60.06 T once 12,500 planted hectares scale up per-day earnings";
    subEl.textContent = "Total estate margin = daily margin per ha × planted hectares across 3 Mar–30 Jun. Central Kalimantan holds the largest area (15,200 ha) yet finishes last (Rp 27.07 T).";
  }

  const W = 480, H = 224, padL = 132, padR = 104, padT = 10, padB = 28;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const yMax = isPerHa() ? 6e9 : 70e12;
  const ticks = isPerHa() ? [0, 2, 4, 6] : [0, 20, 40, 60];
  const ranked = [...D.order].sort((a, b) => metricPeriod(b) - metricPeriod(a));
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
  svg.appendChild(svgEl("title", {})).textContent = "Estate period margin ranking";

  for (const tk of ticks) {
    const val = isPerHa() ? tk * 1e9 : tk * 1e12;
    const x = padL + (val / yMax) * plotW;
    svg.appendChild(svgEl("line", { x1: x, x2: x, y1: padT, y2: padT + plotH, class: "gridline" }));
    const lbl = svgEl("text", { x, y: H - 8, "text-anchor": "middle", class: "axis" });
    lbl.textContent = tk === 0 ? "0" : (isPerHa() ? tk + " bn" : tk + " T");
    svg.appendChild(lbl);
  }

  const slot = plotH / ranked.length;
  const barH = 20;
  ranked.forEach((key, i) => {
    const y = padT + i * slot + (slot - barH) / 2;
    const val = metricPeriod(key);
    const w = (val / yMax) * plotW;
    const dim = state.region && state.region !== key;

    const name = svgEl("text", {
      x: padL - 10, y: y + barH / 2 + 4,
      "text-anchor": "end", class: "axis-ink",
      opacity: dim ? "0.45" : "1",
    });
    name.textContent = D.names[key];
    svg.appendChild(name);

    const g = svgEl("g", { style: "cursor:pointer", opacity: dim ? "0.4" : "1" });
    const bar = svgEl("path", {
      d: rightRoundedBar(padL, y, Math.max(w, 0), barH, 2),
      fill: estateColor(key),
      stroke: state.region === key ? "var(--ink)" : "none",
      "stroke-width": state.region === key ? "1.5" : "0",
    });
    g.appendChild(bar);
    const tt = svgEl("title", {});
    tt.textContent = `${D.names[key]} · Manager: ${D.managers[key]} · ${formatMetric(val)} ${unitSuffix()} · ${D.harvest_period[key]} harvest days`;
    g.appendChild(tt);

    g.addEventListener("mousemove", (ev) => {
      showTip(ev, `<div class="tooltip-head">${D.names[key]}</div>
        <div>Manager: ${D.managers[key]} · ${fmtInt(D.regions[key].planted_hectares)} ha</div>
        <div class="tooltip-mono">${formatMetric(val)} ${unitSuffix()} · ${D.harvest_period[key]}/120 harvest days</div>`);
    });
    g.addEventListener("mouseleave", hideTip);
    g.addEventListener("click", () => toggleRegion(key));
    svg.appendChild(g);

    haloText(svg, {
      x: padL + w + 8, y: y + barH / 2 + 4,
      class: "axis-mono",
      opacity: dim ? "0.45" : "1",
    }, formatMetric(val));

    if (key === "riau") {
      svg.appendChild(svgEl("circle", {
        cx: padL + w - 9, cy: y + barH / 2, r: 4.5, class: "flag",
      }));
      const flagLbl = svgEl("text", {
        x: padL + w + 42, y: y + barH / 2 + 4,
        class: "axis",
        opacity: dim ? "0.45" : "1",
      });
      flagLbl.textContent = "2 deficit days";
      svg.appendChild(flagLbl);
    }
  });
  host.appendChild(svg);

  const list = document.createElement("div");
  list.className = "estate-list";
  ranked.forEach((key) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "row";
    btn.setAttribute("aria-pressed", String(state.region === key));
    btn.innerHTML = `<span class="row-left"><span class="swatch" style="background:${estateColor(key)}"></span><span>${state.region === key ? "Selected: " : ""}${D.names[key]}</span></span><span class="row-meta">${D.managers[key]} · ${D.harvest_period[key]}d</span>`;
    btn.addEventListener("click", () => toggleRegion(key));
    list.appendChild(btn);
  });
  host.appendChild(list);
}

function renderTrend() {
  const host = document.getElementById("trend");
  host.replaceChildren();
  const W = 680, H = 280, padL = 44, padR = 166, padT = 16, padB = 30;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const yMax = isPerHa() ? 2.0e9 : 25e12;
  const yTicks = isPerHa() ? [0, 0.5, 1.0, 1.5, 2.0] : [0, 5, 10, 15, 20, 25];
  const yOf = (v) => padT + plotH * (1 - v / yMax);
  const xOf = (i) => padL + (i / (D.months.length - 1)) * plotW;

  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
  svg.appendChild(svgEl("title", {})).textContent = "Monthly margin trend by estate";

  for (const tk of yTicks) {
    const val = isPerHa() ? tk * 1e9 : tk * 1e12;
    const y = yOf(val);
    svg.appendChild(svgEl("line", { x1: padL, x2: padL + plotW, y1: y, y2: y, class: "gridline" }));
    const lbl = svgEl("text", { x: padL - 8, y: y + 4, "text-anchor": "end", class: "axis" });
    lbl.textContent = isPerHa() ? tk.toFixed(1) : String(tk);
    svg.appendChild(lbl);
  }
  const monthNames = ["Mar 2026", "Apr", "May", "Jun"];
  D.months.forEach((m, i) => {
    const lbl = svgEl("text", { x: xOf(i), y: H - 8, "text-anchor": "middle", class: "axis" });
    lbl.textContent = monthNames[i];
    svg.appendChild(lbl);
  });

  // Always show FIXED 4-estate average line
  const avgPts = D.months.map((m, i) => `${xOf(i)},${yOf(monthAvg(m))}`).join(" ");
  svg.appendChild(svgEl("polyline", { points: avgPts, class: "avg" }));

  const shown = state.region ? [state.region] : D.order;
  const labels = [];
  for (const key of shown) {
    const pts = D.months.map((m, i) => `${xOf(i)},${yOf(metricMonth(m, key))}`).join(" ");
    svg.appendChild(svgEl("polyline", { points: pts, class: "series", stroke: estateColor(key) }));

    // Annotated markers ONLY on Central Kalimantan May trough & June endpoint (when shown)
    if (key === "central_kalimantan") {
      const mayVal = metricMonth("2026-05", key);
      const junVal = metricMonth("2026-06", key);
      const mayX = xOf(2), mayY = yOf(mayVal);
      svg.appendChild(svgEl("circle", { cx: mayX, cy: mayY, r: 4, fill: estateColor(key), stroke: "var(--halo)", "stroke-width": 1.5 }));
      haloText(svg, { x: mayX - 10, y: mayY - 12, "text-anchor": "end", class: "axis-mono" },
        "May trough " + formatMetric(mayVal));
      svg.appendChild(svgEl("circle", { cx: xOf(3), cy: yOf(junVal), r: 4, fill: estateColor(key), stroke: "var(--halo)", "stroke-width": 1.5 }));
    }

    const lastVal = metricMonth(D.months[D.months.length - 1], key);
    labels.push({
      key,
      y: yOf(lastVal),
      color: estateColor(key),
      dashed: false,
      text: `${key === "central_kalimantan" ? "C. Kalimantan" : (key === "north_sumatra" ? "N. Sumatra" : D.names[key])} ${formatMetric(lastVal)}`,
    });
  }

  const lastAvg = monthAvg(D.months[D.months.length - 1]);
  labels.push({
    key: "avg",
    y: yOf(lastAvg),
    color: state.theme === "dark" ? "#9BA4AC" : "#5C6570",
    dashed: true,
    text: `Four-estate avg ${formatMetric(lastAvg)}`,
  });

  // Resolve vertical collisions among right-end legend labels
  labels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) {
    if (labels[i].y - labels[i - 1].y < 18) labels[i].y = labels[i - 1].y + 18;
  }
  const lx = xOf(3) + 12;
  for (const lb of labels) {
    if (lb.dashed) {
      svg.appendChild(svgEl("line", { x1: lx, x2: lx + 12, y1: lb.y, y2: lb.y, class: "avg" }));
    } else {
      svg.appendChild(svgEl("rect", { x: lx, y: lb.y - 4, width: 9, height: 9, rx: 2, fill: lb.color }));
    }
    const t = svgEl("text", { x: lx + 16, y: lb.y + 4, class: "axis-ink" });
    t.textContent = lb.text;
    svg.appendChild(t);
  }

  // Hover bands per month
  D.months.forEach((m, i) => {
    const bw = plotW / 3;
    const hit = svgEl("rect", {
      x: Math.max(padL, xOf(i) - bw / 2), y: padT, width: bw, height: plotH,
      fill: "transparent", style: "cursor:crosshair",
    });
    hit.addEventListener("mousemove", (ev) => {
      const lines = shown
        .map((k) => ({ k, v: metricMonth(m, k) }))
        .sort((a, b) => b.v - a.v)
        .map((x) => `<div><span class="swatch" style="background:${estateColor(x.k)};margin-right:6px;"></span>${D.names[x.k]}: <b>${formatMetric(x.v)}</b> (${D.harvest[m][x.k]}d)</div>`)
        .join("");
      showTip(ev, `<div class="tooltip-head">${monthNames[i]} (${unitSuffix()})</div>${lines}<div class="tooltip-mono" style="margin-top:4px;">4-estate avg: ${formatMetric(monthAvg(m))}</div>`);
    });
    hit.addEventListener("mouseleave", hideTip);
    svg.appendChild(hit);
  });

  host.appendChild(svg);
  document.getElementById("filter-status").textContent = state.region
    ? `Filter: ${D.names[state.region]} only · Four-estate average holds steady`
    : "Filter: all estates";
}

function renderCumulative() {
  const host = document.getElementById("cumulative");
  host.replaceChildren();
  const readout = document.getElementById("cum-hover-readout");
  const dates = [...new Set(D.daily_ops.map((d) => d.d))].sort();
  const byEstateDate = {};
  for (const rk of D.order) byEstateDate[rk] = [];
  const runSum = { central_kalimantan: 0, lampung: 0, north_sumatra: 0, riau: 0 };
  const rowsByKey = new Map(D.daily_ops.map((x) => [`${x.r}|${x.d}`, x]));
  dates.forEach((dt) => {
    for (const rk of D.order) {
      const row = rowsByKey.get(`${rk}|${dt}`);
      runSum[rk] += isPerHa() ? row.m : row.mt;
      byEstateDate[rk].push({ d: dt, cum: runSum[rk], day: row });
    }
  });

  const W = 1360, H = 230, padL = 56, padR = 160, padT = 16, padB = 28;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const yMax = isPerHa() ? 6e9 : 65e12;
  const yTicks = isPerHa() ? [0, 2, 4, 6] : [0, 20, 40, 60];
  const yOf = (v) => padT + plotH * (1 - v / yMax);
  const xOf = (i) => padL + (i / (dates.length - 1)) * plotW;

  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
  svg.appendChild(svgEl("title", {})).textContent = "Daily cumulative margin trajectory";

  for (const tk of yTicks) {
    const val = isPerHa() ? tk * 1e9 : tk * 1e12;
    const y = yOf(val);
    svg.appendChild(svgEl("line", { x1: padL, x2: padL + plotW, y1: y, y2: y, class: "gridline" }));
    const lbl = svgEl("text", { x: padL - 8, y: y + 4, "text-anchor": "end", class: "axis" });
    lbl.textContent = tk === 0 ? "0" : (isPerHa() ? tk + " bn" : tk + " T");
    svg.appendChild(lbl);
  }
  ["2026-03-03", "2026-04-01", "2026-05-01", "2026-06-01", "2026-06-30"].forEach((dt) => {
    const idx = dates.indexOf(dt);
    if (idx >= 0) {
      const lbl = svgEl("text", { x: xOf(idx), y: H - 8, "text-anchor": "middle", class: "axis" });
      lbl.textContent = dt.slice(5);
      svg.appendChild(lbl);
    }
  });

  const shown = state.region ? [state.region] : D.order;
  const endLabels = [];
  for (const rk of shown) {
    const series = byEstateDate[rk];
    const pts = series.map((p, i) => `${xOf(i)},${yOf(p.cum)}`).join(" ");
    svg.appendChild(svgEl("polyline", { points: pts, class: "series", stroke: estateColor(rk) }));
    const last = series[series.length - 1];
    endLabels.push({ rk, y: yOf(last.cum), val: last.cum });
  }
  endLabels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < endLabels.length; i++) {
    if (endLabels[i].y - endLabels[i - 1].y < 16) endLabels[i].y = endLabels[i - 1].y + 16;
  }
  for (const lb of endLabels) {
    const lx = padL + plotW + 10;
    svg.appendChild(svgEl("rect", { x: lx, y: lb.y - 4, width: 8, height: 8, rx: 2, fill: estateColor(lb.rk) }));
    const t = svgEl("text", { x: lx + 14, y: lb.y + 4, class: "axis-ink" });
    const sn = lb.rk === "central_kalimantan" ? "C. Kalimantan" : (lb.rk === "north_sumatra" ? "N. Sumatra" : D.names[lb.rk]);
    t.textContent = `${sn} ${formatMetric(lb.val)}`;
    svg.appendChild(t);
  }

  const guide = svgEl("line", { x1: padL, x2: padL, y1: padT, y2: padT + plotH, stroke: "var(--muted)", "stroke-width": 1, opacity: "0" });
  svg.appendChild(guide);
  const overlay = svgEl("rect", { x: padL, y: padT, width: plotW, height: plotH, fill: "transparent", style: "cursor:crosshair" });
  overlay.addEventListener("mousemove", (ev) => {
    const rect = overlay.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
    const idx = Math.round(frac * (dates.length - 1));
    const dt = dates[idx];
    const x = xOf(idx);
    guide.setAttribute("x1", x);
    guide.setAttribute("x2", x);
    guide.setAttribute("opacity", "0.75");
    const rows = shown
      .map((k) => byEstateDate[k][idx])
      .sort((a, b) => b.cum - a.cum)
      .map((p) => `<div><span class="swatch" style="background:${estateColor(p.day.r)};margin-right:6px;"></span>${D.names[p.day.r]}: <b>${formatMetric(p.cum)}</b> (${p.day.eff ? "harvest" : p.day.st})</div>`)
      .join("");
    readout.textContent = `${dt} · ${shown.map((k) => D.names[k].split(" ")[0] + " " + formatMetric(byEstateDate[k][idx].cum)).join(" · ")}`;
    showTip(ev, `<div class="tooltip-head">${dt} (${unitSuffix()})</div>${rows}`);
  });
  overlay.addEventListener("mouseleave", () => {
    guide.setAttribute("opacity", "0");
    readout.textContent = "Hover chart to inspect daily cumulative margin";
    hideTip();
  });
  svg.appendChild(overlay);
  host.appendChild(svg);
}

function renderCalendar() {
  const leg = document.getElementById("cal-legend");
  leg.replaceChildren();
  [
    ["Effective harvest", "var(--accent)"],
    ["Weather blocked", "var(--weather)"],
    ["Weekend (labour off)", "var(--weekend)"],
    ["Public holiday", "var(--holiday)"],
    ["Rainfall deficit (Riau May 2–3)", "var(--alert)"],
  ].forEach(([lbl, col]) => {
    const item = document.createElement("span");
    item.className = "legend-item";
    item.innerHTML = `<span class="swatch" style="background:${col}"></span><span>${lbl}</span>`;
    leg.appendChild(item);
  });

  const host = document.getElementById("ops-calendar");
  host.replaceChildren();
  const dates = [...new Set(D.daily_ops.map((d) => d.d))].sort();
  const rowsByKey = new Map(D.daily_ops.map((x) => [`${x.r}|${x.d}`, x]));
  const estates = ["lampung", "riau", "north_sumatra", "central_kalimantan"];

  const W = 780, H = 166, padL = 132, padR = 16, padT = 20, padB = 18;
  const plotW = W - padL - padR;
  const cellW = plotW / dates.length;
  const rowH = 24, rowGap = 8;

  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
  svg.appendChild(svgEl("title", {})).textContent = "120-day operational weather and labour calendar matrix";

  ["2026-03-03", "2026-04-01", "2026-05-01", "2026-06-01"].forEach((dt) => {
    const i = dates.indexOf(dt);
    if (i >= 0) {
      const lbl = svgEl("text", { x: padL + i * cellW, y: 12, class: "axis" });
      lbl.textContent = dt.slice(5);
      svg.appendChild(lbl);
    }
  });

  estates.forEach((rk, rIdx) => {
    const y = padT + rIdx * (rowH + rowGap);
    const dim = state.region && state.region !== rk;
    const lbl = svgEl("text", { x: padL - 10, y: y + rowH / 2 + 4, "text-anchor": "end", class: "axis-ink", opacity: dim ? "0.45" : "1" });
    lbl.textContent = D.names[rk];
    svg.appendChild(lbl);

    dates.forEach((dt, dIdx) => {
      const row = rowsByKey.get(`${rk}|${dt}`);
      let fill = "var(--weather)";
      if (row.st === "harvest") fill = estateColor(rk);
      else if (row.st === "weekend") fill = "var(--weekend)";
      else if (row.st === "holiday") fill = "var(--holiday)";

      const rect = svgEl("rect", {
        x: (padL + dIdx * cellW).toFixed(2),
        y,
        width: Math.max(cellW - 0.8, 1.5).toFixed(2),
        height: rowH,
        rx: 1,
        fill,
        opacity: dim ? "0.35" : "1",
        "data-cal-cell": "1",
      });
      rect.addEventListener("mousemove", (ev) => {
        showTip(ev, `<div class="tooltip-head">${D.names[rk]} · ${dt}</div>
          <div>Gate: <b>${row.st}</b>${row.rd ? " · Rainfall deficit flag" : ""}</div>
          <div class="tooltip-mono">Rain: ${row.pr} mm · Soil moisture: ${row.sm}</div>
          <div class="tooltip-mono">Margin: ${(row.m / 1e6).toFixed(1)} m IDR/ha</div>`);
      });
      rect.addEventListener("mouseleave", hideTip);
      rect.addEventListener("click", () => toggleRegion(rk));
      svg.appendChild(rect);

      if (row.rd) {
        svg.appendChild(svgEl("circle", {
          cx: padL + dIdx * cellW + cellW / 2,
          cy: y + rowH - 4,
          r: 2.5,
          fill: "var(--alert)",
          stroke: "var(--halo)",
          "stroke-width": 1,
        }));
      }
    });
  });

  host.appendChild(svg);
}

function renderBlockingMix() {
  const host = document.getElementById("blocking-mix");
  host.replaceChildren();
  const estates = ["lampung", "riau", "north_sumatra", "central_kalimantan"];
  const W = 520, H = 196, padL = 128, padR = 76, padT = 12, padB = 26;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
  svg.appendChild(svgEl("title", {})).textContent = "120-day harvest blocking decomposition";

  for (const pctTick of [0, 25, 50, 75, 100]) {
    const x = padL + (pctTick / 100) * plotW;
    svg.appendChild(svgEl("line", { x1: x, x2: x, y1: padT, y2: padT + plotH, class: "gridline" }));
    const lbl = svgEl("text", { x, y: H - 6, "text-anchor": "middle", class: "axis" });
    lbl.textContent = pctTick + "%";
    svg.appendChild(lbl);
  }

  const slot = plotH / estates.length;
  const barH = 20;
  estates.forEach((rk, i) => {
    const b = D.blocking[rk];
    const y = padT + i * slot + (slot - barH) / 2;
    const dim = state.region && state.region !== rk;
    const lbl = svgEl("text", { x: padL - 10, y: y + barH / 2 + 4, "text-anchor": "end", class: "axis-ink", opacity: dim ? "0.45" : "1" });
    lbl.textContent = D.names[rk];
    svg.appendChild(lbl);

    const segs = [
      ["Effective harvest", b.effective_harvest_days, estateColor(rk)],
      ["Weekend", b.weekend_blocked_days, "var(--weekend)"],
      ["Public holiday", b.holiday_blocked_days, "var(--holiday)"],
      ["Weather blocked", b.weather_blocked_days, "var(--weather)"],
    ];
    let xCur = padL;
    segs.forEach(([label, days, fill], sIdx) => {
      const sw = (days / b.total_days) * plotW;
      const isLast = sIdx === segs.length - 1;
      const shape = isLast
        ? svgEl("path", { d: rightRoundedBar(xCur, y, sw, barH, 2), fill, opacity: dim ? "0.4" : "1" })
        : svgEl("rect", { x: xCur, y, width: sw, height: barH, fill, opacity: dim ? "0.4" : "1" });
      shape.addEventListener("mousemove", (ev) => {
        showTip(ev, `<div class="tooltip-head">${D.names[rk]} · ${label}</div>
          <div class="tooltip-mono">${days} / ${b.total_days} days (${((days / b.total_days) * 100).toFixed(1)}%)</div>
          <div class="tooltip-mono">Mean rainfall: ${b.avg_precip_mm} mm/day</div>`);
      });
      shape.addEventListener("mouseleave", hideTip);
      svg.appendChild(shape);
      xCur += sw;
    });

    const rainTxt = svgEl("text", { x: padL + plotW + 8, y: y + barH / 2 + 4, class: "axis", opacity: dim ? "0.45" : "1" });
    rainTxt.textContent = `${b.avg_precip_mm.toFixed(1)} mm/d`;
    svg.appendChild(rainTxt);
  });
  host.appendChild(svg);
}

function renderVarianceBridge() {
  const host = document.getElementById("variance-bridge");
  host.replaceChildren();
  const bench = "lampung";
  const target = state.bridgeTarget;
  const ub = D.unit_econ[bench];
  const ut = D.unit_econ[target];

  const mA = ub.net_margin_idr_per_ha;
  const mB = ut.net_margin_idr_per_ha;
  const hA = ub.effective_harvest_days;
  const hB = ut.effective_harvest_days;
  const rA = (mA - ub.idle_drag_idr_per_ha) / hA;
  const rB = (mB - ut.idle_drag_idr_per_ha) / hB;

  const volEff = (hB - hA) * rA;
  const rateEff = hB * (rB - rA);
  const idleEff = ut.idle_drag_idr_per_ha - ub.idle_drag_idr_per_ha;
  const residual = (mA + volEff + rateEff + idleEff) - mB;

  const steps = [
    { label: `${D.names[bench]} benchmark`, kind: "total", start: 0, end: mA, delta: mA, color: estateColor(bench) },
    { label: `Harvest volume (${hB - hA >= 0 ? "+" : ""}${hB - hA} d)`, kind: "delta", start: mA, end: mA + volEff, delta: volEff, color: volEff >= 0 ? "var(--accent)" : "var(--alert)" },
    { label: `Harvest-day rate (${(rB - rA) >= 0 ? "+" : "−"}${mn(Math.abs(rB - rA))} m/d)`, kind: "delta", start: mA + volEff, end: mA + volEff + rateEff, delta: rateEff, color: rateEff >= 0 ? "var(--accent)" : "var(--alert)" },
    { label: "Idle fertilizer drag", kind: "delta", start: mA + volEff + rateEff, end: mB, delta: idleEff, color: idleEff >= 0 ? "var(--accent)" : "var(--alert)" },
    { label: `${D.names[target]} actual`, kind: "total", start: 0, end: mB, delta: mB, color: estateColor(target) },
  ];

  const W = 580, H = 228, padL = 188, padR = 92, padT = 10, padB = 28;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const xMax = 6e9;
  const xOf = (v) => padL + (Math.max(0, v) / xMax) * plotW;

  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
  svg.appendChild(svgEl("title", {})).textContent = "Margin variance bridge waterfall";

  for (const tk of [0, 2, 4, 6]) {
    const x = xOf(tk * 1e9);
    svg.appendChild(svgEl("line", { x1: x, x2: x, y1: padT, y2: padT + plotH, class: "gridline" }));
    const lbl = svgEl("text", { x, y: H - 8, "text-anchor": "middle", class: "axis" });
    lbl.textContent = tk === 0 ? "0" : tk + " bn";
    svg.appendChild(lbl);
  }

  const slot = plotH / steps.length;
  const barH = 20;
  steps.forEach((st, i) => {
    const y = padT + i * slot + (slot - barH) / 2;
    const x0 = xOf(Math.min(st.start, st.end));
    const x1 = xOf(Math.max(st.start, st.end));
    const w = Math.max(x1 - x0, 2);

    const lbl = svgEl("text", { x: padL - 10, y: y + barH / 2 + 4, "text-anchor": "end", class: "axis-ink" });
    lbl.textContent = st.label;
    svg.appendChild(lbl);

    if (i > 0) {
      const cx = xOf(st.start);
      svg.appendChild(svgEl("line", { x1: cx, x2: cx, y1: y - (slot - barH), y2: y + barH, stroke: "var(--line)", "stroke-width": 1, "stroke-dasharray": "2 2" }));
    }

    const dPath = st.kind === "total"
      ? rightRoundedBar(x0, y, w, barH, 2)
      : (st.delta >= 0 ? rightRoundedBar(x0, y, w, barH, 2) : leftRoundedBar(x1, y, w, barH, 2));
    const bar = svgEl("path", { d: dPath, fill: st.color });
    bar.addEventListener("mousemove", (ev) => {
      showTip(ev, `<div class="tooltip-head">${st.label}</div>
        <div class="tooltip-mono">${st.kind === "total" ? "Period total" : "Contribution"}: ${(st.delta >= 0 && st.kind === "delta" ? "+" : "")}${bn(st.delta)} bn IDR/ha</div>
        <div class="tooltip-mono">Residual check: ${residual.toFixed(4)} IDR/ha</div>`);
    });
    bar.addEventListener("mouseleave", hideTip);
    svg.appendChild(bar);

    const valTxt = st.kind === "total"
      ? `${bn(st.delta)} bn`
      : `${st.delta >= 0 ? "+" : "−"}${bn(Math.abs(st.delta))} bn`;
    haloText(svg, { x: x1 + 8, y: y + barH / 2 + 4, class: "axis-mono" }, valTxt);
  });
  host.appendChild(svg);
}

function renderQuadrant() {
  const host = document.getElementById("quadrant");
  host.replaceChildren();
  const W = 580, H = 228, padL = 52, padR = 36, padT = 18, padB = 34;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const xMin = 20, xMax = 80;
  const yMin = 65e6, yMax = 96e6;
  const xOf = (d) => padL + ((d - xMin) / (xMax - xMin)) * plotW;
  const yOf = (m) => padT + plotH * (1 - (m - yMin) / (yMax - yMin));

  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
  svg.appendChild(svgEl("title", {})).textContent = "Harvest days vs unit margin per harvest day";

  for (const yt of [65, 75, 85, 95]) {
    const y = yOf(yt * 1e6);
    svg.appendChild(svgEl("line", { x1: padL, x2: padL + plotW, y1: y, y2: y, class: "gridline" }));
    const lbl = svgEl("text", { x: padL - 8, y: y + 4, "text-anchor": "end", class: "axis" });
    lbl.textContent = yt + " m";
    svg.appendChild(lbl);
  }
  for (const xt of [20, 35, 50, 65, 80]) {
    const x = xOf(xt);
    svg.appendChild(svgEl("line", { x1: x, x2: x, y1: padT, y2: padT + plotH, class: "gridline" }));
    const lbl = svgEl("text", { x, y: H - 8, "text-anchor": "middle", class: "axis" });
    lbl.textContent = xt + " d";
    svg.appendChild(lbl);
  }

  const labelOffsets = {
    riau: { dx: -18, dy: -16, anchor: "end" },
    lampung: { dx: 16, dy: 4, anchor: "start" },
    north_sumatra: { dx: -16, dy: 16, anchor: "end" },
    central_kalimantan: { dx: 22, dy: 4, anchor: "start" },
  };

  for (const rk of D.order) {
    const u = D.unit_econ[rk];
    const reg = D.regions[rk];
    const cx = xOf(u.effective_harvest_days);
    const cy = yOf(u.avg_harvest_day_margin_idr_per_ha);
    const r = Math.sqrt(reg.planted_hectares / 7400) * 12;
    const dim = state.region && state.region !== rk;

    const c = svgEl("circle", {
      cx, cy, r: r.toFixed(1),
      fill: estateColor(rk),
      "fill-opacity": dim ? "0.25" : "0.82",
      stroke: state.region === rk ? "var(--ink)" : "var(--surface)",
      "stroke-width": state.region === rk ? "2" : "1.5",
      style: "cursor:pointer",
    });
    c.addEventListener("mousemove", (ev) => {
      showTip(ev, `<div class="tooltip-head">${reg.region_name} (${reg.island})</div>
        <div class="tooltip-mono">Area: ${fmtInt(reg.planted_hectares)} ha · Yield: ${reg.yield_t_ha} t/ha</div>
        <div class="tooltip-mono">${u.effective_harvest_days} harvest days · ${mn(u.avg_harvest_day_margin_idr_per_ha)} m/harvest-day</div>
        <div class="tooltip-mono">Estate total: Rp ${tn(u.total_estate_margin_idr)} T</div>`);
    });
    c.addEventListener("mouseleave", hideTip);
    c.addEventListener("click", () => toggleRegion(rk));
    svg.appendChild(c);

    const off = labelOffsets[rk];
    const sn = rk === "central_kalimantan" ? "C. Kalimantan" : (rk === "north_sumatra" ? "N. Sumatra" : reg.region_name);
    haloText(svg, {
      x: cx + off.dx, y: cy + off.dy,
      "text-anchor": off.anchor,
      class: "axis-ink",
      opacity: dim ? "0.45" : "1",
    }, `${sn} (${fmtInt(reg.planted_hectares)} ha)`);
  }
  host.appendChild(svg);
}

function renderDiscount() {
  const host = document.getElementById("discount");
  host.replaceChildren();
  const readout = document.getElementById("discount-hover");
  const rows = D.discount;
  const W = 620, H = 260, padL = 48, padR = 20, padT = 22, padB = 28;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const yMin = -0.42, yMax = 0;
  const yOf = (v) => padT + plotH * (1 - (v - yMin) / (yMax - yMin));
  const xOf = (i) => padL + (i / (rows.length - 1)) * plotW;

  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
  svg.appendChild(svgEl("title", {})).textContent = "Palm discount to soybean oil";

  // Shaded calm region for Jul-Sep constant price print
  const julIdx = rows.findIndex((r) => r.date === "2026-07-01");
  if (julIdx >= 0) {
    svg.appendChild(svgEl("rect", {
      x: xOf(julIdx), y: padT, width: xOf(rows.length - 1) - xOf(julIdx), height: plotH,
      fill: "var(--inset)", opacity: "0.75",
    }));
  }

  for (const tk of [0, -0.1, -0.2, -0.3, -0.4]) {
    const y = yOf(tk);
    svg.appendChild(svgEl("line", { x1: padL, x2: padL + plotW, y1: y, y2: y, class: "gridline" }));
    const lbl = svgEl("text", { x: padL - 8, y: y + 4, "text-anchor": "end", class: "axis" });
    lbl.textContent = (tk * 100).toFixed(0) + "%";
    svg.appendChild(lbl);
  }

  const march = rows.find((r) => r.date.startsWith("2026-03")).pct;
  svg.appendChild(svgEl("line", { x1: padL, x2: padL + plotW, y1: yOf(march), y2: yOf(march), class: "avg" }));
  haloText(svg, { x: padL + plotW - 4, y: yOf(march) - 8, "text-anchor": "end", class: "axis" }, "March baseline −25.7%");

  const pts = rows.map((r, i) => `${xOf(i)},${yOf(r.pct)}`).join(" ");
  svg.appendChild(svgEl("polyline", { points: pts, class: "series", stroke: "var(--accent)" }));

  // Annotated markers strictly on March start & June freeze
  const junIdx = rows.findIndex((r) => r.date === "2026-06-01");
  svg.appendChild(svgEl("circle", { cx: xOf(0), cy: yOf(rows[0].pct), r: 4, fill: "var(--accent)", stroke: "var(--halo)", "stroke-width": 1.5 }));
  haloText(svg, { x: xOf(0) + 6, y: yOf(rows[0].pct) - 10, class: "axis-mono" }, "March −25.7%");

  svg.appendChild(svgEl("circle", { cx: xOf(junIdx), cy: yOf(rows[junIdx].pct), r: 4, fill: "var(--accent)", stroke: "var(--halo)", "stroke-width": 1.5 }));
  haloText(svg, { x: xOf(junIdx) + 6, y: yOf(rows[junIdx].pct) - 10, class: "axis-mono" }, "June −36.6% (Jul–Sep flat)");

  ["2026-03-03", "2026-05-01", "2026-06-01", "2026-08-01", "2026-09-27"].forEach((dt) => {
    const i = rows.findIndex((r) => r.date === dt);
    if (i >= 0) {
      const lbl = svgEl("text", { x: xOf(i), y: H - 6, "text-anchor": "middle", class: "axis" });
      lbl.textContent = dt === "2026-09-27" ? "27 Sep" : dt.slice(5);
      svg.appendChild(lbl);
    }
  });

  const overlay = svgEl("rect", { x: padL, y: padT, width: plotW, height: plotH, fill: "transparent", style: "cursor:crosshair" });
  overlay.addEventListener("mousemove", (ev) => {
    const rect = overlay.getBoundingClientRect();
    const idx = Math.round(Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width)) * (rows.length - 1));
    const r = rows[idx];
    readout.textContent = `${r.date} · Discount ${signedPct(r.pct)} · Spread −$${Math.abs(r.spread).toFixed(0)}/t · Palm $${fmtInt(r.palm)}/t · Soy $${fmtInt(r.soy)}/t · Local ${fmtInt(r.idr)} IDR/t`;
    showTip(ev, `<div class="tooltip-head">${r.date}</div>
      <div class="tooltip-mono">Discount: <b>${signedPct(r.pct)}</b> ($${r.spread.toFixed(0)}/t)</div>
      <div class="tooltip-mono">Palm $${fmtInt(r.palm)}/t · Soy $${fmtInt(r.soy)}/t</div>
      <div class="tooltip-mono">FX ${fmtInt(r.fx)} IDR/USD · Local ${fmtInt(r.idr)} IDR/t</div>`);
  });
  overlay.addEventListener("mouseleave", hideTip);
  svg.appendChild(overlay);
  host.appendChild(svg);
}

function renderMarketMultiples() {
  // 1. Local CPO IDR/t with 6 May trailing-high spike markers
  const cpoHost = document.getElementById("cpo-idr-chart");
  cpoHost.replaceChildren();
  const rows = D.discount;
  const W = 620, H = 148, padL = 52, padR = 16, padT = 14, padB = 26;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const yMin = 18.0e6, yMax = 20.6e6;
  const yOf = (v) => padT + plotH * (1 - (v - yMin) / (yMax - yMin));
  const xOf = (i) => padL + (i / (rows.length - 1)) * plotW;

  const svg1 = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
  svg1.appendChild(svgEl("title", {})).textContent = "Local CPO IDR per tonne and trailing-high spike flags";
  for (const tk of [18.0, 19.0, 20.0]) {
    const y = yOf(tk * 1e6);
    svg1.appendChild(svgEl("line", { x1: padL, x2: padL + plotW, y1: y, y2: y, class: "gridline" }));
    const lbl = svgEl("text", { x: padL - 8, y: y + 4, "text-anchor": "end", class: "axis" });
    lbl.textContent = tk.toFixed(1) + "M";
    svg1.appendChild(lbl);
  }
  svg1.appendChild(svgEl("polyline", { points: rows.map((r, i) => `${xOf(i)},${yOf(r.idr)}`).join(" "), class: "series", stroke: "var(--accent)" }));
  rows.forEach((r, i) => {
    if (r.spike) {
      svg1.appendChild(svgEl("circle", { cx: xOf(i), cy: yOf(r.idr), r: 3.5, class: "flag", stroke: "var(--halo)", "stroke-width": 1 }));
    }
  });
  const peakIdx = rows.reduce((best, r, i) => (r.idr > rows[best].idr ? i : best), 0);
  haloText(svg1, { x: xOf(peakIdx) + 6, y: yOf(rows[peakIdx].idr) - 6, class: "axis-mono" }, "May peak 20.3M (6 spike days)");
  ["2026-03-03", "2026-05-01", "2026-07-01", "2026-09-27"].forEach((dt) => {
    const i = rows.findIndex((r) => r.date === dt);
    if (i >= 0) {
      const lbl = svgEl("text", { x: xOf(i), y: H - 6, "text-anchor": "middle", class: "axis" });
      lbl.textContent = dt === "2026-09-27" ? "27 Sep" : dt.slice(5);
      svg1.appendChild(lbl);
    }
  });
  cpoHost.appendChild(svg1);

  // 2. 14-day rolling rainfall (May 2 - Jun 30)
  const rainHost = document.getElementById("rain-14d-chart");
  rainHost.replaceChildren();
  const winDates = [...new Set(D.daily_ops.filter((d) => d.r14 !== null).map((d) => d.d))].sort();
  const mapOps = new Map(D.daily_ops.map((d) => [`${d.r}|${d.d}`, d]));

  const H2 = 156;
  const plotH2 = H2 - padT - padB;
  const yOf2 = (v) => padT + plotH2 * (1 - v / 330);
  const xOf2 = (i) => padL + (i / (winDates.length - 1)) * plotW;

  const svg2 = svgEl("svg", { viewBox: `0 0 ${W} ${H2}`, role: "img" });
  svg2.appendChild(svgEl("title", {})).textContent = "14-day rolling rainfall by estate";
  for (const tk of [0, 100, 200, 300]) {
    const y = yOf2(tk);
    svg2.appendChild(svgEl("line", { x1: padL, x2: padL + plotW, y1: y, y2: y, class: "gridline" }));
    const lbl = svgEl("text", { x: padL - 8, y: y + 4, "text-anchor": "end", class: "axis" });
    lbl.textContent = tk + " mm";
    svg2.appendChild(lbl);
  }
  const shown = state.region ? [state.region] : D.order;
  for (const rk of shown) {
    const pts = winDates.map((dt, i) => `${xOf2(i)},${yOf2(mapOps.get(`${rk}|${dt}`).r14)}`).join(" ");
    svg2.appendChild(svgEl("polyline", { points: pts, class: "series", stroke: estateColor(rk) }));
    if (rk === "riau") {
      const rRow = mapOps.get(`riau|${winDates[0]}`);
      const rx = xOf2(0), ry = yOf2(rRow.r14);
      const lx = xOf2(2), ly = yOf2(304);
      svg2.appendChild(svgEl("line", { x1: rx, y1: ry, x2: lx, y2: ly + 6, stroke: "var(--muted)", "stroke-width": 1, "stroke-dasharray": "2 2" }));
      svg2.appendChild(svgEl("circle", { cx: rx, cy: ry, r: 4, class: "flag", stroke: "var(--halo)", "stroke-width": 1.5 }));
      haloText(svg2, { x: lx + 4, y: ly + 4, class: "axis-mono" }, "Riau 0.8 mm deficit (2–3 May)");
    }
  }
  ["2026-05-02", "2026-05-15", "2026-06-01", "2026-06-15", "2026-06-30"].forEach((dt) => {
    const i = winDates.indexOf(dt);
    if (i >= 0) {
      const lbl = svgEl("text", { x: xOf2(i), y: H2 - 6, "text-anchor": "middle", class: "axis" });
      lbl.textContent = dt.slice(5);
      svg2.appendChild(lbl);
    }
  });
  rainHost.appendChild(svg2);
}

function rowsForShock(shock) {
  const mult = 1 + shock / 100;
  return D.whatif
    .filter((r) => Math.abs(r.palm_mult - mult) < 1e-9)
    .sort((a, b) => b.margin - a.margin);
}

function renderShock() {
  const ladder = document.getElementById("ladder");
  ladder.replaceChildren();
  for (const shock of D.shocks) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "shock";
    btn.setAttribute("aria-pressed", String(state.shock === shock));
    btn.textContent = (shock > 0 ? "+" : "") + shock + "%";
    btn.addEventListener("click", () => { state.shock = shock; renderShock(); });
    ladder.appendChild(btn);
  }

  const rows = rowsForShock(state.shock);
  const base = Object.fromEntries(rowsForShock(0).map((r) => [r.region_key, r.margin]));
  document.getElementById("shock-status").textContent =
    `Price shock % = ${state.shock} · CPO ${fmtInt(rows[0].cpo)} IDR/t · FX held at 1.00`;

  // Sheet 4a: Shock ladder
  const lHost = document.getElementById("ladder-chart");
  lHost.replaceChildren();
  const LW = 480, LH = 148, lpL = 56, lpR = 64, lpT = 6, lpB = 22;
  const lPlotW = LW - lpL - lpR, lPlotH = LH - lpT - lpB;
  const lSvg = svgEl("svg", { viewBox: `0 0 ${LW} ${LH}`, role: "img" });
  for (const tk of [0, 40, 80, 120]) {
    const x = lpL + (tk / 120) * lPlotW;
    lSvg.appendChild(svgEl("line", { x1: x, x2: x, y1: lpT, y2: lpT + lPlotH, class: "gridline" }));
    const lbl = svgEl("text", { x, y: LH - 4, "text-anchor": "middle", class: "axis" });
    lbl.textContent = String(tk);
    lSvg.appendChild(lbl);
  }
  const lSlot = lPlotH / D.shocks.length;
  const lBarH = 18;
  D.shocks.forEach((sh, i) => {
    const sr = rowsForShock(sh);
    const meanVal = sr.reduce((a, r) => a + r.margin, 0) / sr.length;
    const y = lpT + i * lSlot + (lSlot - lBarH) / 2;
    const w = (meanVal / 120e6) * lPlotW;
    const active = state.shock === sh;
    const txt = svgEl("text", { x: lpL - 8, y: y + lBarH / 2 + 4, "text-anchor": "end", class: "axis-mono" });
    txt.textContent = (sh > 0 ? "+" : "") + sh + "%";
    lSvg.appendChild(txt);

    const g = svgEl("g", { style: "cursor:pointer" });
    g.appendChild(svgEl("path", {
      d: rightRoundedBar(lpL, y, w, lBarH, 2),
      fill: active ? "var(--ink)" : "var(--muted)",
      opacity: active ? "1" : "0.48",
    }));
    g.addEventListener("click", () => { state.shock = sh; renderShock(); });
    lSvg.appendChild(g);
    haloText(lSvg, { x: lpL + w + 8, y: y + lBarH / 2 + 4, class: "axis-mono" }, mn(meanVal));
  });
  lHost.appendChild(lSvg);

  // Sheet 4b: Harvest-day margin bars at selected shock
  const bHost = document.getElementById("shock-bars");
  bHost.replaceChildren();
  const BW = 480, BH = 172, bpL = 132, bpR = 110, bpT = 6, bpB = 24;
  const bPlotW = BW - bpL - bpR, bPlotH = BH - bpT - bpB;
  const bSvg = svgEl("svg", { viewBox: `0 0 ${BW} ${BH}`, role: "img" });
  for (const tk of [0, 40, 80, 120]) {
    const x = bpL + (tk / 120) * bPlotW;
    bSvg.appendChild(svgEl("line", { x1: x, x2: x, y1: bpT, y2: bpT + bPlotH, class: "gridline" }));
    const lbl = svgEl("text", { x, y: BH - 4, "text-anchor": "middle", class: "axis" });
    lbl.textContent = String(tk);
    bSvg.appendChild(lbl);
  }
  const bSlot = bPlotH / rows.length;
  const bBarH = 20;
  rows.forEach((r, i) => {
    const y = bpT + i * bSlot + (bSlot - bBarH) / 2;
    const w = (r.margin / 120e6) * bPlotW;
    const dim = state.region && state.region !== r.region_key;
    const impact = (r.margin - base[r.region_key]) / base[r.region_key];
    const lbl = svgEl("text", { x: bpL - 10, y: y + bBarH / 2 + 4, "text-anchor": "end", class: "axis-ink", opacity: dim ? "0.45" : "1" });
    lbl.textContent = D.names[r.region_key];
    bSvg.appendChild(lbl);

    const bar = svgEl("path", { d: rightRoundedBar(bpL, y, w, bBarH, 2), fill: estateColor(r.region_key), opacity: dim ? "0.4" : "1" });
    bar.addEventListener("mousemove", (ev) => {
      showTip(ev, `<div class="tooltip-head">${D.names[r.region_key]} (${state.shock > 0 ? "+" : ""}${state.shock}% palm)</div>
        <div class="tooltip-mono">Margin: ${mn(r.margin)} m IDR/ha (${signedPct(impact)} vs base)</div>
        <div class="tooltip-mono">Manager: ${D.managers[r.region_key]} · CPO ${fmtInt(r.cpo)} IDR/t</div>`);
    });
    bar.addEventListener("mouseleave", hideTip);
    bSvg.appendChild(bar);
    haloText(bSvg, { x: bpL + w + 8, y: y + bBarH / 2 + 4, class: "axis-mono", opacity: dim ? "0.45" : "1" }, `${mn(r.margin)}  ${signedPct(impact)}`);
  });
  bHost.appendChild(bSvg);

  // Right: Full 9-scenario Price x FX matrix
  const mHost = document.getElementById("stress-matrix");
  mHost.replaceChildren();
  const scenarios = [
    ["palm_-20pct", "−20% palm", "0.80", "1.00"],
    ["palm-10_fx-10", "−10% palm & −10% FX", "0.90", "0.90"],
    ["palm_-10pct", "−10% palm", "0.90", "1.00"],
    ["idr_-10pct", "−10% FX", "1.00", "0.90"],
    ["base", "Base (27 Sep 2026)", "1.00", "1.00"],
    ["idr_+10pct", "+10% FX", "1.00", "1.10"],
    ["palm_+10pct", "+10% palm", "1.10", "1.00"],
    ["palm_+20pct", "+20% palm", "1.20", "1.00"],
    ["palm+10_fx+10", "+10% palm & +10% FX", "1.10", "1.10"],
  ];
  const byKey = new Map(D.whatif_all.map((w) => [`${w.scenario}|${w.region_key}`, w]));
  const estates = ["riau", "lampung", "north_sumatra", "central_kalimantan"];
  const tbl = document.createElement("table");
  tbl.className = "ledger";
  tbl.innerHTML = `<thead><tr>
    <th>Scenario</th><th class="num">Palm × FX</th><th class="num">CPO IDR/t</th>
    ${estates.map((e) => `<th class="num">${e === "central_kalimantan" ? "C. Kal." : (e === "north_sumatra" ? "N. Sum." : D.names[e])}</th>`).join("")}
  </tr></thead>`;
  const tb = document.createElement("tbody");
  for (const [sc, label, pm, fm] of scenarios) {
    const tr = document.createElement("tr");
    const isBase = sc === "base";
    const isSelectedPriceOnly = Number(fm) === 1 && Math.abs((Number(pm) - 1) * 100 - state.shock) < 1e-6;
    if (isSelectedPriceOnly) tr.className = "selected-row";
    const sample = byKey.get(`${sc}|riau`);
    const cells = estates.map((rk) => {
      const row = byKey.get(`${sc}|${rk}`);
      const delta = (row.margin - base[rk]) / base[rk];
      let bg = "transparent";
      if (delta > 0.005) bg = state.theme === "dark" ? "rgba(126,184,188,0.16)" : "rgba(31,122,128,0.10)";
      else if (delta < -0.005) bg = state.theme === "dark" ? "rgba(224,154,148,0.16)" : "rgba(194,65,12,0.09)";
      return `<td class="num"><div class="matrix-cell" style="background:${bg}">${mn(row.margin)}<span class="matrix-sub">${signedPct(delta)}</span></div></td>`;
    }).join("");
    tr.innerHTML = `<td>${isBase ? "<b>" + label + "</b>" : label}</td><td class="num">${pm} × ${fm}</td><td class="num">${(sample.cpo / 1e6).toFixed(2)}M</td>${cells}`;
    tb.appendChild(tr);
  }
  tbl.appendChild(tb);
  mHost.appendChild(tbl);
}

function renderLedger() {
  const host = document.getElementById("ledger-table");
  host.replaceChildren();
  const base = Object.fromEntries(rowsForShock(0).map((r) => [r.region_key, r.margin]));
  const down20 = Object.fromEntries(rowsForShock(-20).map((r) => [r.region_key, r.margin]));
  const ranked = [...D.order].sort((a, b) => D.unit_econ[b].net_margin_idr_per_ha - D.unit_econ[a].net_margin_idr_per_ha);

  const tbl = document.createElement("table");
  tbl.className = "ledger";
  tbl.innerHTML = `<thead><tr>
    <th>Estate</th><th>Manager</th><th class="num">Area (ha)</th><th class="num">Harvest</th>
    <th class="num">Rev (bn/ha)</th><th class="num">Cost (bn/ha)</th><th class="num">Idle (m/ha)</th>
    <th class="num">Margin (bn/ha)</th><th class="num">Total (Rp Tn)</th>
    <th class="num">Base (m/ha)</th><th class="num">−20% (m/ha)</th><th>Flags on 30 Jun</th>
  </tr></thead>`;
  const tb = document.createElement("tbody");
  for (const rk of ranked) {
    const u = D.unit_econ[rk];
    const reg = D.regions[rk];
    const costs = u.fertilizer_cost_idr_per_ha + u.harvest_cost_idr_per_ha + u.transport_cost_idr_per_ha;
    const tr = document.createElement("tr");
    tr.className = "clickable" + (state.region === rk ? " selected-row" : "");
    const status = rk === "riau"
      ? `<span class="status-dot" style="background:var(--alert)"></span>Closed (2 deficit d)`
      : `<span class="status-dot" style="background:var(--muted)"></span>Closed (0 open)`;
    tr.innerHTML = `
      <td style="white-space:nowrap;"><span class="swatch" style="background:${estateColor(rk)};margin-right:8px;"></span>${reg.region_name}</td>
      <td style="white-space:nowrap;">${reg.estate_manager}</td>
      <td class="num">${fmtInt(reg.planted_hectares)}</td>
      <td class="num">${u.effective_harvest_days}/120</td>
      <td class="num">${bn(u.revenue_idr_per_ha)}</td>
      <td class="num">${bn(costs)}</td>
      <td class="num">−${mn(Math.abs(u.idle_drag_idr_per_ha))}</td>
      <td class="num"><b>${bn(u.net_margin_idr_per_ha)}</b></td>
      <td class="num">${tn(u.total_estate_margin_idr)}</td>
      <td class="num">${mn(base[rk])}</td>
      <td class="num">${mn(down20[rk])}</td>
      <td style="white-space:nowrap;">${status}</td>`;
    tr.addEventListener("click", () => toggleRegion(rk));
    tb.appendChild(tr);
  }
  tbl.appendChild(tb);
  host.appendChild(tbl);
}

function renderAudit() {
  const host = document.getElementById("audit-body");
  host.replaceChildren();
  const rowsHtml = D.audit.extracts.map((e) => `
    <tr><td>${e.file}</td><td>${e.model}</td><td class="num">${e.rows}</td><td class="num">${e.nulls}</td><td class="num">${e.dups}</td></tr>
  `).join("");
  const left = document.createElement("div");
  left.className = "table-wrap";
  left.innerHTML = `<table class="ledger"><thead><tr><th>Extract CSV</th><th>dbt model</th><th class="num">Rows</th><th class="num">Null keys</th><th class="num">Dup grains</th></tr></thead><tbody>${rowsHtml}</tbody></table>`;

  const fh = D.audit.forecast_health;
  const right = document.createElement("div");
  right.className = "callout-box";
  right.innerHTML = `
    <p style="margin:0 0 8px;"><b>Data honesty &amp; scope disclosures</b></p>
    <p style="margin:0 0 6px;"><b>No plan or budget column:</b> Information schema check across main found ${D.audit.plan_columns.length} matching columns. Only the four-estate FIXED mean is plotted as reference.</p>
    <p style="margin:0 0 6px;"><b>30-day CPO forecast rejected from chart:</b> forecast_cpo_30day (${fh.n_rows} rows, ${fh.min_date}..${fh.max_date}) carries flat ${fmtInt(fh.forecast_usd)} USD/t, band width ${fh.band_max}, and ${fh.overlap_days} overlap days with actual prices.</p>
    <p style="margin:0;"><b>Constant Jul–Sep commodity print:</b> Pink Sheet history ends 2026-06-30; July–September forward-fills the June level (${D.audit.price_span.min_date}..${D.audit.price_span.max_date}).</p>
  `;
  host.appendChild(left);
  host.appendChild(right);
}

function renderAll() {
  renderTopControls();
  renderKpis();
  renderRank();
  renderTrend();
  renderCumulative();
  renderCalendar();
  renderBlockingMix();
  renderVarianceBridge();
  renderQuadrant();
  renderDiscount();
  renderMarketMultiples();
  renderShock();
  renderLedger();
}

document.getElementById("clear-filter").addEventListener("click", () => { state.region = null; renderAll(); });
document.getElementById("bridge-target").addEventListener("change", (ev) => { state.bridgeTarget = ev.target.value; renderVarianceBridge(); });
document.querySelectorAll("#unit-basis-toggle button").forEach((btn) => {
  btn.addEventListener("click", () => { state.unit = btn.dataset.unit; renderAll(); });
});
document.getElementById("theme-toggle").addEventListener("click", () => {
  state.theme = state.theme === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", state.theme);
  renderAll();
});

renderAudit();
renderAll();
</script>
</body>
</html>
"""


def main() -> None:
    payload = build_payload()
    payload_json = json.dumps(payload, separators=(",", ":"))
    html_out = HTML_TEMPLATE.replace("__PAYLOAD_JSON__", payload_json)
    OUT_HTML.write_text(html_out, encoding="utf-8")
    print(f"Wrote {OUT_HTML} ({len(html_out):,} bytes)")


if __name__ == "__main__":
    main()
