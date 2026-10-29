"""Feature rows ("spines") and their labels.

A spine row is a prediction to make: about ``target_utc``, made at ``as_of``. Three spines:

- ``departures``: every scheduled ORD departure (cancelled ones included), for the flight-level
  delay distribution (T2) and cancellation (T5).
- ``hours``: every UTC hour at ORD, for the airport-level outlook (T1).
- ``days``: every local day at ORD (America/Chicago), for the daily outlook (T1). The target is
  the whole day, from ``target_utc`` to ``target_end_utc``.

Departures and hours are forecast at fixed horizons, ``as_of = target_utc - horizon`` (the
feasibility study, section 7.5). Days are forecast at fixed local times (``DAY_ISSUES``), the
way a daily outlook is published.

Labels are post-hoc outcomes (``y_`` columns), never features.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import polars as pl

from ordfi.features.knowledge import Tables

HORIZONS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "6h": timedelta(hours=6),
    "3h": timedelta(hours=3),
    "1h": timedelta(hours=1),
    "15m": timedelta(minutes=15),
}
# Daily outlook issues: (days before the target day, local hour). The 19:00 issues come after
# the 00Z TAF (sent about 18:30 local), which covers all of the next day; at 07:00 the day
# before, the 12Z TAF covers the target day to about noon; at 05:00 on the day, the 06Z TAF
# covers all of it. Two and three days ahead, no TAF reaches the day.
DAY_ISSUES: dict[str, tuple[int, int]] = {
    "d3_1900": (3, 19),
    "d2_1900": (2, 19),
    "d1_0700": (1, 7),
    "d1_1900": (1, 19),
    "d0_0500": (0, 5),
}
SPINES = ("departures", "hours", "days")
UTC = pl.Datetime("us", "UTC")
LOCAL_TZ = "America/Chicago"

# Departure-delay buckets (study section 6.4): every threshold from one distribution.
DELAY_BUCKETS = [(0, "<=0"), (14, "1-14"), (29, "15-29"), (59, "30-59"), (119, "60-119"),
                 (179, "120-179")]  # fmt: skip


def horizons(spine: str) -> list[str]:
    """The spine's horizons (issue times for days), longest lead first."""
    return list(DAY_ISSUES if spine == "days" else HORIZONS)


def max_lead(spine: str) -> timedelta:
    """The longest time from a row's as_of to its target_utc (the start of a day)."""
    if spine == "days":  # an hour more for a daylight-saving change in between
        return max(timedelta(days=d, hours=1 - h) for d, h in DAY_ISSUES.values())
    return max(HORIZONS.values())


def _check(names: list[str], known: list[str]) -> None:
    unknown = set(names) - set(known)
    if unknown:
        raise ValueError(f"unknown horizons {sorted(unknown)}; choose from {known}")


def _horizons(names: list[str]) -> pl.DataFrame:
    _check(names, list(HORIZONS))
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


def days(start: date, end: date, issues: list[str]) -> pl.DataFrame:
    """Local days in [start, end), one row per issue: the day's start and end in UTC
    (``target_utc``, ``target_end_utc``; 23 or 25 hours apart when the clocks change) and the
    issue time (``as_of``)."""
    _check(issues, list(DAY_ISSUES))
    schedule = pl.DataFrame(
        {"horizon": issues, "days_before": [DAY_ISSUES[i][0] for i in issues],
         "local_hour": [DAY_ISSUES[i][1] for i in issues]},
        schema={"horizon": pl.String(), "days_before": pl.Int64(), "local_hour": pl.Int64()},
    )  # fmt: skip
    midnight = pl.col("target_date").cast(pl.Datetime("us"))
    issued = (
        midnight - pl.duration(days=pl.col("days_before")) + pl.duration(hours=pl.col("local_hour"))
    )
    return (
        pl.DataFrame({"target_date": pl.date_range(start, end, "1d", closed="left", eager=True)})
        .join(schedule, how="cross")
        .with_columns(
            target_utc=_utc(midnight),
            target_end_utc=_utc(midnight + pl.duration(days=1)),
            as_of=_utc(issued),
        )
        .drop("days_before", "local_hour")
        .sort("target_date", "horizon")
    )


def _utc(local: pl.Expr) -> pl.Expr:
    """A naive local (America/Chicago) time in UTC. The issue times and midnight are never
    skipped or repeated by a clock change (at 02:00)."""
    return local.dt.replace_time_zone(LOCAL_TZ).dt.convert_time_zone("UTC")


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


def _departure_outcomes(legs: pl.DataFrame, period: pl.Expr, key: str) -> pl.DataFrame:
    """ORD departures by scheduled ``period`` (named ``key``): count and shares late (15, 60
    min or cancelled) and cancelled."""
    return (
        legs.filter(pl.col("direction") == "departure")
        .group_by(period.alias(key))
        .agg(
            y_n_departures=pl.len(),
            y_late15_share=((pl.col("dep_delay") >= 15) | pl.col("cancelled")).mean(),
            y_late60_share=((pl.col("dep_delay") >= 60) | pl.col("cancelled")).mean(),
            y_cancelled_share=pl.col("cancelled").mean(),
        )
    )


def _general_programs(tables: Tables) -> pl.DataFrame:
    return tables.programs.filter(
        (pl.col("airport") == "ORD")
        & (pl.col("scope") == "general")
        & (pl.col("end_utc") > pl.col("start_utc"))  # not cancelled before it began
    )


PROGRAM_FLAGS = (
    (pl.col("program_type") == "gdp").any().alias("y_gdp"),
    (pl.col("program_type") == "ground_stop").any().alias("y_ground_stop"),
)
# The windowed ground-stop event of the hours spine: the target hour and the two after it.
GROUND_STOP_WINDOW = timedelta(hours=3)


def _outcome_labels(spine: pl.DataFrame, key: str, deps: pl.DataFrame,
                    flags: pl.DataFrame) -> pl.DataFrame:  # fmt: skip
    return (
        spine.select("row", key)
        .join(deps, on=key, how="left")
        .join(flags, on=key, how="left")
        .with_columns(
            pl.col("y_n_departures").fill_null(0),
            pl.col("y_gdp").fill_null(False),
            pl.col("y_ground_stop").fill_null(False),
        )
        .drop(key)
    )


def hour_labels(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """Each hour's ORD departures: count, shares late (15, 60 min or cancelled), cancelled;
    whether a general GDP or ground stop was in effect at any time in the hour; and whether a
    general ground stop was at any time in the window of hours from it (``y_ground_stop_3h``)."""
    deps = _departure_outcomes(tables.legs, pl.col("sched_dep_utc").dt.truncate("1h"),
                               "target_utc")  # fmt: skip
    targets = spine.select("target_utc").unique()
    flags = (
        targets.join_where(
            _general_programs(tables).with_columns(
                start_hour=pl.col("start_utc").dt.truncate("1h")
            ),
            pl.col("target_utc") >= pl.col("start_hour"),
            pl.col("target_utc") < pl.col("end_utc"),
        )
        .group_by("target_utc")
        .agg(PROGRAM_FLAGS)
    )
    stops = _general_programs(tables).filter(pl.col("program_type") == "ground_stop")
    window = (
        targets.join_where(
            stops,
            pl.col("start_utc") < pl.col("target_utc") + GROUND_STOP_WINDOW,
            pl.col("end_utc") > pl.col("target_utc"),
        )
        .select("target_utc", y_ground_stop_3h=pl.lit(True))
        .unique()
    )
    in_window = spine.select("row", "target_utc").join(window, on="target_utc", how="left")
    return (
        _outcome_labels(spine, "target_utc", deps, flags)
        .join(in_window.drop("target_utc"), on="row")
        .with_columns(pl.col("y_ground_stop_3h").fill_null(False))
    )


def day_labels(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """Each local day's ORD departures: count, shares late (15, 60 min or cancelled),
    cancelled, and whether a general GDP or ground stop was in effect at any time in the day."""
    local_date = pl.col("sched_dep_utc").dt.convert_time_zone(LOCAL_TZ).dt.date()
    deps = _departure_outcomes(tables.legs, local_date, "target_date")
    flags = (
        spine.select("target_date", "target_utc", "target_end_utc")
        .unique()
        .join_where(
            _general_programs(tables),
            pl.col("start_utc") < pl.col("target_end_utc"),
            pl.col("end_utc") > pl.col("target_utc"),
        )
        .group_by("target_date")
        .agg(PROGRAM_FLAGS)
    )
    return _outcome_labels(spine, "target_date", deps, flags)
