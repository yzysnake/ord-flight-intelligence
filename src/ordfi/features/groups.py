"""As-of feature groups.

Each group takes the spine (``row``, ``as_of``, ``target_utc`` and, for departures,
``flight_key``; for days, ``target_date`` and ``target_end_utc``) and the tables, and returns
one row per spine row: its features, computed only from what was known at ``as_of``
(ordfi.features.knowledge). Groups that depend on ``as_of`` alone are computed once per
distinct ``as_of`` and joined back. The ``day_`` groups summarize the whole target day.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import polars as pl

from ordfi.features.knowledge import TAIL_LEAD, Tables

Group = Callable[[pl.DataFrame, Tables], pl.DataFrame]

LOCAL_TZ = "America/Chicago"
RECENT_WEATHER = timedelta(hours=3)
PROGRAM_COUNT_WINDOW = timedelta(hours=24)
# A program version with no end stated (an open ground stop) is assumed to last this long.
OPEN_PROGRAM = timedelta(hours=2)
INBOUND_WINDOW = timedelta(hours=24)
PREVIOUS_DAY = timedelta(hours=24)
FAR_FUTURE = pl.lit(datetime(9999, 1, 1, tzinfo=UTC), dtype=pl.Datetime("us", "UTC"))
FLIGHT_CATEGORIES = ("LIFR", "IFR", "MVFR", "VFR")  # worst first
# Station guidance comes in 3-hourly projections: an instantaneous one stands for the 90 minutes
# around it; a period element covers the hours before its valid time.
NEAR = timedelta(minutes=90)
# (column, aggregate) at the projections near the target, and (column, hours) of the periods.
Instant = list[tuple[str, str]]
Periods = list[tuple[str, int]]
GUIDANCE: dict[str, tuple[str, Instant, Periods]] = {
    "mos": ("gfs_mos",
            [("ceiling_category", "min"), ("visibility_category", "min"),
             ("wind_speed_kt", "max"), ("snow_pct", "max"), ("freezing_pct", "max")],
            [("thunder_6h_pct", 6), ("severe_6h_pct", 6), ("pop_6h_pct", 6)]),
    "nbm": ("nbm",
            [("ceiling_ft", "min"), ("visibility_mi", "min"), ("ifr_ceiling_pct", "max"),
             ("ifr_visibility_pct", "max"), ("snow_pct", "max"), ("freezing_pct", "max"),
             ("sleet_pct", "max"), ("wind_speed_kt", "max"), ("wind_gust_kt", "max")],
            [("thunder_3h_pct", 3), ("pop_6h_pct", 6), ("snow_6h_in", 6), ("ice_6h_in", 6)]),
}  # fmt: skip


def _minutes(duration: pl.Expr) -> pl.Expr:
    return duration.dt.total_minutes()


def _per_key(spine: pl.DataFrame, features: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    """Join features computed per distinct key back onto the spine rows."""
    return spine.select("row", *keys).join(features, on=keys, how="left").drop(keys)


def calendar(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """The target's local hour, weekday, month and holiday proximity (always known)."""
    local = pl.col("target_utc").dt.convert_time_zone(LOCAL_TZ)
    rows = spine.select("row", date=local.dt.date(), cal_local_hour=local.dt.hour())
    days = tables.calendar.select(
        "date",
        cal_day_of_week="day_of_week",
        cal_month="month",
        cal_is_weekend="is_weekend",
        cal_is_holiday="is_holiday_observed",
        cal_days_to_holiday="days_to_holiday",
        cal_days_since_holiday="days_since_holiday",
    )
    return rows.join(days, on="date", how="left").drop("date")


def day_calendar(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """The target day's weekday, month and holiday proximity (always known)."""
    return calendar(spine, tables).drop("cal_local_hour")


def weather(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """The latest ORD METAR known at as_of, and the worst of the last three hours."""
    keys = spine.select("as_of").unique().sort("as_of")
    obs = tables.weather.sort("known_time", "valid_time", "report_type", maintain_order=True)
    latest = keys.join_asof(obs, left_on="as_of", right_on="known_time", strategy="backward")
    now = latest.select(
        "as_of",
        wx_age_min=_minutes(pl.col("as_of") - pl.col("valid_time")),
        wx_flight_category="flight_category",
        wx_visibility_mi="visibility_mi",
        wx_ceiling_ft="ceiling_ft",
        wx_wind_speed_kt="wind_speed_kt",
        wx_wind_gust_kt="wind_gust_kt",
        wx_temp_c="temp_c",
        wx_thunder="has_thunder",
        wx_snow="has_snow",
        wx_freezing="has_freezing",
    )
    recent = (
        keys.with_columns(since=pl.col("as_of") - RECENT_WEATHER)
        .join_where(
            obs.select("known_time", "visibility_mi", "ceiling_ft", "has_thunder", "has_snow"),
            pl.col("known_time") > pl.col("since"),
            pl.col("known_time") <= pl.col("as_of"),
        )
        .group_by("as_of")
        .agg(
            wx_min_visibility_3h=pl.col("visibility_mi").min(),
            wx_min_ceiling_3h=pl.col("ceiling_ft").min(),
            wx_thunder_3h=pl.col("has_thunder").any(),
            wx_snow_3h=pl.col("has_snow").any(),
        )
    )
    return _per_key(spine, now.join(recent, on="as_of", how="left"), ["as_of"])


def taf(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """The latest TAF known at as_of, for the target's hour."""
    keys = (
        spine.select("as_of", target_hour=pl.col("target_utc").dt.truncate("1h"))
        .unique()
        .sort("as_of")
    )
    hourly = tables.taf.sort("known_time", "product_id", maintain_order=True)
    # Sorted by known_time above; Polars cannot verify that within the hour groups.
    latest = keys.join_asof(
        hourly, left_on="as_of", right_on="known_time", by_left="target_hour",
        by_right="valid_time", strategy="backward", check_sortedness=False,
    )  # fmt: skip
    features = latest.select(
        "as_of",
        "target_hour",
        taf_available=pl.col("product_id").is_not_null(),
        taf_lead_min=_minutes(pl.col("target_hour") - pl.col("sent_at")),
        taf_is_amendment="is_amendment",
        taf_flight_category="flight_category",
        taf_worst_flight_category="worst_flight_category",
        taf_visibility_sm="visibility_sm",
        taf_ceiling_ft="ceiling_ft",
        taf_wind_speed_kt="wind_speed_kt",
        taf_wind_gust_kt="wind_gust_kt",
        taf_thunder=pl.any_horizontal(
            pl.col("has_thunder").fill_null(False),
            pl.col("tempo_thunder").fill_null(False),
            pl.col("prob_thunder").fill_null(False),
        ),
        taf_snow=pl.any_horizontal(
            pl.col("has_snow").fill_null(False), pl.col("tempo_snow").fill_null(False)
        ),
        taf_prob_pct="prob_pct",
    ).with_columns(
        # Null rather than False when no TAF covers the hour (e.g. beyond its 30 hours).
        *(pl.when(pl.col("taf_available")).then(pl.col(c)).alias(c)
          for c in ("taf_thunder", "taf_snow")),
    )  # fmt: skip
    rows = spine.select("row", "as_of", target_hour=pl.col("target_utc").dt.truncate("1h"))
    return rows.join(features, on=["as_of", "target_hour"], how="left").drop("as_of", "target_hour")


def day_taf(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """The latest TAF known at as_of for each hour of the target day, summed up: the hours
    covered; the worst flight category, prevailing and with TEMPO and PROB groups; hours of IFR
    or worse, of thunder (prevailing, TEMPO or PROB) and of snow; the strongest wind and gust;
    the lowest ceiling and visibility; the highest PROB; and the newest TAF's age and whether it
    is an amendment. Null when no TAF reaches the day (beyond its 30 hours)."""
    keys = spine.select("as_of", "target_utc", "target_end_utc").unique()
    day_hours = (
        keys.with_columns(
            valid_time=pl.datetime_ranges("target_utc", "target_end_utc", "1h", closed="left")
        )
        .explode("valid_time")
        .sort("as_of")
    )
    hourly = tables.taf.sort("known_time", "product_id", maintain_order=True)
    # Sorted by known_time above; Polars cannot verify that within the hour groups.
    latest = day_hours.join_asof(
        hourly, left_on="as_of", right_on="known_time", by="valid_time", strategy="backward",
        check_sortedness=False,
    )  # fmt: skip
    rank = {name: i for i, name in enumerate(FLIGHT_CATEGORIES)}
    prevailing = pl.col("flight_category").replace_strict(rank, default=None)
    covered = pl.col("product_id").is_not_null()
    thunder = pl.any_horizontal(
        *(pl.col(c).fill_null(False) for c in ("has_thunder", "tempo_thunder", "prob_thunder"))
    )
    snow = pl.any_horizontal(*(pl.col(c).fill_null(False) for c in ("has_snow", "tempo_snow")))
    hours_of = {"taf_day_ifr_hours": prevailing <= rank["IFR"], "taf_day_thunder_hours": thunder,
                "taf_day_snow_hours": snow}  # fmt: skip
    summary = latest.group_by("as_of", "target_utc", "target_end_utc").agg(
        taf_day_hours=covered.sum(),
        newest_sent=pl.col("sent_at").max(),
        taf_day_amendment=pl.col("is_amendment").sort_by("sent_at", nulls_last=False).last(),
        prevailing_rank=prevailing.min(),
        worst_rank=pl.col("worst_flight_category").replace_strict(rank, default=None).min(),
        **{name: (covered & hour).sum() for name, hour in hours_of.items()},
        taf_day_max_wind_kt=pl.col("wind_speed_kt").max(),
        taf_day_max_gust_kt=pl.col("wind_gust_kt").max(),
        taf_day_min_ceiling_ft=pl.col("ceiling_ft").min(),
        taf_day_min_visibility_sm=pl.col("visibility_sm").min(),
        taf_day_max_prob_pct=pl.col("prob_pct").max(),
    )
    category = dict(enumerate(FLIGHT_CATEGORIES))
    features = summary.with_columns(
        # Null rather than 0 hours when no TAF reaches the day.
        *(pl.when(pl.col("taf_day_hours") > 0).then(pl.col(name)).alias(name) for name in hours_of),
        taf_day_age_min=_minutes(pl.col("as_of") - pl.col("newest_sent")),
        taf_day_flight_category=pl.col("prevailing_rank").replace_strict(category, default=None),
        taf_day_worst_flight_category=pl.col("worst_rank").replace_strict(category, default=None),
    ).drop("newest_sent", "prevailing_rank", "worst_rank")
    return _per_key(spine, features, ["as_of", "target_utc", "target_end_utc"])


def guidance(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """GFS MOS (``mos_``) and NBM (``nbm_``) station guidance for the target hour (or day), each
    3-hourly projection from the latest run known at as_of. Instantaneous elements come from the
    projections within 90 minutes of the target: the worst flight category, the lowest ceiling
    and visibility, the strongest wind and gust, and the highest precipitation-type and IFR
    probabilities. Thunder, precipitation, snow and ice come from the periods overlapping it.
    Also how many projections cover the target, and the newest run's age. Null beyond the
    guidance's 72 hours, and for NBM before it starts (2018-11)."""
    end = (pl.col("target_end_utc") if "target_end_utc" in spine.columns
           else pl.col("target_utc") + timedelta(hours=1))  # fmt: skip
    rows = spine.with_columns(window_end=end)
    keys = rows.select("as_of", "target_utc", "window_end").unique()
    on = ["as_of", "target_utc", "window_end"]
    for prefix, (table, instant, periods) in GUIDANCE.items():
        found = _guidance(keys, getattr(tables, table), prefix, instant, periods)
        keys = keys.join(found, on=on, how="left").with_columns(
            pl.col(f"{prefix}_projections").fill_null(0)
        )
    return _per_key(rows, keys, on)


def _guidance(keys: pl.DataFrame, frame: pl.DataFrame, prefix: str, instant: Instant,
              periods: Periods) -> pl.DataFrame:  # fmt: skip
    """One model's guidance features for each (as_of, target window)."""
    on = ["as_of", "target_utc", "window_end"]
    longest = timedelta(hours=max(hours for _, hours in periods))
    candidates = keys.with_columns(
        lo=pl.col("target_utc") - NEAR, hi=pl.col("window_end") + longest
    ).join_where(
        frame,
        pl.col("known_time") <= pl.col("as_of"),
        pl.col("valid_time") >= pl.col("lo"),
        pl.col("valid_time") < pl.col("hi"),
    )
    # Each projection from the latest run known at as_of.
    latest = candidates.filter(
        pl.col("known_time") == pl.col("known_time").max().over([*on, "valid_time"])
    )
    near = (pl.col("valid_time") < pl.col("window_end") + NEAR).alias("near")
    overlap = {hours: ((pl.col("valid_time") > pl.col("target_utc"))
                       & (pl.col("valid_time") - timedelta(hours=hours) < pl.col("window_end")))
                      .alias(f"overlap_{hours}")
               for hours in {hours for _, hours in periods}}  # fmt: skip
    rank = {name: i for i, name in enumerate(FLIGHT_CATEGORIES)}
    marked = latest.with_columns(
        near, *overlap.values(),
        category_rank=pl.col("flight_category").replace_strict(rank, default=None),
    )  # fmt: skip
    aggregates = [
        pl.col("near").sum().alias(f"{prefix}_projections"),
        pl.col("runtime").max().alias("newest_run"),
        pl.col("category_rank").filter(pl.col("near")).min().alias("worst_rank"),
        *(getattr(pl.col(column).filter(pl.col("near")), how)().alias(f"{prefix}_{column}")
          for column, how in instant),
        *(pl.col(column).filter(pl.col(f"overlap_{hours}")).max().alias(f"{prefix}_{column}")
          for column, hours in periods),
    ]  # fmt: skip
    category = dict(enumerate(FLIGHT_CATEGORIES))
    return (
        marked.group_by(on)
        .agg(aggregates)
        .with_columns(
            pl.col("worst_rank").replace_strict(category, default=None)
            .alias(f"{prefix}_flight_category"),
            _minutes(pl.col("as_of") - pl.col("newest_run")).alias(f"{prefix}_age_min"),
        )
        .drop("worst_rank", "newest_run")
    )  # fmt: skip


def _versions(tables: Tables) -> pl.DataFrame:
    """ORD's general program versions, with how long each stays current and its assumed end."""
    return tables.program_versions.filter(
        (pl.col("airport") == "ORD") & (pl.col("scope") == "general")
    ).with_columns(
        valid_until=pl.coalesce("valid_to", FAR_FUTURE),
        end_assumed=pl.coalesce("end_utc", pl.col("start_utc") + OPEN_PROGRAM),
    )


def programs(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """ORD's general GDPs and ground stops as known at as_of: in effect now (minutes since the
    start, to the announced end), announced to cover the target, and how many were issued in
    the last 24 hours."""
    at_target = (pl.col("start_utc") <= pl.col("target_utc")) & (
        pl.col("target_utc") < pl.col("end_assumed")
    )
    return _programs(spine, tables, ["target_utc"], at_target, pl.col("as_of"))


def day_programs(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """As ``programs``, with the target the whole day: announced to cover any part of it."""
    at_target = (pl.col("start_utc") < pl.col("target_end_utc")) & (
        pl.col("end_assumed") > pl.col("target_utc")
    )
    # Issued on the day, a forecast also sees programs that ended since midnight.
    after = pl.min_horizontal("as_of", "target_utc")
    return _programs(spine, tables, ["target_utc", "target_end_utc"], at_target, after)


def _programs(spine: pl.DataFrame, tables: Tables, target: list[str], at_target: pl.Expr,
              after: pl.Expr) -> pl.DataFrame:  # fmt: skip
    """Program features for the spine's ``target`` columns: versions current at as_of that end
    after ``after``, announced to cover the target when ``at_target``."""
    versions = _versions(tables)
    keys = spine.select("as_of", *target).unique().with_columns(after=after)
    current = keys.join_where(
        versions,
        pl.col("known_time") <= pl.col("as_of"),
        pl.col("end_assumed") > pl.col("after"),
    ).filter(pl.col("valid_until") > pl.col("as_of"))
    now = (pl.col("start_utc") <= pl.col("as_of")) & (pl.col("as_of") < pl.col("end_assumed"))
    aggregates = []
    for kind, prefix in (("gdp", "atc_gdp"), ("ground_stop", "atc_gs")):
        is_kind = pl.col("program_type") == kind
        aggregates += [
            (is_kind & now).any().alias(f"{prefix}_now"),
            pl.when(is_kind & now).then(_minutes(pl.col("as_of") - pl.col("start_utc")))
            .max().alias(f"{prefix}_since_start_min"),
            pl.when(is_kind & now).then(_minutes(pl.col("end_assumed") - pl.col("as_of")))
            .max().alias(f"{prefix}_to_end_min"),
            (is_kind & at_target).any().alias(f"{prefix}_at_target"),
        ]  # fmt: skip
    state = current.group_by("as_of", *target).agg(aggregates)
    issued = (
        keys.select("as_of")
        .unique()
        .with_columns(since=pl.col("as_of") - PROGRAM_COUNT_WINDOW)
        .join_where(
            versions.filter(pl.col("version") == 1).select("program_type", "known_time"),
            pl.col("known_time") > pl.col("since"),
            pl.col("known_time") <= pl.col("as_of"),
        )
        .group_by("as_of")
        .agg(
            atc_gdp_issued_24h=(pl.col("program_type") == "gdp").sum(),
            atc_gs_issued_24h=(pl.col("program_type") == "ground_stop").sum(),
        )
    )
    features = (
        keys.drop("after")
        .join(state, on=["as_of", *target], how="left")
        .join(issued, on="as_of", how="left")
    )
    flags = [c for c in features.columns if c.endswith(("_now", "_at_target"))]
    counts = ["atc_gdp_issued_24h", "atc_gs_issued_24h"]
    features = features.with_columns(
        *(pl.col(c).fill_null(False) for c in flags), *(pl.col(c).fill_null(0) for c in counts)
    )
    return _per_key(spine, features, ["as_of", *target])


def _recent_counts(
    keys: pl.DataFrame, events: pl.DataFrame, window: timedelta, prefix: str
) -> pl.DataFrame:
    """Events (``time``, ``delay``) in (as_of - window, as_of]: count, mean delay and the
    share 15+ min late, from cumulative sums (keys sorted by ``as_of``)."""
    cumulative = events.sort("time", maintain_order=True).select(
        "time",
        n=pl.int_range(1, pl.len() + 1),
        n_delay=pl.col("delay").is_not_null().cum_sum(),
        delay=pl.col("delay").fill_null(0).cast(pl.Int64).cum_sum(),
        late=(pl.col("delay") >= 15).fill_null(False).cum_sum(),
    )
    sums = ["n", "n_delay", "delay", "late"]

    def upto(on: str) -> pl.DataFrame:
        frame = keys.with_columns(on=pl.col("as_of") - window if on == "start" else pl.col("as_of"))
        found = frame.sort("on").join_asof(
            cumulative, left_on="on", right_on="time", strategy="backward"
        )
        return found.select("as_of", *(pl.col(c).fill_null(0) for c in sums))

    end, start = upto("end"), upto("start")
    diff = end.join(start, on="as_of", suffix="_start").select(
        "as_of", *((pl.col(c) - pl.col(f"{c}_start")).alias(c) for c in sums)
    )
    some = pl.col("n_delay") > 0
    return diff.select(
        "as_of",
        pl.col("n").alias(f"{prefix}_n"),
        pl.when(some).then(pl.col("delay") / pl.col("n_delay")).alias(f"{prefix}_delay_mean"),
        pl.when(some).then(pl.col("late") / pl.col("n_delay")).alias(f"{prefix}_late15_share"),
    )


def operations(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """ORD's departures and arrivals that happened in the last one and three hours before
    as_of (count, mean delay, share 15+ min late), and the departures scheduled in the last
    hour, so the ratio shows flights held."""
    keys = spine.select("as_of").unique().sort("as_of")
    departed, arrived = _happened(tables)
    scheduled = tables.legs.filter(pl.col("direction") == "departure").select(
        time="sched_dep_utc", delay=pl.lit(None, dtype=pl.Int32)
    )
    features = keys
    for events, window, prefix in (
        (departed, timedelta(hours=1), "ops_dep_1h"),
        (departed, timedelta(hours=3), "ops_dep_3h"),
        (arrived, timedelta(hours=1), "ops_arr_1h"),
        (arrived, timedelta(hours=3), "ops_arr_3h"),
    ):
        features = features.join(_recent_counts(keys, events, window, prefix), on="as_of")
    planned = _recent_counts(keys, scheduled, timedelta(hours=1), "ops_sched_dep_1h").select(
        "as_of", "ops_sched_dep_1h_n"
    )
    features = features.join(planned, on="as_of").with_columns(
        ops_dep_flow_1h=pl.when(pl.col("ops_sched_dep_1h_n") > 0).then(
            pl.col("ops_dep_1h_n") / pl.col("ops_sched_dep_1h_n")
        )
    )
    return _per_key(spine, features, ["as_of"])


def previous_day(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """ORD's departures and arrivals that happened in the 24 hours before as_of (count, mean
    delay, share 15+ min late): the previous day's state (study §6.4)."""
    keys = spine.select("as_of").unique().sort("as_of")
    departed, arrived = _happened(tables)
    features = keys.join(
        _recent_counts(keys, departed, PREVIOUS_DAY, "ops_dep_24h"), on="as_of"
    ).join(_recent_counts(keys, arrived, PREVIOUS_DAY, "ops_arr_24h"), on="as_of")
    return _per_key(spine, features, ["as_of"])


def _happened(tables: Tables) -> tuple[pl.DataFrame, pl.DataFrame]:
    """ORD departures and arrivals that happened (``time``, ``delay``)."""
    legs = tables.legs
    deps = legs.filter((pl.col("direction") == "departure") & pl.col("dep_utc").is_not_null())
    arrs = legs.filter((pl.col("direction") == "arrival") & pl.col("arr_utc").is_not_null())
    return (deps.select(time="dep_utc", delay="dep_delay"),
            arrs.select(time="arr_utc", delay="arr_delay"))  # fmt: skip


def demand(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """ORD departures and arrivals scheduled in the target's hour (schedules are known a week
    ahead, longer than any horizon)."""
    legs = tables.legs
    deps = (
        legs.filter(pl.col("direction") == "departure")
        .group_by(target_hour=pl.col("sched_dep_utc").dt.truncate("1h"))
        .agg(dem_departures=pl.len())
    )
    arrs = (
        legs.filter(pl.col("direction") == "arrival")
        .group_by(target_hour=pl.col("sched_arr_utc").dt.truncate("1h"))
        .agg(dem_arrivals=pl.len())
    )
    rows = spine.select("row", target_hour=pl.col("target_utc").dt.truncate("1h"))
    return (
        rows.join(deps, on="target_hour", how="left")
        .join(arrs, on="target_hour", how="left")
        .with_columns(pl.col("dem_departures").fill_null(0), pl.col("dem_arrivals").fill_null(0))
        .drop("target_hour")
    )


def day_demand(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """ORD departures and arrivals scheduled on the target day, and in its busiest hour."""
    parts = []
    for direction, column, name in (("departure", "sched_dep_utc", "departures"),
                                    ("arrival", "sched_arr_utc", "arrivals")):  # fmt: skip
        parts.append(
            tables.legs.filter(pl.col("direction") == direction)
            .group_by(
                target_date=pl.col(column).dt.convert_time_zone(LOCAL_TZ).dt.date(),
                hour=pl.col(column).dt.truncate("1h"),
            )
            .agg(n=pl.len())
            .group_by("target_date")
            .agg(**{f"dem_{name}": pl.col("n").sum(), f"dem_peak_{name}": pl.col("n").max()})
        )
    rows = spine.select("row", "target_date")
    for part in parts:
        rows = rows.join(part, on="target_date", how="left")
    return rows.drop("target_date").with_columns(pl.exclude("row").fill_null(0))


def flight(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """The departure's schedule: carriers, destination, distance and block time."""
    legs = tables.legs.select(
        "flight_key",
        flt_carrier="operating_carrier",
        flt_marketing_carrier="marketing_carrier",
        flt_dest="dest",
        flt_distance="distance",
        flt_sched_block_min="crs_elapsed_time",
    )
    return (
        spine.select("row", "flight_key").join(legs, on="flight_key", how="left").drop("flight_key")
    )


def inbound(spine: pl.DataFrame, tables: Tables) -> pl.DataFrame:
    """The aircraft's previous arrival at ORD, once its tail is known (TAIL_LEAD before the
    departure): the scheduled turn, the inbound's departure and arrival delays known at as_of,
    and the turn slack left. Null before TAIL_LEAD.

    BTS leaves the tail blank for some cancelled flights (and only those), so a blank tail
    would reveal the cancellation. Availability therefore follows TAIL_LEAD alone; flights with
    no tail in the source (``y_no_tail``) get null inbound features and should be left out
    when training with them.
    """
    own = tables.legs.select("flight_key", "tail_number", "sched_dep_utc")
    rows = (
        spine.select("row", "as_of", "flight_key")
        .join(own, on="flight_key", how="left")
        .with_columns(
            tail=pl.when(pl.col("as_of") >= pl.col("sched_dep_utc") - TAIL_LEAD).then(
                pl.col("tail_number")
            )
        )
    )
    arrivals = (
        tables.legs.filter((pl.col("direction") == "arrival") & pl.col("tail_number").is_not_null())
        .select(
            tail="tail_number",
            in_sched_arr="sched_arr_utc",
            in_sched_dep="sched_dep_utc",
            in_origin="origin",
            in_dep_utc="dep_utc",
            in_dep_delay="dep_delay",
            in_arr_utc="arr_utc",
            in_arr_delay="arr_delay",
        )
        .sort("in_sched_arr")
    )
    known = rows.filter(pl.col("tail").is_not_null()).sort("sched_dep_utc")
    linked = known.join_asof(
        arrivals, left_on="sched_dep_utc", right_on="in_sched_arr", by="tail",
        strategy="backward", tolerance=INBOUND_WINDOW, allow_exact_matches=False,
        check_sortedness=False,  # both sorted above
    )  # fmt: skip
    departed = pl.col("in_dep_utc") <= pl.col("as_of")
    arrived = pl.col("in_arr_utc") <= pl.col("as_of")
    found = pl.col("in_sched_arr").is_not_null()
    late = (
        pl.when(arrived).then(pl.col("in_arr_delay"))
        .when(departed).then(pl.col("in_dep_delay"))
        .when(found).then(pl.max_horizontal(_minutes(pl.col("as_of") - pl.col("in_sched_dep")), 0))
    )  # fmt: skip
    features = linked.select(
        "row",
        inb_found=found,
        inb_origin="in_origin",
        inb_sched_turn_min=_minutes(pl.col("sched_dep_utc") - pl.col("in_sched_arr")),
        inb_departed=pl.when(found).then(departed.fill_null(False)),
        inb_arrived=pl.when(found).then(arrived.fill_null(False)),
        inb_dep_delay=pl.when(departed).then(pl.col("in_dep_delay")),
        inb_arr_delay=pl.when(arrived).then(pl.col("in_arr_delay")),
        # What is known of the inbound's delay: its arrival delay, else its departure delay,
        # else how long it is overdue to leave.
        inb_known_late_min=late,
    ).with_columns(
        inb_slack_min=pl.col("inb_sched_turn_min") - pl.max_horizontal("inb_known_late_min", 0)
    )
    return rows.select("row").join(features, on="row", how="left")
