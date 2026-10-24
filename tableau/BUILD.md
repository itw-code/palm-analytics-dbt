# Build spec — Palm estate margin

Workbook name, when Tableau Desktop is available: `Palm estate margin`. This environment does not have Tableau Desktop or `tableauhyperapi`. Do not invent a `.twbx`. The sheets below are the rebuild contract.

Connect to the CSVs in `tableau/export/`. Text file properties: comma, first row is names, UTF-8. Date columns are `YYYY-MM-DD`. Do not let Tableau treat `palm_mom_pct` as a fraction; it is already in percent points.

## Data model

Two data sources. Do not physically join the facts.

**Estate margin.** `fct_estate_margin_daily__region_date.csv` related to `dim_region__region_key.csv` on `region_key`. Cardinality many-to-one. This is the primary source for sheets 1 and 3.

**Commodity.** `fct_commodity_price_daily__price_date.csv` alone. Sheet 2.

**Anomaly flags.** `rec_anomaly_flags__region_date.csv` is a second connection, blended into sheet 3 only. Data > Edit Relationships (blend) > Custom. Linking field: `region_key` only. If Tableau adds `operation_date`, remove it. A date link would be wrong: the flag window is 60 days and the margin window is 120.

**What-if.** `whatif_margin_shocks__region_scenario.csv` related to `dim_region__region_key.csv` on `region_key`, many-to-one. Separate data source from Estate margin. Do not filter it from the ranking sheet. The price date is 2026-09-27; the operations window ends 2026-06-30.

Do not connect `forecast_cpo_30day__forecast_date.csv` to a worksheet. See the rejection under sheet 2.

## Colour

Assign colours by hand. Edit Colors, select the item, custom colour. Same hex on every sheet that encodes estate. Sort the legend alphabetically by `region_name`.

| `region_name` | Hex | RGB |
|---|---|---|
| Central Kalimantan | `#7A5F28` | 122, 95, 40 |
| Lampung | `#8C4A6B` | 140, 74, 107 |
| North Sumatra | `#3F6B52` | 63, 107, 82 |
| Riau | `#1F7A80` | 31, 122, 128 |

Not an estate colour:

| Use | Hex | RGB |
|---|---|---|
| Four-estate average line | `#5C6570` | 92, 101, 112 |
| Rainfall-flag mark | `#C2410C` | 194, 65, 12 |

Do not recolour Riau's bar to the flag colour. That would make Riau teal on the trend and amber on the ranking. The flag is a mark on top of the estate colour.

Fonts: Tableau Book for axis titles, Tableau Bold for the sheet title. Title 14 pt. Subtitle 10 pt, colour `#5C6570`. Background left at the Tableau default.

## Sheet 1 — Margin trend

Title: `Central Kalimantan is last on margin per hectare in every month; there is no plan to judge drift against`

Subtitle: `Sum of daily margin per hectare, 3 Mar–30 Jun 2026. March has 29 days because the extract starts 3 Mar; every estate has those same 29 days. The dashed line is the four-estate average, not a plan.`

Chart: line. Continuous month on Columns. Estate on Colour.

Calculated fields, data source Estate margin:

```text
Month start = DATETRUNC('month', [operation_date])

Monthly margin per ha = SUM([margin_idr_per_ha])

Four-estate average =
    { FIXED [Month start] : SUM([margin_idr_per_ha]) }
    / { FIXED [Month start] : COUNTD([region_key]) }
```

`Monthly margin per ha` is the required calculated field. Do not plot raw `margin_idr_per_ha` at day grain and call it a month.

Marks:

- Columns: `Month start` (month, continuous). Four ticks: Mar, Apr, May, Jun 2026.
- Rows: `Monthly margin per ha`, coloured by `region_name`.
- Dual axis, synchronized: `Four-estate average`. Mark type line, dashed, colour `#5C6570`, not in the estate legend. Hide the right axis title after synchronizing.

Format `Monthly margin per ha` and `Four-estate average` as `#,##0.00,,,"bn IDR/ha"`. Three trailing commas divide by 1,000 three times (billions). Axis title: `Monthly margin per hectare`. June Lampung must read 1.78, not 1,784,241,115 and not 1.78 million.

Do not add a reference line labelled Plan, Budget, or Target. No column supports it.

Caption under the sheet, 9 pt: `Central Kalimantan is last in all four months. May is its trough: 0.12 bn IDR/ha and 2 effective harvest days. June recovers to 0.72 and is still last. North Sumatra also breaks in May (0.41, 5 harvest days) and recovers.`

## Sheet 2 — Price vs the requested forecast

Do not build "actual daily price against the 30-day forecast band".

Measured rejection, from `forecast_cpo_30day__forecast_date.csv` after the same `dbt build`:

- 30 rows, all `forecast_palm_usd` 1104.00, all `band_half_width_usd` 0.00, so `lower_usd` equals `upper_usd`.
- Forecast dates 2026-09-28 to 2026-10-27.
- 0 dates also present in `fct_commodity_price_daily`.

A zero-width band drawn after the last actual is not a forecast-error chart. Building it would show a flat line and invite a false error reading. The extract stays in `tableau/export/` so this can be re-checked. It is not on the dashboard.

Replacement sheet, still a price view, from `fct_commodity_price_daily__price_date.csv`.

Title: `Palm's discount to soybean oil widened from 25.7% in March to 36.6% by June, then froze`

Subtitle: `Discount = (palm − soy) / soy. The USD spread was widest in May at −645 USD/t; the percent of soy was widest from June at −36.6%. July–September repeats the June print. It is not a new market, and it is not the 30-day forecast.`

Calculated fields, data source Commodity:

```text
Palm discount to soy % = [palm_soy_spread_usd] / [soybean_oil_usd]

March discount % =
    { FIXED : MIN(
        IF DATETRUNC('month', [price_date]) = DATE('2026-03-01')
        THEN [Palm discount to soy %]
        END
    ) }
```

Chart: line. `price_date` continuous day on Columns. `Palm discount to soy %` on Rows. Mark type line. One colour, `#1F7A80`. This series is not an estate, so it does not take an estate colour from the legend.

Format `Palm discount to soy %` as `0.0%`. Axis title: `Palm discount to soybean oil`. The March mark must read −25.7%. The June-onward flat must read −36.6%.

Reference line: value from `March discount %`, scope entire table, label `March discount`, colour `#5C6570`, no arrow. Do not label it Plan.

Tooltip, in this order: `price_date`; `Palm discount to soy %`; `palm_soy_spread_usd` formatted `$#,##0.00"/t"`; `palm_oil_usd` and `soybean_oil_usd` formatted `$#,##0.00"/t"`; `palm_oil_idr` formatted `#,##0" IDR/t"`.

Do not add a band. The only band in the warehouse has width 0 and no overlapping actual.

## Sheet 3 — Estate ranking

Title: `Lampung leads period margin per hectare; only Riau has an estate-specific flag, and it is closed`

Subtitle: `Bars are the 3 Mar–30 Jun sum of daily margin per hectare, same 120 days for every estate. Colour is the estate. The amber mark is a rainfall-deficit flag. Price-spike fired for all four estates on the same six May dates, so it is not an estate exception. Both flags are false on 30 Jun.`

Calculated fields:

On the Anomaly flags connection:

```text
Deficit day = IF [is_rainfall_deficit] THEN 1 ELSE 0 END
```

On Estate margin, after the blend link is region_key only:

```text
Period margin per ha = SUM([margin_idr_per_ha])

Rainfall deficit days = SUM([Deficit day])

Has rainfall flag = SUM([Deficit day]) > 0
```

`Period margin per ha` is the required calculated field. Format `#,##0.00,,,"bn IDR/ha"`. Lampung must read 5.36. Central Kalimantan must read 1.78.

Marks:

- Columns: `Period margin per ha`.
- Rows: `region_name`, sorted descending by `Period margin per ha`.
- Colour: `region_name`, palette above.
- Shape shelf, from the blend: a circle when `Has rainfall flag` is true, nothing when false. Colour of that shape `#C2410C`. Place it at the end of the bar (dual axis of a copy of the measure, or a label). The circle is the exception callout. Do not change the bar colour.
- Label the bar with `Period margin per ha` and, for Riau only, the text `2 deficit days, 2–3 May`.

Do not colour by `is_price_spike`. On this extract that flag is 6 days for every estate.

Show `estate_manager` in the tooltip, not on the axis. Four names fit a tooltip; they clutter a ranked bar.

## Sheet 4 — What-if shock

Two worksheets plus a parameter. The parameter is the driver. A filter on `scenario` is not a substitute.

Parameter, workbook scope:

| Setting | Value |
|---|---|
| Name | `Price shock %` |
| Data type | Integer |
| Allowable values | List: −20, −10, 0, 10, 20 |
| Current value | 0 |
| Display format | `0"%"` |

Calculated fields, data source What-if:

```text
Shock pct = ([palm_mult] - 1) * 100

Is price-only shock = [fx_mult] = 1

Is selected shock =
    [fx_mult] = 1
    AND [palm_mult] = 1 + [Price shock %] / 100

Base margin per ha =
    { FIXED [region_key] :
        MAX(IF [scenario] = 'base' THEN [shocked_margin_idr_per_ha] END)
    }

Selected margin per ha =
    IF [Is selected shock] THEN [shocked_margin_idr_per_ha] END

Margin impact vs base = [Selected margin per ha] - [Base margin per ha]

Margin impact % = [Margin impact vs base] / [Base margin per ha]
```

`Is selected shock` is the parameter calculated field. Do not interpolate between the grid points. The list matches the five `fx_mult = 1` rows.

Format:

- `Selected margin per ha` and `Base margin per ha`: `#,##0.0,,"m IDR/ha"` (two trailing commas = millions). Riau at 0% must read 91.3, not 91.3 billion.
- `Margin impact %`: `+0.0%;-0.0%;0.0%`.
- `Margin impact vs base`: `+#,##0.0,,"m IDR/ha";-#,##0.0,,"m IDR/ha";0`.

### Sheet 4a — Shock ladder

This sheet exists to drive the parameter action. It is not a finding chart.

- Filter to `Is price-only shock`.
- Rows: `Shock pct`, discrete, sorted −20 to 20.
- Columns: `AVG([shocked_margin_idr_per_ha])` across the four estates, only so the mark is clickable. Format millions as above. Axis title: `Average harvest-day margin`.
- Colour: one neutral, `#5C6570`. Do not colour this sheet by estate.
- Label: `Shock pct`.
- Title of this helper sheet: `Set the palm-price shock`. Hide it from the dashboard title area if it collides; the dashboard title carries the finding.

### Sheet 4b — Harvest-day margin at the selected shock

Title: `On a harvest day Riau clears the most per hectare at every palm-price shock; Central Kalimantan stays last`

Subtitle: `Weather is held fixed. Base price is the 27 Sep 2026 print, 1,104 USD/t at 17,903 IDR per USD, not the 30 Jun operations close. At −20% the Riau gap to its own base is 18.7 million IDR/ha, which is −20.5% of margin, not −20%, because costs do not scale. A +10% palm shock and a +10% FX shock print the same IDR margin on this grid; this parameter does not move FX.`

The title stays true at every allowable parameter value. The −20% sentence is in the subtitle because that comparison is against base, which the impact label also shows.

Marks:

- Filter: `Is selected shock` is true. This filter follows the parameter. It is not a scenario dropdown.
- Columns: `Selected margin per ha`.
- Rows: `region_name`, sorted descending by `Selected margin per ha`.
- Colour: `region_name`, same hex as sheet 1.
- Label: `Selected margin per ha` and `Margin impact %`.
- Tooltip: `estate_manager`, `shocked_cpo_idr` formatted `#,##0" IDR/t"`, `Margin impact vs base`.

At current value 0 the impact label is 0.0% on every bar. After a click on −20 the Riau label is −20.5% and the bar reads 72.6.

### Parameter action

Dashboard > Actions > Add Action > Change Parameter.

| Setting | Value |
|---|---|
| Name | `Set palm-price shock` |
| Source sheet | Shock ladder |
| Run action on | Select |
| Target parameter | `Price shock %` |
| Field | `Shock pct` |
| Aggregation | None, or AVG if Tableau requires an aggregation. Every row in a shock bin has the same `Shock pct`. |
| Clearing the selection | Keep current value |

Do not set the parameter from the ranking sheet. Do not add a filter action that filters `scenario` as the way to "change the shock". The calculated field `Is selected shock` is what moves sheet 4b.

## Dashboard — Where margin is drifting

Single dashboard. Size 1200 × 800, tiled, margin 8.

| Tile | Content |
|---|---|
| Top, height 72 | Dashboard title `Where margin is drifting, March–June 2026` and one line: `Click an estate to filter the trend. The average line is not a plan.` |
| Left, width 460 | Sheet 3, Estate ranking |
| Right | Sheet 1, Margin trend |

Filter action:

| Setting | Value |
|---|---|
| Name | `Filter trend to selected estate` |
| Source | Estate ranking |
| Target | Margin trend |
| Run on | Select |
| Clearing the selection | Show all values |
| Filter | `region_key` only |

Do not target sheet 2 or sheet 4. Sheet 2 has no estate. Sheet 4 is a different date basis; filtering it from a June ranking would imply the September price shock is a June result.

Sheet 2 and sheet 4 are in the workbook, not on this dashboard. Sheet 4a and 4b go on a second dashboard, `Harvest-day price shock`, 1000 × 640, tiled: ladder on the left (width 280), sheet 4b on the right, parameter control `Price shock %` in the top strip so the value is visible before the first click. Dashboard title: `Harvest-day margin under a palm-price shock`. Repeat the subtitle's date warning in a text object. No filter action on this dashboard. The parameter action above is the interaction.

## Checks after the workbook exists

These cannot be run here. They are the acceptance checks for the human build.

1. Sheet 1 has four lines and one dashed average. No plan line. June Central Kalimantan is the lowest June point and reads 0.72 bn IDR/ha.
2. Sheet 2's line is −25.7% in March and flat at −36.6% from June through 27 Sep. No band, no forecast extract.
3. Sheet 3 sort is Lampung, Riau, North Sumatra, Central Kalimantan. Only Riau has the amber mark. Bar colours match sheet 1.
4. Sheet 4 at −20% shows Riau 72.6 m IDR/ha and −20.5%. Estate colours match sheet 1. FX scenarios are not in the ladder.
5. Clicking Lampung on the ranking leaves only the Lampung line on the trend. Clearing the selection restores four lines.
6. Clicking −20 on the ladder changes sheet 4b without a scenario filter being touched.
