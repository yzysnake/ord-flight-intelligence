"""Property tests: vectorized and scalar UTC conversion agree everywhere, DST days included."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import polars as pl
from hypothesis import given, settings
from hypothesis import strategies as st

from ordfi.timeutil.core import hhmm_minutes, local_to_utc, localize_to_utc

ZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
    "America/Puerto_Rico",
]

cases = st.lists(
    st.tuples(
        st.dates(min_value=date(2015, 1, 1), max_value=date(2030, 12, 31)),
        st.integers(min_value=0, max_value=24 * 60).map(
            lambda m: "2400" if m == 1440 else f"{m // 60:02d}{m % 60:02d}"
        ),
        st.sampled_from(ZONES),
    ),
    min_size=1,
    max_size=40,
)


@settings(deadline=None, max_examples=60)
@given(cases)
def test_vectorized_equals_scalar(rows: list[tuple[date, str, str]]) -> None:
    frame = pl.DataFrame(
        {"d": [r[0] for r in rows], "t": [r[1] for r in rows], "tz": [r[2] for r in rows]}
    )
    naive = pl.col("d").cast(pl.Datetime("us")) + pl.duration(minutes=hhmm_minutes("t"))
    got = frame.select(localize_to_utc(naive, "tz", ZONES)).to_series().to_list()
    assert got == [local_to_utc(*row) for row in rows]


@settings(deadline=None, max_examples=200)
@given(
    st.dates(min_value=date(2015, 1, 1), max_value=date(2030, 12, 31)),
    st.integers(min_value=0, max_value=1439),
    st.sampled_from(ZONES),
)
def test_round_trip_recovers_wall_clock(day: date, minute: int, zone: str) -> None:
    """Converting back to local time returns the input, except inside a DST gap (+1 h)."""
    hhmm = f"{minute // 60:02d}{minute % 60:02d}"
    utc = local_to_utc(day, hhmm, zone)
    assert utc is not None
    wall = datetime.combine(day, time()) + timedelta(minutes=minute)
    back = utc.astimezone(ZoneInfo(zone)).replace(tzinfo=None)
    assert back - wall in (timedelta(0), timedelta(hours=1)), (day, hhmm, zone, back)
