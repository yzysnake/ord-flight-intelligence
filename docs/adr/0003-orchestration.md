# ADR-0003: Orchestration

- **Status:** Proposed
- **Date:** 2026-10-26

## Context

The project has two very different workloads.

1. **Partitioned batch work**, which needs retries, backfills and visible partition status:
   - BTS monthly files (2015 →, re-published when BTS revises them);
   - IEM daily METAR/TAF/MOS backfills;
   - the ATCSCC advisory crawl (2001 →);
   - hourly NBM/LAMP/HRRR station extraction (2020 →);
   - the daily CBP pull;
   - dbt builds, monthly retraining and backtests.
2. **Continuous live collection**:
   - FAA NAS Status every minute;
   - ATCSCC advisories, METAR and D-ATIS every five minutes;
   - ADS-B every few seconds.

   These need low latency and must never miss a window, because live snapshots cannot be backfilled.

Constraints: one developer; free and open source; must work on a laptop (Phase 1) and a single small VM (Phase 2); must integrate with dbt Core (ADR-0002). Current versions are Dagster 1.13.27 and dagster-dbt 0.29.27 (both Apache-2.0, released 2026-10-26), and Prefect 3.9.0 (Apache-2.0, released 2026-10-21).

## Options considered

1. **Dagster OSS.**
   - Pros: software-defined assets with first-class partitions and backfills; asset checks for data quality; sensors (e.g., "new BTS month published"); dbt integration; local UI via `dagster dev`.
   - Cons: learning curve; a larger dependency set; needs instance storage (SQLite locally, PostgreSQL later).
2. **Prefect 3.**
   - Pros: Python-first flows; simple deployment; good retries and observability.
   - Cons: partition- and asset-centric backfills are less native, so monthly/daily partition bookkeeping would be ours to build.
3. **cron + Make** (plus GitHub Actions for light jobs).
   - Pros: minimal.
   - Cons: no backfill UI, lineage or partition status. GitHub Actions schedules are delayed under load and unsuitable for data-heavy jobs.
4. **Apache Airflow.**
   - Pros: industry standard.
   - Cons: heavy to operate for one developer; task-centric rather than asset-centric.

## Decision

**Batch work uses Dagster OSS.**

- Each dataset is an asset with a partitions definition: monthly for BTS, daily for IEM/ATCSCC/CBP, hourly for model guidance.
- dbt models are loaded through `dagster-dbt`.
- Data-quality rules are asset checks.
- Phase 1 runs `dagster dev` locally. Phase 2 runs the webserver and daemon on the VM, with PostgreSQL instance storage.

**Live collection is a separate, always-on collector service, not Dagster jobs.**

- It is an asyncio worker run under systemd or Docker.
- It writes raw files and a heartbeat only.
- Dagster sensors register new raw partitions, and asset checks monitor collector freshness.

This keeps minute-level polling independent of orchestrator restarts, and keeps DuckDB writes single-writer (ADR-0002).

## Consequences

**Easier:**

- One place to see which BTS months or forecast hours are loaded, failed or stale.
- One-click backfills.
- Lineage from raw files to dbt models to features.

**Harder:**

- Dagster concepts to learn.
- Dependency pins to verify against pandas 3 and pydantic 2.14 when added.
- Two runtime processes to supervise: the orchestrator and the collector.

**On acceptance:**

- Add `dagster`, `dagster-webserver` and `dagster-dbt` to `environment.yml` (verify conda-forge builds), then `make lock`.
- Create the code location in `pipelines/`.
- Until the first partitioned asset exists, `make` targets remain the entry points.

**Revisit when any of these happens:**

- Dagster overhead outweighs its value (for example, fewer than about ten assets after Phase 1). Then fall back to Make + cron.
- A managed service becomes worthwhile (Dagster+ or Prefect Cloud).
- The live collector outgrows a single process (consider a message broker).

## References

- Research study §7.4, §7.9.
- [Dagster partitions and backfills](https://docs.dagster.io/guides/build/partitions-and-backfills); [dagster-dbt](https://docs.dagster.io/api/libraries/dagster-dbt); [Prefect](https://github.com/PrefectHQ/prefect).
