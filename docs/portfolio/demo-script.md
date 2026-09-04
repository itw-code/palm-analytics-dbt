# Demo script — palm-analytics-dbt (≈2 minutes)

> Audience: hiring manager / technical reviewer. Pace: unhurried. Total: ~120s.
> Setup: live dashboard open on Overview; `/status` in a second tab; repo open
> in a third. GIF version: same beats without narration (see capture notes in
> `docs/portfolio/README-v2-PROPOSAL.md`).

## 0:00–0:20 — Hook (Overview)

> "This is palm-analytics-dbt: an end-to-end analytics-engineering project on
> Indonesian palm-oil estates. It answers one question: *given today's weather
> and the palm-oil price, which field operations are favorable in each region —
> and what is a good harvest day worth?* Four free public sources feed it, and
> everything refreshes daily."

Show: Overview page, region switcher.

## 0:20–0:50 — Planner (Forecast)

> "The 7-day planner is the decision surface. Weather forecast flows through
> shared agronomy rules — the same macro that scores history — so history and
> forecast can never disagree. Green days are go for fertilize, harvest, spray;
> labour availability already accounts for weekends and Indonesian holidays."

Show: `/forecast`, mixed favorable/unfavorable days, region change.

## 0:50–1:20 — Money (Market / Margin)

> "Prices arrive monthly in dollars, so the pipeline forward-fills them to
> daily grain with ASOF joins and converts at the daily reference rate. The
> margin mart then prices each favorable harvest day per hectare — that's the
> 'what is a good day worth' number."

Show: `/market` price curve, `/margin` per-ha table.

## 1:20–1:50 — Trust (Status + repo)

> "And it's observable: the status page shows last refresh, lake snapshot,
> test counts, and per-source freshness — machine-readable too. Underneath:
> 92 passing dbt checks including mutation-verified unit tests, contracts, and
> an SCD2 price snapshot — all green on a daily cron."

Show: `/status` page, `status.json`, repo Actions green runs (or README badges).

## 1:50–2:00 — Close

> "Zero infrastructure — DuckDB, DuckLake, dbt, Evidence, GitHub Actions — and
> a cold bootstrap reproduces everything. Links and the full case study are in
> the repo."

## If asked…

- *"Is the price data real?"* — "Weather, FX, and holidays are live; commodity
  is a documented synthetic fixture in CI so builds are deterministic — the
  trade-off is written up in the case study."
- *"What would you add with funding?"* — "Live price feed, forecast accuracy
  backtest, and the 06:00 WhatsApp digest — details in the case study."
