---
title: Pantauan & Kesehatan Data
description: Buku pantauan pipa data — kesegaran, hasil tes dbt, snapshot danau data, dan asumsi margin.
---

{@partial "lang_toggle.md"}

{#if inputs.lang.value == 'en'}

How this dashboard is built, tested, and monitored — the trust ledger. Updated on every run.

{:else}

Gimana dasbor ini dibangun, dites, dan dipantau — buku catatannya. Update tiap ada jalan.

{/if}

```sql status
select * from palm.status
```

{#if status[0].freshness_status == 'error'}
{#if inputs.lang.value == 'en'}
<Alert status="negative" title="Source freshness: ERROR">Some raw sources are stale beyond the error threshold. Check the freshness summary below and the Actions tab.</Alert>
{:else}
<Alert status="negative" title="Kesegaran data: ERROR">Ada sumber yang basi kelewat batas. Cek ringkasan di bawah sama tab Actions.</Alert>
{/if}
{:else if status[0].freshness_status == 'warn'}
{#if inputs.lang.value == 'en'}
<Alert status="warning" title="Source freshness: WARN">At least one source is past its warn threshold (expected in CI with the pinned fixture). Live deploys are fresh — see generated_at.</Alert>
{:else}
<Alert status="warning" title="Kesegaran data: WARN">Ada sumber yang lewat batas waspada (wajar di CI; yang live mah seger — lihat generated_at).</Alert>
{/if}
{:else}
{#if inputs.lang.value == 'en'}
<Alert status="info" title="Freshness OK">Raw sources are within their freshness window.</Alert>
{:else}
<Alert status="info" title="Data seger">Semua sumber masih dalam batas wajar.</Alert>
{/if}
{/if}

{#if status[0].synthetic_sources > 0}
{#if inputs.lang.value == 'en'}
<Alert status="warning" title="Synthetic fallback active">`synthetic_sources = {status[0].synthetic_sources}` — at least one API fell back to deterministic synthetic data (see ingestion manifest for which source).</Alert>
{:else}
<Alert status="warning" title="Data cadangan aktif">`synthetic_sources = {status[0].synthetic_sources}` — minimal satu API lagi putus, jadi pakai data cadangan (cek manifest sumber mana).</Alert>
{/if}
{/if}

{#if inputs.lang.value == 'en'}

<Grid cols=3>
  <BigValue data={status} value=dbt_pass title="dbt PASS"/>
  <BigValue data={status} value=dbt_total title="dbt total checks"/>
  <BigValue data={status} value=lake_snapshot_id title="Lake snapshot"/>
</Grid>

| Field | Value |
|---|---|
| Generated at | <Value data={status} column=generated_at/> |
| Warehouse | <Value data={status} column=warehouse/> |
| Ingestion status | <Value data={status} column=ingestion_status/> |
| Synthetic sources | <Value data={status} column=synthetic_sources/> |
| Freshness | <Value data={status} column=freshness_summary/> |
| Row counts (raw) | <Value data={status} column=row_counts_json/> |
| dbt | <Value data={status} column=dbt_pass/> / <Value data={status} column=dbt_total/> PASS (<Value data={status} column=dbt_error/> error, <Value data={status} column=dbt_warn/> warn) |

*Every scheduled run appends this same ledger to the GitHub Actions Summary and, on failure, opens a deduplicated Issue. Lake snapshots are queryable at any past `snapshot_id` via DuckLake time travel.*

## Margin assumptions

The margin mart uses `seeds/cost_assumptions.csv` — fertilizer, harvest and transport costs per region plus extraction rate. Replace those seed values with your estate's actuals and the margin recomputes everywhere. Formula per effective harvest day:

`revenue_per_ha = CPO_IDR_per_tonne * yield_t_ha * extraction_rate`

`margin_per_ha = revenue_per_ha - fertilizer - harvest - transport` ; otherwise `-fertilizer` (you still fertilize even when you don't harvest).

See [7-Day Forecast](/forecast) for prescriptive outlook and [Operations](/operations) for historical planner.

{:else}

<Grid cols=3>
  <BigValue data={status} value=dbt_pass title="Tes LOLOS"/>
  <BigValue data={status} value=dbt_total title="Total tes"/>
  <BigValue data={status} value=lake_snapshot_id title="Snapshot danau"/>
</Grid>

| Kolom | Isi |
|---|---|
| Dibikin jam | <Value data={status} column=generated_at/> |
| Gudang data | <Value data={status} column=warehouse/> |
| Status sedot | <Value data={status} column=ingestion_status/> |
| Sumber cadangan | <Value data={status} column=synthetic_sources/> |
| Kesegaran | <Value data={status} column=freshness_summary/> |
| Jumlah baris (mentah) | <Value data={status} column=row_counts_json/> |
| dbt | <Value data={status} column=dbt_pass/> / <Value data={status} column=dbt_total/> LOLOS (<Value data={status} column=dbt_error/> gagal, <Value data={status} column=dbt_warn/> waspada) |

*Tiap jalan terjadwal, catatan ini ditempel juga ke ringkasan GitHub Actions; kalau gagal, dibikinin Issue otomatis. Snapshot danau bisa ditengok mundur ke `snapshot_id` kapan aja.*

## Asumsi cuan

Margin pakai `seeds/cost_assumptions.csv` — biaya pupuk, panen, angkut per kebun plus rendemen. Ganti angka contoh itu sama angka kebunmu yang asli, margin ngitung ulang semua. Rumus per hari panen efektif:

`masuk_per_ha = CPO_Rp_per_ton * tonase_per_ha * rendemen`

`bersih_per_ha = masuk_per_ha - pupuk - panen - angkut` ; kalau nggak panen ya `-pupuk` (mupuk tetap jalan walau nggak manen).

Lihat [Ramalan 7 Hari](/forecast) buat perintah ke depan dan [Jadwal Operasi](/operations) buat catatan kemarin.

{/if}
