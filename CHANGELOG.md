# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

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
  - Progress lines are flushed, so logs update live.
  - Partial downloads are removed on failure, and stale ones are swept.

### Changed

- Environment pins dbt Core and dbt-duckdb to the v1 line (`<2`, ADR-0002) and adds `dagster`, `dagster-webserver` and `dagster-dbt` (ADR-0003); `conda-lock.yml` regenerated.
