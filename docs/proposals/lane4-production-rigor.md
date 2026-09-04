# Lane 4 — Production Rigor: proposal (contracts, CI lint, hosted docs)

New files already on disk (verified): `.pre-commit-config.yaml`
(sqlfluff 3.1.0 + dbt-checkpoint v1.2.1 + yamllint + hygiene),
`.sqlfluff` (duckdb dialect, dbt templater), `.yamllint.yml`,
`Dockerfile` (python:3.12-slim, `make repro`), `Makefile`
(setup/ingest/compile/build/freshness/docs/lint/repro/clean),
`.dockerignore`, `.devcontainer/devcontainer.json`.

## Proposal A — contract + version rollout for all marts

Ground truth from the live warehouse (`describe` output): `dim_date.date_key
DATE`, flags `BOOLEAN`; `dim_region.planted_hectares/yield_t_ha DOUBLE`;
`fct_estate_margin_daily` seed-sourced cost columns are `INTEGER`
(`fertilizer_cost_idr_per_ha`, `harvest_cost_idr_per_ha`,
`transport_cost_idr_per_tonne`) while computed money columns are `DOUBLE`.
Contracts must use INTEGER for those three or the build will fail.

Rollout order (one PR per mart, contract first with `enforced: false` to
surface drift, then enforce):

1. `fct_estate_operations_daily` (already has incremental config) — add
   `contract: {enforced: true}` + column `data_type`s matching warehouse.
2. `fct_estate_margin_daily` — INTEGER costs, DOUBLE computed, BOOLEAN flag.
3. `dim_date`, `dim_region` — DATE/BOOLEAN/VARCHAR/DOUBLE per describe.
4. New Lane 2 marts (`rec_harvest_day_ranked`, `whatif_margin_shocks`,
   `forecast_cpo_30day`, `rec_anomaly_flags`) — add contracts at v1.
5. Add `versions: [v: 1]` to each mart yml entry once contracted.

Example (margin, note INTEGER costs):

```yaml
models:
  - name: fct_estate_margin_daily
    config:
      contract: {enforced: true}
    columns:
      - name: operation_date
        data_type: date
      - name: fertilizer_cost_idr_per_ha
        data_type: integer
      - name: margin_idr_per_ha
        data_type: double
```

## Proposal B — CI lint job (add to `.github/workflows/dbt.yml`)

```yaml
lint:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: {python-version: "3.12", cache: pip}
    - run: pip install -r requirements.txt pre-commit
    - run: pre-commit run --show-diff-on-failure --all-files
```

Local: `make setup && make lint`. sqlfluff needs dbt installed in the
pre-commit env (pinned via `additional_dependencies` in the config).

## Proposal C — hosted dbt docs on Pages

`make docs` already emits `target/manifest.json` + `target/catalog.json`.
Append to `pages.yml` after the Evidence build:

```yaml
- run: .venv/Scripts/dbt.exe docs generate --profiles-dir . --target prod
- run: mkdir -p dashboard/build/dbt-docs && cp target/manifest.json target/catalog.json dashboard/build/dbt-docs/
```

Serves lineage at `<pages-url>/dbt-docs/` — or run `dbt docs serve`
locally. No new action needed; same artifact upload path as Evidence.
