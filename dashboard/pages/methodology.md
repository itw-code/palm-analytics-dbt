---
title: Cara Kerja & Alur Data
description: Gimana pipa datanya jalan — sumber, lapisan dbt, metrik, dan cara nambah kebun sendiri.
---

{@partial "lang_toggle.md"}

{#if inputs.lang.value == 'en'}

This dashboard is the serving layer of an end-to-end analytics-engineering pipeline. It is deliberately built with the industry-standard toolchain to demonstrate the full workflow, not just charts.

## Data sources (all free)

| Source | What it provides | Auth |
|---|---|---|
| Open-Meteo Archive | historical daily weather per region - temperature, precipitation, wind, soil moisture, ET0, humidity | keyless |
| Open-Meteo Forecast / Historical-Forecast | **7-day forward forecast** per region (same variables) | keyless |
| Frankfurter (ECB) | USD → IDR daily reference rate | keyless |
| Nager.Date | Indonesia public-holiday calendar | keyless |
| World Bank Pink Sheet | monthly palm-oil & soybean-oil prices | keyless |

All ingestion attempts a live fetch with retries and falls back to deterministic synthetic data, so the pipeline and its CI are always reproducible offline. **In production the fallback is never silent:** `ingestion/load_raw.py` writes `ingestion_manifest.json` with per-source provenance (`live` vs `synthetic`) and the scheduled GitHub Actions job surfaces any synthetic fallback as a warning in the workflow summary. Pass `--require-live` to fail-fast instead.

## Transformation layers (dbt)

- **raw layer (DuckLake)** — API payloads land in a DuckLake catalog (`palm_lake/`): open parquet files with ACID snapshot metadata. Each daily load commits as one immutable snapshot.
- **staging** (`stg_*`) — one cleaned, typed model per source
- **intermediate** (`int_*`) — reusable business logic: a date spine, forward-filled daily FX and commodity prices (DuckDB ASOF joins), and the agronomy rules via a shared `agronomy_signals` macro
- **forecast mart** (`fct_estate_forecast_7day`) — prescriptive 7-day planner per region (H+1..7) with carried-forward prices
- **semantic layer** — canonical metric definitions (`_marts__semantic.yml`) compiled by `semantic/compile_metrics.py` into the governed `sl_metrics_daily` view
- **marts** — a Kimball star: `dim_date` (weekend + holiday flags), `dim_region`, `fct_estate_operations_daily` (incremental), `fct_commodity_price_daily` (contract-enforced)

## Engineering practices demonstrated

- 4 heterogeneous sources with **source freshness** checks
- **DuckLake lakehouse raw layer** feeding a DuckDB warehouse
- Layered modelling (staging → intermediate → marts) with **seeds**
- **Incremental** materialization and an **SCD2 snapshot** on commodity prices
- **Model contract** on the commodity mart
- Data quality: `not_null`, `unique`, `relationships`, `accepted_values`, `accepted_range`, custom `non_negative`, and **dbt unit tests**
- **Exposures** + CI/CD: `dbt build` on every push/PR + **daily 00:00 UTC refresh**

## 7-day forward planner

The [7-Day Forward Planner](/forecast) extends the same agronomy rules into the forecast window (H+1 → H+7). Prices are assumed flat at the latest known value — honest about what is forecast vs known.

## Add your estate (Indonesia only)

Regions are not hardcoded — the estate registry is `seeds/region_profile.csv`. To track your own estate:

1. Add one row to `seeds/region_profile.csv` (`region_key`, `planted_hectares`, `yield_t_ha`, `estate_manager`, `latitude`, `longitude`, `island`) **and** a matching cost row to `seeds/cost_assumptions.csv`. Coordinates are required and must fall inside Indonesia (lat −11…6, lon 95…141).
2. Run `python ingestion/load_raw.py` (reads the registry; `--regions other.csv` or `PALM_REGIONS=other.csv` overrides it) then `dbt build --profiles-dir .`.
3. The build fails loudly if a region lacks a cost row (`assert_margin_covers_all_regions`).

## The decision it supports

*Given today's weather and the palm price (in local currency), which estate operations — fertilize, harvest, spray — are favorable in each region, and what is a good harvest day worth?* An **effective harvest day** additionally requires that labour is available (not a weekend or public holiday).

{:else}

Dasbor ini itu ujungnya pipa data analitik yang utuh. Sengaja dibangun pakai perkakas standar industri biar alurnya kelihatan semua, bukan cuma grafik doang.

## Sumber data (gratis semua)

| Sumber | Isinya apa | Kunci |
|---|---|---|
| Open-Meteo Archive | cuaca harian per kebun — suhu, hujan, angin, lengas tanah, ET0, kelembapan | tanpa kunci |
| Open-Meteo Forecast | **ramalan 7 hari** per kebun (variabel sama) | tanpa kunci |
| Frankfurter (ECB) | kurs acuan harian USD → IDR | tanpa kunci |
| Nager.Date | kalender tanggal merah Indonesia | tanpa kunci |
| World Bank Pink Sheet | harga bulanan sawit & minyak kedelai | tanpa kunci |

Tiap sedot data dicoba live dulu (3x retry), gagal ya pakai data cadangan yang deterministik — jadi pipa dan CI-nya selalu bisa jalan offline. **Yang penting nggak diam-diam:** `ingestion/load_raw.py` nulis `ingestion_manifest.json` per sumber (`live` vs `synthetic`), dan job terjadwal GitHub Actions ngasih warning kalau ada yang cadangan. Mau galak? `--require-live` biar langsung gagal aja.

## Lapisan olahan (dbt)

- **mentah (DuckLake)** — mentahan API mendarat di katalog DuckLake (`palm_lake/`): file parquet + snapshot ACID. Tiap sedotan harian = satu snapshot.
- **staging** (`stg_*`) — satu model bersih per sumber
- **intermediate** (`int_*`) — logika bisnis: tulang tanggal, harga & kurs dimajuin harian (ASOF join), aturan agronomi via macro `agronomy_signals` bareng-bareng
- **mart ramalan** (`fct_estate_forecast_7day`) — perencana 7 hari per kebun (H+1..7), harga dianggap stagnan
- **lapisan semantik** — definisi metrik baku (`_marts__semantic.yml`) dikompilasi jadi view `sl_metrics_daily`
- **mart** — bintang Kimball: `dim_date` (flag weekend + libur), `dim_region`, `fct_estate_operations_daily` (incremental), `fct_commodity_price_daily` (dikontrak)

## Praktik yang dipamerkan

- 4 sumber beda rupa + cek **kesegaran sumber**
- **raw DuckLake** nyuapin warehouse DuckDB
- Modelling berlapis + **seeds**
- Materialisasi **incremental** + **snapshot SCD2** harga
- **Kontrak model**, tes kualitas data, **unit test dbt**
- CI/CD: `dbt build` tiap push/PR + **refresh harian 00:00 UTC**

## Perencana 7 hari

[Perencana 7 Hari](/forecast) pakai aturan agronomi yang sama ke jendela ramalan (H+1 → H+7). Harga dianggap stagnan di angka terakhir — jujur mana yang ramalan mana yang fakta.

## Tambah kebunmu sendiri (khusus Indonesia)

Wilayah nggak di-hardcode — daftarnya di `seeds/region_profile.csv`. Cara nambah kebunmu:

1. Tambah satu baris ke `seeds/region_profile.csv` (`region_key`, `planted_hectares`, `yield_t_ha`, `estate_manager`, `latitude`, `longitude`, `island`) **plus** baris biaya pasangannya di `seeds/cost_assumptions.csv`. Koordinat wajib dan harus di dalam Indonesia (lat −11…6, lon 95…141) — di luar itu ditolak mentah-mentah.
2. Jalanin `python ingestion/load_raw.py` (baca daftar itu; `--regions lain.csv` atau `PALM_REGIONS=lain.csv` buat override) terus `dbt build --profiles-dir .`.
3. Build-nya gagal berisik kalau ada kebun yang belum ada baris biayanya (`assert_margin_covers_all_regions`).

## Keputusan yang dibantu

*Cuaca hari ini + harga sawit rupiah → kebun mana yang gas mupuk, manen, nyemprot, dan sehari panen yang bagus itu cuannya berapa?* **Hari panen efektif** syarat tambahannya: timnya masuk (bukan weekend/tanggal merah).

{/if}

{#if inputs.lang.value == 'en'}

## Automation & observability

- **Schedule:** both workflows run on `push`/`pull_request` and on `schedule: cron '0 0 * * *'` (00:00 UTC) plus `workflow_dispatch`.
- **E2E on schedule:** the Pages workflow does the full pipeline — `pip install` → `dbt deps` → `python ingestion/load_raw.py` → `dbt build` → freshness → `cp palm.duckdb` → `npm run build` → deploy to `gh-pages`.
- **Observability:** every run appends the ingestion manifest and freshness status to the Actions *Summary*; on `schedule` failures a GitHub Issue is opened automatically (deduplicated).

Source: [github.com/itw-code/palm-analytics-dbt](https://github.com/itw-code/palm-analytics-dbt)

{:else}

## Otomatisasi & pantauan

- **Jadwal:** dua workflow jalan tiap `push`/`pull_request`, plus `schedule: cron '0 0 * * *'` (00:00 UTC) dan tombol manual `workflow_dispatch`.
- **E2E terjadwal:** workflow Pages ngerjain semuanya — `pip install` → `dbt deps` → `python ingestion/load_raw.py` → `dbt build` → freshness → `cp palm.duckdb` → `npm run build` → deploy ke `gh-pages`.
- **Pantauan:** tiap jalan, manifest + status kesegaran ditempel ke ringkasan Actions; kalau jadwal gagal, dibikinin Issue otomatis (nggak dobel-dobel).

Sumber: [github.com/itw-code/palm-analytics-dbt](https://github.com/itw-code/palm-analytics-dbt)

{/if}
