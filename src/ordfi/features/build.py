"""Build as-of feature snapshots, one month at a time.

``python -m ordfi.features --spine departures --from 2019-01 --to 2019-12`` writes
``features/<spine>/horizon=<h>/<yyyy-mm>.parquet`` under the data directory. Each row is a
spine row (a flight or an hour, at a horizon) with its features, known at ``as_of``, and its
``y_`` labels. Live scoring is meant to call ``features`` on the same tables with
``as_of = now``.
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl

from ordfi.features import groups
from ordfi.features.knowledge import LEG_COLUMNS, SCHEDULE_LEAD, Tables
from ordfi.features.spines import (
    HORIZONS,
    SPINES,
    departure_labels,
    departures,
    hour_labels,
    hours,
)
from ordfi.settings import data_dir

GROUPS: dict[str, list[groups.Group]] = {
    "departures": [
        groups.calendar, groups.weather, groups.taf, groups.programs, groups.operations,
        groups.demand, groups.flight, groups.inbound,
    ],
    "hours": [
        groups.calendar, groups.weather, groups.taf, groups.programs, groups.operations,
        groups.demand,
    ],
}  # fmt: skip
LABELS = {"departures": departure_labels, "hours": hour_labels}
LICENCE = "public-domain"  # every input is public domain

# Demand and inbound features take the schedules around the target as known at as_of.
assert max(HORIZONS.values()) + timedelta(days=1) <= SCHEDULE_LEAD


def features(spine_name: str, spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """The spine with a ``row`` index and every feature of the spine's groups."""
    rows = spine.with_row_index("row")
    out = rows
    for group in GROUPS[spine_name]:
        out = out.join(group(rows, tables), on="row", how="left")
    return out


def build(spine_name: str, spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """Features and labels for each spine row."""
    rows = features(spine_name, spine, tables)
    labels = LABELS[spine_name](rows, tables)
    return (
        rows.join(labels, on="row", how="left")
        .drop("row")
        .with_columns(licence_class=pl.lit(LICENCE))
    )


def load(core: Path, start: datetime, end: datetime) -> Tables:
    """The core tables for targets in [start, end), with the history before them."""
    before = start - max(HORIZONS.values()) - timedelta(days=2)
    after = end + timedelta(days=1)

    def scan(name: str) -> pl.LazyFrame:
        return pl.scan_parquet(core / f"{name}.parquet")

    weather = scan("weather_obs").filter(
        pl.col("known_time").is_between(before, end, closed="left")
    )
    taf = scan("taf_hourly").filter(
        pl.col("valid_time").is_between(start - timedelta(hours=1), after, closed="left")
        & (pl.col("known_time") < end)
    )
    versions = scan("atc_program_interval_version").filter(
        (pl.col("known_time") < end)
        & (pl.coalesce("end_utc", pl.col("start_utc") + timedelta(days=1)) > before)
    )
    programs = scan("atc_program_interval").filter(
        (pl.col("end_utc") > start - timedelta(hours=1)) & (pl.col("start_utc") < end)
    )
    legs = scan("flight_leg").filter(
        pl.col("sched_dep_utc").is_between(before - timedelta(days=1), after, closed="left")
    )
    return Tables(
        calendar=scan("calendar").collect(),
        weather=weather.collect(),
        taf=taf.collect(),
        program_versions=versions.collect(),
        programs=programs.collect(),
        legs=legs.select(LEG_COLUMNS).collect(),
    )


def spine_for(spine_name: str, tables: Tables, start: datetime, end: datetime,
              horizons: list[str]) -> pl.DataFrame:  # fmt: skip
    if spine_name == "departures":
        return departures(tables.legs, start, end, horizons)
    return hours(start, end, horizons)


def _months(first: date, last: date) -> list[date]:
    months, month = [], first.replace(day=1)
    while month <= last:
        months.append(month)
        month = (month + timedelta(days=32)).replace(day=1)
    return months


def run(spine_name: str, first: date, last: date, horizons: list[str], root: Path) -> None:
    out_dir = root / "features" / spine_name
    for month in _months(first, last):
        began = time.monotonic()
        start = datetime(month.year, month.month, 1, tzinfo=UTC)
        end = (start + timedelta(days=32)).replace(day=1)
        tables = load(root / "core", start, end)
        frame = build(spine_name, spine_for(spine_name, tables, start, end, horizons), tables)
        for (horizon,), part in frame.partition_by("horizon", as_dict=True).items():
            target = out_dir / f"horizon={horizon}" / f"{month:%Y-%m}.parquet"
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f".{target.name}.tmp")
            part.write_parquet(tmp, compression="zstd")
            os.replace(tmp, target)
        print(
            f"{month:%Y-%m}: {spine_name} rows={frame.height} "
            f"seconds={time.monotonic() - began:.1f}",
            flush=True,
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build as-of feature snapshots.")
    parser.add_argument("--spine", choices=SPINES, default="departures")
    parser.add_argument("--from", dest="first", required=True, help="YYYY-MM")
    parser.add_argument("--to", dest="last", required=True, help="YYYY-MM")
    parser.add_argument("--horizons", default=",".join(HORIZONS), help="e.g. 24h,6h,1h")
    args = parser.parse_args(argv)
    first = date.fromisoformat(f"{args.first}-01")
    last = date.fromisoformat(f"{args.last}-01")
    run(args.spine, first, last, args.horizons.split(","), data_dir())
