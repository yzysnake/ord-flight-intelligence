# Pipelines

Dagster code location (ADR-0003): `definitions.py`.

| Asset | Partitions | What it does |
|---|---|---|
| `bts_ontime_reporting_raw` / `_stage` | monthly from 2015-01 | Conditional download of the BTS reporting-carrier ZIP into the raw zone; typed Parquet with UTC timestamps |
| `bts_ontime_marketing_raw` / `_stage` | monthly from 2018-01 | Same for the marketing-carrier file (primary for ORD; includes non-reporting operators) |

Stage assets run two asset checks: `utc_derivation` (≥ 99.9 % of rows reproduce BTS local times) and `timezones_resolved`.

```bash
make dagster                                   # UI at http://127.0.0.1:3000 (state in .dagster/)
make ingest-bts TABLE=marketing MONTH=2026-08  # same steps without Dagster
```

Live collection (NAS Status, ADS-B, D-ATIS, METAR polling) will run as a separate always-on service that writes raw files only (ADR-0003).
