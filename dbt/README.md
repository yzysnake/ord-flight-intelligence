# dbt

SQL transformations with **dbt Core v1 + dbt-duckdb** (ADR-0002): stage → core, with tests.

- **Sources** are the stage Parquet files written by `ordfi.ingest` (`models/sources.yml`).
- **Outputs** are external Parquet materializations in `$ORDFI_DATA_DIR/core/<model>.parquet`.
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

Every model carries `known_time` (when its content became available) and `licence_class`. The dbt tests check:
- keys, accepted values and not-nulls;
- known holiday and DST dates (`tests/calendar_known_dates.sql`);
- parsed program periods (`tests/atc_program_periods_are_plausible.sql`).

`tests/unit/test_dbt_models.py` builds every model on a small synthetic stage in CI.

## Next

- Resolve `atc_program` revisions into in-effect intervals.
- Hourly TAF forecasts from our own bulletin parser (see the `iem_taf` card).
- Aircraft rotations; Dagster assets through `dagster-dbt` (ADR-0003).
