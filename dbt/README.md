# dbt

SQL transformations with **dbt Core v1 + dbt-duckdb** (ADR-0002): staging → core → marts, with tests.

The project is initialized in Phase 1a and orchestrated through `dagster-dbt` (ADR-0003). Sources are Parquet files in `data/`, and outputs are external Parquet materializations.
