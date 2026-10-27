"""Clock-time parsing and local-to-UTC conversion, including DST edge cases."""

from datetime import UTC, date, datetime

import polars as pl
import pytest

from ordfi.timeutil.core import (
    airport_timezones,
    hhmm_minutes,
    local_to_utc,
    localize_to_utc,
    parse_hhmm,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0005", (0, 5)),
        ("5", (0, 5)),
        (1315, (13, 15)),
        ("2400", (24, 0)),
        (" 0930 ", (9, 30)),
        ("2460", None),
        ("2401", None),
        ("1260", None),
        ("", None),
        ("12:30", None),
        (None, None),
    ],
)
def test_parse_hhmm(value: str | int | None, expected: tuple[int, int] | None) -> None:
    assert parse_hhmm(value) == expected


@pytest.mark.parametrize(
    ("day", "hhmm", "zone", "expected"),
    [
        # Ordinary summer time: CDT is UTC-5.
        (date(2026, 8, 23), "1315", "America/Chicago", datetime(2026, 8, 23, 18, 15, tzinfo=UTC)),
        # 2400 is midnight at the end of the day.
        (date(2026, 8, 23), "2400", "America/Chicago", datetime(2026, 8, 24, 5, 0, tzinfo=UTC)),
        # Spring-forward gap: 02:30 does not exist, shifted to 03:30 CDT.
        (date(2026, 3, 8), "0230", "America/Chicago", datetime(2026, 3, 8, 8, 30, tzinfo=UTC)),
        # Fall-back ambiguity: 01:30 resolves to the earlier (CDT) instant.
        (date(2026, 11, 1), "0130", "America/Chicago", datetime(2026, 11, 1, 6, 30, tzinfo=UTC)),
        # Arizona does not observe DST.
        (date(2026, 7, 1), "1200", "America/Phoenix", datetime(2026, 7, 1, 19, 0, tzinfo=UTC)),
    ],
)
def test_local_to_utc(day: date, hhmm: str, zone: str, expected: datetime) -> None:
    assert local_to_utc(day, hhmm, zone) == expected


def test_local_to_utc_rejects_invalid_time() -> None:
    assert local_to_utc(date(2026, 8, 23), "2460", "America/Chicago") is None


def test_hhmm_minutes_expression() -> None:
    frame = pl.DataFrame({"t": ["0005", "2400", "2460", "", "1315", None]})
    result = frame.select(hhmm_minutes("t")).to_series().to_list()
    assert result == [5, 1440, None, None, 795, None]


def test_vectorized_matches_scalar_on_dst_edges() -> None:
    cases = [
        (date(2026, 3, 8), "0230", "America/Chicago"),
        (date(2026, 11, 1), "0130", "America/Chicago"),
        (date(2026, 8, 23), "2400", "America/New_York"),
        (date(2026, 1, 15), "0610", "Pacific/Honolulu"),
    ]
    frame = pl.DataFrame(
        {"d": [c[0] for c in cases], "t": [c[1] for c in cases], "tz": [c[2] for c in cases]}
    )
    naive = pl.col("d").cast(pl.Datetime("us")) + pl.duration(minutes=hhmm_minutes("t"))
    zones = [c[2] for c in cases]
    got = frame.select(localize_to_utc(naive, "tz", zones)).to_series().to_list()
    assert got == [local_to_utc(*case) for case in cases]


def test_airport_timezones_include_overrides() -> None:
    zones = airport_timezones()
    assert zones["ORD"] == "America/Chicago"
    assert zones["DJT"] == "America/New_York"
    assert zones["ISN"] == "America/Chicago"
