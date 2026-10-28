"""Station guidance features: the latest run known, the projections near the target, the periods
overlapping it, and nothing beyond the runs' reach."""

from datetime import UTC, date, datetime, timedelta

import polars as pl

from ordfi.features import build
from ordfi.features.spines import days
from tests.feature_tables import tables


def utc(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2019, 7, day, hour, minute, tzinfo=UTC)


def run(runtime: datetime, lag: timedelta, **by_hour: dict[str, object]) -> list[dict[str, object]]:
    """A run's 3-hourly projections from 6 to 72 h, VFR and calm unless ``by_hour`` (keyed
    ``h<lead>``) says otherwise."""
    return [
        {"runtime": runtime, "known_time": runtime + lag,
         "valid_time": runtime + timedelta(hours=lead), "flight_category": "VFR",
         "wind_speed_kt": 5, **by_hour.get(f"h{lead}", {})}
        for lead in range(6, 73, 3)
    ]  # fmt: skip


def hour_spine(*rows: tuple[datetime, datetime]) -> pl.DataFrame:
    return pl.DataFrame(
        {"as_of": [r[0] for r in rows], "target_utc": [r[1] for r in rows], "horizon": "x"},
        schema={"as_of": pl.Datetime("us", "UTC"), "target_utc": pl.Datetime("us", "UTC"),
                "horizon": pl.String()},
    )  # fmt: skip


MOS = timedelta(hours=5)
GFS = [
    *run(utc(15, 0), MOS, h12={"flight_category": "IFR", "ceiling_category": 3},
         h15={"thunder_6h_pct": 40}, h18={"thunder_6h_pct": 10}),
    *run(utc(15, 6), MOS, h6={"flight_category": "MVFR", "wind_speed_kt": 25},
         h9={"thunder_6h_pct": 70}),
]  # fmt: skip


def test_hours_take_the_latest_known_run_near_the_target() -> None:
    t = tables(date(2019, 7, 15), gfs_mos=GFS)
    rows = hour_spine((utc(15, 10), utc(15, 12)), (utc(15, 11, 30), utc(15, 12)),
                      (utc(15, 10), utc(18, 12)))  # fmt: skip
    got = build.features("hours", rows, t).sort("row")
    picked = ["mos_projections", "mos_flight_category", "mos_ceiling_category",
              "mos_wind_speed_kt", "mos_thunder_6h_pct", "mos_age_min"]  # fmt: skip
    assert got.select(picked).rows() == [
        # Only the 00Z run is known: its 12Z IFR; thunder in the periods overlapping 12-13Z.
        (1, "IFR", 3, 5, 40, 600),
        # The 06Z run is known by 11:00 and replaces it: MVFR and 25 kt at 12Z.
        (1, "MVFR", None, 25, 70, 330),
        (0, None, None, None, None, None),  # beyond 72 h of any known run
    ]
    assert got["nbm_projections"].to_list() == [0, 0, 0]  # no NBM in this world


def test_days_sum_up_every_projection_of_the_local_day() -> None:
    nbm = run(utc(15, 1), timedelta(minutes=70),
              h12={"flight_category": "LIFR", "ceiling_ft": 300, "ifr_ceiling_pct": 80},
              h15={"thunder_3h_pct": 55}, h36={"ceiling_ft": 2000, "wind_gust_kt": 30},
              h72={"thunder_3h_pct": 90})  # fmt: skip
    t = tables(date(2019, 7, 15), gfs_mos=GFS, nbm=nbm)
    target = date(2019, 7, 16)  # 05Z on the 16th to 05Z on the 17th
    got = build.features("days", days(target, target + timedelta(days=1), ["d1_1900"]), t)
    row = got.row(0, named=True)  # issued 00Z on the 16th: both runs known
    assert row["nbm_projections"] == 9  # 03Z (90 min before 05Z) .. 03Z the next day
    assert (row["nbm_flight_category"], row["nbm_ceiling_ft"], row["nbm_wind_gust_kt"]) == (
        "VFR", 2000, 30
    )  # fmt: skip  # the 15th's LIFR is the day before
    assert row["nbm_thunder_3h_pct"] is None  # 90 % falls on the 18th
    assert row["mos_projections"] == 9 and row["mos_age_min"] == 18 * 60
