"""When each input becomes known: the knowledge-time rules behind every as-of feature.

A feature for a prediction made at ``as_of`` may only use what was known then. ``visible``
returns the inputs exactly as they were known at one instant. The feature code must give the
same result on them as on the full tables; ``tests/property/test_features_no_leakage.py``
checks that on random inputs.

Rules (see the feasibility study, section 7.5):

- METARs and TAFs: their ``known_time`` (issue time + 10 min).
- ATC program versions: their ``known_time`` (the advisory's send time). Until the next
  version is known, a version's ``valid_to`` is unknown too.
- Flight schedules (times, carrier, route): ``SCHEDULE_LEAD`` before scheduled departure.
  Schedules are published months ahead; a week is a conservative bound for horizons up to 72 h.
- Tail numbers: ``TAIL_LEAD`` before scheduled departure. BTS records the aircraft that
  actually flew; aircraft swaps make it unreliable further ahead.
- Actual departure (arrival) times and delays: when the departure (arrival) happened.
- Outcomes known only from the published BTS file (cancellations, diversions, delay causes,
  elapsed times): never inputs; they are labels.
- The calendar: always.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

import polars as pl

SCHEDULE_LEAD = timedelta(days=7)
TAIL_LEAD = timedelta(hours=6)

# flight_leg columns by when they become known.
SCHEDULE_COLUMNS = (
    "flight_key", "direction", "operating_carrier", "flight_number", "marketing_carrier",
    "origin", "dest", "sched_dep_utc", "sched_arr_utc", "distance", "crs_elapsed_time",
)  # fmt: skip
DEPARTURE_COLUMNS = ("dep_utc", "dep_delay")  # known at dep_utc
ARRIVAL_COLUMNS = ("arr_utc", "arr_delay")  # known at arr_utc
OUTCOME_COLUMNS = ("cancelled", "diverted")  # labels only
LEG_COLUMNS = (*SCHEDULE_COLUMNS, "tail_number", *DEPARTURE_COLUMNS, *ARRIVAL_COLUMNS,
               *OUTCOME_COLUMNS)  # fmt: skip


@dataclass(frozen=True)
class Tables:
    """The core tables the features read (subsets of columns and time ranges)."""

    calendar: pl.DataFrame  # calendar
    weather: pl.DataFrame  # weather_obs
    taf: pl.DataFrame  # taf_hourly
    program_versions: pl.DataFrame  # atc_program_interval_version
    programs: pl.DataFrame  # atc_program_interval (labels only)
    legs: pl.DataFrame  # flight_leg (LEG_COLUMNS)


def visible(tables: Tables, as_of: datetime) -> Tables:
    """The tables as known at ``as_of``: unknown rows dropped, unknown fields nulled."""
    t = pl.lit(as_of, dtype=pl.Datetime("us", "UTC"))
    versions = tables.program_versions.filter(pl.col("known_time") <= t).with_columns(
        valid_to=pl.when(pl.col("valid_to") <= t).then(pl.col("valid_to"))
    )
    legs = tables.legs.filter(pl.col("sched_dep_utc") - SCHEDULE_LEAD <= t).with_columns(
        pl.when(pl.col("sched_dep_utc") - TAIL_LEAD <= t).then(pl.col("tail_number"))
        .alias("tail_number"),
        *(pl.when(pl.col("dep_utc") <= t).then(pl.col(c)).alias(c) for c in DEPARTURE_COLUMNS),
        *(pl.when(pl.col("arr_utc") <= t).then(pl.col(c)).alias(c) for c in ARRIVAL_COLUMNS),
        *(pl.lit(None, dtype=tables.legs.schema[c]).alias(c) for c in OUTCOME_COLUMNS),
    )  # fmt: skip
    return replace(
        tables,
        weather=tables.weather.filter(pl.col("known_time") <= t),
        taf=tables.taf.filter(pl.col("known_time") <= t),
        program_versions=versions,
        programs=tables.programs.clear(),
        legs=legs,
    )
