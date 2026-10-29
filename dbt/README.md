# dbt

SQL transformations with **dbt Core v1 + dbt-duckdb** (ADR-0002): stage → core, with tests.

- **Sources** are the stage Parquet files written by `ordfi.ingest` (`models/sources.yml`).
- **Outputs** are external Parquet materializations (zstd) in `$ORDFI_DATA_DIR/core/<model>.parquet`.
- **Warehouse:** `$ORDFI_DATA_DIR/warehouse/ordfi.duckdb` holds views over the outputs. Open it read-only from notebooks, because DuckDB allows a single writer.
- **Sessions run in UTC** (`profiles.yml`), so date casts and hour truncation don't depend on the host's time zone.

```bash
make dbt-build                     # all models and tests (about 10 s on the full data)
make dbt-build SELECT=flight_leg+  # one model and its dependants
```

## Core models

| Model | Grain | Notes |
|---|---|---|
| `calendar` | date, 2000–2030 | Weekdays; US federal holidays (actual and observed); days to/since the nearest holiday; America/Chicago DST |
| `flight_leg` | scheduled ORD departure or arrival | Marketing-carrier file from 2018; reporting-carrier file for 2015–2017 (which misses some carriers). UTC times, `sched_ord_utc`, delays, causes |
| `weather_obs` | ORD METAR (routine + special) | Ceiling, FAA flight category, present-weather flags. Use both report types together |
| `weather_obs_hourly` | UTC hour | Latest and worst conditions per hour; empty hours kept. Use rows with `known_time <= as_of` |
| `atc_program` | ATCSCC program advisory | GDP / ground stop periods parsed to UTC; proposals, cancellations and re-sent listings handled. Filter on `airport` |
| `atc_program_interval` | ORD GDP or ground stop (2001 →) | Advisories chained into programs: start, end after revisions and cancellations, end reason, scope (general, carrier-only, CAT I/II). Final at `known_time` |
| `atc_program_interval_version` | program × advisory | Each program as known after each of its advisories, with the cause that advisory states (`reason`). As of time t: `known_time <= t < valid_to`; in effect if `start_utc <= t < end_utc` |
| `aircraft_rotation` | flown leg of an aircraft on a day it touches ORD (national) | Legs in flown order. Each row links to the previous leg (including the previous evening) and carries scheduled and actual ground times and station continuity. Post-hoc: tails are the aircraft that actually flew |
| `taf_hourly` | ORD TAF × hour of its validity window (2000 →) | Prevailing forecast at the start of the hour plus TEMPO/PROB overlays, from our own bulletin parse (`ordfi.ingest.taf`). Flight categories, including the worst the TAF allows. As of time t: `known_time <= t`, latest issuance per hour |

`int_bts_legs` (ephemeral) is the national BTS union behind `flight_leg` and `aircraft_rotation`. It holds the period rule (marketing file from 2018), the flight key and tail cleaning in one place. `int_atc_program_chain` (ephemeral) assigns each ORD advisory to its program.

Every model carries `known_time` (when its content became available) and `licence_class`. The dbt tests check:
- keys, accepted values and not-nulls;
- known holiday and DST dates (`tests/calendar_known_dates.sql`);
- parsed program periods (`tests/atc_program_periods_are_plausible.sql`);
- that rotations form a physical chain, with ≥ 97 % station continuity and no overlapping flown times (`tests/aircraft_rotation_chain_is_coherent.sql`);
- that every ORD leg in a rotation exists in `flight_leg`;
- that programs run forwards, have plausible lengths and do not overlap within their chain, and that every issued ORD advisory is one version of one program (`tests/atc_program_interval_*.sql`).

`tests/unit/test_dbt_models.py` builds every model on a small synthetic stage in CI.

## Next

- A latest-forecast-as-of model on `taf_hourly`; NBM and LAMP guidance.
- Dagster assets through `dagster-dbt` (ADR-0003).
