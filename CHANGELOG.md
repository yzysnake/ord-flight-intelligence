# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- GFS MOS and NBM station guidance for ORD (`ordfi.ingest.mos`, `make ingest-mos`), from IEM's MOS archive, one request per model and month.
  - Coverage: GFS MOS (00, 06, 12 and 18Z runs) from 2014-12, and the NBM short-range bulletin (01, 07, 13 and 19Z cycles) from 2018-11, both 3-hourly to 72 h.
  - dbt models `gfs_mos` and `nbm` decode the ceiling and visibility (MAV categories; NBM feet and miles, unlimited ceilings) into flight categories, beside thunder, precipitation, precipitation-type and IFR probabilities, snow, ice, wind and gusts.
  - Knowledge times follow the catalog cards: the run + 5 h and the cycle + 70 min.
  - NBM's codes changed with its versions (visibility in whole miles before 2020-02-20, an unlimited ceiling 888 before v4.0), found by checking against ORD's METARs. Decoded, NBM's flight categories agree with them 84.6 % of the time at up to 12 h, and GFS MOS's 83.2 %.
  - LAMP is deferred; see its card.
- Alerts and recalibration from the track record (`ordfi.models.recent`).
  - For each test month, the outlook tasks reset their alert threshold on the last 12 months with published outcomes. The threshold is the lowest forecast that flagged at most 10 % of the normal days or hours. The backtest forecasts the 14 months before the first test month for the record, without scoring them.
  - `gbdt_recent` is the GBDT shifted to the record's level. It is scored but not adopted: on the development months every variant lost skill.
  - Results: the evening-before bad-day alert catches 77 % of bad days at 1.19 false alarms per 10 normal days. False alarms held at 9.3 % on the development months, but at 13.7 % in the stormier reported months.
- Daily outlook tasks (`day_bad60`, `day_gdp`, `day_ground_stop`): a bad day, a GDP day and a ground-stop day, scored at the days spine's five issue times.
  - Baselines: a month-by-weekday climatology (the skill reference), persistence of the previous 24 hours and announced programs.
  - Models: the Outlook GBDT on the 67 day features, with 24 held-out months (chosen on the development months) and ablations.
  - Brier skill on Sep 2024 – Aug 2026: 0.354 for bad days the evening before (persistence 0.056), 0.208 the morning before; GDP and ground-stop days 0.249 and 0.266 the evening before.
  - The study's bad-day criterion is met the evening before: 71 % of bad days flagged at 1 false alarm per 10 normal days, and 72 % at 1.05 with a threshold fixed on the development months. It is not met the morning before (55 %).
- Metric `hit_rate`: the share of events flagged at a false-alarm budget of 10 % of non-events, in every backtest's scores.
- Days spine (`make features SPINE=days`): one row per local ORD day, for the daily outlook, issued at fixed local times.
  - Issues: 19:00 three and two days before, 07:00 and 19:00 the day before, and 05:00 on the day, timed around the TAFs that reach the day.
  - Day groups: the TAF summed over the day's hours, programs announced to cover any part of the day, the last 24 hours of operations (the previous day's state), and the day's scheduled demand and busiest hour.
  - Labels: the day's shares of departures late or cancelled, and whether a GDP or ground stop ran.
  - The leakage property test covers the spine, checking every issue of 60 worlds. Real data shows no mismatch in 605 day rows.
- Outlook GBDT (`ordfi.models.gbdt`): a LightGBM classifier per hourly task and horizon, on all 59 features of the hours spine.
  - Fitting: the last 12 training months, after a one-day embargo, pick the number of trees by early stopping; the trees are then refit on the whole window, and a Platt recalibration fitted on the held-out months sets the level.
  - Settings were frozen on development months (Sep 2022 – Aug 2024) before the reported run.
  - Brier skill on Sep 2024 – Aug 2026 is 0.249 at 24 h and 0.431 at 6 h for bad hours (the best baseline scores 0.030 and 0.015), 0.141 and 0.292 for GDP hours, and 0.089 and 0.146 for ground-stop hours. Calibration error is at most 0.012.
  - The run also scores a schedule-only GBDT and ablations without the TAF, the FAA programs or the in-day operations (see `docs/backtests/`).
  - Model card: `docs/model-cards/outlook-gbdt.md`.
- Backtest harness (`ordfi.models.backtest`, `make backtest`). It uses rolling monthly origins, and each fold trains only on months BTS had published (up to M − 3), with the COVID months left out.
  - Scores: Brier skill against the calendar climatology, with intervals from resampling whole days; log loss; ROC and PR AUC; calibration (ECE, slope and intercept) with reliability bins.
  - Results are split by season, program days, storm days, the FAA cap and month.
- Climatology baselines (`ordfi.models.baselines`): base rate, calendar, route, persistence, slack rule and announced programs. They cover six tasks: departures 15+ or 60+ min late, cancellations, bad hours, and GDP and ground-stop hours (see `docs/backtests/`).
- As-of feature builder (`ordfi.features`, `make features`): point-in-time snapshots for every scheduled ORD departure and every hour at the 24 h, 6 h, 3 h, 1 h and 15 min horizons, 2015 →.
  - Feature groups: calendar, METAR, TAF, ATC programs, recent ORD operations, scheduled demand, and the flight and its inbound aircraft. Labels are kept separate.
  - Knowledge-time rules live in one module, with a `visible(tables, as_of)` view.
  - A property test checks that no feature changes when unknown inputs are removed, and it catches injected leaks. The same check on real months finds no mismatch (see `docs/features/`).
- dbt models `atc_program_interval` and `atc_program_interval_version`: ORD's GDP and ground-stop advisories chained into 5,333 programs (2001 →). Each has its start, its end after revisions and cancellations, how it ended and its scope (general, carrier-only, CAT I/II). Versions give each program as known after each advisory, for point-in-time use. Validated against flights to ORD (see the ATCSCC card).
- TAF bulletin parser (`ordfi.ingest.taf`), run by `make ingest-iem`. It reads the verbatim bulletins in current and pre-2008 formats into `bulletins` and `periods` stage tables. It repairs IEM's misdated or missing windows and covers TAFs missing from IEM's tables. Validated against IEM and against observed weather (see the `iem_taf` card).
- dbt model `taf_hourly`: every ORD TAF expanded to hourly prevailing forecasts and TEMPO/PROB overlays, with flight categories, 2000 →.
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

- ATCSCC advisories, found while chaining ORD's programs:
  - Ground stops issued during a GDP took the GDP's cumulative period (1,468 advisories, 2006 →); their own `GROUND STOP PERIOD` now comes first.
  - Informal ground stops' `EVENT TIME` (2016 →) and old ones' `EXPECT UPDATE` are read as periods, as are dated periods without the end's day or with an `@` left over. 98.8 % of ORD ground-stop advisories now have a period (93.6 % before).
  - Cancellations titled `CNCL'D`, `CNXL` or `CANCLED` are flagged as cancellations.
- ATCSCC advisories in the older layouts, found during the 2001–2014 backfill:
  - GDP periods before November 2006 are read from `ARRIVALS ESTIMATED FOR`, rates from `PROGRAM AAR` (to May 2004) and the element from `AIRPORT`. For 2001–2006 ORD GDPs, periods rise from 5 % to 95 % and rates from 46 % to 88 %.
  - The `AIRPORT` element corrects the airport of 19 program advisories whose listing names another element (e.g. ORD GDPs listed as `ZAU/ORD`, Toronto programs listed under ORD).
  - `atc_program` leaves implausible periods (a mistyped day such as `142056Z-182230Z`) null rather than reporting a four-day ground stop. Its test now checks that they stay rare.
- BTS ingestion, found during the full backfill:
  - CSVs are decoded lossily (a corrupt source row in Aug 2018 failed the month); affected rows are counted as `rows_invalid_text`.
  - Time-zone override for `ISN` (Williston, ND; closed 2019); unresolved airport codes are now reported per month.
  - Airport time zones fall back to airportsdata's FAA location identifiers, which resolves `TKI` (McKinney, TX) and replaces the `DJT` override; every airport code in 2015-01..2026-08 now resolves.
  - Progress lines are flushed, so logs update live.
  - Partial downloads are removed on failure, and stale ones are swept.

### Changed

- `--horizons` defaults to each task's own horizons or issue times. A requested horizon applies to the tasks whose spine has it.
- The backtest harness runs a subset of models (`--models`, `MODELS=`; the calendar reference always runs). It fits test months in parallel worker processes (`--workers`, `WORKERS=`): one per CPU for the hourly tasks by default, one process for the departure tasks. Processes, not threads, because LightGBM boosters trained in concurrent threads corrupt memory.
- mypy skips scikit-learn imports, which ship no type information.
- Flight-category logic is a shared dbt macro, used by `weather_obs`, `weather_obs_hourly` and `taf_hourly`.
- `flight_leg` reads from `int_bts_legs`. Tail numbers are upper-cased, and placeholders shorter than 4 characters become null.
- dbt core outputs use zstd compression (about a third smaller).
- Ruff allows the en dash and apostrophe in strings, for chart labels.
- Environment pins dbt Core and dbt-duckdb to the v1 line (`<2`, ADR-0002) and adds `dagster`, `dagster-webserver` and `dagster-dbt` (ADR-0003); `conda-lock.yml` regenerated.
