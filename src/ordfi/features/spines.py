"""Feature rows ("spines") and their labels.

A spine row is a prediction to make: about ``target_utc``, made at ``as_of = target_utc -
horizon``. Two spines, at the horizons of the feasibility study (section 7.5):

- ``departures``: every scheduled ORD departure (cancelled ones included), for the flight-level
  delay distribution (T2) and cancellation (T5).
- ``hours``: every UTC hour at ORD, for the airport-level outlook (T1).

Labels are post-hoc outcomes (``y_`` columns), never features.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl

from ordfi.features.knowledge import Tables

HORIZONS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "6h": timedelta(hours=6),
    "3h": timedelta(hours=3),
    "1h": timedelta(hours=1),
    "15m": timedelta(minutes=15),
}
SPINES = ("departures", "hours")
UTC = pl.Datetime("us", "UTC")

# Departure-delay buckets (study section 6.4): every threshold from one distribution.
DELAY_BUCKETS = [(0, "<=0"), (14, "1-14"), (29, "15-29"), (59, "30-59"), (119, "60-119"),
                 (179, "120-179")]  # fmt: skip


def _horizons(names: list[str]) -> pl.DataFrame:
    unknown = set(names) - set(HORIZONS)
    if unknown:
        raise ValueError(f"unknown horizons {sorted(unknown)}; choose from {list(HORIZONS)}")
    return pl.DataFrame(
        {"horizon": names, "lead": [HORIZONS[n] for n in names]},
        schema={"horizon": pl.String(), "lead": pl.Duration("us")},
    )


def departures(
    legs: pl.DataFrame, start: datetime, end: datetime, horizons: list[str]
) -> pl.DataFrame:
    """ORD departures scheduled in [start, end) (UTC), one row per horizon."""
    flights = legs.filter(
        (pl.col("direction") == "departure")
        & (pl.col("sched_dep_utc") >= start)
        & (pl.col("sched_dep_utc") < end)
    ).select("flight_key", target_utc="sched_dep_utc")
    return _rows(flights, horizons).sort("target_utc", "flight_key", "horizon")


def hours(start: datetime, end: datetime, horizons: list[str]) -> pl.DataFrame:
    """UTC hours in [start, end) (tz-aware), one row per horizon."""
    targets = pl.DataFrame(
        {"target_utc": pl.datetime_range(start, end, "1h", closed="left", eager=True)}
    ).with_columns(pl.col("target_utc").cast(UTC))
    return _rows(targets, horizons).sort("target_utc", "horizon")


def _rows(targets: pl.DataFrame, horizons: list[str]) -> pl.DataFrame:
    return (
        targets.join(_horizons(horizons), how="cross")
        .with_columns(as_of=pl.col("target_utc") - pl.col("lead"))
        .drop("lead")
    )


def departure_labels(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """Outcome of each flight: delay (min), cancellation, diversion and the delay bucket.

    ``y_no_tail`` marks flights BTS gives no tail for; all were cancelled, so their (null)
    inbound features are an outcome artifact. Leave them out when training with inbound
    features.
    """
    legs = tables.legs.select(
        "flight_key",
        y_dep_delay="dep_delay",
        y_cancelled="cancelled",
        y_diverted="diverted",
        y_no_tail=pl.col("tail_number").is_null(),
    )
    # The first bucket that applies: cancelled, then by delay.
    bucket = pl.coalesce(
        pl.when(pl.col("y_cancelled")).then(pl.lit("cancelled")),
        *(
            pl.when(pl.col("y_dep_delay") <= upper).then(pl.lit(name))
            for upper, name in DELAY_BUCKETS
        ),
        pl.when(pl.col("y_dep_delay").is_not_null()).then(pl.lit(">=180")),
    )
    return (
        spine.select("row", "flight_key")
        .join(legs, on="flight_key", how="left")
        .select("row", "y_dep_delay", "y_cancelled", "y_diverted", "y_no_tail", y_dep_bucket=bucket)
    )


def hour_labels(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """Each hour's ORD departures: count, shares late (15, 60 min or cancelled), cancelled,
    and whether a general GDP or ground stop was in effect at any time in the hour."""
    deps = (
        tables.legs.filter(pl.col("direction") == "departure")
        .with_columns(target_utc=pl.col("sched_dep_utc").dt.truncate("1h"))
        .group_by("target_utc")
        .agg(
            y_n_departures=pl.len(),
            y_late15_share=((pl.col("dep_delay") >= 15) | pl.col("cancelled")).mean(),
            y_late60_share=((pl.col("dep_delay") >= 60) | pl.col("cancelled")).mean(),
            y_cancelled_share=pl.col("cancelled").mean(),
        )
    )
    hours_ = spine.select("target_utc").unique()
    programs = tables.programs.filter(
        (pl.col("airport") == "ORD")
        & (pl.col("scope") == "general")
        & (pl.col("end_utc") > pl.col("start_utc"))  # not cancelled before it began
    )
    flags = (
        hours_.join_where(
            programs.with_columns(start_hour=pl.col("start_utc").dt.truncate("1h")),
            pl.col("target_utc") >= pl.col("start_hour"),
            pl.col("target_utc") < pl.col("end_utc"),
        )
        .group_by("target_utc")
        .agg(
            y_gdp=(pl.col("program_type") == "gdp").any(),
            y_ground_stop=(pl.col("program_type") == "ground_stop").any(),
        )
    )
    return (
        spine.select("row", "target_utc")
        .join(deps, on="target_utc", how="left")
        .join(flags, on="target_utc", how="left")
        .with_columns(
            pl.col("y_n_departures").fill_null(0),
            pl.col("y_gdp").fill_null(False),
            pl.col("y_ground_stop").fill_null(False),
        )
        .drop("target_utc")
    )
