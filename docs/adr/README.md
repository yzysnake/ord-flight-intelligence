# Architecture decision records

Significant technical decisions are recorded here *before* implementation, using [the template](0000-template.md). See [ADR-0001](0001-record-architecture-decisions.md) for why.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| 0002 | Analytical storage and engine (Parquet + DuckDB; transformation tool) | To write (Phase 0) |
| 0003 | Orchestration (Dagster vs. Prefect vs. cron) | To write (Phase 0) |
| 0004 | Live data providers (ADS-B source, optional flight-status API, routing) | To write (Phase 0) |

**Process:**

- Copy the template to `NNNN-short-title.md` and open a PR. Merging accepts the ADR.
- Never rewrite an accepted ADR. Supersede it with a new one and link the two.
