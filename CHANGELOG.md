# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- dbt model `aircraft_rotation`: every flown leg of an aircraft on the days it touches ORD (national, 10.6 M legs), in the order the aircraft flew them. Each leg links to the previous one (including the previous evening) and carries scheduled and actual ground times and station continuity. Tests check the chain's coherence and the link to `flight_leg`.
- Ephemeral dbt model `int_bts_legs`: the national BTS union, flight key and tail cleaning shared by `flight_leg` and `aircraft_rotation`.
- First EDA notebook (`notebooks/01_ord_delays_overview.ipynb`) on the core tables. It covers coverage changes, the yearly trend, season × hour of day, ORD weather, FAA programs, inbound-aircraft delay and carriers, with a table beside every chart.
- Chart theme (`ordfi.viz`): the validated categorical and sequential palette, a light matplotlib style, and title and axis helpers.
- dbt project (`dbt/`, dbt Core v1 + dbt-duckdb, ADR-0002): stage sources and five core models, written as Parquet to `data/core`:
  - `calendar`: federal holidays (actual and observed), holiday distances, America/Chicago DST.
  - `flight_leg`: ORD departures and arrivals, marketing-carrier file from 2018 and reporting-carrier file before.
  - `weather_obs` and `weather_obs_hourly`: ceiling, flight category and present-weather flags; latest and worst conditions per hour.
  - `atc_program`: ORD-related GDP and ground-stop advisories, with periods parsed to UTC.
  - dbt tests for keys, values, known holiday and DST dates and period plausibility; a CI test that builds every model on a synthetic stage; `make dbt-build`.
- IEM weather backfill (`ordfi.ingest.iem`) for ORD, monthly from 2000, polite (1 request/s) and resumable:
  - METARs: routine, specials and 5-minute HFMETAR, fetched separately because IEM's CSV has no report-type column.
  - TAFs: IEM's parsed groups, its product overview and the verbatim bulletins.
  - Staged yearly tables for METARs, TAF products and TAF groups. Known IEM TAF faults are flagged (`old_format`, `window_valid`), not silently used.
  - `make ingest-iem`.
- FAA ATCSCC advisory crawler (`ordfi.ingest.atcscc`): daily listings (every advisory) plus full texts of ORD-related advisories; polite (1 request/s), resumable crawl into the raw zone partitioned by advisory date; staged `index` and `advisories` tables with categories and typed program fields; `make ingest-atcscc`. Raw-zone `commit_download` gains `partition` and in-memory `index` options.
- Live collector (`ordfi.collector`): an asyncio service archiving FAA NAS Status (XML and airport events), ORD D-ATIS and CBP T5 wait times.
  - Every content change goes to daily `snapshots.jsonl`; every poll goes to `polls.jsonl`.
  - Change detection ignores volatile fields.
  - PID-file supervision; `make collector-start|status|stop`.
- BTS on-time ingestion (`ordfi.ingest.bts`):
  - conditional monthly downloads into an append-only raw zone with a checksum manifest;
  - typed Parquet staging with UTC event timestamps derived from scheduled times plus BTS minute offsets;
  - quality checks against BTS's own local times;
  - CLI and `make ingest-bts`.
- Time utilities (`ordfi.timeutil`): `hhmm` parsing (incl. `2400`); DST-safe local-to-UTC conversion (scalar and vectorized); airport time zones via `airportsdata`.
- Dagster code location (`pipelines/definitions.py`): monthly-partitioned raw and stage assets for both BTS tables, with asset checks; `make dagster`.
- Tests for time handling (including Hypothesis property tests), the raw zone, HTTP retries and conditional requests, and BTS staging.
- Data-catalog card for `airportsdata`.
- Research and feasibility study v1.0 (`docs/research/`).
- Repository scaffold: `ordfi` package (src layout), tests, CI, pre-commit hooks and Makefile.
- Conda environment (`environment.yml`) and multi-platform lock file (`conda-lock.yml`).
- ADR process (ADR-0001), plus templates for data-catalog cards and model cards.
- ADR-0002 (Parquet + DuckDB + dbt Core v1), ADR-0003 (Dagster OSS for batch; separate live collector) and ADR-0004 (live data providers), accepted in #1.
- Data-catalog cards for 15 Phase 1 sources.

### Fixed

- BTS ingestion, found during the full backfill:
  - CSVs are decoded lossily (a corrupt source row in Aug 2018 failed the month); affected rows are counted as `rows_invalid_text`.
  - Time-zone override for `ISN` (Williston, ND; closed 2019); unresolved airport codes are now reported per month.
  - Airport time zones fall back to airportsdata's FAA location identifiers, which resolves `TKI` (McKinney, TX) and replaces the `DJT` override; every airport code in 2015-01..2026-08 now resolves.
  - Progress lines are flushed, so logs update live.
  - Partial downloads are removed on failure, and stale ones are swept.

### Changed

- `flight_leg` reads from `int_bts_legs`. Tail numbers are upper-cased, and placeholders shorter than 4 characters become null.
- dbt core outputs use zstd compression (about a third smaller).
- Ruff allows the en dash and apostrophe in strings, for chart labels.
- Environment pins dbt Core and dbt-duckdb to the v1 line (`<2`, ADR-0002) and adds `dagster`, `dagster-webserver` and `dagster-dbt` (ADR-0003); `conda-lock.yml` regenerated.
