# Tableau extracts

Worksheet sources for a Tableau Public portfolio workbook. Generated from `palm.duckdb`. The dbt project is not modified by this export.

`tableau/export/manifest.json` is written by the same script. If a number below disagrees with that file or with a re-opened CSV, this dictionary is wrong.

## Browser view

`tableau/dashboard.html` is a self-contained DOM reconstruction of `BUILD.md`. It is not a `.twbx`. Open that file in the `ihsan.wanda@sawitpro.com` Chrome profile (Profile 3). Click an estate to filter the trend. The shock buttons are the price parameter, not a scenario filter.

Published Tableau Public dashboard: https://public.tableau.com/views/Estatemarginbyregion/Dashboard1
Sheet-only bar: https://public.tableau.com/views/Estatemarginbyregion/Sheet1
Older text table: https://public.tableau.com/views/Palmestatemargin/Sheet1
Account `oneda9@gmail.com` (display name Ihsan Tri Wanda). Password is in `C:\Users\oneda\.omp\tableau-public-oneda9.txt`, outside this repo.



## How to refresh

From the repo root, after `palm.duckdb` already exists:

```text
.venv/Scripts/python.exe tableau/export.py
.venv/Scripts/python.exe tableau/export.py --check
```

The script opens the warehouse read-only, writes one CSV per model at native grain, re-opens each CSV, and exits non-zero if a CSV row count differs from the mart, a dimension key is null, or a grain combination is duplicated. It does not run dbt and it does not insert rows.

Refresh Tableau from the same filenames. Do not rename them: the grain is in the name. No Excel step.

On this machine `.venv/Scripts/dbt.exe` exits 1 with empty stdout and stderr. The build that certified these extracts was the dbt 1.12.3 CLI entry point (`dbt.cli.main:cli`), not a change to the project. Result: `PASS=129 WARN=0 ERROR=0 SKIP=0 NO-OP=1 TOTAL=130`.

## What these files are not

There is no plan, budget, or target measure. A column search for those names in `main` returned no columns. `planted_hectares` is area, not a plan.

`forecast_cpo_30day` is exported so the rejection is checkable. It is not a worksheet source. All 30 rows are `forecast_palm_usd = 1104` and `band_half_width_usd = 0`. Forecast dates are 2026-09-28 through 2026-10-27. Overlap with `fct_commodity_price_daily` is 0 days. A forecast-error band cannot be drawn from it.

July–September prices are not a fresh market. The ingest manifest for this warehouse (`ingestion_manifest.json`, generated 2026-09-20T10:41:38Z, status `live`, `synthetic_sources` 0) records 8 live commodity rows and history end 2026-06-30. Eight rows is four months times palm and soy. The daily mart is constant from 2026-07-01 at the June level.

## Shared conventions

| Item | Value |
|---|---|
| Currency | IDR for local margin and `palm_oil_idr`. USD for Pink Sheet prices and the palm−soy spread. `usd_idr` is IDR per 1 USD. |
| Area | hectares. Yield is tonnes of FFB per hectare (`t/ha`). |
| IDR rounding | Margin, revenue, transport, and `palm_oil_idr` are `round(..., 0)` in dbt, stored as DOUBLE. CSV may show a trailing `.0`. Format as integers in Tableau. Do not round again in the extract. |
| Timezone | DATE columns have no time and no offset. Weather days were requested from Open-Meteo with `timezone=Asia/Jakarta` (WIB, UTC+7, no DST). Commodity dates are Pink Sheet months forward-filled onto the calendar. FX dates are Frankfurter reference dates, ASOF-filled onto that same calendar. Do not convert these dates to UTC. |
| Booleans | lowercase `true` / `false`. |
| Estates | Four regional estates. `region_key` is the estate id. Names and managers live in `dim_region`. |

## Row counts

Checked after `dbt build` on 2026-10-24, then re-checked by re-opening each CSV.

| Extract | dbt model | Grain | Mart rows | CSV rows | Null keys | Duplicate grains |
|---|---|---|---|---:|---:|---:|
| `fct_estate_margin_daily__region_date.csv` | `fct_estate_margin_daily` | `region_key`, `operation_date` | 480 | 480 | 0 | 0 |
| `fct_commodity_price_daily__price_date.csv` | `fct_commodity_price_daily` | `price_date` | 209 | 209 | 0 | 0 |
| `forecast_cpo_30day__forecast_date.csv` | `forecast_cpo_30day` | `forecast_date` | 30 | 30 | 0 | 0 |
| `rec_anomaly_flags__region_date.csv` | `rec_anomaly_flags` | `region_key`, `operation_date` | 240 | 240 | 0 | 0 |
| `whatif_margin_shocks__region_scenario.csv` | `whatif_margin_shocks` | `region_key`, `scenario` | 36 | 36 | 0 | 0 |
| `dim_region__region_key.csv` | `dim_region` | `region_key` | 4 | 4 | 0 | 0 |

## fct_estate_margin_daily__region_date.csv

Model: `models/marts/fct_estate_margin_daily.sql`.

Grain: one row per estate per operations day. 2026-03-03 through 2026-06-30. 4 estates × 120 dates = 480. March has 29 dates (starts 3 March) for every estate.

`margin_idr_per_ha` is already per hectare per day. A month's margin per hectare is the sum of the daily values, not the average. Non-harvest days contribute the fertilizer cost as a negative. Summing across estates without dividing by hectares double-counts area; the column is already per hectare.

| Column | Unit | Notes |
|---|---|---|
| `operations_key` | surrogate id | Not a chart key. |
| `region_key` | estate id | `central_kalimantan`, `lampung`, `north_sumatra`, `riau`. |
| `operation_date` | date, WIB weather day | No time component. |
| `is_effective_harvest_day` | boolean | Harvest weather, and not a weekend, and not an Indonesian public holiday. |
| `cpo_idr_per_tonne` | IDR / tonne CPO | Forward-filled daily local price. |
| `planted_hectares` | ha | Seeded estate area. Constant per estate. |
| `yield_t_ha` | t/ha | Seeded FFB yield. Constant per estate. |
| `fertilizer_cost_idr_per_ha` | IDR / ha / day | From `cost_assumptions`. Charged every day. |
| `harvest_cost_idr_per_ha` | IDR / ha | Charged in the harvest-day branch of the model. |
| `transport_cost_idr_per_tonne` | IDR / tonne CPO | Input rate, not the day's transport bill. |
| `extraction_rate` | fraction of FFB | 0.22 except Central Kalimantan 0.21. |
| `revenue_idr_per_ha` | IDR / ha / day | 0 when it is not an effective harvest day. |
| `transport_cost_idr_per_ha` | IDR / ha / day | 0 on non-harvest days. |
| `margin_idr_per_ha` | IDR / ha / day | Revenue minus fertilizer, harvest, and transport. Negative fertilizer cost on non-harvest days. |
| `margin_total_idr` | IDR / day | `margin_idr_per_ha * planted_hectares`. Do not use this to rank estates on the per-hectare view. |

Period sum of `margin_idr_per_ha` (same 120 days, so the comparison is fair): Lampung 5,360,560,128; Riau 4,804,958,853; North Sumatra 3,898,222,057; Central Kalimantan 1,781,136,087. Harvest days: 64, 54, 48, 26.

## fct_commodity_price_daily__price_date.csv

Model: `models/marts/fct_commodity_price_daily.sql`. Contract-enforced.

Grain: one row per `price_date`. 2026-03-03 through 2026-09-27. 209 rows.

| Column | Unit | Notes |
|---|---|---|
| `price_date` | date | Calendar date. Not a WIB timestamp. |
| `palm_oil_usd` | USD / tonne | Pink Sheet palm oil, forward-filled from the month. Constant inside a month. |
| `soybean_oil_usd` | USD / tonne | Pink Sheet soybean oil, same fill. |
| `palm_soy_spread_usd` | USD / tonne | Palm minus soy. Negative means palm is cheaper. |
| `usd_idr` | IDR per 1 USD | Frankfurter rate, ASOF forward-filled. Varies inside March–June. Constant 17,903 from 2026-07-01 through 2026-09-27. |
| `palm_oil_idr` | IDR / tonne | `round(palm_oil_usd * usd_idr, 0)`. |

Monthly levels (min = max inside the month):

| Month | Days | Palm USD/t | Soy USD/t | Spread USD/t | Discount vs soy |
|---|---:|---:|---:|---:|---:|
| 2026-03 | 29 | 1,109 | 1,493 | −384 | −25.7% |
| 2026-04 | 30 | 1,146 | 1,643 | −497 | −30.2% |
| 2026-05 | 31 | 1,136 | 1,781 | −645 | −36.2% |
| 2026-06 | 30 | 1,104 | 1,740 | −636 | −36.6% |
| 2026-07 | 31 | 1,104 | 1,740 | −636 | −36.6% |
| 2026-08 | 31 | 1,104 | 1,740 | −636 | −36.6% |
| 2026-09 | 27 | 1,104 | 1,740 | −636 | −36.6% |

Discount vs soy is `palm_soy_spread_usd / soybean_oil_usd`, not a stored column. March −384/1,493 = −25.7%. June −636/1,740 = −36.6%. The USD spread is widest in May (−645). The percent of soy is widest from June onward (−36.6%). Do not collapse those two statements.

FX range on the file: 16,855 to 18,151 IDR per USD. Local palm price range: 18,692,195 to 20,278,736 IDR/t.

## forecast_cpo_30day__forecast_date.csv

Model: `models/marts/forecast_cpo_30day.sql`. Not used by a worksheet.

Grain: one row per `forecast_date`. 30 rows, horizon 1..30, 2026-09-28 through 2026-10-27.

| Column | Unit | Observed on this extract |
|---|---|---|
| `forecast_date` | date | Day after the last actual price date (2026-09-27). |
| `horizon_days` | days ahead | 1 through 30. |
| `forecast_palm_usd` | USD / tonne | 1,104.00 on every row. |
| `band_half_width_usd` | USD / tonne | 0.00 on every row. |
| `lower_usd` | USD / tonne | 1,104.00 on every row. |
| `upper_usd` | USD / tonne | 1,104.00 on every row. |

Overlap with actual `price_date`: 0. There is no forecast error to plot.

## rec_anomaly_flags__region_date.csv

Model: `models/marts/rec_anomaly_flags.sql`.

Grain: one row per estate per day for the last 60 operations days. 2026-05-02 through 2026-06-30. 4 × 60 = 240.

| Column | Unit | Notes |
|---|---|---|
| `anomaly_key` | surrogate id | Not a chart key. |
| `region_key` | estate id | |
| `operation_date` | date | Same WIB weather day as the margin mart. |
| `rain_14d_mm` | mm / 14 days | |
| `deficit_14d_mm` | mm / day, 14-day mean | Positive means a deficit. |
| `is_rainfall_deficit` | boolean | Estate-specific. True only for Riau on 2026-05-02 and 2026-05-03. |
| `palm_mom_pct` | percent, already × 100 | Month-on-month palm USD change. Same value on every estate for a given day. Not a fraction. |
| `is_price_spike` | boolean | Market-wide on this extract. True for all four estates on the same six May dates (15, 18, 19, 26, 27, 28). `palm_mom_pct` on those days is −0.87, so the flag is the IDR trailing-high breach, not a monthly spike. |

On 2026-06-30 every estate has both flags false. Nothing is open on the as-of day.

## whatif_margin_shocks__region_scenario.csv

Model: `models/marts/whatif_margin_shocks.sql`.

Grain: one row per estate per scenario. 4 × 9 = 36. No date column.

The base price is the latest commodity row, not the latest operations day and not "yesterday". That row is 2026-09-27: palm 1,104 USD/t, FX 17,903 IDR per USD, local price 19,764,912 IDR/t. Agronomy is held at a harvest day. This will not match the March–June operations ranking.

| Column | Unit | Notes |
|---|---|---|
| `whatif_key` | surrogate id | |
| `region_key` | estate id | |
| `scenario` | label | `palm_-20pct`, `palm_-10pct`, `base`, `palm_+10pct`, `palm_+20pct`, `idr_-10pct`, `idr_+10pct`, `palm+10_fx+10`, `palm-10_fx-10`. |
| `palm_mult` | factor | DECIMAL, written as `0.80` … `1.20`. |
| `fx_mult` | factor | `0.90`, `1.00`, or `1.10`. |
| `shocked_palm_usd` | USD / tonne | |
| `shocked_usd_idr` | IDR per 1 USD | |
| `shocked_cpo_idr` | IDR / tonne | Product of shocked palm and shocked FX. |
| `shocked_margin_idr_per_ha` | IDR / ha | One harvest day. Not a month sum. |

Price-only rows (`fx_mult = 1`) at base and at −20%:

| Estate | Base IDR/ha | −20% palm IDR/ha | Gap |
|---|---:|---:|---:|
| Riau | 91,332,184 | 72,634,577 | −18,697,607 (−20.5%) |
| Lampung | 85,325,985 | 67,845,897 | −17,480,088 (−20.5%) |
| North Sumatra | 84,072,557 | 66,853,365 | −17,219,192 (−20.5%) |
| Central Kalimantan | 73,379,084 | 58,270,785 | −15,108,299 (−20.6%) |

Order is the same at −20, −10, 0, +10, and +20: Riau, Lampung, North Sumatra, Central Kalimantan. `palm_+10pct` and `idr_+10pct` print the same `shocked_cpo_idr` (21,741,403) and the same margin, because revenue is the product. The parameter in the build spec moves only the palm factor.

## dim_region__region_key.csv

Model: `models/marts/dim_region.sql`.

Grain: one row per estate. 4 rows.

| Column | Unit | Notes |
|---|---|---|
| `region_key` | estate id | Relationship key. |
| `region_name` | label | Central Kalimantan, Lampung, North Sumatra, Riau. Use this on axes, not the key. |
| `island` | label | Sumatra or Kalimantan. |
| `latitude` | degrees | |
| `longitude` | degrees | |
| `planted_hectares` | ha | Riau 12,500; North Sumatra 9,800; Central Kalimantan 15,200; Lampung 7,400. |
| `yield_t_ha` | t/ha | Riau 21.5; North Sumatra 19.8; Central Kalimantan 18.2; Lampung 20.1. |
| `estate_manager` | name | Andi Pratama, Sri Wahyuni, Budi Santoso, Dewi Lestari. |

Relate this to the margin extract and the what-if extract on `region_key`. Do not physically join it to the anomaly extract on date.
