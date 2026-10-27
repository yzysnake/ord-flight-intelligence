# data/ (git-ignored)

Local mirror of the data lake. Only this README is committed.

```
data/
├── raw/<source>/<yyyy>/<mm>/<dd>/   # verbatim payloads + fetch metadata (immutable)
├── stage/<entity>/                  # typed Parquet, UTC, bi-temporal columns
├── core/                            # dbt core models (Parquet)
├── warehouse/ordfi.duckdb           # DuckDB views over core (written by dbt; open read-only)
└── features/<horizon>/              # point-in-time feature snapshots
```

Retention follows each source's licence class (see `docs/data-catalog/`).
