"""BTS staging on a synthetic monthly ZIP: names, types, UTC derivation and quality checks."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from ordfi.ingest import bts
from ordfi.ingest.http import Download
from ordfi.ingest.raw import commit_download
from tests.bts_sample import ROWS, ZONES, write_zip


@pytest.fixture
def staged_frame(tmp_path: Path) -> pl.DataFrame:
    frame = bts.cast_columns(bts.read_month_csv(write_zip(tmp_path / "m.zip")))
    return bts.add_utc_columns(frame, ZONES)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("CRSDepTime", "crs_dep_time"),
        ("DOT_ID_Reporting_Airline", "dot_id_reporting_airline"),
        ("OriginAirportSeqID", "origin_airport_seq_id"),
        ("DayofMonth", "day_of_month"),
        ("DepDel15", "dep_del15"),
        ("Div1AirportID", "div1_airport_id"),
        ("TotalAddGTime", "total_add_gtime"),
        ("Operating_Airline ", "operating_airline"),
        ("NASDelay", "nas_delay"),
    ],
)
def test_to_snake(raw: str, expected: str) -> None:
    assert bts.to_snake(raw) == expected


def test_types(staged_frame: pl.DataFrame) -> None:
    schema = staged_frame.schema
    assert schema["flight_date"] == pl.Date
    assert schema["dep_delay"] == pl.Int32
    assert schema["cancelled"] == pl.Boolean
    assert schema["distance"] == pl.Float64
    assert schema["origin_airport_id"] == pl.Int64
    assert schema["crs_dep_time"] == pl.String
    assert schema["duplicate"] == pl.Boolean
    assert staged_frame["total_add_gtime"].null_count() == len(ROWS)


def test_utc_derivation(staged_frame: pl.DataFrame) -> None:
    def at(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
        return datetime(year, month, day, hour, minute, tzinfo=UTC)

    pdx, overnight, cancelled = staged_frame.iter_rows(named=True)
    assert pdx["sched_dep_utc"] == at(2026, 8, 23, 20, 15)
    assert pdx["sched_arr_utc"] == at(2026, 8, 23, 22, 7)
    assert pdx["dep_utc"] == at(2026, 8, 23, 20, 14)
    assert pdx["wheels_off_utc"] == at(2026, 8, 23, 20, 32)
    assert pdx["wheels_on_utc"] == at(2026, 8, 23, 22, 2)
    assert pdx["arr_utc"] == at(2026, 8, 23, 22, 11)
    assert overnight["sched_dep_utc"] == at(2026, 8, 24, 4, 50)
    assert overnight["arr_utc"] == at(2026, 8, 24, 9, 45)
    assert cancelled["cancelled"] is True
    assert cancelled["sched_arr_utc"] == at(2026, 8, 23, 12, 45)
    assert cancelled["dep_utc"] is None and cancelled["arr_utc"] is None


def test_quality_checks_pass_on_consistent_rows(staged_frame: pl.DataFrame) -> None:
    checks = bts.quality_checks(staged_frame)
    assert checks["rows"] == len(ROWS)
    assert checks["rows_missing_tz"] == 0
    for key in ("match_sched_arr", "match_dep_time", "match_arr_time", "match_wheels_on"):
        assert checks[key] == 1.0


def test_stage_month_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "data"
    archive = write_zip(tmp_path / "upload.zip")
    payload = archive.read_bytes()
    when = datetime(2026, 10, 27, 5, 23, tzinfo=UTC)
    dl = Download(
        url="https://example.test/m.zip", tmp_path=archive, fetched_at=when, status=200,
        sha256=hashlib.sha256(payload).hexdigest(), size_bytes=len(payload),
        content_type="application/zip", last_modified=None, etag=None,
    )  # fmt: skip
    table = bts.TABLES["reporting"]
    commit_download(root, table.source_id, "2026-08", "m.zip", dl, "public-domain")
    monkeypatch.setattr(bts, "airport_timezones", lambda: ZONES)

    result = bts.stage_month(table, 2026, 8, data_root=root)

    staged = pl.read_parquet(result.path)
    assert result.rows == len(ROWS) and result.ord_rows == 2
    assert staged["known_time"].unique().to_list() == [when]
    assert staged["licence_class"].unique().to_list() == ["public-domain"]
    assert result.path == root / "stage/bts_ontime_reporting/year=2026/month=08/data.parquet"


def test_month_range_crosses_year_boundary() -> None:
    assert bts._months("2025-11", "2026-02") == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]
    assert bts._months("2026-08", "2026-08") == [(2026, 8)]
    assert bts._months("2026-09", "2026-08") == []


def test_stage_is_current(tmp_path: Path) -> None:
    path = tmp_path / "data.parquet"
    assert not bts.stage_is_current(path, "abc")
    pl.DataFrame({"raw_sha256": ["abc", "abc"]}).write_parquet(path)
    assert bts.stage_is_current(path, "abc")
    assert not bts.stage_is_current(path, "def")
