"""BTS on-time performance: monthly download to the raw zone and typed Parquet staging.

UTC timestamps are derived from the scheduled departure (local time at the origin) plus the
minute offsets BTS reports, so overnight arrivals never need a date guess:

    sched_arr = sched_dep + CRSElapsedTime     dep = sched_dep + DepDelay
    arr = sched_arr + ArrDelay                 wheels_off = dep + TaxiOut
                                               wheels_on = arr - TaxiIn

Stage quality checks confirm that these UTC times reproduce BTS's local ``hhmm`` fields.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
import polars as pl

from ordfi.ingest.http import (
    NotModifiedError,
    NotPublishedError,
    download,
    make_client,
    sweep_partial_downloads,
)
from ordfi.ingest.raw import (
    LicenceClass,
    RawRecord,
    commit_download,
    conditional_headers,
    latest,
)
from ordfi.settings import data_dir
from ordfi.timeutil.core import airport_timezones, hhmm_minutes, localize_to_utc

LICENCE: LicenceClass = "public-domain"


@dataclass(frozen=True)
class BtsTable:
    source_id: str
    url_template: str
    first_month: date

    def url(self, year: int, month: int) -> str:
        return self.url_template.format(year=year, month=month)


TABLES = {
    "reporting": BtsTable(
        source_id="bts_ontime_reporting",
        url_template=(
            "https://transtats.bts.gov/PREZIP/"
            "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"
        ),
        first_month=date(1987, 10, 1),
    ),
    "marketing": BtsTable(
        source_id="bts_ontime_marketing",
        url_template=(
            "https://transtats.bts.gov/PREZIP/On_Time_Marketing_Carrier_On_Time_Performance_"
            "Beginning_January_2018_{year}_{month}.zip"
        ),
        first_month=date(2018, 1, 1),
    ),
}

# --- column handling ------------------------------------------------------------------------

_RENAMES = {
    "DayofMonth": "day_of_month",
    "TotalAddGTime": "total_add_gtime",
    "LongestAddGTime": "longest_add_gtime",
}
_HHMM = {"crs_dep_time", "dep_time", "wheels_off", "wheels_on", "crs_arr_time", "arr_time"}
_HHMM_PATTERN = re.compile(r"^(first_dep_time|div\d_wheels_o(n|ff))$")
_MINUTES = {
    "dep_delay", "dep_delay_minutes", "taxi_out", "taxi_in", "arr_delay", "arr_delay_minutes",
    "crs_elapsed_time", "actual_elapsed_time", "air_time", "carrier_delay", "weather_delay",
    "nas_delay", "security_delay", "late_aircraft_delay", "total_add_gtime",
    "longest_add_gtime", "div_actual_elapsed_time", "div_arr_delay",
}  # fmt: skip
_MINUTES_PATTERN = re.compile(r"^div\d_(total|longest)_gtime$")
_FLAGS = {"cancelled", "diverted", "dep_del15", "arr_del15", "div_reached_dest"}
_FLOATS = {"distance", "div_distance", "flights"}
_INT_PATTERN = re.compile(
    r"^(year|quarter|month|day_of_month|day_of_week|distance_group|div_airport_landings"
    r"|departure_delay_groups|arrival_delay_groups|.*_id|.*_seq_id|.*_market_id|.*_state_fips"
    r"|.*_wac|flight_num(ber)?_.*)$"
)


def to_snake(name: str) -> str:
    """Convert a BTS column name to snake_case (``CRSDepTime`` → ``crs_dep_time``)."""
    name = name.strip()
    if name in _RENAMES:
        return _RENAMES[name]
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    spaced = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", spaced)
    return re.sub(r"_+", "_", spaced).lower()


def read_month_csv(zip_path: Path) -> pl.DataFrame:
    """Read the CSV inside a BTS monthly ZIP as strings, with snake_case column names.

    Decoding is lossy: rare corrupt bytes at the source (e.g. a truncated byte-order mark in one
    Aug 2018 row) become U+FFFD instead of failing the month; they are counted by
    :func:`quality_checks` as ``rows_invalid_text``.
    """
    with zipfile.ZipFile(zip_path) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"expected one CSV in {zip_path}, found {members}")
        payload = archive.read(members[0])
    frame = pl.read_csv(io.BytesIO(payload), infer_schema=False, encoding="utf8-lossy")
    frame = frame.select([c for c in frame.columns if c.strip() and not c.startswith("_")])
    return frame.rename({c: to_snake(c) for c in frame.columns})


def cast_columns(frame: pl.DataFrame) -> pl.DataFrame:
    """Apply BTS types: dates, integer minutes, booleans, floats, IDs; hhmm stays text."""
    exprs: list[pl.Expr] = []
    for name in frame.columns:
        col = pl.col(name).str.strip_chars()
        if name == "flight_date":
            exprs.append(col.str.to_date("%Y-%m-%d"))
        elif name in _HHMM or _HHMM_PATTERN.match(name):
            exprs.append(pl.when(col == "").then(None).otherwise(col.str.zfill(4)).alias(name))
        elif name in _MINUTES or _MINUTES_PATTERN.match(name):
            exprs.append(col.cast(pl.Float64, strict=False).round(0).cast(pl.Int32).alias(name))
        elif name in _FLAGS:
            exprs.append((col.cast(pl.Float64, strict=False) > 0).alias(name))
        elif name in _FLOATS:
            exprs.append(col.cast(pl.Float64, strict=False).alias(name))
        elif _INT_PATTERN.match(name):
            exprs.append(col.cast(pl.Float64, strict=False).cast(pl.Int64).alias(name))
        elif name == "duplicate":
            exprs.append((col == "Y").alias(name))
        else:
            exprs.append(pl.when(col == "").then(None).otherwise(col).alias(name))
    return frame.select(exprs)


def add_utc_columns(frame: pl.DataFrame, zones: dict[str, str]) -> pl.DataFrame:
    """Add origin/destination time zones and UTC event timestamps (see module docstring)."""
    frame = frame.with_columns(
        origin_tz=pl.col("origin").replace_strict(zones, default=None),
        dest_tz=pl.col("dest").replace_strict(zones, default=None),
    )
    present = [z for z in frame["origin_tz"].unique().to_list() if z]
    naive_sched_dep = pl.col("flight_date").cast(pl.Datetime("us")) + pl.duration(
        minutes=hhmm_minutes("crs_dep_time")
    )

    def plus(base: str, minutes: str, sign: int = 1) -> pl.Expr:
        return pl.col(base) + pl.duration(minutes=pl.col(minutes) * sign)

    return (
        frame.with_columns(sched_dep_utc=localize_to_utc(naive_sched_dep, "origin_tz", present))
        .with_columns(
            sched_arr_utc=plus("sched_dep_utc", "crs_elapsed_time"),
            dep_utc=plus("sched_dep_utc", "dep_delay"),
        )
        .with_columns(
            arr_utc=plus("sched_arr_utc", "arr_delay"),
            wheels_off_utc=plus("dep_utc", "taxi_out"),
        )
        .with_columns(wheels_on_utc=plus("arr_utc", "taxi_in", sign=-1))
    )


def _local_hhmm(utc: str, tz_column: str, zones: list[str]) -> pl.Expr:
    """Format a UTC timestamp column as local ``hhmm`` text in a per-row zone."""
    out: pl.Expr = pl.lit(None, dtype=pl.String)
    for zone in sorted(set(zones)):
        local = pl.col(utc).dt.convert_time_zone(zone).dt.strftime("%H%M")
        out = pl.when(pl.col(tz_column) == zone).then(local).otherwise(out)
    return out


def missing_tz_codes(frame: pl.DataFrame) -> list[str]:
    """Airport codes in ``frame`` with no time zone (add them to ``TIMEZONE_OVERRIDES``)."""
    origins = frame.filter(pl.col("origin_tz").is_null())["origin"]
    dests = frame.filter(pl.col("dest_tz").is_null())["dest"]
    return sorted(set(origins.to_list()) | set(dests.to_list()))


def quality_checks(frame: pl.DataFrame) -> dict[str, float | int]:
    """Share of rows whose derived UTC times reproduce the BTS local hhmm fields."""
    zones = [z for z in pl.concat([frame["origin_tz"], frame["dest_tz"]]).unique().to_list() if z]

    def normalise(column: str) -> pl.Expr:
        return pl.col(column).str.replace("^2400$", "0000")

    checks = {
        "sched_arr": (_local_hhmm("sched_arr_utc", "dest_tz", zones), "crs_arr_time"),
        "dep_time": (_local_hhmm("dep_utc", "origin_tz", zones), "dep_time"),
        "arr_time": (_local_hhmm("arr_utc", "dest_tz", zones), "arr_time"),
        "wheels_off": (_local_hhmm("wheels_off_utc", "origin_tz", zones), "wheels_off"),
        "wheels_on": (_local_hhmm("wheels_on_utc", "dest_tz", zones), "wheels_on"),
    }
    invalid_text = pl.any_horizontal(pl.col(pl.String).str.contains("\ufffd", literal=True))
    results: dict[str, float | int] = {
        "rows": frame.height,
        "rows_missing_tz": frame.filter(
            pl.col("origin_tz").is_null() | pl.col("dest_tz").is_null()
        ).height,
        "rows_invalid_text": frame.filter(invalid_text.fill_null(False)).height,
    }
    for name, (derived, reported) in checks.items():
        both = frame.select(derived.alias("d"), normalise(reported).alias("r")).drop_nulls()
        share = both.select((pl.col("d") == pl.col("r")).cast(pl.Float64).mean()).item()
        results[f"match_{name}"] = round(float(share), 6) if share is not None else 0.0
    return results


# --- pipeline steps -------------------------------------------------------------------------


@dataclass(frozen=True)
class StageResult:
    path: Path
    rows: int
    ord_rows: int
    checks: dict[str, float | int]
    raw: RawRecord
    missing_tz_codes: tuple[str, ...] = ()


def month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def fetch_month(
    table: BtsTable, year: int, month: int, *, client: httpx.Client, data_root: Path
) -> tuple[RawRecord, bool]:
    """Download one month into the raw zone; returns the record and whether it is new.

    Re-fetches are conditional on the stored ETag/Last-Modified, so an unchanged month costs a
    single HTTP 304 instead of a full download.
    """
    url, key = table.url(year, month), month_key(year, month)
    previous = latest(data_root, table.source_id, key)
    try:
        dl = download(client, url, data_root / "tmp", headers=conditional_headers(previous))
    except NotModifiedError:
        if previous is None:  # 304 needs validators, which only come from a stored record
            raise RuntimeError(f"unexpected HTTP 304 without a stored record: {url}") from None
        return previous, False
    return commit_download(data_root, table.source_id, key, url.rsplit("/", 1)[-1], dl, LICENCE)


def stage_path(table: BtsTable, year: int, month: int, data_root: Path) -> Path:
    return (
        data_root / "stage" / table.source_id / f"year={year:04d}" / f"month={month:02d}"
        / "data.parquet"
    )  # fmt: skip


def stage_is_current(path: Path, raw_sha256: str) -> bool:
    """True if ``path`` exists and was built from the raw payload with this checksum."""
    if not path.exists():
        return False
    built_from = pl.scan_parquet(path).select(pl.col("raw_sha256").first()).collect().item()
    return bool(built_from == raw_sha256)


def stage_month(table: BtsTable, year: int, month: int, *, data_root: Path) -> StageResult:
    """Convert the latest raw file for a month into typed Parquet with UTC timestamps."""
    record = latest(data_root, table.source_id, month_key(year, month))
    if record is None:
        raise FileNotFoundError(f"no raw file for {table.source_id} {month_key(year, month)}")
    frame = cast_columns(read_month_csv(data_root / record.path))
    frame = add_utc_columns(frame, airport_timezones())
    checks = quality_checks(frame)
    missing = missing_tz_codes(frame)
    frame = frame.with_columns(
        source_id=pl.lit(table.source_id),
        raw_sha256=pl.lit(record.sha256),
        known_time=pl.lit(record.fetched_at_dt).cast(pl.Datetime("us", "UTC")),
        licence_class=pl.lit(record.licence_class),
    )
    out = stage_path(table, year, month, data_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(".data.parquet.tmp")
    frame.write_parquet(tmp, compression="zstd")
    os.replace(tmp, out)
    ord_rows = frame.filter((pl.col("origin") == "ORD") | (pl.col("dest") == "ORD")).height
    return StageResult(out, frame.height, ord_rows, checks, record, tuple(missing))


def _months(first: str, last: str) -> list[tuple[int, int]]:
    year, month = (int(part) for part in first.split("-"))
    end_year, end_month = (int(part) for part in last.split("-"))
    months = []
    while (year, month) <= (end_year, end_month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fetch and stage BTS on-time months.")
    parser.add_argument("--table", choices=sorted(TABLES), default="marketing")
    parser.add_argument("--month", help="single month, YYYY-MM")
    parser.add_argument("--from", dest="first", help="first month of a range, YYYY-MM")
    parser.add_argument("--to", dest="last", help="last month of a range, YYYY-MM")
    parser.add_argument("--stage-only", action="store_true", help="skip the download")
    parser.add_argument("--force-stage", action="store_true", help="re-stage even if current")
    parser.add_argument("--pause", type=float, default=2.0, help="seconds between downloads")
    args = parser.parse_args(argv)
    if args.month:
        months = _months(args.month, args.month)
    elif args.first and args.last:
        months = _months(args.first, args.last)
    else:
        parser.error("give --month, or both --from and --to")
    table, root = TABLES[args.table], data_dir()
    if removed := sweep_partial_downloads(root / "tmp"):
        print(f"removed {removed} stale partial download(s)", flush=True)
    failures: list[str] = []
    with make_client() as client:
        for year, month in months:
            key = month_key(year, month)
            try:
                if not args.stage_only:
                    record, new = fetch_month(table, year, month, client=client, data_root=root)
                    state = "new" if new else "unchanged"
                    print(f"{key}: raw revision {record.revision} ({state})", flush=True)
                    if new:
                        time.sleep(args.pause)
                latest_raw = latest(root, table.source_id, key)
                current = latest_raw is not None and stage_is_current(
                    stage_path(table, year, month, root), latest_raw.sha256
                )
                if current and not args.force_stage:
                    print(f"{key}: stage already current", flush=True)
                    continue
                result = stage_month(table, year, month, data_root=root)
            except NotPublishedError:
                print(f"{key}: not published yet; stopping", flush=True)
                break
            except Exception as exc:  # keep a long backfill going; report at the end
                failures.append(key)
                print(f"{key}: FAILED: {type(exc).__name__}: {exc}", flush=True)
                continue
            worst = min(float(v) for k, v in result.checks.items() if k.startswith("match_"))
            print(
                f"{key}: staged rows={result.rows} ord_rows={result.ord_rows} "
                f"missing_tz={result.checks['rows_missing_tz']} worst_match={worst:.6f}"
                + (
                    f" missing_tz_codes={','.join(result.missing_tz_codes)}"
                    if result.missing_tz_codes
                    else ""
                ),
                flush=True,
            )
    if failures:
        raise SystemExit(f"{len(failures)} month(s) failed: {', '.join(failures)}")


if __name__ == "__main__":
    main()
