"""Clock-time parsing and DST-safe conversion from airport-local times to UTC.

Conventions:

- BTS times are local ``hhmm`` strings; ``2400`` means midnight at the end of the day.
- A local time that does not exist (spring-forward gap) is shifted forward by one hour,
  i.e. ``02:30`` on a spring-forward night becomes ``03:30`` local daylight time.
- A local time that occurs twice (fall-back night) resolves to the earlier instant
  (daylight time). Airline schedules rarely use these hours; the ambiguity is documented.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

import airportsdata
import polars as pl

UTC = ZoneInfo("UTC")

# Codes used by BTS that are missing from or differ in airportsdata. Extend as found.
TIMEZONE_OVERRIDES: dict[str, str] = {
    "DJT": "America/New_York",  # Palm Beach, FL: BTS reports DJT in 2026 data (formerly PBI)
    "ISN": "America/Chicago",  # Williston, ND (Sloulin Field), closed 2019; replaced by XWA
}


def parse_hhmm(value: str | int | None) -> tuple[int, int] | None:
    """Parse a BTS ``hhmm`` value into (hours, minutes); ``2400`` becomes ``(24, 0)``.

    Returns ``None`` for blanks and invalid values.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or not text.isdigit() or len(text) > 4:
        return None
    number = int(text)
    hours, minutes = divmod(number, 100)
    if minutes >= 60 or hours > 24 or (hours == 24 and minutes != 0):
        return None
    return hours, minutes


def localize(naive: datetime, tz: ZoneInfo) -> datetime:
    """Attach ``tz`` to a naive local datetime using the gap and ambiguity conventions above."""
    aware = naive.replace(tzinfo=tz, fold=0)
    roundtrip = aware.astimezone(UTC).astimezone(tz).replace(tzinfo=None)
    if roundtrip != naive:  # nonexistent local time: shift forward by one hour
        aware = (naive + timedelta(hours=1)).replace(tzinfo=tz, fold=0)
    return aware


def local_to_utc(day: date, hhmm: str | int | None, tz_name: str) -> datetime | None:
    """Convert a local calendar date and ``hhmm`` clock time at ``tz_name`` to an aware UTC time."""
    parsed = parse_hhmm(hhmm)
    if parsed is None:
        return None
    hours, minutes = parsed
    naive = datetime.combine(day, time()) + timedelta(hours=hours, minutes=minutes)
    return localize(naive, ZoneInfo(tz_name)).astimezone(UTC)


@lru_cache(maxsize=1)
def airport_timezones() -> dict[str, str]:
    """Map IATA airport codes to IANA time-zone names (airportsdata plus local overrides)."""
    zones = {code: entry["tz"] for code, entry in airportsdata.load("IATA").items() if entry["tz"]}
    zones.update(TIMEZONE_OVERRIDES)
    return zones


def hhmm_minutes(column: str) -> pl.Expr:
    """Polars expression: minutes after local midnight for an ``hhmm`` string column (or null)."""
    text = pl.col(column).str.strip_chars()
    number = text.str.to_integer(strict=False)
    hours = number // 100
    minutes = number % 100
    valid = (
        text.str.contains(r"^\d{1,4}$")
        & (minutes < 60)
        & ((hours < 24) | ((hours == 24) & (minutes == 0)))
    )
    return pl.when(valid).then(hours * 60 + minutes).otherwise(None).cast(pl.Int32)


def localize_to_utc(naive: pl.Expr, tz_column: str, zones: Iterable[str]) -> pl.Expr:
    """Polars expression converting naive local datetimes to UTC, per-row time zone.

    ``zones`` must list every time zone present in ``tz_column``; rows with other zones yield
    null. Uses the same gap and ambiguity conventions as :func:`localize`.
    """
    result: pl.Expr = pl.lit(None, dtype=pl.Datetime("us", "UTC"))
    for zone in sorted(set(zones)):
        first = naive.dt.replace_time_zone(zone, ambiguous="earliest", non_existent="null")
        shifted = (naive + pl.duration(hours=1)).dt.replace_time_zone(
            zone, ambiguous="earliest", non_existent="null"
        )
        converted = pl.coalesce(first, shifted).dt.convert_time_zone("UTC")
        result = pl.when(pl.col(tz_column) == zone).then(converted).otherwise(result)
    return result
