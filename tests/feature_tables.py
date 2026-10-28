"""In-memory feature inputs shared by the feature tests: the columns the features read."""

from collections.abc import Iterable, Mapping
from datetime import date, timedelta

import polars as pl

from ordfi.features.knowledge import LEG_COLUMNS, Tables

UTC_TS = pl.Datetime("us", "UTC")
Row = Mapping[str, object]

WEATHER = {
    "valid_time": UTC_TS, "known_time": UTC_TS, "report_type": pl.String(),
    "flight_category": pl.String(), "visibility_mi": pl.Float64(), "ceiling_ft": pl.Float64(),
    "wind_speed_kt": pl.Float64(), "wind_gust_kt": pl.Float64(), "temp_c": pl.Float64(),
    "has_thunder": pl.Boolean(), "has_snow": pl.Boolean(), "has_freezing": pl.Boolean(),
}  # fmt: skip
TAF = {
    "product_id": pl.String(), "sent_at": UTC_TS, "known_time": UTC_TS, "valid_time": UTC_TS,
    "is_amendment": pl.Boolean(), "flight_category": pl.String(),
    "worst_flight_category": pl.String(), "visibility_sm": pl.Float64(),
    "ceiling_ft": pl.Int32(), "wind_speed_kt": pl.Int32(), "wind_gust_kt": pl.Int32(),
    "has_thunder": pl.Boolean(), "tempo_thunder": pl.Boolean(), "prob_thunder": pl.Boolean(),
    "has_snow": pl.Boolean(), "tempo_snow": pl.Boolean(), "prob_pct": pl.Int32(),
}  # fmt: skip
GFS_MOS = {
    "runtime": UTC_TS, "known_time": UTC_TS, "valid_time": UTC_TS,
    "flight_category": pl.String(), "ceiling_category": pl.Int32(),
    "visibility_category": pl.Int32(), "wind_speed_kt": pl.Int32(), "snow_pct": pl.Int32(),
    "freezing_pct": pl.Int32(), "thunder_6h_pct": pl.Int32(), "severe_6h_pct": pl.Int32(),
    "pop_6h_pct": pl.Int32(),
}  # fmt: skip
NBM = {
    "runtime": UTC_TS, "known_time": UTC_TS, "valid_time": UTC_TS,
    "flight_category": pl.String(), "ceiling_ft": pl.Int32(), "visibility_mi": pl.Float64(),
    "ifr_ceiling_pct": pl.Int32(), "ifr_visibility_pct": pl.Int32(), "snow_pct": pl.Int32(),
    "freezing_pct": pl.Int32(), "sleet_pct": pl.Int32(), "wind_speed_kt": pl.Int32(),
    "wind_gust_kt": pl.Int32(), "thunder_3h_pct": pl.Int32(), "pop_6h_pct": pl.Int32(),
    "snow_6h_in": pl.Float64(), "ice_6h_in": pl.Float64(),
}  # fmt: skip
VERSIONS = {
    "program_id": pl.String(), "airport": pl.String(), "program_type": pl.String(),
    "scope": pl.String(), "version": pl.Int64(), "start_utc": UTC_TS, "end_utc": UTC_TS,
    "known_time": UTC_TS, "valid_to": UTC_TS,
}  # fmt: skip
PROGRAMS = {
    "airport": pl.String(), "program_type": pl.String(), "scope": pl.String(),
    "start_utc": UTC_TS, "end_utc": UTC_TS,
}  # fmt: skip
LEGS = {
    "flight_key": pl.String(), "direction": pl.String(), "operating_carrier": pl.String(),
    "flight_number": pl.Int64(), "marketing_carrier": pl.String(), "origin": pl.String(),
    "dest": pl.String(), "sched_dep_utc": UTC_TS, "sched_arr_utc": UTC_TS,
    "distance": pl.Float64(), "crs_elapsed_time": pl.Int32(), "tail_number": pl.String(),
    "dep_utc": UTC_TS, "dep_delay": pl.Int32(), "arr_utc": UTC_TS, "arr_delay": pl.Int32(),
    "cancelled": pl.Boolean(), "diverted": pl.Boolean(),
}  # fmt: skip


def calendar(first: date, days: int) -> pl.DataFrame:
    dates = [first + timedelta(days=d) for d in range(days)]
    return pl.DataFrame(
        {
            "date": dates,
            "day_of_week": [d.isoweekday() for d in dates],
            "month": [d.month for d in dates],
            "is_weekend": [d.isoweekday() > 5 for d in dates],
            "is_holiday_observed": [False] * days,
            "days_to_holiday": [50] * days,
            "days_since_holiday": [10] * days,
        },
        schema_overrides={"days_to_holiday": pl.Int32(), "days_since_holiday": pl.Int32()},
    )


def tables(
    first: date,
    *,
    weather: Iterable[Row] = (),
    taf: Iterable[Row] = (),
    gfs_mos: Iterable[Row] = (),
    nbm: Iterable[Row] = (),
    versions: Iterable[Row] = (),
    programs: Iterable[Row] = (),
    legs: Iterable[Row] = (),
) -> Tables:
    """Feature inputs from row dicts (columns left out are null), with a week of calendar."""
    return Tables(
        calendar=calendar(first - timedelta(days=2), 7),
        weather=pl.DataFrame(list(weather), schema=WEATHER),
        taf=pl.DataFrame(list(taf), schema=TAF),
        gfs_mos=pl.DataFrame(list(gfs_mos), schema=GFS_MOS),
        nbm=pl.DataFrame(list(nbm), schema=NBM),
        program_versions=pl.DataFrame(list(versions), schema=VERSIONS),
        programs=pl.DataFrame(list(programs), schema=PROGRAMS),
        legs=pl.DataFrame(list(legs), schema=LEGS).select(LEG_COLUMNS),
    )
