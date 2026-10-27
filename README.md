# ORD Flight Intelligence

Transparent, ORD-specific forecasts of airport disruption and passenger pickup timing at Chicago O'Hare (ORD).

> **Status: Phase 1a (historical foundation).** BTS on-time ingestion and the live collector are in place; weather and FAA advisory history are next. The [research and feasibility study](docs/research/ORD_Flight_Intelligence_Feasibility_Study.md) covers the evidence, the recommended scope, the architecture and the roadmap.

## What this project will build

- **v0.1 "ORD Outlook & Reliability Lab"** (public data only):
  - calibrated 1–72 h forecasts of airport-level disruption, with plain-language drivers;
  - historical reliability by flight, route, airline and hour, including connection-pair history;
  - research write-ups on why ORD's delays happen;
  - a public track record of the project's own forecast accuracy.
- **v0.2 "Pickup Planner"** (live beta): when an arriving passenger will actually be at the curb (domestic or Terminal 5 international), and when to leave the cell-phone lot.

This is deliberately **not** a flight tracker. Existing apps already cover live tracking, alerts and inbound-aircraft views well.

## Quickstart

You need conda (Miniconda or Miniforge) on macOS or Linux.

```bash
make env            # conda env create -f environment.yml   (env name: ordfi)
conda activate ordfi
make install        # editable install of the ordfi package
make hooks          # install the pre-commit git hooks
make check          # lint + type-check + tests
```

For an exactly pinned environment, install from the lock file instead (osx-arm64, linux-64):

```bash
conda-lock install -n ordfi conda-lock.yml
```

Ingest BTS on-time data (raw ZIP → typed Parquet with UTC timestamps), or run it through Dagster:

```bash
make ingest-bts TABLE=marketing FROM=2018-01 TO=2026-08
make dagster        # http://127.0.0.1:3000
```

Backfill FAA traffic-management advisories and IEM weather, then build the core tables with dbt:

```bash
make ingest-atcscc  # ATCSCC advisories, 2001 →
make ingest-iem     # ORD METAR and TAF, 2000 →
make dbt-build      # calendar, flight_leg, weather_obs(_hourly), atc_program → data/core
```

Archive the live feeds that have no public history (FAA NAS Status, ORD D-ATIS, CBP customs waits):

```bash
make collector-start   # also: collector-status, collector-stop (see infra/README.md)
```

To use the environment in PyCharm: *Settings → Project → Python Interpreter → Add → Conda → Existing environment → `ordfi`*.

## Repository layout

| Path | Purpose |
|---|---|
| `src/ordfi/` | Python package: `ingest`, `timeutil`, `features`, `models`, `serving`, `quality` |
| `tests/` | `unit/`, `property/` (point-in-time invariants), `integration/` |
| `dbt/` | SQL transformations, stage → core (dbt Core v1 + DuckDB; see `dbt/README.md`) |
| `pipelines/` | Dagster code location: assets, partitions, schedules, sensors (ADR-0003) |
| `notebooks/` | Numbered exploratory notebooks (outputs stripped) |
| `apps/` | Public web app, static analytics site, internal dashboards |
| `docs/research/` | Research and feasibility study |
| `docs/adr/` | Architecture decision records |
| `docs/data-catalog/` | One card per data source: licence, cadence, knowledge-time rule |
| `docs/model-cards/` | One card per released model |
| `infra/` | Deployment configuration |
| `data/` | Local data mirror (git-ignored) |

## Data and licensing

- **Code** is MIT-licensed (see [LICENSE](LICENSE)). **Data is never committed.**
- Every data source keeps its own licence. Each one has a card in [`docs/data-catalog/`](docs/data-catalog/README.md) recording:
  - licence class and attribution;
  - retention limits;
  - the *knowledge-time* rule used to prevent leakage.
- Public-domain and openly licensed sources come first: BTS, FAA, NOAA/IEM, CBP and ADS-B under ODbL. Licensed live feeds are used only within their terms.

## Roadmap

| Phase | Scope |
|---|---|
| 0 | Repository, environment, ADRs, data-catalog cards *(done; owner actions pending)* |
| 1a | Historical foundation: BTS, weather and FAA advisory ingestion; start the free live archivers *(in progress)* |
| 1b | Point-in-time feature store, Outlook models, public v0.1 |
| 2 | Pickup Planner live beta |
| 3 | Day-of flight risk, live connection risk, operations analytics; data-licensing decision |

Details: §11 of the research study.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
