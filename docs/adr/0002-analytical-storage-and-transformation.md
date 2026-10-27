# ADR-0002: Analytical storage, engine and transformation tool

- **Status:** Proposed
- **Date:** 2026-10-26

## Context

- **Scale is small.** National BTS on-time data is about 7 M rows per year (≈ 0.5 GB/year as column-pruned Parquet). Station-extracted weather is megabytes. Aggregated ADS-B events are modest. One developer works on a laptop first, then a small VM (research study §7).
- **Hard requirements:**
  - an immutable raw zone with **licence-based retention** (ADR-0004);
  - **point-in-time correctness**: every row carries `valid_time` and `known_time`;
  - reviewable, tested SQL transformations;
  - zero or near-zero cost;
  - portability between laptop, VM and object storage.
- **The dbt landscape changed in September 2026.**
  - **dbt v2** (new Rust engine) became the default for `pip install dbt` on 2026-09-14. It is proprietary under the dbt Product Licensing Agreement: free to use, with some features behind a login. Its open-source build, `dbt-oss`, is Apache-2.0.
  - v2 ships a **built-in DuckDB adapter**, but it does not yet support some dbt-duckdb features, such as plugins, Python models and external materializations. It may fail to infer schemas for models that read files through `read_parquet()` or `read_csv()`, which is this project's main source pattern.
  - **dbt Core v1** (Apache-2.0) "remains fully supported": 1.12.6 shipped 2026-10-14. The community **dbt-duckdb** adapter is active (1.11.1, 2026-10-26), and `dagster-dbt` supports dbt-core 1.12.
- **DuckDB 2.0** is already in the environment (`python-duckdb` 2.0.0).

## Options considered

1. **Parquet + DuckDB + dbt Core v1 (dbt-duckdb).**
   - Pros: mature DuckDB support (external Parquet materializations, plugins); Apache-2.0 end to end; orchestrator integration; already installed.
   - Cons: v1 will eventually be superseded, so a later migration is likely.
2. **Parquet + DuckDB + dbt v2** (proprietary build, or `dbt-oss`).
   - Pros: the future dbt line; faster parsing; stricter validation.
   - Cons: the DuckDB adapter has feature gaps exactly where we need it (file sources, external outputs). The default build is proprietary, which is awkward for a public, open-source repo.
3. **Parquet + DuckDB + SQLMesh.**
   - Pros: Apache-2.0; built-in virtual environments and column-level lineage.
   - Cons: smaller ecosystem; weaker orchestrator integration for our needs; a second paradigm to learn.
4. **PostgreSQL for everything** (warehouse and serving).
   - Pros: one system.
   - Cons: slow and costly for columnar scans over many years of BTS and forecast data; needs a running server from day one.
5. **A lakehouse table format now** (DuckLake or Iceberg).
   - Pros: ACID, time travel, multiple writers.
   - Cons: unnecessary at this scale with a single writer; more moving parts.

## Decision

Adopt **option 1**.

- **Raw zone.**
  - Payloads are stored verbatim as fetched, partitioned as `raw/<source>/<yyyy>/<mm>/<dd>/`.
  - Each payload has a metadata sidecar: URL, fetch time, HTTP status, checksum, `licence_class`.
  - It is append-only. Deletion happens only through licence TTLs.
- **Staging, core and feature layers** are Parquet (zstd) with Hive-style partitions. They carry `valid_time`, `known_time` and `licence_class` columns. Writes go to a temporary path and are then renamed, with a manifest per partition.
- **Engine:** embedded **DuckDB** for transformations and analysis. **Polars** is allowed inside Python steps.
- **Transformations:** **dbt Core v1 + dbt-duckdb**, pinned below 2.0.
- **Location:** local disk under `data/` in Phase 1. Mirrored to S3-compatible object storage (Cloudflare R2 by default) by Phase 2.
- **Out of scope here:** the operational database for the live product (PostgreSQL, Phase 2) and table formats (deferred; see the revisit triggers below).

## Consequences

**Easier:**

- No infrastructure cost; fast scans on a laptop.
- SQL reviewed in PRs, with dbt tests and documentation.
- Apache-2.0 tooling throughout.

**Harder:**

- **DuckDB has a single writer.** Only the orchestrator writes DuckDB or Parquet. The live collectors (ADR-0004) write raw files only.
- **No cross-file ACID.** Mitigated by write-then-rename, manifests and idempotent partition rebuilds.
- **A future dbt v1 → v2 migration.** Mitigated by avoiding deprecated features, keeping models in standard SQL, and treating v1 support announcements as a trigger.

**On acceptance:**

- Change `environment.yml` to `dbt-core>=1.9,<2` and `dbt-duckdb>=1.9,<2`, then `make lock`.
- Initialize `dbt/` in Phase 1a.

**Revisit when any of these happens:**

- `dbt-oss` v2's DuckDB adapter supports external Parquet materializations and file-based sources;
- dbt Labs announces an end-of-support date for v1.12;
- data exceeds about 100 GB, or more than one concurrent writer is needed (consider DuckLake, Iceberg or MotherDuck);
- DuckDB 2.x introduces breaking changes affecting our models.

## References

- Research study §7.1–7.4, §7.9.
- dbt: [versions](https://docs.getdbt.com/docs/dbt-versions), [licensing](https://docs.getdbt.com/docs/dbt-licensing), [DuckDB setup](https://docs.getdbt.com/docs/local/connect-data-platform/duckdb-setup).
- DuckDB: ["DuckDB now ships inside dbt v2"](https://duckdb.org/2026/09/22/dbt-fusion); [dbt-duckdb](https://github.com/duckdb/dbt-duckdb).
