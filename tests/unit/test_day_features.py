"""The days spine on hand-built inputs: issue times, each day group, the labels and the run.

The target day is Tuesday 16 July 2019 at ORD (CDT): 05:00 UTC on the 16th to 05:00 UTC on
the 17th. Its issues: d1_0700 at 12:00 UTC on the 15th, d1_1900 at 00:00 UTC on the 16th and
d0_0500 at 10:00 UTC on the 16th.
"""

from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from ordfi.features import build
from ordfi.features.knowledge import Tables
from ordfi.features.spines import days
from tests.feature_tables import tables

TARGET = date(2019, 7, 16)


def utc(day: int, hour: int, minute: int = 0, month: int = 7) -> datetime:
    return datetime(2019, month, day, hour, minute, tzinfo=UTC)


def leg(key: str, direction: str, sched_dep: datetime, **fields: object) -> dict[str, object]:
    return {
        "flight_key": key, "direction": direction, "operating_carrier": "UA",
        "origin": "DEN" if direction == "arrival" else "ORD",
        "dest": "ORD" if direction == "arrival" else "LGA", "sched_dep_utc": sched_dep,
        "sched_arr_utc": sched_dep + timedelta(hours=2), "cancelled": False, **fields,
    }  # fmt: skip


def day_features(t: Tables, *issues: str) -> dict[str, dict[str, object]]:
    """Features of the target day, by issue."""
    frame = build.features("days", days(TARGET, TARGET + timedelta(days=1), list(issues)), t)
    return {row["horizon"]: row for row in frame.iter_rows(named=True)}


def test_days_are_issued_at_local_times_and_last_a_local_day() -> None:
    rows = days(date(2019, 3, 9), date(2019, 3, 11), ["d1_1900", "d0_0500"])
    columns = ["target_date", "horizon", "target_utc", "target_end_utc", "as_of"]
    assert rows.select(columns).rows() == [
        (date(2019, 3, 9), "d0_0500", utc(9, 6, month=3), utc(10, 6, month=3), utc(9, 11, month=3)),
        (date(2019, 3, 9), "d1_1900", utc(9, 6, month=3), utc(10, 6, month=3), utc(9, 1, month=3)),
        # The clocks go forward at 02:00 on the 10th: a 23-hour day, issued in CDT.
        (date(2019, 3, 10), "d0_0500", utc(10, 6, month=3), utc(11, 5, month=3),
         utc(10, 10, month=3)),
        (date(2019, 3, 10), "d1_1900", utc(10, 6, month=3), utc(11, 5, month=3),
         utc(10, 1, month=3)),
    ]  # fmt: skip
    with pytest.raises(ValueError, match="unknown horizons"):
        days(date(2019, 3, 9), date(2019, 3, 10), ["24h"])


Hours = Mapping[datetime, Mapping[str, object]]


def taf_issue(product: str, sent: datetime, first: datetime,
              special: Hours) -> list[dict[str, object]]:  # fmt: skip
    """A 30-hour TAF from ``first``: VFR and 10 kt, except for the ``special`` hours."""
    hours = [first + timedelta(hours=h) for h in range(30)]
    return [
        {"product_id": product, "sent_at": sent, "known_time": sent + timedelta(minutes=10),
         "valid_time": hour, "is_amendment": False, "flight_category": "VFR",
         "worst_flight_category": "VFR", "wind_speed_kt": 10, **special.get(hour, {})}
        for hour in hours
    ]  # fmt: skip


def test_day_taf_sums_up_the_latest_issue_known_for_each_hour() -> None:
    ifr = {"flight_category": "IFR", "worst_flight_category": "IFR"}
    lifr = {"flight_category": "LIFR", "worst_flight_category": "LIFR"}
    old = taf_issue("old", utc(15, 17, 30), utc(15, 18), {utc(16, 10): ifr})
    new = taf_issue("new", utc(15, 23, 30), utc(16, 0), {
        utc(16, 15): {"flight_category": "MVFR", "worst_flight_category": "IFR",
                      "ceiling_ft": 1500},
        utc(16, 18): {"wind_speed_kt": 25, "wind_gust_kt": 35},
        utc(16, 21): {"prob_thunder": True, "prob_pct": 30},
        utc(16, 22): {"prob_thunder": True, "prob_pct": 30},
    })  # fmt: skip
    later = taf_issue("later", utc(16, 5, 30), utc(16, 6), {utc(16, 12): lifr})
    got = day_features(tables(TARGET, taf=old + new + later), "d1_0700", "d1_1900", "d0_0500")
    summary = ["taf_day_hours", "taf_day_age_min", "taf_day_flight_category",
               "taf_day_worst_flight_category", "taf_day_ifr_hours", "taf_day_thunder_hours",
               "taf_day_max_wind_kt", "taf_day_max_gust_kt", "taf_day_min_ceiling_ft",
               "taf_day_max_prob_pct"]  # fmt: skip
    # The evening before, the newest TAF covers every hour and supersedes the old one's IFR.
    assert [got["d1_1900"][c] for c in summary] == [24, 30, "MVFR", "IFR", 0, 2, 25, 35, 1500, 30]
    # On the morning, "later" covers all but the first hour, which "new" still holds.
    assert [got["d0_0500"][c] for c in summary] == [24, 270, "LIFR", "LIFR", 1, 0, 10, None, None,
                                                    None]  # fmt: skip
    # The morning before, no TAF is out yet: nothing is known, not "no thunder".
    assert got["d1_0700"]["taf_day_hours"] == 0
    assert all(got["d1_0700"][c] is None for c in summary[1:])


def test_day_programs_cover_the_target_day_as_announced() -> None:
    versions = [
        {"program_id": "previous", "program_type": "gdp", "start_utc": utc(15, 13),
         "end_utc": utc(15, 18), "known_time": utc(15, 12, 30)},  # the day before only
        {"program_id": "gdp", "program_type": "gdp", "start_utc": utc(16, 18),
         "end_utc": utc(16, 22), "known_time": utc(15, 20)},
        {"program_id": "stop", "program_type": "ground_stop", "start_utc": utc(16, 6),
         "end_utc": utc(16, 7), "known_time": utc(16, 5, 55)},  # 01:00-02:00 on the day
    ]  # fmt: skip
    versions = [{"airport": "ORD", "scope": "general", "version": 1, **v} for v in versions]
    got = day_features(tables(TARGET, versions=versions), "d1_0700", "d1_1900", "d0_0500")
    flags = ["atc_gdp_now", "atc_gdp_at_target", "atc_gs_now", "atc_gs_at_target",
             "atc_gdp_issued_24h"]  # fmt: skip
    assert [got["d1_0700"][c] for c in flags] == [False, False, False, False, 0]
    assert [got["d1_1900"][c] for c in flags] == [False, True, False, False, 2]
    # Issued on the morning, the forecast still sees the night's ground stop on the day.
    assert [got["d0_0500"][c] for c in flags] == [False, True, False, True, 2]


def test_day_demand_and_the_previous_day() -> None:
    legs = [
        leg("a", "departure", utc(16, 12), dep_utc=utc(16, 12, 5), dep_delay=5),
        leg("b", "departure", utc(16, 12, 10)),
        leg("c", "departure", utc(16, 13, 5)),
        leg("late", "departure", utc(16, 4, 30)),  # 23:30 local on the 15th
        leg("in", "arrival", utc(16, 10)),  # lands 12:00 UTC on the target day
        leg("y1", "departure", utc(15, 1), dep_utc=utc(15, 1), dep_delay=0),  # 23 h before
        leg("y2", "departure", utc(15, 19, 30), dep_utc=utc(15, 20), dep_delay=30),
        leg("y0", "departure", utc(14, 23), dep_utc=utc(14, 23), dep_delay=90),  # 25 h before
        leg("ya", "arrival", utc(15, 20), arr_utc=utc(15, 22), arr_delay=0),
    ]
    got = day_features(tables(TARGET, legs=legs), "d1_1900")["d1_1900"]
    assert [got[c] for c in ("dem_departures", "dem_peak_departures", "dem_arrivals",
                             "dem_peak_arrivals")] == [3, 2, 1, 1]  # fmt: skip
    assert [got[c] for c in ("ops_dep_24h_n", "ops_dep_24h_delay_mean", "ops_dep_24h_late15_share",
                             "ops_arr_24h_n")] == [2, 15.0, 0.5, 1]  # fmt: skip
    assert got["cal_day_of_week"] == 2 and "cal_local_hour" not in got


def test_day_labels_summarize_the_local_day() -> None:
    t = tables(TARGET, legs=[
        leg("on time", "departure", utc(16, 12), dep_utc=utc(16, 12), dep_delay=0),
        leg("late", "departure", utc(16, 14), dep_utc=utc(16, 15, 10), dep_delay=70),
        leg("gone", "departure", utc(17, 3), cancelled=True),  # 22:00 local
        leg("before", "departure", utc(16, 4), cancelled=True),  # the 15th, local
    ], programs=[
        {"airport": "ORD", "program_type": "gdp", "scope": "general", "start_utc": utc(16, 20),
         "end_utc": utc(16, 22)},
        {"airport": "ORD", "program_type": "ground_stop", "scope": "general",
         "start_utc": utc(15, 18), "end_utc": utc(15, 19)},
    ])  # fmt: skip
    labelled = build.build("days", days(TARGET, TARGET + timedelta(days=1), ["d1_1900"]), t)
    assert labelled.select("y_n_departures", "y_late15_share", "y_late60_share",
                           "y_cancelled_share", "y_gdp", "y_ground_stop").rows() == [
        (3, 2 / 3, 2 / 3, 1 / 3, True, False)
    ]  # fmt: skip


def test_run_writes_days_by_issue_and_month(tmp_path: Path) -> None:
    t = tables(TARGET, legs=[leg("out", "departure", utc(16, 18))])
    core = tmp_path / "core"
    core.mkdir()
    names = {"calendar": t.calendar, "weather_obs": t.weather, "taf_hourly": t.taf,
             "gfs_mos": t.gfs_mos, "nbm": t.nbm,
             "atc_program_interval_version": t.program_versions,
             "atc_program_interval": t.programs, "flight_leg": t.legs}  # fmt: skip
    for name, frame in names.items():
        frame.write_parquet(core / f"{name}.parquet")
    build.run("days", date(2019, 7, 1), date(2019, 7, 1), ["d1_1900", "d0_0500"], tmp_path)
    issue = pl.read_parquet(tmp_path / "features/days/horizon=d1_1900/2019-07.parquet")
    assert issue.height == 31 and issue["target_date"].is_sorted()
    assert issue.filter(pl.col("target_date") == TARGET)["y_n_departures"].to_list() == [1]
    assert (tmp_path / "features/days/horizon=d0_0500/2019-07.parquet").is_file()
