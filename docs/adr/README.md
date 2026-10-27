# Architecture decision records

Significant technical decisions are recorded here *before* implementation, using [the template](0000-template.md). See [ADR-0001](0001-record-architecture-decisions.md) for why.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-analytical-storage-and-transformation.md) | Analytical storage, engine and transformation tool (Parquet + DuckDB + dbt Core v1) | Proposed |
| [0003](0003-orchestration.md) | Orchestration (Dagster OSS for batch; separate live collector) | Proposed |
| [0004](0004-live-data-providers.md) | Live data providers (FAA feeds, adsb.lol, deferred commercial APIs, routing) | Proposed |

**Process:**

- Copy the template to `NNNN-short-title.md` and open a PR. Merging accepts the ADR.
- Never rewrite an accepted ADR. Supersede it with a new one and link the two.
