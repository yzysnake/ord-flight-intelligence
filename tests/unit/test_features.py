"""As-of features on hand-built inputs: what each group reports, the labels and the CLI run."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl

from ordfi.features import build
from ordfi.features.knowledge import visible
from ordfi.features.spines import departures, hours
from tests.feature_tables import tables

DAY = date(2019, 7, 15)


def at(hour: int, minute: int = 0, day: int = 15) -> datetime:
    return datetime(2019, 7, day, hour, minute, tzinfo=UTC)


def spine(*rows: tuple[datetime, datetime], flight_key: str | None = None) -> pl.DataFrame:
    """Spine rows (as_of, target_utc), for one flight if given."""
    frame = pl.DataFrame(
        {"as_of": [r[0] for r in rows], "target_utc": [r[1] for r in rows], "horizon": "x"},
        schema={"as_of": pl.Datetime("us", "UTC"), "target_utc": pl.Datetime("us", "UTC"),
                "horizon": pl.String()},
    )  # fmt: skip
    return frame if flight_key is None else frame.with_columns(flight_key=pl.lit(flight_key))


def leg(key: str, direction: str, sched_dep: datetime, **fields: object) -> dict[str, object]:
    return {
        "flight_key": key, "direction": direction, "operating_carrier": "UA",
        "origin": "DEN" if direction == "arrival" else "ORD",
        "dest": "ORD" if direction == "arrival" else "LGA", "sched_dep_utc": sched_dep,
        "sched_arr_utc": sched_dep + timedelta(hours=2), "cancelled": False, **fields,
    }  # fmt: skip


def pick(frame: pl.DataFrame, *columns: str) -> list[tuple[object, ...]]:
    return frame.sort("row").select(columns).rows()


def test_visible_hides_rows_and_fields_not_yet_known() -> None:
    t = tables(DAY, legs=[
        leg("out", "departure", at(12), tail_number="N1", dep_utc=at(12, 20), dep_delay=20),
        leg("next_week", "departure", at(12) + timedelta(days=8)),
    ], versions=[
        {"program_id": "p", "version": 1, "known_time": at(9), "valid_to": at(10)},
        {"program_id": "p", "version": 2, "known_time": at(10)},
    ])  # fmt: skip
    before = visible(t, at(5))  # 7 h out: schedule known, tail not yet
    assert before.legs.select("flight_key", "tail_number", "dep_utc", "cancelled").rows() == [
        ("out", None, None, None)
    ]
    after = visible(t, at(12, 30)).legs.filter(pl.col("flight_key") == "out")
    assert after.select("tail_number", "dep_utc", "dep_delay").row(0) == ("N1", at(12, 20), 20)
    known_versions = visible(t, at(9, 30)).program_versions
    assert known_versions.select("version", "valid_to").rows() == [(1, None)]


def test_weather_takes_the_latest_observation_known() -> None:
    t = tables(DAY, weather=[
        {"valid_time": at(10, 51), "known_time": at(11, 1), "flight_category": "VFR",
         "visibility_mi": 10.0, "report_type": "routine"},
        {"valid_time": at(11, 51), "known_time": at(12, 1), "flight_category": "IFR",
         "visibility_mi": 2.0, "has_thunder": True, "report_type": "routine"},
    ])  # fmt: skip
    got = build.features("hours", spine((at(12), at(13)), (at(12, 1), at(13))), t)
    assert pick(got, "wx_age_min", "wx_flight_category", "wx_min_visibility_3h",
                "wx_thunder_3h") == [(69, "VFR", 10.0, False), (10, "IFR", 2.0, True)]  # fmt: skip


def test_taf_takes_the_latest_issue_known_for_the_target_hour() -> None:
    def hour(product: str, sent: datetime, category: str, **fields: object) -> dict[str, object]:
        return {"product_id": product, "sent_at": sent, "known_time": sent + timedelta(minutes=10),
                "valid_time": at(18), "flight_category": category, "has_thunder": False,
                "has_snow": False, **fields}  # fmt: skip

    t = tables(DAY, taf=[
        hour("a", at(5, 20), "VFR"), hour("b", at(11, 20), "IFR", tempo_thunder=True),
    ])  # fmt: skip
    got = build.features("hours", spine((at(11), at(18, 30)), (at(12), at(18, 30))), t)
    assert pick(got, "taf_available", "taf_flight_category", "taf_lead_min", "taf_thunder") == [
        (True, "VFR", 760, False), (True, "IFR", 400, True),
    ]  # fmt: skip
    beyond = build.features("hours", spine((at(12), at(20))), t)
    assert pick(beyond, "taf_available", "taf_thunder") == [(False, None)]


def test_programs_show_the_state_as_announced() -> None:
    def version(
        pid: str,
        kind: str,
        v: int,
        known: datetime,
        start: datetime,
        end: datetime,
        valid_to: datetime | None = None,
        scope: str = "general",
    ) -> dict[str, object]:
        return {"program_id": pid, "airport": "ORD", "program_type": kind, "scope": scope,
                "version": v, "known_time": known, "start_utc": start, "end_utc": end,
                "valid_to": valid_to}  # fmt: skip

    t = tables(DAY, versions=[
        version("gdp", "gdp", 1, at(12), at(13), at(18), valid_to=at(15)),
        version("gdp", "gdp", 2, at(15), at(13), at(16)),  # shortened
        version("gs", "ground_stop", 1, at(14), at(14), at(15)),
        version("nks", "ground_stop", 1, at(14, 10), at(14, 10), at(16), scope="carrier"),
    ])  # fmt: skip
    got = build.features("hours", spine((at(12, 30), at(17)), (at(14, 30), at(17)),
                                        (at(15, 30), at(17))), t)  # fmt: skip
    assert pick(got, "atc_gdp_now", "atc_gdp_since_start_min", "atc_gdp_to_end_min",
                "atc_gdp_at_target", "atc_gs_now", "atc_gs_to_end_min", "atc_gs_issued_24h") == [
        (False, None, None, True, False, None, 0),  # announced, not started
        (True, 90, 210, True, True, 30, 1),
        (True, 150, 30, False, False, None, 1),  # shortened: ends 16:00, before the target
    ]  # fmt: skip


def test_operations_count_what_happened_in_the_window() -> None:
    t = tables(DAY, legs=[
        leg("d1", "departure", at(11, 5), dep_utc=at(11, 15), dep_delay=10),
        leg("d2", "departure", at(11), dep_utc=at(11, 40), dep_delay=40),
        leg("d3", "departure", at(11, 50), dep_utc=at(12, 5), dep_delay=15),  # after as_of
        leg("a1", "arrival", at(9, 30), arr_utc=at(11, 30), arr_delay=20),
    ])  # fmt: skip
    got = build.features("hours", spine((at(12), at(13))), t)
    assert pick(got, "ops_dep_1h_n", "ops_dep_1h_delay_mean", "ops_dep_1h_late15_share",
                "ops_sched_dep_1h_n", "ops_dep_flow_1h", "ops_arr_1h_n",
                "ops_arr_1h_delay_mean") == [(2, 25.0, 0.5, 2, 1.0, 1, 20.0)]  # fmt: skip


def test_inbound_needs_the_tail_and_reports_what_is_known() -> None:
    t = tables(DAY, legs=[
        leg("out", "departure", at(18), tail_number="N1"),
        leg("in", "arrival", at(14), sched_arr_utc=at(17), tail_number="N1",
            dep_utc=at(14, 45), dep_delay=45, arr_utc=at(17, 40), arr_delay=40),
    ])  # fmt: skip
    rows = spine((at(11), at(18)), (at(14, 30), at(18)), (at(15), at(18)), (at(17, 45), at(18)),
                 flight_key="out")  # fmt: skip
    got = build.features("departures", rows, t)
    assert pick(got, "inb_found", "inb_departed", "inb_arrived", "inb_known_late_min",
                "inb_slack_min") == [
        (None, None, None, None, None),  # 7 h out: tail not known yet
        (True, False, False, 30, 30),  # overdue 30 min
        (True, True, False, 45, 15),  # left 45 min late
        (True, True, True, 40, 20),  # landed 40 min late
    ]  # fmt: skip


def test_labels_bucket_delays_and_summarize_hours() -> None:
    t = tables(DAY, legs=[
        leg("early", "departure", at(14), tail_number="N1", dep_utc=at(13, 55), dep_delay=-5),
        leg("late", "departure", at(14, 10), tail_number="N2", dep_utc=at(15, 20), dep_delay=70),
        leg("gone", "departure", at(14, 20), cancelled=True),  # BTS: no tail
    ], programs=[
        {"airport": "ORD", "program_type": "gdp", "scope": "general", "start_utc": at(13, 30),
         "end_utc": at(14, 10)},
    ])  # fmt: skip
    flights = build.build("departures", departures(t.legs, at(0), at(23), ["1h"]), t)
    assert flights.sort("flight_key").select(
        "flight_key", "y_dep_bucket", "y_no_tail", "inb_found"
    ).rows() == [
        ("early", "<=0", False, False), ("gone", "cancelled", True, None),
        ("late", "60-119", False, False),
    ]  # fmt: skip
    by_hour = build.build("hours", hours(at(13), at(16), ["1h"]), t)
    assert by_hour.sort("target_utc").select(
        "y_n_departures", "y_late15_share", "y_cancelled_share", "y_gdp"
    ).rows() == [(0, None, None, True), (3, 2 / 3, 1 / 3, True), (0, None, None, False)]


def test_run_writes_one_file_per_horizon_and_month(tmp_path: Path) -> None:
    t = tables(DAY, legs=[leg("out", "departure", at(18), tail_number="N1")])
    core = tmp_path / "core"
    core.mkdir()
    names = {"calendar": t.calendar, "weather_obs": t.weather, "taf_hourly": t.taf,
             "atc_program_interval_version": t.program_versions,
             "atc_program_interval": t.programs, "flight_leg": t.legs}  # fmt: skip
    for name, frame in names.items():
        frame.write_parquet(core / f"{name}.parquet")
    build.run("departures", date(2019, 7, 1), date(2019, 7, 1), ["6h", "1h"], tmp_path)
    written = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.parquet")
                     if p.parts[-3] == "departures")  # fmt: skip
    assert written == ["features/departures/horizon=1h/2019-07.parquet",
                       "features/departures/horizon=6h/2019-07.parquet"]  # fmt: skip
    six = pl.read_parquet(tmp_path / "features/departures/horizon=6h/2019-07.parquet")
    assert six.select("flight_key", "as_of", "inb_found", "y_no_tail", "licence_class").rows() == [
        ("out", at(12), False, False, "public-domain")
    ]
