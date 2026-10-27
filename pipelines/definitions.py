"""Dagster code location for ORD Flight Intelligence (ADR-0003).

Run locally with ``make dagster`` (``dagster dev -f pipelines/definitions.py``).
"""

# No ``from __future__ import annotations``: Dagster inspects the real `context` type.
from datetime import datetime

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetCheckSpec,
    AssetExecutionContext,
    AssetsDefinition,
    Definitions,
    Failure,
    MaterializeResult,
    MonthlyPartitionsDefinition,
    asset,
)

from ordfi.ingest import bts
from ordfi.ingest.http import NotPublishedError, make_client
from ordfi.settings import data_dir

# Minimum share of rows whose UTC derivation must reproduce BTS's own local hhmm fields.
MIN_MATCH = 0.999
MATCH_KEYS = ("match_sched_arr", "match_dep_time", "match_arr_time", "match_wheels_off")


def _partition_month(context: AssetExecutionContext) -> tuple[int, int]:
    when = datetime.strptime(context.partition_key, "%Y-%m-%d")
    return when.year, when.month


def bts_assets(table_name: str, start_date: str) -> list[AssetsDefinition]:
    """Raw-download and stage assets for one BTS on-time table, partitioned by month."""
    table = bts.TABLES[table_name]
    partitions = MonthlyPartitionsDefinition(start_date=start_date)
    raw_name, stage_name = f"{table.source_id}_raw", f"{table.source_id}_stage"

    @asset(
        name=raw_name,
        partitions_def=partitions,
        group_name="bts",
        kinds={"python"},
        description=f"Monthly ZIP from BTS TranStats ({table_name} carrier), stored verbatim.",
    )
    def raw(context: AssetExecutionContext) -> MaterializeResult:  # type: ignore[type-arg]  # Dagster needs the bare class
        year, month = _partition_month(context)
        try:
            with make_client() as client:
                record, new = bts.fetch_month(
                    table, year, month, client=client, data_root=data_dir()
                )
        except NotPublishedError as exc:
            raise Failure(description=f"BTS has not published {year}-{month:02d} yet") from exc
        return MaterializeResult(
            metadata={
                "path": record.path,
                "sha256": record.sha256,
                "revision": record.revision,
                "new_payload": new,
                "size_mb": round(record.size_bytes / 1e6, 1),
                "last_modified": record.last_modified or "",
            }
        )

    @asset(
        name=stage_name,
        deps=[raw],
        partitions_def=partitions,
        group_name="bts",
        kinds={"python", "parquet"},
        description="Typed Parquet with UTC timestamps, time zones and knowledge time.",
        check_specs=[
            AssetCheckSpec("utc_derivation", asset=stage_name),
            AssetCheckSpec("timezones_resolved", asset=stage_name),
        ],
    )
    def stage(context: AssetExecutionContext) -> MaterializeResult:  # type: ignore[type-arg]  # Dagster needs the bare class
        year, month = _partition_month(context)
        result = bts.stage_month(table, year, month, data_root=data_dir())
        checks = result.checks
        worst = min(float(checks[k]) for k in MATCH_KEYS)
        return MaterializeResult(
            metadata={
                "path": str(result.path),
                "rows": result.rows,
                "ord_rows": result.ord_rows,
                **{k: v for k, v in checks.items() if k != "rows"},
            },
            check_results=[
                AssetCheckResult(
                    check_name="utc_derivation",
                    passed=worst >= MIN_MATCH,
                    severity=AssetCheckSeverity.ERROR,
                    metadata={"worst_match": worst, "threshold": MIN_MATCH},
                ),
                AssetCheckResult(
                    check_name="timezones_resolved",
                    passed=int(checks["rows_missing_tz"]) == 0,
                    severity=AssetCheckSeverity.WARN,
                    metadata={"rows_missing_tz": int(checks["rows_missing_tz"])},
                ),
            ],
        )

    return [raw, stage]


defs = Definitions(
    assets=[
        *bts_assets("reporting", start_date="2015-01-01"),
        *bts_assets("marketing", start_date="2018-01-01"),
    ]
)
