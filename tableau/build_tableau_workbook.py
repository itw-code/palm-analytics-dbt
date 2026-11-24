"""Programmatically build ONE unified long-scroll Proof Room Tableau workbench (.twbx).

Mirrors tableau/dashboard.html inside a single coherent 1366x2680 executive dashboard
backed by 4 typed Hyper extracts generated from tableau/export/*.csv, with all supporting
worksheets hidden into the single workbench tab and validated via cwtwb + XSD schemas.
"""

from __future__ import annotations

import csv
import datetime as dt
import zipfile
from collections import defaultdict
from pathlib import Path

from tableauhyperapi import (
    Connection,
    CreateMode,
    HyperProcess,
    Inserter,
    Nullability,
    SqlType,
    TableDefinition,
    TableName,
    Telemetry,
)
from cwtwb.twb_editor import TWBEditor
from cwtwb.validator import load_workbook_root, validate_against_schema

TABLEAU_DIR = Path(__file__).resolve().parent
EXPORT_DIR = TABLEAU_DIR / "export"
EXTRACT_DIR = TABLEAU_DIR / "extracts"
OUTPUT_TWBX = TABLEAU_DIR / "palm_estate_margin_workbench.twbx"

ESTATE_PALETTE = {
    "Central Kalimantan": "#7A5F28",
    "Lampung": "#8C4A6B",
    "North Sumatra": "#3F6B52",
    "Riau": "#1F7A80",
}

STATUS_PALETTE = {
    "Effective Harvest": "#3F6B52",
    "Weather Blocked": "#C2410C",
    "Weekend": "#94A3B8",
    "Public Holiday": "#CBD5E1",
}

SCENARIO_LABELS = {
    "palm_-20pct": "01 · Palm -20% (FX 1.00)",
    "palm-10_fx-10": "02 · Palm -10% & FX -10%",
    "palm_-10pct": "03 · Palm -10% (FX 1.00)",
    "idr_-10pct": "04 · IDR -10% Stronger",
    "base": "05 · Base Case (0%)",
    "idr_+10pct": "06 · IDR +10% Weaker",
    "palm_+10pct": "07 · Palm +10% (FX 1.00)",
    "palm_+20pct": "08 · Palm +20% (FX 1.00)",
    "palm+10_fx+10": "09 · Palm +10% & FX +10%",
}

MARGIN_BN_FORMAT = '#,##0.00,,,"bn IDR/ha"'
MARGIN_M_FORMAT = '#,##0.0,,"m IDR/ha"'
MARGIN_T_FORMAT = '"Rp "#,##0.00,,,,"T"'
PCT_FORMAT = "0.0%"
CPO_IDR_M_FORMAT = '#,##0.0,,"m IDR/t"'

CARD_STYLE = {
    "background-color": "#ffffff",
    "border-color": "#e5e0d5",
    "border-style": "solid",
    "border-width": "1",
    "padding": "10",
}

RAIL_STYLE = {
    "background-color": "#efeae0",
    "border-color": "#e5e0d5",
    "border-style": "solid",
    "border-width": "1",
    "padding": "10",
}


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _parse_date(val: str) -> dt.date:
    return dt.date.fromisoformat(val[:10])


def _parse_bool(val: str) -> bool:
    return str(val).strip().lower() in {"true", "1", "yes"}


def _build_hyper_extracts() -> tuple[tuple[Path, Path, Path, Path], dict[str, str]]:
    """Compile 4 typed .hyper extracts and compute verified executive KPI strings."""
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    dim_regions = {
        r["region_key"]: r for r in _read_csv_rows(EXPORT_DIR / "dim_region__region_key.csv")
    }
    ops_rows = {
        (r["region_key"], r["operation_date"]): r
        for r in _read_csv_rows(EXPORT_DIR / "fct_estate_operations_daily__region_date.csv")
    }
    margin_rows = _read_csv_rows(EXPORT_DIR / "fct_estate_margin_daily__region_date.csv")
    price_rows = _read_csv_rows(EXPORT_DIR / "fct_commodity_price_daily__price_date.csv")
    anomaly_rows = _read_csv_rows(EXPORT_DIR / "rec_anomaly_flags__region_date.csv")
    shock_rows = _read_csv_rows(EXPORT_DIR / "whatif_margin_shocks__region_scenario.csv")

    # Sort margin rows chronologically within region for exact running cumulative margin/ha
    margin_sorted = sorted(margin_rows, key=lambda r: (r["region_key"], r["operation_date"]))
    running_cum: dict[str, float] = defaultdict(float)

    total_portfolio_idr = 0.0
    total_eff_days = 0
    total_weather_days = 0
    region_margin_ha: dict[str, float] = defaultdict(float)
    region_margin_total: dict[str, float] = defaultdict(float)
    region_eff_days: dict[str, int] = defaultdict(int)
    region_weather_days: dict[str, int] = defaultdict(int)

    enriched_margin = []
    for r in margin_sorted:
        rk = r["region_key"]
        op_dt = r["operation_date"]
        dim = dim_regions[rk]
        op = ops_rows[(rk, op_dt)]

        eff = _parse_bool(r["is_effective_harvest_day"])
        harv_fav = _parse_bool(op["is_harvest_favorable"])
        is_hol = _parse_bool(op["is_holiday"])
        is_wknd = _parse_bool(op["is_weekend"])
        if eff:
            day_status = "Effective Harvest"
        elif harv_fav and is_hol:
            day_status = "Public Holiday"
        elif harv_fav and is_wknd:
            day_status = "Weekend"
        else:
            day_status = "Weather Blocked"

        m_ha = float(r["margin_idr_per_ha"])
        m_tot = float(r["margin_total_idr"])
        fert_ha = float(r["fertilizer_cost_idr_per_ha"])
        running_cum[rk] += m_ha

        total_portfolio_idr += m_tot
        region_margin_ha[rk] += m_ha
        region_margin_total[rk] += m_tot
        if eff:
            total_eff_days += 1
            region_eff_days[rk] += 1
        if day_status == "Weather Blocked":
            total_weather_days += 1
            region_weather_days[rk] += 1

        enriched_margin.append([
            r["operations_key"],
            rk,
            dim["region_name"],
            dim["island"],
            dim["estate_manager"],
            _parse_date(op_dt),
            day_status,
            eff,
            1.0 if eff else 0.0,
            1.0 if day_status == "Weather Blocked" else 0.0,
            float(r["cpo_idr_per_tonne"]),
            float(r["planted_hectares"]),
            float(r["yield_t_ha"]),
            fert_ha,
            float(r["harvest_cost_idr_per_ha"]),
            float(r["transport_cost_idr_per_ha"]),
            float(r["extraction_rate"]),
            float(r["revenue_idr_per_ha"]),
            m_ha,
            m_tot,
            float(op.get("precip_mm", 0.0) or 0.0),
            float(op.get("water_deficit_mm", 0.0) or 0.0),
            running_cum[rk],
            m_ha if eff else None,
            0.0 if eff else fert_ha,
        ])

    total_ha = sum(float(d["planted_hectares"]) for d in dim_regions.values())
    leader_rk = max(region_margin_ha, key=lambda k: region_margin_ha[k])
    last_price = price_rows[-1]
    latest_disc_pct = float(last_price["palm_soy_spread_usd"]) / float(last_price["soybean_oil_usd"]) * 100.0
    kpis = {
        "portfolio_val": f"Rp {total_portfolio_idr / 1e12:.2f} T",
        "portfolio_note": f"{total_eff_days} harvest estate-days across {int(total_ha):,} planted ha (480 scheduled)",
        "leader_val": f"{dim_regions[leader_rk]['region_name']} · {region_margin_ha[leader_rk] / 1e9:.2f} bn/ha",
        "leader_note": f"{region_eff_days[leader_rk]} harvest days vs Riau Rp {region_margin_total['riau'] / 1e12:.2f} T total",
        "weather_val": f"{total_weather_days} / {len(margin_sorted)} days",
        "weather_note": f"Central Kalimantan loses {region_weather_days['central_kalimantan']} / 120 calendar days to rain",
        "discount_val": f"{latest_disc_pct:.1f}%",
        "discount_note": f"Spread ${float(last_price['palm_soy_spread_usd']):,.0f}/t as of {last_price['price_date']} print",
    }

    estate_hyper = EXTRACT_DIR / "estate_margin.hyper"
    price_hyper = EXTRACT_DIR / "commodity_prices.hyper"
    anom_hyper = EXTRACT_DIR / "anomaly_flags.hyper"
    shock_hyper = EXTRACT_DIR / "whatif_shocks.hyper"

    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        estate_def = TableDefinition(
            TableName("Extract", "Extract"),
            [
                TableDefinition.Column("operations_key", SqlType.text()),
                TableDefinition.Column("region_key", SqlType.text()),
                TableDefinition.Column("region_name", SqlType.text()),
                TableDefinition.Column("island", SqlType.text()),
                TableDefinition.Column("estate_manager", SqlType.text()),
                TableDefinition.Column("operation_date", SqlType.date()),
                TableDefinition.Column("day_status", SqlType.text()),
                TableDefinition.Column("is_effective_harvest_day", SqlType.bool()),
                TableDefinition.Column("effective_harvest_day_int", SqlType.double()),
                TableDefinition.Column("weather_blocked_day_int", SqlType.double()),
                TableDefinition.Column("cpo_idr_per_tonne", SqlType.double()),
                TableDefinition.Column("planted_hectares", SqlType.double()),
                TableDefinition.Column("yield_t_ha", SqlType.double()),
                TableDefinition.Column("fertilizer_cost_idr_per_ha", SqlType.double()),
                TableDefinition.Column("harvest_cost_idr_per_ha", SqlType.double()),
                TableDefinition.Column("transport_cost_idr_per_ha", SqlType.double()),
                TableDefinition.Column("extraction_rate", SqlType.double()),
                TableDefinition.Column("revenue_idr_per_ha", SqlType.double()),
                TableDefinition.Column("margin_idr_per_ha", SqlType.double()),
                TableDefinition.Column("margin_total_idr", SqlType.double()),
                TableDefinition.Column("precip_mm", SqlType.double()),
                TableDefinition.Column("water_deficit_mm", SqlType.double()),
                TableDefinition.Column("cum_margin_idr_per_ha", SqlType.double()),
                TableDefinition.Column("harvest_day_margin_idr_per_ha", SqlType.double(), nullability=Nullability.NULLABLE),
                TableDefinition.Column("idle_fertilizer_cost_idr_per_ha", SqlType.double()),
            ],
        )
        with Connection(hyper.endpoint, estate_hyper, CreateMode.CREATE_AND_REPLACE) as conn:
            conn.catalog.create_schema("Extract")
            conn.catalog.create_table(estate_def)
            with Inserter(conn, estate_def) as ins:
                ins.add_rows(enriched_margin)
                ins.execute()

        price_def = TableDefinition(
            TableName("Extract", "Extract"),
            [
                TableDefinition.Column("price_date", SqlType.date()),
                TableDefinition.Column("palm_oil_usd", SqlType.double()),
                TableDefinition.Column("soybean_oil_usd", SqlType.double()),
                TableDefinition.Column("palm_soy_spread_usd", SqlType.double()),
                TableDefinition.Column("discount_pct", SqlType.double()),
                TableDefinition.Column("usd_idr", SqlType.double()),
                TableDefinition.Column("palm_oil_idr", SqlType.double()),
            ],
        )
        with Connection(hyper.endpoint, price_hyper, CreateMode.CREATE_AND_REPLACE) as conn:
            conn.catalog.create_schema("Extract")
            conn.catalog.create_table(price_def)
            with Inserter(conn, price_def) as ins:
                for r in price_rows:
                    soy = float(r["soybean_oil_usd"])
                    spread = float(r["palm_soy_spread_usd"])
                    ins.add_row([
                        _parse_date(r["price_date"]),
                        float(r["palm_oil_usd"]),
                        soy,
                        spread,
                        spread / soy,
                        float(r["usd_idr"]),
                        float(r["palm_oil_idr"]),
                    ])
                ins.execute()

        anom_def = TableDefinition(
            TableName("Extract", "Extract"),
            [
                TableDefinition.Column("region_key", SqlType.text()),
                TableDefinition.Column("region_name", SqlType.text()),
                TableDefinition.Column("operation_date", SqlType.date()),
                TableDefinition.Column("rain_14d_mm", SqlType.double()),
                TableDefinition.Column("deficit_14d_mm", SqlType.double()),
                TableDefinition.Column("is_rainfall_deficit", SqlType.bool()),
                TableDefinition.Column("palm_mom_pct", SqlType.double()),
                TableDefinition.Column("is_price_spike", SqlType.bool()),
            ],
        )
        with Connection(hyper.endpoint, anom_hyper, CreateMode.CREATE_AND_REPLACE) as conn:
            conn.catalog.create_schema("Extract")
            conn.catalog.create_table(anom_def)
            with Inserter(conn, anom_def) as ins:
                for r in anomaly_rows:
                    dim = dim_regions[r["region_key"]]
                    ins.add_row([
                        r["region_key"],
                        dim["region_name"],
                        _parse_date(r["operation_date"]),
                        float(r["rain_14d_mm"]),
                        float(r["deficit_14d_mm"]),
                        _parse_bool(r["is_rainfall_deficit"]),
                        float(r["palm_mom_pct"]),
                        _parse_bool(r["is_price_spike"]),
                    ])
                ins.execute()

        shock_def = TableDefinition(
            TableName("Extract", "Extract"),
            [
                TableDefinition.Column("whatif_key", SqlType.text()),
                TableDefinition.Column("region_key", SqlType.text()),
                TableDefinition.Column("region_name", SqlType.text()),
                TableDefinition.Column("island", SqlType.text()),
                TableDefinition.Column("scenario", SqlType.text()),
                TableDefinition.Column("scenario_label", SqlType.text()),
                TableDefinition.Column("palm_mult", SqlType.double()),
                TableDefinition.Column("fx_mult", SqlType.double()),
                TableDefinition.Column("shocked_palm_usd", SqlType.double()),
                TableDefinition.Column("shocked_usd_idr", SqlType.double()),
                TableDefinition.Column("shocked_cpo_idr", SqlType.double()),
                TableDefinition.Column("shocked_margin_idr_per_ha", SqlType.double()),
            ],
        )
        with Connection(hyper.endpoint, shock_hyper, CreateMode.CREATE_AND_REPLACE) as conn:
            conn.catalog.create_schema("Extract")
            conn.catalog.create_table(shock_def)
            with Inserter(conn, shock_def) as ins:
                for r in shock_rows:
                    dim = dim_regions[r["region_key"]]
                    sc = r["scenario"]
                    ins.add_row([
                        r["whatif_key"],
                        r["region_key"],
                        dim["region_name"],
                        dim["island"],
                        sc,
                        SCENARIO_LABELS.get(sc, sc),
                        float(r["palm_mult"]),
                        float(r["fx_mult"]),
                        float(r["shocked_palm_usd"]),
                        float(r["shocked_usd_idr"]),
                        float(r["shocked_cpo_idr"]),
                        float(r["shocked_margin_idr_per_ha"]),
                    ])
                ins.execute()

    return (estate_hyper, price_hyper, anom_hyper, shock_hyper), kpis


def _title_ws(editor: TWBEditor, ws: str, headline: str, subtitle: str) -> None:
    editor.set_worksheet_rich_title(
        ws,
        [
            {"text": headline, "bold": True, "fontsize": "11", "fontcolor": "#111e29"},
            {"text": f"\n{subtitle}", "fontsize": "8", "fontcolor": "#5C6570"},
        ],
    )


def _kpi_card(label: str, value: str, note: str) -> dict:
    return {
        "type": "text",
        "runs": [
            {"text": label.upper(), "bold": True, "font_size": "8", "font_color": "#5C6570", "font_alignment": "0"},
            {"text": f"\n{value}", "bold": True, "font_size": "16", "font_color": "#111e29", "font_alignment": "0"},
            {"text": f"\n{note}", "font_size": "8", "font_color": "#5C6570", "font_alignment": "0"},
        ],
        "style": CARD_STYLE,
    }


def _section_header(title: str, tag: str, rail: str) -> dict:
    return {
        "type": "text",
        "fixed_size": 58,
        "runs": [
            {"text": title, "bold": True, "font_size": "13", "font_color": "#111e29", "font_alignment": "0"},
            {"text": f"   [{tag}]", "font_size": "8", "font_color": "#5C6570", "font_alignment": "0"},
            {"text": f"\n{rail}", "font_size": "9", "font_color": "#26313d", "font_alignment": "0"},
        ],
        "style": RAIL_STYLE,
    }


def _promote_measures(editor: TWBEditor, field_names: list[str]) -> None:
    """Force numeric fields containing 'id' (like '*_idr*') from dimension to measure."""
    from lxml import etree as _etree

    ds = editor._datasource
    for fname in field_names:
        local = f"[{fname}]"
        col = ds.find(f"column[@name='{local}']")
        if col is None:
            col = _etree.Element("column", name=local, datatype="real")
            anchor = ds.find("layout") or ds.find("extract") or ds.find("style")
            if anchor is not None:
                anchor.addprevious(col)
            else:
                ds.append(col)
        col.set("role", "measure")
        col.set("type", "quantitative")
    editor._init_fields()


def build_workbook() -> Path:
    (estate_hyper, price_hyper, anom_hyper, shock_hyper), kpis = _build_hyper_extracts()

    editor = TWBEditor("")
    editor.clear_worksheets()

    # ==========================================================
    # DATASOURCE 1: Estate Margin Daily (Primary)
    # ==========================================================
    editor.set_hyper_connection(str(estate_hyper), table_name="Extract")
    editor._datasource.set("caption", "Estate Margin Daily")
    ds_estate_name = "Estate Margin Daily"

    _promote_measures(
        editor,
        [
            "cpo_idr_per_tonne",
            "fertilizer_cost_idr_per_ha",
            "harvest_cost_idr_per_ha",
            "transport_cost_idr_per_ha",
            "revenue_idr_per_ha",
            "margin_idr_per_ha",
            "margin_total_idr",
            "cum_margin_idr_per_ha",
            "harvest_day_margin_idr_per_ha",
            "idle_fertilizer_cost_idr_per_ha",
            "water_deficit_mm",
            "precip_mm",
            "extraction_rate",
            "planted_hectares",
            "yield_t_ha",
            "effective_harvest_day_int",
            "weather_blocked_day_int",
        ],
    )

    editor.set_datasource_color_palette("region_name", ESTATE_PALETTE)
    editor.set_datasource_color_palette("day_status", STATUS_PALETTE)
    editor.set_field_format("margin_idr_per_ha", MARGIN_BN_FORMAT)
    editor.set_field_format("cum_margin_idr_per_ha", MARGIN_BN_FORMAT)
    editor.set_field_format("margin_total_idr", MARGIN_T_FORMAT)
    editor.set_field_format("revenue_idr_per_ha", MARGIN_BN_FORMAT)
    editor.set_field_format("harvest_day_margin_idr_per_ha", MARGIN_M_FORMAT)
    editor.set_field_format("idle_fertilizer_cost_idr_per_ha", MARGIN_M_FORMAT)
    editor.set_field_format("planted_hectares", '#,##0" ha"')
    editor.set_field_format("yield_t_ha", '0.0" t/ha"')
    editor.set_field_format("effective_harvest_day_int", "#,##0")
    editor.set_field_format("weather_blocked_day_int", "#,##0")

    # 1. Estate Margin Ranking
    editor.add_worksheet("Estate Margin Ranking")
    editor.configure_chart(
        worksheet_name="Estate Margin Ranking",
        mark_type="Bar",
        columns=["SUM(margin_idr_per_ha)"],
        rows=["region_name"],
        color="region_name",
        label="SUM(margin_idr_per_ha)",
        sort_descending="SUM(margin_idr_per_ha)",
        color_map=ESTATE_PALETTE,
    )
    _title_ws(
        editor,
        "Estate Margin Ranking",
        "Lampung leads period margin per hectare (5.36 vs 4.80 bn/ha)",
        "Cumulative 3 Mar-30 Jun margin/ha; click bar to filter views",
    )
    editor.configure_custom_tooltip(
        "Estate Margin Ranking",
        [
            {"field": "region_name", "bold": True, "fontsize": "11"},
            {"text": " ("},
            {"field": "ATTR(estate_manager)"},
            {"text": ")\nMargin / ha: "},
            {"field": "SUM(margin_idr_per_ha)", "bold": True},
            {"text": "\nTotal Margin: "},
            {"field": "SUM(margin_total_idr)"},
            {"text": "\nHarvest Days: "},
            {"field": "SUM(effective_harvest_day_int)"},
        ],
    )
    editor.configure_worksheet_style("Estate Margin Ranking", hide_row_field_labels=True, hide_borders=True)

    # 2. Monthly Margin Drift
    editor.add_worksheet("Monthly Margin Drift")
    editor.configure_chart(
        worksheet_name="Monthly Margin Drift",
        mark_type="Line",
        columns=["MONTH(operation_date)"],
        rows=["SUM(margin_idr_per_ha)"],
        color="region_name",
        color_map=ESTATE_PALETTE,
    )
    editor.add_reference_line(
        "Monthly Margin Drift",
        axis_field="SUM(margin_idr_per_ha)",
        value_field="SUM(margin_idr_per_ha)",
        scope="per-table",
        formula="average",
        label_type="value",
        label="Monthly avg",
    )
    editor.configure_reference_line_style("Monthly Margin Drift", "refline0", {"stroke-color": "#5C6570", "line-pattern-only": "dashed"})
    _title_ws(
        editor,
        "Monthly Margin Drift",
        "Central Kalimantan stays 4th every month; May marks the trough",
        "Monthly margin/ha across 4 estates vs portfolio average line",
    )
    editor.configure_custom_tooltip(
        "Monthly Margin Drift",
        [
            {"field": "region_name", "bold": True},
            {"text": " - "},
            {"field": "MONTH(operation_date)"},
            {"text": "\nMargin / ha: "},
            {"field": "SUM(margin_idr_per_ha)", "bold": True},
            {"text": "\nHarvest Days: "},
            {"field": "SUM(effective_harvest_day_int)"},
        ],
    )
    editor.configure_worksheet_style("Monthly Margin Drift", hide_col_field_labels=True, hide_borders=True)

    # 3. Daily Cumulative Margin
    editor.add_worksheet("Daily Cumulative Margin")
    editor.configure_chart(
        worksheet_name="Daily Cumulative Margin",
        mark_type="Line",
        columns=["DAYTRUNC(operation_date)"],
        rows=["AVG(cum_margin_idr_per_ha)"],
        color="region_name",
        color_map=ESTATE_PALETTE,
    )
    _title_ws(
        editor,
        "Daily Cumulative Margin",
        "Daily cumulative trajectory reveals flat & negative idle-fertilizer burn windows",
        "120 calendar days per estate (flat slopes mark rain-blocked idle days)",
    )
    editor.configure_custom_tooltip(
        "Daily Cumulative Margin",
        [
            {"field": "region_name", "bold": True},
            {"text": " - "},
            {"field": "DAYTRUNC(operation_date)"},
            {"text": "\nCumulative Margin / ha: "},
            {"field": "AVG(cum_margin_idr_per_ha)", "bold": True},
            {"text": "\nDaily Rainfall (mm): "},
            {"field": "AVG(precip_mm)"},
        ],
    )
    editor.configure_worksheet_style("Daily Cumulative Margin", hide_col_field_labels=True, hide_borders=True)

    # 4. Harvest Blocking Mix
    editor.add_worksheet("Harvest Blocking Mix")
    editor.configure_chart(
        worksheet_name="Harvest Blocking Mix",
        mark_type="Bar",
        columns=["COUNT(operations_key)"],
        rows=["region_name"],
        color="day_status",
        color_map=STATUS_PALETTE,
    )
    _title_ws(
        editor,
        "Harvest Blocking Mix",
        "Central Kalimantan loses 82 of 120 calendar days to weather blocks",
        "120-day breakdown: Effective Harvest vs Weather, Weekend & Holiday",
    )
    editor.configure_custom_tooltip(
        "Harvest Blocking Mix",
        [
            {"field": "region_name", "bold": True},
            {"text": " - "},
            {"field": "day_status"},
            {"text": "\nDays: "},
            {"field": "COUNT(operations_key)", "bold": True},
            {"text": "\nMean Rain (mm/d): "},
            {"field": "AVG(precip_mm)"},
        ],
    )
    editor.configure_worksheet_style("Harvest Blocking Mix", hide_row_field_labels=True, hide_borders=True)

    # 5. Idle Fertilizer Burn
    editor.add_worksheet("Idle Fertilizer Burn")
    editor.configure_chart(
        worksheet_name="Idle Fertilizer Burn",
        mark_type="Bar",
        columns=["SUM(idle_fertilizer_cost_idr_per_ha)"],
        rows=["region_name"],
        color="region_name",
        label="SUM(idle_fertilizer_cost_idr_per_ha)",
        sort_descending="SUM(idle_fertilizer_cost_idr_per_ha)",
        color_map=ESTATE_PALETTE,
    )
    _title_ws(
        editor,
        "Idle Fertilizer Burn",
        "Central Kalimantan absorbs 86.5 m IDR/ha in idle non-harvest fertilizer",
        "Unrecovered fertilizer outlays incurred on blocked days (m IDR/ha)",
    )
    editor.configure_custom_tooltip(
        "Idle Fertilizer Burn",
        [
            {"field": "region_name", "bold": True},
            {"text": "\nIdle Fertilizer Burn: "},
            {"field": "SUM(idle_fertilizer_cost_idr_per_ha)", "bold": True},
            {"text": "\nWeather-Blocked Days: "},
            {"field": "SUM(weather_blocked_day_int)"},
        ],
    )
    editor.configure_worksheet_style("Idle Fertilizer Burn", hide_row_field_labels=True, hide_borders=True)

    # 6. Footprint vs Productivity
    editor.add_worksheet("Footprint vs Productivity")
    editor.configure_chart(
        worksheet_name="Footprint vs Productivity",
        mark_type="Circle",
        columns=["SUM(effective_harvest_day_int)"],
        rows=["AVG(harvest_day_margin_idr_per_ha)"],
        size="AVG(planted_hectares)",
        color="region_name",
        label="region_name",
        color_map=ESTATE_PALETTE,
    )
    _title_ws(
        editor,
        "Footprint vs Productivity",
        "Largest estate sits bottom-left: high area (15.2k ha) trapped by few harvest days",
        "X: Effective harvest days | Y: Avg harvest-day margin/ha | Size: Planted ha",
    )
    editor.configure_custom_tooltip(
        "Footprint vs Productivity",
        [
            {"field": "region_name", "bold": True},
            {"text": "\nEffective Harvest Days: "},
            {"field": "SUM(effective_harvest_day_int)"},
            {"text": "\nHarvest-Day Margin / ha: "},
            {"field": "AVG(harvest_day_margin_idr_per_ha)", "bold": True},
            {"text": "\nPlanted Area: "},
            {"field": "AVG(planted_hectares)"},
        ],
    )
    editor.configure_worksheet_style("Footprint vs Productivity", hide_borders=True)

    # 12. Estate Unit Economics Ledger (multi-measure comparison bars across 6 KPIs)
    editor.add_worksheet("Estate Unit Economics Ledger")
    editor.configure_chart(
        worksheet_name="Estate Unit Economics Ledger",
        mark_type="Bar",
        rows=["region_name"],
        color="region_name",
        sort_descending="SUM(margin_idr_per_ha)",
        measure_values=[
            "AVG(planted_hectares)",
            "AVG(yield_t_ha)",
            "SUM(effective_harvest_day_int)",
            "SUM(weather_blocked_day_int)",
            "SUM(margin_idr_per_ha)",
            "SUM(margin_total_idr)",
        ],
        color_map=ESTATE_PALETTE,
    )
    _title_ws(
        editor,
        "Estate Unit Economics Ledger",
        "Multi-metric estate scorecard (click any estate row to cross-filter charts)",
        "Planted area | Yield/ha | Harvest days | Weather blocks | Period margin/ha | Total estate margin",
    )
    editor.configure_worksheet_style("Estate Unit Economics Ledger", hide_row_field_labels=True, hide_borders=True)

    # ==========================================================
    # DATASOURCE 2: Commodity Prices
    # ==========================================================
    editor.add_hyper_datasource("Commodity Prices", str(price_hyper), table_name="Extract")
    _promote_measures(
        editor,
        ["palm_oil_usd", "soybean_oil_usd", "palm_soy_spread_usd", "discount_pct", "usd_idr", "palm_oil_idr"],
    )
    editor.set_field_format("discount_pct", PCT_FORMAT)
    editor.set_field_format("palm_oil_idr", CPO_IDR_M_FORMAT)

    # 7. Palm Discount vs Soy
    editor.add_worksheet("Palm Discount vs Soy")
    editor.configure_chart(
        worksheet_name="Palm Discount vs Soy",
        mark_type="Line",
        columns=["DAYTRUNC(price_date)"],
        rows=["AVG(discount_pct)"],
    )
    editor.add_reference_line(
        "Palm Discount vs Soy",
        axis_field="AVG(discount_pct)",
        value_field="AVG(discount_pct)",
        scope="per-table",
        formula="average",
        label_type="value",
        label="Avg",
    )
    editor.configure_reference_line_style("Palm Discount vs Soy", "refline0", {"stroke-color": "#5C6570", "line-pattern-only": "dashed"})
    _title_ws(
        editor,
        "Palm Discount vs Soy",
        "Palm discount to soy widened (-25.7% to -36.6%)",
        "Discount = (CPO - Soy) / Soy across 209 pricing days",
    )
    editor.configure_custom_tooltip(
        "Palm Discount vs Soy",
        [
            {"field": "DAYTRUNC(price_date)", "bold": True},
            {"text": "\nDiscount to Soy: "},
            {"field": "AVG(discount_pct)", "bold": True},
            {"text": "\nCPO USD/t: "},
            {"field": "AVG(palm_oil_usd)"},
            {"text": " | Soy: "},
            {"field": "AVG(soybean_oil_usd)"},
        ],
    )
    editor.configure_worksheet_style("Palm Discount vs Soy", hide_col_field_labels=True, hide_borders=True)

    # 8. Local CPO Price IDR
    editor.add_worksheet("Local CPO Price IDR")
    editor.configure_chart(
        worksheet_name="Local CPO Price IDR",
        mark_type="Line",
        columns=["DAYTRUNC(price_date)"],
        rows=["AVG(palm_oil_idr)"],
    )
    editor.add_reference_line(
        "Local CPO Price IDR",
        axis_field="AVG(palm_oil_idr)",
        value_field="AVG(palm_oil_idr)",
        scope="per-table",
        formula="average",
        label_type="value",
        label="Avg",
    )
    editor.configure_reference_line_style("Local CPO Price IDR", "refline0", {"stroke-color": "#5C6570", "line-pattern-only": "dashed"})
    _title_ws(
        editor,
        "Local CPO Price IDR",
        "Local CPO price in IDR (m IDR/t) & May FX peak",
        "Rupiah weakness amplified local pricing in May",
    )
    editor.configure_custom_tooltip(
        "Local CPO Price IDR",
        [
            {"field": "DAYTRUNC(price_date)", "bold": True},
            {"text": "\nCPO Local Price: "},
            {"field": "AVG(palm_oil_idr)", "bold": True},
            {"text": "\nUSD/IDR: "},
            {"field": "AVG(usd_idr)"},
        ],
    )
    editor.configure_worksheet_style("Local CPO Price IDR", hide_col_field_labels=True, hide_borders=True)

    # ==========================================================
    # DATASOURCE 3: Anomaly Flags
    # ==========================================================
    editor.add_hyper_datasource("Anomaly Flags", str(anom_hyper), table_name="Extract")
    _promote_measures(editor, ["rain_14d_mm", "deficit_14d_mm", "palm_mom_pct"])
    editor.set_datasource_color_palette("region_name", ESTATE_PALETTE)

    # 9. 14-Day Rolling Rainfall
    editor.add_worksheet("14-Day Rolling Rainfall")
    editor.configure_chart(
        worksheet_name="14-Day Rolling Rainfall",
        mark_type="Line",
        columns=["DAYTRUNC(operation_date)"],
        rows=["AVG(rain_14d_mm)"],
        color="region_name",
        color_map=ESTATE_PALETTE,
    )
    _title_ws(
        editor,
        "14-Day Rolling Rainfall",
        "14-day rolling rainfall dips briefly in Riau (May)",
        "Closed cleanly before 30 Jun (0 open anomalies)",
    )
    editor.configure_custom_tooltip(
        "14-Day Rolling Rainfall",
        [
            {"field": "region_name", "bold": True},
            {"text": " - "},
            {"field": "DAYTRUNC(operation_date)"},
            {"text": "\n14d Rainfall: "},
            {"field": "AVG(rain_14d_mm)", "bold": True},
            {"text": " mm\nDeficit: "},
            {"field": "AVG(deficit_14d_mm)"},
        ],
    )
    editor.configure_worksheet_style("14-Day Rolling Rainfall", hide_col_field_labels=True, hide_borders=True)

    # ==========================================================
    # DATASOURCE 4: What-If Shocks + Parameter "Price Shock %"
    # ==========================================================
    editor.add_hyper_datasource("What-If Shocks", str(shock_hyper), table_name="Extract")
    _promote_measures(
        editor,
        ["palm_mult", "fx_mult", "shocked_palm_usd", "shocked_usd_idr", "shocked_cpo_idr", "shocked_margin_idr_per_ha"],
    )
    editor.set_datasource_color_palette("region_name", ESTATE_PALETTE)
    editor.set_field_format("shocked_margin_idr_per_ha", MARGIN_M_FORMAT)

    editor.add_parameter(
        name="Price Shock %",
        datatype="string",
        default_value="base",
        domain_type="list",
        allowed_values=["palm_-20pct", "palm_-10pct", "base", "palm_+10pct", "palm_+20pct"],
        allowed_aliases={
            "palm_-20pct": "-20% CPO",
            "palm_-10pct": "-10% CPO",
            "base": "Base (0%)",
            "palm_+10pct": "+10% CPO",
            "palm_+20pct": "+20% CPO",
        },
    )
    editor.add_calculated_field(
        field_name="Selected Shock Margin",
        formula="IF [scenario] = [Parameters].[Price Shock %] THEN [shocked_margin_idr_per_ha] END",
        datatype="real",
        role="measure",
        field_type="quantitative",
        default_format=MARGIN_M_FORMAT,
    )

    # 10. Shocked Harvest Margin (responds interactively to Price Shock % parameter)
    editor.add_worksheet("Shocked Harvest Margin")
    editor.configure_chart(
        worksheet_name="Shocked Harvest Margin",
        mark_type="Bar",
        columns=["SUM(Selected Shock Margin)"],
        rows=["region_name"],
        color="region_name",
        label="SUM(Selected Shock Margin)",
        sort_descending="SUM(Selected Shock Margin)",
        color_map=ESTATE_PALETTE,
    )
    _title_ws(
        editor,
        "Shocked Harvest Margin",
        "Harvest-day margin at <[Parameters].[Price Shock %]>",
        "Fixed costs amplify commodity swings 1.025x in Rupiah",
    )
    editor.configure_custom_tooltip(
        "Shocked Harvest Margin",
        [
            {"field": "region_name", "bold": True},
            {"text": "\nScenario: "},
            {"field": "ATTR(scenario_label)"},
            {"text": "\nHarvest-Day Margin: "},
            {"field": "SUM(Selected Shock Margin)", "bold": True},
        ],
    )
    editor.configure_worksheet_style("Shocked Harvest Margin", hide_row_field_labels=True, hide_borders=True)

    # 11. Price x FX Stress Matrix
    editor.add_worksheet("Price x FX Stress Matrix")
    editor.configure_chart(
        worksheet_name="Price x FX Stress Matrix",
        mark_type="Square",
        columns=["region_name"],
        rows=["scenario_label"],
        color="AVG(shocked_margin_idr_per_ha)",
        label="AVG(shocked_margin_idr_per_ha)",
    )
    _title_ws(
        editor,
        "Price x FX Stress Matrix",
        "Full 9-scenario Price x FX stress matrix (m IDR/ha on a harvest day)",
        "Riau stays #1 in every scenario; +10% palm and +10% IDR yield identical CPO IDR",
    )
    editor.configure_custom_tooltip(
        "Price x FX Stress Matrix",
        [
            {"field": "region_name", "bold": True},
            {"text": " | "},
            {"field": "scenario_label"},
            {"text": "\nShocked Margin / ha: "},
            {"field": "AVG(shocked_margin_idr_per_ha)", "bold": True},
            {"text": "\nShocked CPO USD/t: "},
            {"field": "AVG(shocked_palm_usd)"},
            {"text": " | USD/IDR: "},
            {"field": "AVG(shocked_usd_idr)"},
        ],
    )
    editor.configure_worksheet_style("Price x FX Stress Matrix", hide_col_field_labels=True, hide_row_field_labels=True, hide_borders=True)

    # ==========================================================
    # UNIFIED WORKBENCH DASHBOARD (1366 x 2680 long-scroll Executive Page)
    # Must select primary Estate Margin Daily datasource so color legends bind cleanly.
    # ==========================================================
    editor.select_datasource(ds_estate_name)
    all_worksheets = [
        "Estate Margin Ranking",
        "Monthly Margin Drift",
        "Daily Cumulative Margin",
        "Harvest Blocking Mix",
        "Idle Fertilizer Burn",
        "Footprint vs Productivity",
        "Palm Discount vs Soy",
        "Local CPO Price IDR",
        "14-Day Rolling Rainfall",
        "Shocked Harvest Margin",
        "Price x FX Stress Matrix",
        "Estate Unit Economics Ledger",
    ]

    workbench_layout = {
        "type": "container",
        "direction": "vertical",
        "style": {"background-color": "#F7F5F0", "padding": "12"},
        "children": [
            # Top Editorial Masthead (86 px)
            {
                "type": "text",
                "fixed_size": 86,
                "runs": [
                    {
                        "text": "PALM ESTATE OPERATIONS & MARGIN WORKBENCH · PROOF ROOM",
                        "bold": True,
                        "font_size": "8",
                        "font_color": "#5C6570",
                        "font_alignment": "0",
                    },
                    {
                        "text": "\nWhere Estate Margin Drifts — Weather Cadence, Macro Spread & Price Sensitivity",
                        "bold": True,
                        "font_size": "18",
                        "font_color": "#111e29",
                        "font_alignment": "0",
                    },
                    {
                        "text": "\n3 Mar - 30 Jun 2026 operational panel (4 estates, 44,900 ha) + Feb - Sep commodity & stress scenarios · Select any bar or scorecard row to cross-filter",
                        "font_size": "9",
                        "font_color": "#5C6570",
                        "font_alignment": "0",
                    },
                ],
                "style": CARD_STYLE,
            },
            # KPI Strip (96 px)
            {
                "type": "container",
                "direction": "horizontal",
                "fixed_size": 96,
                "children": [
                    _kpi_card("Portfolio Total Margin", kpis["portfolio_val"], kpis["portfolio_note"]),
                    _kpi_card("Per-Hectare Leader", kpis["leader_val"], kpis["leader_note"]),
                    _kpi_card("Weather Throughput Loss", kpis["weather_val"], kpis["weather_note"]),
                    _kpi_card("Palm Discount to Soy", kpis["discount_val"], kpis["discount_note"]),
                ],
            },
            # Section 1: Where margin is drifting (604 px)
            _section_header(
                "1. Where margin is drifting, March-June 2026",
                "fct_estate_margin_daily · 480 rows",
                "Operational cadence decides the period table: Lampung wins per-ha (5.36 vs 4.80 bn) with 10 extra harvest days, while Riau leads total Rp.",
            ),
            {
                "type": "container",
                "direction": "horizontal",
                "fixed_size": 286,
                "children": [
                    {"type": "worksheet", "name": "Estate Margin Ranking", "fixed_size": 460, "fit": "entire", "style": CARD_STYLE},
                    {"type": "worksheet", "name": "Monthly Margin Drift", "fit": "entire", "style": CARD_STYLE},
                    {"type": "color", "worksheet": "Monthly Margin Drift", "field": "region_name", "caption": "Estate Region", "fixed_size": 155, "style": CARD_STYLE},
                ],
            },
            {
                "type": "worksheet",
                "name": "Daily Cumulative Margin",
                "fixed_size": 250,
                "fit": "entire",
                "style": CARD_STYLE,
            },
            # Section 2: Diagnostic root cause (594 px)
            _section_header(
                "2. Diagnostic root cause: weather throughput vs estate scale",
                "fct_estate_operations_daily · 480 rows · dim_region",
                "Stranded land sits in Central Kalimantan: largest area (15,200 ha) yet 82 rain-blocked days force 86.5 m IDR/ha of idle fertilizer drag.",
            ),
            {
                "type": "container",
                "direction": "horizontal",
                "fixed_size": 266,
                "children": [
                    {"type": "worksheet", "name": "Harvest Blocking Mix", "fit": "entire", "style": CARD_STYLE},
                    {"type": "color", "worksheet": "Harvest Blocking Mix", "field": "day_status", "caption": "Day Classification", "fixed_size": 155, "style": CARD_STYLE},
                    {"type": "worksheet", "name": "Idle Fertilizer Burn", "fit": "entire", "style": CARD_STYLE},
                ],
            },
            {
                "type": "worksheet",
                "name": "Footprint vs Productivity",
                "fixed_size": 260,
                "fit": "entire",
                "style": CARD_STYLE,
            },
            # Section 3: Commodity, FX & Anomaly Small Multiples (398 px)
            _section_header(
                "3. Commodity spread, local CPO pricing, and anomaly signals",
                "fct_commodity_price_daily · 209 rows · rec_anomaly_flags · 240 rows",
                "Single-axis small multiples: CPO discount vs soy widened to -36.6% while Rupiah weakness drove May IDR highs and a brief Riau rainfall dip.",
            ),
            {
                "type": "container",
                "direction": "horizontal",
                "fixed_size": 330,
                "children": [
                    {"type": "worksheet", "name": "Palm Discount vs Soy", "fit": "entire", "style": CARD_STYLE},
                    {"type": "worksheet", "name": "Local CPO Price IDR", "fit": "entire", "style": CARD_STYLE},
                    {"type": "worksheet", "name": "14-Day Rolling Rainfall", "fit": "entire", "style": CARD_STYLE},
                ],
            },
            # Section 4: 2D Price x FX Stress-Test Engine (464 px)
            _section_header(
                "4. Harvest-day margin under a palm-price and FX stress test",
                "whatif_margin_shocks · 36 rows · Base print 2026-09-27",
                "Fixed costs amplify commodity swings 1.025x in Rupiah: use the Price Shock % selector to update harvest-day rankings against the full 9-scenario matrix.",
            ),
            {
                "type": "container",
                "direction": "horizontal",
                "fixed_size": 396,
                "children": [
                    {
                        "type": "container",
                        "direction": "vertical",
                        "fixed_size": 490,
                        "children": [
                            {
                                "type": "paramctrl",
                                "parameter": "Price Shock %",
                                "caption": "Select CPO Price Shock",
                                "mode": "compact",
                                "fixed_size": 68,
                                "style": CARD_STYLE,
                            },
                            {
                                "type": "worksheet",
                                "name": "Shocked Harvest Margin",
                                "fit": "entire",
                                "style": CARD_STYLE,
                            },
                        ],
                    },
                    {"type": "worksheet", "name": "Price x FX Stress Matrix", "fit": "entire", "style": CARD_STYLE},
                ],
            },
            # Section 5: Executive Scorecard Ledger + Footer (316 px)
            _section_header(
                "5. Estate unit economics and agronomy ledger",
                "dim_region + fct_estate_margin_daily · 4 estates",
                "Cross-metric bar scorecard comparing footprint, yield, cadence, weather losses, and earnings per hectare vs total portfolio contribution.",
            ),
            {
                "type": "worksheet",
                "name": "Estate Unit Economics Ledger",
                "fixed_size": 250,
                "fit": "entire",
                "style": CARD_STYLE,
            },
            {
                "type": "text",
                "fixed_size": 36,
                "runs": [
                    {
                        "text": "Certified dbt + DuckDB exports (4 Hyper extracts bundled): estate_margin.hyper · commodity_prices.hyper · anomaly_flags.hyper · whatif_shocks.hyper",
                        "font_size": "8",
                        "font_color": "#5C6570",
                        "font_alignment": "1",
                    },
                ],
                "style": {"background-color": "#F7F5F0", "padding": "6"},
            },
        ],
    }

    workbench_name = "Palm Estate Operations & Margin Workbench"
    editor.add_dashboard(
        workbench_name,
        width=1366,
        height=2680,
        layout=workbench_layout,
        worksheet_names=all_worksheets,
    )

    regional_targets = [
        "Monthly Margin Drift",
        "Daily Cumulative Margin",
        "Harvest Blocking Mix",
        "Idle Fertilizer Burn",
        "Footprint vs Productivity",
    ]
    editor.add_dashboard_action(
        workbench_name,
        action_type="filter",
        source_sheet="Estate Margin Ranking",
        target_sheets=regional_targets,
        fields=["region_name"],
        event_type="on-select",
        clear_behavior="show-all",
        caption="Filter workbench views by selected estate bar",
    )
    editor.add_dashboard_action(
        workbench_name,
        action_type="filter",
        source_sheet="Estate Unit Economics Ledger",
        target_sheets=["Estate Margin Ranking"] + regional_targets,
        fields=["region_name"],
        event_type="on-select",
        clear_behavior="show-all",
        caption="Filter workbench views by selected ledger row",
    )

    # Hide individual worksheet tabs so the workbook opens cleanly onto the single workbench
    for ws in all_worksheets:
        editor.set_worksheet_hidden(ws, True)
    editor.set_active_dashboard(workbench_name)

    msg = editor.save(OUTPUT_TWBX, validate=True)
    print(msg)

    root = load_workbook_root(OUTPUT_TWBX)
    xsd_result = validate_against_schema(root)
    print("XSD SCHEMA VALID:", xsd_result.valid, "VERSION:", xsd_result.schema_version)
    if xsd_result.errors:
        print("XSD ERRORS:", xsd_result.errors)
        raise RuntimeError("Schema validation errors detected")
    if xsd_result.compatibility_warnings:
        print("XSD WARNINGS:", xsd_result.compatibility_warnings)

    with zipfile.ZipFile(OUTPUT_TWBX) as zf:
        names = zf.namelist()
        print("TWBX CONTENTS:", names)
        twb_name = next(n for n in names if n.endswith(".twb"))
        twb_xml = zf.read(twb_name).decode("utf-8")
        for needle in [
            "#7a5f28", "#8c4a6b", "#3f6b52", "#1f7a80", "#c2410c",
            "#,##0.00,,,&quot;bn IDR/ha&quot;",
            "Estate Margin Daily",
            "Commodity Prices",
            "Anomaly Flags",
            "What-If Shocks",
            "Price Shock %",
            "Selected Shock Margin",
            workbench_name.replace("&", "&amp;"),
            "Estate Margin Ranking",
            "Monthly Margin Drift",
            "Daily Cumulative Margin",
            "Harvest Blocking Mix",
            "Idle Fertilizer Burn",
            "Footprint vs Productivity",
            "Palm Discount vs Soy",
            "Local CPO Price IDR",
            "14-Day Rolling Rainfall",
            "Shocked Harvest Margin",
            "Price x FX Stress Matrix",
            "Estate Unit Economics Ledger",
            "estate_margin.hyper",
            "commodity_prices.hyper",
            "anomaly_flags.hyper",
            "whatif_shocks.hyper",
        ]:
            assert needle.lower() in twb_xml.lower(), f"Missing expected XML token: {needle}"
        assert "Superstore" not in twb_xml, "Template Superstore datasource caption leaked!"
        assert "C:/Users/" not in twb_xml and "C:\\Users\\" not in twb_xml, "Leaked absolute path inside TWBX!"
    print("ALL SINGLE-PAGE WORKBENCH TWBX ASSERTIONS PASSED.")
    return OUTPUT_TWBX


if __name__ == "__main__":
    build_workbook()
