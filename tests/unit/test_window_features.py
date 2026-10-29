"""The windowed ground-stop event of the hours spine: its label, and the window's features as
known at as_of."""

from datetime import UTC, datetime, timedelta

from ordfi.features import build
from ordfi.features.spines import hours
from tests.feature_tables import tables


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2019, 7, 15, hour, minute, tzinfo=UTC)


def leg(key: str, direction: str, sched: datetime) -> dict[str, object]:
    """A flight scheduled to leave ORD (or arrive there) at ``sched``."""
    block = timedelta(hours=2)
    dep, arr = (sched, sched + block) if direction == "departure" else (sched - block, sched)
    return {"flight_key": key, "direction": direction, "operating_carrier": "UA",
            "origin": "ORD" if direction == "departure" else "DEN",
            "dest": "LGA" if direction == "departure" else "ORD", "sched_dep_utc": dep,
            "sched_arr_utc": arr, "cancelled": False}  # fmt: skip


def test_the_window_label_and_its_features_cover_the_three_hours_from_the_target() -> None:
    stop = {"airport": "ORD", "program_type": "ground_stop", "scope": "general",
            "start_utc": at(14, 30), "end_utc": at(15, 10)}  # fmt: skip
    taf = [
        {"product_id": "t", "sent_at": at(11, 30), "known_time": at(11, 40),
         "valid_time": at(12) + timedelta(hours=h), "flight_category": "VFR",
         "worst_flight_category": "VFR", "is_amendment": False,
         **({"tempo_thunder": True} if h in (2, 3) else {}),
         **({"flight_category": "IFR", "worst_flight_category": "IFR"} if h == 4 else {})}
        for h in range(30)
    ]  # fmt: skip
    t = tables(
        at(0).date(),
        programs=[stop],
        versions=[{**stop, "program_id": "s", "version": 1, "known_time": at(12, 30)}],
        taf=taf,
        legs=[leg("d1", "departure", at(12, 15)), leg("d2", "departure", at(13, 40)),
              leg("d3", "departure", at(14, 5)), leg("a1", "arrival", at(14, 20)),
              leg("a2", "arrival", at(16, 10))],
    )  # fmt: skip
    got = build.build("hours", hours(at(11), at(18), ["1h"]), t).sort("target_utc")
    columns = ["y_ground_stop", "y_ground_stop_3h", "taf_win_thunder_hours", "taf_win_ifr_hours",
               "atc_win_gs_announced", "dem_win_departures", "dem_win_arrivals"]  # fmt: skip
    assert got.select(columns).rows() == [
        # 11:00-14:00, forecast at 10:00: before the stop, the TAF and its announcement.
        (False, False, None, None, False, 2, 0),
        (False, True, None, None, False, 3, 1),  # forecast at 11:00: the TAF is out at 11:40
        (False, True, 2, 0, False, 2, 1),  # 13:00-16:00 at 12:00: thunder at 14 and 15
        (True, True, 2, 1, True, 1, 2),  # announced at 12:30 to cover 14:30-15:10
        (True, True, 1, 1, True, 0, 1),
        (False, False, 0, 1, False, 0, 1),  # 16:00-19:00: the stop ended at 15:10
        (False, False, 0, 0, False, 0, 0),
    ]
