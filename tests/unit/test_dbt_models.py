"""dbt core models on a tiny synthetic stage: calendar, flight legs, weather and ATC programs."""

import hashlib
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from ordfi.ingest import atcscc, iem, taf
from ordfi.ingest.http import Download
from ordfi.ingest.raw import commit_download
from ordfi.settings import project_root

UTC_TS = pl.Datetime("us", "UTC")
FETCHED = datetime(2026, 10, 27, 5, 0, tzinfo=UTC)
BTS_SHARED: dict[str, pl.DataType] = {
    "flight_date": pl.Date(), "tail_number": pl.String(), "origin": pl.String(),
    "dest": pl.String(), "origin_airport_id": pl.Int64(), "dest_airport_id": pl.Int64(),
    "crs_dep_time": pl.String(), "dep_time": pl.String(), "crs_arr_time": pl.String(),
    "arr_time": pl.String(), "wheels_off": pl.String(), "wheels_on": pl.String(),
    "sched_dep_utc": UTC_TS, "sched_arr_utc": UTC_TS, "dep_utc": UTC_TS, "arr_utc": UTC_TS,
    "wheels_off_utc": UTC_TS, "wheels_on_utc": UTC_TS, "origin_tz": pl.String(),
    "dest_tz": pl.String(), "dep_delay": pl.Int32(), "dep_del15": pl.Boolean(),
    "arr_delay": pl.Int32(), "arr_del15": pl.Boolean(), "taxi_out": pl.Int32(),
    "taxi_in": pl.Int32(), "cancelled": pl.Boolean(), "cancellation_code": pl.String(),
    "diverted": pl.Boolean(), "div_reached_dest": pl.Boolean(), "div_arr_delay": pl.Int32(),
    "crs_elapsed_time": pl.Int32(), "actual_elapsed_time": pl.Int32(), "air_time": pl.Int32(),
    "distance": pl.Float64(), "carrier_delay": pl.Int32(), "weather_delay": pl.Int32(),
    "nas_delay": pl.Int32(), "security_delay": pl.Int32(), "late_aircraft_delay": pl.Int32(),
    "total_add_gtime": pl.Int32(), "raw_sha256": pl.String(), "known_time": UTC_TS,
    "licence_class": pl.String(),
}  # fmt: skip
MARKETING = {
    **BTS_SHARED, "operating_airline": pl.String(), "flight_number_operating_airline": pl.Int64(),
    "marketing_airline_network": pl.String(), "flight_number_marketing_airline": pl.Int64(),
}  # fmt: skip
REPORTING = {
    **BTS_SHARED,
    "reporting_airline": pl.String(),
    "flight_number_reporting_airline": pl.Int64(),
}
EXTRA = {"known_time": UTC_TS, "licence_class": pl.String()}


def at(day: int, hour: int, minute: int, month: int = 7, year: int = 2019) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def aug5(hour: int, minute: int) -> datetime:
    return at(5, hour, minute, month=8)


def leg(day: date, origin: str, dest: str, dep: str, sched_dep: datetime, sched_arr: datetime,
        **fields: object) -> dict[str, object]:  # fmt: skip
    return {
        "flight_date": day, "origin": origin, "dest": dest, "crs_dep_time": dep,
        "sched_dep_utc": sched_dep, "sched_arr_utc": sched_arr, "cancelled": False,
        "diverted": False, "known_time": FETCHED, "licence_class": "public-domain", **fields,
    }  # fmt: skip


def write(
    root: Path, relative: str, rows: list[dict[str, object]], schema: Mapping[str, pl.DataType]
) -> None:
    """One stage file; columns missing from a row are null, as in the real stage."""
    path = root / "stage" / relative / "data.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows, schema=dict(schema)).write_parquet(path)


def write_stage(root: Path) -> None:
    july15 = date(2019, 7, 15)
    gojet = {"operating_airline": "G7", "marketing_airline_network": "UA"}
    write(root, "bts_ontime_marketing/year=2019/month=07", [
        leg(july15, "ORD", "SFO", "0700", at(15, 12, 0), at(15, 16, 30), operating_airline="UA",
            flight_number_operating_airline=1, marketing_airline_network="UA",
            tail_number="N12345"),
        # One aircraft: the evening before (not an ORD day), an ORD turn, then a cancelled leg.
        leg(date(2019, 7, 14), "DSM", "LGA", "1700", at(14, 22, 0), at(14, 23, 30),
            flight_number_operating_airline=4400, tail_number="N501GJ", dep_utc=at(14, 22, 0),
            arr_utc=at(14, 23, 35), **gojet),
        leg(july15, "LGA", "ORD", "0600", at(15, 10, 0), at(15, 12, 45),
            flight_number_operating_airline=4507, tail_number="n501gj", dep_utc=at(15, 10, 10),
            arr_utc=at(15, 12, 55), arr_delay=10, **gojet),
        leg(july15, "ORD", "DSM", "0830", at(15, 13, 30), at(15, 14, 45),
            flight_number_operating_airline=4508, tail_number="N501GJ", dep_utc=at(15, 13, 40),
            arr_utc=at(15, 14, 50), **gojet),
        leg(july15, "DSM", "ORD", "1100", at(15, 16, 0), at(15, 17, 15),
            flight_number_operating_airline=4509, tail_number="N501GJ", cancelled=True, **gojet),
        leg(july15, "PDX", "SLC", "1315", at(15, 20, 15), at(15, 22, 7), operating_airline="DL",
            flight_number_operating_airline=1209, marketing_airline_network="DL",
            tail_number="N999DN"),  # never at ORD
    ], MARKETING)  # fmt: skip
    write(root, "bts_ontime_reporting/year=2017/month=07", [
        leg(date(2017, 7, 15), "LGA", "ORD", "0600", at(15, 10, 0, year=2017),
            at(15, 12, 45, year=2017), reporting_airline="AA", flight_number_reporting_airline=2),
    ], REPORTING)  # fmt: skip
    write(root, "bts_ontime_reporting/year=2019/month=07", [  # 2018+ comes from marketing
        leg(july15, "ORD", "SFO", "0700", at(15, 12, 0), at(15, 16, 30), reporting_airline="UA",
            flight_number_reporting_airline=1),
    ], REPORTING)  # fmt: skip

    def obs(when: datetime, kind: str, **fields: object) -> dict[str, object]:
        return {"station": "ORD", "valid": when, "report_type": kind,
                "known_time": when + timedelta(minutes=10), "licence_class": "public-domain",
                **fields}  # fmt: skip

    write(root, "iem_asos_metar/station=ORD/year=2019", [
        obs(at(15, 0, 5), "hfmetar", vsby=10.0),
        obs(at(15, 0, 9), "special", tmpf=75.0, vsby=2.0, skyc1="BKN", skyl1=800.0,
            wxcodes="TSRA"),
        obs(at(15, 0, 51), "routine", tmpf=78.0, sknt=3.0, vsby=10.0, skyc1="FEW", skyl1=4500.0,
            p01i=iem.TRACE),
        obs(at(15, 2, 51), "routine", tmpf=70.0, vsby=0.5, skyc1="OVC", skyl1=400.0),
    ], {**iem.METAR_SCHEMA, **EXTRA})  # fmt: skip

    def listed(day: date, number: int, title: str, category: str, sent: datetime,
               element: str = "ORD/ZAU") -> dict[str, object]:  # fmt: skip
        return {"adv_date": day, "number": number, "control_element": element, "title": title,
                "category": category, "is_cancellation": atcscc.is_cancellation(title),
                "ord_related": True, "send_time": sent, "known_time": sent,
                "licence_class": "public-domain"}  # fmt: skip

    def text(day: date, number: int, period: str | None, element: str = "ORD",
             **fields: object) -> dict[str, object]:  # fmt: skip
        return {"adv_date": day, "number": number, "ctl_element": element, "period": period,
                "average_delay": "130", "licence_class": "public-domain", **fields}  # fmt: skip

    july31, august1, august5 = date(2019, 7, 31), date(2019, 8, 1), date(2019, 8, 5)

    write(root, "faa_atcscc_advisories/index/year=2019", [
        listed(july15, 3, "CDM GROUND DELAY PROGRAM", "gdp", at(15, 0, 57)),
        listed(july15, 7, "ROUTE RQD", "reroute", at(15, 1, 0), "DCC"),
        listed(july31, 5, "CDM GROUND STOP", "ground_stop", at(31, 23, 40)),
        listed(july31, 5, "CDM GROUND STOP", "ground_stop", at(31, 23, 41)),  # re-sent
        listed(august1, 2, "CDM GROUND DELAY PROGRAM", "gdp", at(1, 0, 10, month=8)),
        listed(august1, 4, "ORD GROUND STOP", "ground_stop", at(1, 20, 59, month=8)),
        # 5 Aug: a GDP shortened, then cancelled; a stop extended after it lapsed, partly
        # cancelled, cancelled and re-issued backdated; a carrier-only stop beside it.
        listed(august5, 11, "CDM PROPOSED GROUND DELAY PROGRAM", "gdp", aug5(13, 40)),
        listed(august5, 10, "CDM GROUND DELAY PROGRAM", "gdp", aug5(14, 0)),
        listed(august5, 12, "CDM GROUND STOP", "ground_stop", aug5(15, 10)),
        listed(august5, 13, "ORD GROUND STOP FOR NKS ONLY", "ground_stop", aug5(15, 30)),
        listed(august5, 14, "CDM GROUND DELAY PROGRAM", "gdp", aug5(16, 0)),
        listed(august5, 15, "CDM GROUND STOP", "ground_stop", aug5(16, 5)),
        listed(august5, 16, "PARTIAL ORD GROUND STOP CANCELLATION", "ground_stop", aug5(16, 20)),
        listed(august5, 17, "CDM GS CNX", "ground_stop", aug5(16, 30)),
        listed(august5, 18, "CDM GROUND STOP", "ground_stop", aug5(16, 40)),
        listed(august5, 20, "CDM GROUND DELAY PROGRAM CNX", "gdp", aug5(19, 2)),
    ], {**atcscc.INDEX_SCHEMA, "licence_class": pl.String()})  # fmt: skip
    write(root, "faa_atcscc_advisories/advisories/year=2019", [
        text(july15, 3, "14/2219Z - 15/0259Z"),
        text(july15, 7, "ETD 152030 TO 160100", "KORD KMDW"),
        text(july31, 5, "UNTIL 0100Z"),
        text(august1, 2, "31/2300Z - 01/0200Z"),
        text(august1, 4, "142056Z-012230Z"),  # start day mistyped (14 for 01)
        text(august5, 11, "05/1500Z - 05/2359Z"),
        text(august5, 10, "05/1500Z - 05/2359Z", program_rate="68/68/72"),
        text(august5, 12, "05/1505Z - 05/1600Z"),
        text(august5, 13, "05/1530Z - 05/1700Z"),
        text(august5, 14, "05/1500Z - 05/2159Z", program_rate="64"),
        text(august5, 15, "05/1605Z - 05/1700Z"),
        text(august5, 16, None),
        text(august5, 17, None),
        text(august5, 18, "05/1625Z - 05/1730Z"),
        text(august5, 20, "05/1900Z - 05/2159Z"),
    ], {**atcscc.ADVISORY_SCHEMA, "licence_class": pl.String()})  # fmt: skip
    write_taf(root)


# A routine TAF: VFR, then MVFR thunderstorms from 18Z with a TEMPO to IFR, then VFR.
BULLETIN = """688
FTUS43 KLOT 150520
TAFORD
TAF
KORD 150520Z 1506/1612 20005KT P6SM SCT050
     FM151800 22012G20KT 4SM -TSRA BKN030CB
      TEMPO 1520/1522 1SM +TSRA OVC008CB
     FM160000 24008KT P6SM SKC="""


def write_taf(root: Path) -> None:
    """Stage the TAF tables the way the pipeline does: a raw bulletin file, then the parser."""
    payload = f"\x01\n{BULLETIN}\n\x03\n".encode("latin-1")
    upload = root / "upload.txt"
    upload.parent.mkdir(parents=True, exist_ok=True)
    upload.write_bytes(payload)
    dl = Download(
        url="https://example.test/retrieve.py", tmp_path=upload, fetched_at=FETCHED, status=200,
        sha256=hashlib.sha256(payload).hexdigest(), size_bytes=len(payload),
        content_type="text/plain", last_modified=None, etag=None,
    )  # fmt: skip
    commit_download(root, taf.SOURCE_ID, "ORD/bulletins/2019-07", "b.txt", dl, "public-domain",
                    partition="ORD/2019")  # fmt: skip
    taf.stage_year(root, 2019)


Core = Callable[[str], pl.DataFrame]  # reads one model's Parquet output


@pytest.fixture(scope="module")
def core(tmp_path_factory: pytest.TempPathFactory) -> Core:
    """Build every model once with `dbt build` (models and their tests) on the synthetic stage."""
    tmp = tmp_path_factory.mktemp("dbt")
    data = tmp / "data"
    write_stage(data)
    for folder in ("core", "warehouse"):
        (data / folder).mkdir(parents=True)
    dbt_dir = project_root() / "dbt"
    # A subprocess, as `make dbt-build` runs it: dbt-duckdb keeps process-wide connections.
    build = subprocess.run(
        [str(Path(sys.executable).with_name("dbt")), "build", "--project-dir", str(dbt_dir),
         "--profiles-dir", str(dbt_dir), "--target-path", str(tmp / "target"),
         "--log-path", str(tmp / "logs")],
        env={**os.environ, "ORDFI_DATA_DIR": str(data)}, capture_output=True, text=True,
        check=False,
    )  # fmt: skip
    assert build.returncode == 0, build.stdout[-4000:]
    return lambda model: pl.read_parquet(data / "core" / f"{model}.parquet")


def test_calendar_spans_2000_to_2030(core: Core) -> None:
    calendar = core("calendar")
    assert (calendar.height, calendar["date"].min(), calendar["date"].max()) == (
        11323, date(2000, 1, 1), date(2030, 12, 31)
    )  # fmt: skip


def test_flight_legs_take_marketing_from_2018_and_reporting_before(core: Core) -> None:
    legs = core("flight_leg").sort("flight_key")
    assert legs.select(
        "flight_key", "source_table", "direction", "marketing_carrier", "sched_ord_utc"
    ).rows() == [
        ("2017-07-15_AA_2_LGA_ORD_0600", "reporting", "arrival", None, at(15, 12, 45, year=2017)),
        ("2019-07-15_G7_4507_LGA_ORD_0600", "marketing", "arrival", "UA", at(15, 12, 45)),
        ("2019-07-15_G7_4508_ORD_DSM_0830", "marketing", "departure", "UA", at(15, 13, 30)),
        ("2019-07-15_G7_4509_DSM_ORD_1100", "marketing", "arrival", "UA", at(15, 17, 15)),
        ("2019-07-15_UA_1_ORD_SFO_0700", "marketing", "departure", "UA", at(15, 12, 0)),
    ]
    assert legs.filter(pl.col("flight_number") == 4507)["tail_number"].to_list() == ["N501GJ"]


def test_aircraft_rotation_links_each_flown_leg_to_the_previous_one(core: Core) -> None:
    rotation = core("aircraft_rotation").sort("tail_number", "flight_date", "leg_seq")
    assert rotation.select(
        "tail_number", "leg_seq", "legs_in_day", "flight_key", "prev_flight_key",
        "station_continuous", "sched_ground_min", "actual_ground_min",
    ).rows() == [
        ("N12345", 1, 1, "2019-07-15_UA_1_ORD_SFO_0700", None, None, None, None),
        ("N501GJ", 1, 2, "2019-07-15_G7_4507_LGA_ORD_0600", "2019-07-14_G7_4400_DSM_LGA_1700",
         True, 630, 635),  # linked to the previous evening; the cancelled leg is left out
        ("N501GJ", 2, 2, "2019-07-15_G7_4508_ORD_DSM_0830", "2019-07-15_G7_4507_LGA_ORD_0600",
         True, 45, 45),
    ]  # fmt: skip


def test_weather_obs_drops_hfmetar_and_derives_categories(core: Core) -> None:
    obs = core("weather_obs").sort("valid_time")
    assert obs.select("report_type", "ceiling_ft", "flight_category", "has_thunder").rows() == [
        ("special", 800.0, "IFR", True),
        ("routine", None, "VFR", False),  # FEW is not a ceiling
        ("routine", 400.0, "LIFR", False),
    ]


def test_weather_hours_keep_gaps_and_latest_values(core: Core) -> None:
    hours = core("weather_obs_hourly").sort("valid_time")
    assert hours.select(
        "valid_time", "n_obs", pl.col("temp_c").round(2), "worst_flight_category", "any_thunder",
        "known_time",
    ).rows() == [
        (at(15, 0, 0), 2, 25.56, "IFR", True, at(15, 1, 1)),  # temperature from 00:51
        (at(15, 1, 0), 0, None, None, None, None),
        (at(15, 2, 0), 1, 21.11, "LIFR", False, at(15, 3, 1)),
    ]  # fmt: skip


def test_atc_program_periods_resolve_across_days_and_months(core: Core) -> None:
    programs = core("atc_program").filter(pl.col("adv_date") < date(2019, 8, 5)).sort("issued_at")
    assert programs.select(
        "adv_date", "number", "period_format", "issued_at", "start_utc", "end_utc",
        "average_delay_min",
    ).rows() == [
        (date(2019, 7, 15), 3, "dated", at(15, 0, 57), at(14, 22, 19), at(15, 2, 59), 130),
        (date(2019, 7, 31), 5, "until", at(31, 23, 41), at(31, 23, 41), at(1, 1, 0, month=8), 130),
        (date(2019, 8, 1), 2, "dated", at(1, 0, 10, month=8), at(31, 23, 0), at(1, 2, 0, month=8),
         130),
        (date(2019, 8, 1), 4, "dated", at(1, 20, 59, month=8), None, None, 130),  # implausible
    ]  # fmt: skip


def test_atc_program_intervals_chain_revisions_cancellations_and_scopes(core: Core) -> None:
    programs = core("atc_program_interval").sort("start_utc", "program_id")
    assert programs.select(
        "program_id", "scope", "start_utc", "end_utc", "end_reason", "n_advisories",
    ).rows() == [
        ("ORD-gdp-20190715-003", "general", at(14, 22, 19), at(15, 2, 59), "expired", 1),
        ("ORD-gdp-20190801-002", "general", at(31, 23, 0), at(1, 2, 0, month=8), "expired", 1),
        ("ORD-ground_stop-20190731-005", "general", at(31, 23, 41), at(1, 1, 0, month=8),
         "expired", 1),
        # Its period is implausible, so only its send time is known.
        ("ORD-ground_stop-20190801-004", "general", at(1, 20, 59, month=8), None, "unknown", 1),
        # The proposal is left out; the revision shortened the GDP, then it was cancelled.
        ("ORD-gdp-20190805-010", "general", aug5(15, 0), aug5(19, 0), "cancelled", 2),
        # Extended 5 minutes after it lapsed; the partial cancellation does not end it.
        ("ORD-ground_stop-20190805-012", "general", aug5(15, 5), aug5(16, 30), "cancelled", 2),
        # The carrier-only stop runs on past the general stop's cancellation.
        ("ORD-ground_stop-20190805-013", "carrier", aug5(15, 30), aug5(17, 0), "expired", 1),
        # Re-issued backdated to 16:25; it starts at the cancellation.
        ("ORD-ground_stop-20190805-018", "general", aug5(16, 30), aug5(17, 30), "expired", 1),
    ]  # fmt: skip
    gdp = programs.filter(pl.col("program_id") == "ORD-gdp-20190805-010")
    assert gdp.select("planned_end_utc", "min_program_rate", "cancelled_at", "known_time").row(
        0
    ) == (aug5(23, 59), 64, aug5(19, 2), aug5(19, 2))  # fmt: skip


def test_atc_program_interval_versions_replay_each_advisory(core: Core) -> None:
    versions = core("atc_program_interval_version").filter(
        pl.col("program_id") == "ORD-ground_stop-20190805-012"
    )
    assert versions.sort("version").select(
        "version", "change", "start_utc", "end_utc", "known_time", "valid_to",
    ).rows() == [
        (1, "issued", aug5(15, 5), aug5(16, 0), aug5(15, 10), aug5(16, 5)),
        (2, "revised", aug5(15, 5), aug5(17, 0), aug5(16, 5), aug5(16, 20)),
        (3, "partly cancelled", aug5(15, 5), aug5(17, 0), aug5(16, 20), aug5(16, 30)),
        (4, "cancelled", aug5(15, 5), aug5(16, 30), aug5(16, 30), None),
    ]  # fmt: skip


def test_taf_hourly_expands_prevailing_and_overlay_groups(core: Core) -> None:
    hours = core("taf_hourly").sort("valid_time")
    assert hours.height == 30  # 15 Jul 06Z to 16 Jul 12Z
    picked = hours.filter(pl.col("valid_time").is_in([at(15, 17, 0), at(15, 20, 0), at(16, 0, 0)]))
    assert picked.select(
        "valid_time", "prevailing_kind", "flight_category", "tempo_thunder",
        "worst_flight_category", "lead_hours",
    ).rows() == [
        (at(15, 17, 0), "initial", "VFR", None, "VFR", 11 + 40 / 60),
        (at(15, 20, 0), "FM", "MVFR", True, "IFR", 14 + 40 / 60),  # TEMPO 1 SM, OVC008
        (at(16, 0, 0), "FM", "VFR", None, "VFR", 18 + 40 / 60),
    ]  # fmt: skip
    assert hours["known_time"].unique().to_list() == [at(15, 5, 30)]
