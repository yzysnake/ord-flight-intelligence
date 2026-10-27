# Pipelines

Dagster code location (ADR-0003):

- software-defined assets with partitions (monthly BTS; daily IEM/ATCSCC/CBP; hourly forecast extraction);
- dbt models loaded through `dagster-dbt`;
- data-quality rules as asset checks;
- sensors for new raw partitions and collector freshness.

Live collection (NAS Status, ADS-B, D-ATIS, METAR polling) runs as a separate always-on service that writes raw files only.

The code location is created in Phase 1a. Until the first asset exists, batch jobs run through `make` targets.
