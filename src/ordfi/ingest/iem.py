"""IEM (Iowa Environmental Mesonet) weather archives for ORD: METAR observations and TAFs.

Endpoints on mesonet.agron.iastate.edu (public domain; IEM throttles each IP to one request per
second):

- **METAR**: ``/cgi-bin/request/asos.py`` CSV. It has no report-type column, so each month is
  fetched once per type: routine (3), special (4) and 5-minute HFMETAR (1; empty in early years);
- **TAF groups**: ``/cgi-bin/request/taf.py`` CSV, one row per forecast group (initial
  conditions, FM, TEMPO, PROB, BECMG), selected by issuance time;
- **TAF products**: ``/api/1/nws/taf_overview.json``, one row per TAF with issuance time,
  validity window and amendment flag (the station must be the ICAO code, e.g. ``KORD``);
- **TAF bulletins**: ``/cgi-bin/afos/retrieve.py?pil=TAFORD``, the verbatim bulletins, the
  authoritative record for re-parsing.

Raw responses are stored verbatim, partitioned by data month. Past months are fetched once; the
current month and months that ended less than ``REFRESH_DAYS`` ago are re-fetched.

IEM's TAF parse has known faults. They are flagged in its staged tables, and
``ordfi.ingest.taf`` re-parses the bulletins instead (``bulletins`` and ``periods`` tables):

- ``old_format``: TAFs in the format used before November 2008 (``FMhhmm`` groups without a day,
  ``DDhhhh`` validity), detected from the group text. IEM gives them no validity window, and
  their group times can be wrong;
- ``window_valid`` is null when IEM has no validity window (old-format TAFs, and most of 2011)
  and false when the window is implausible (longer than 30 h, or ending before it starts): IEM
  misdates windows ending in the next month, or at hour 24 on a month's last day.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import partial
from pathlib import Path

import httpx
import polars as pl

from ordfi.ingest.http import download, make_client, sweep_partial_downloads
from ordfi.ingest.raw import LicenceClass, RawRecord, commit_download, load_latest
from ordfi.ingest.taf import stage_year as stage_taf_bulletins
from ordfi.settings import data_dir

METAR_SOURCE = "iem_asos_metar"
TAF_SOURCE = "iem_taf"
LICENCE: LicenceClass = "public-domain"
BASE = "https://mesonet.agron.iastate.edu"
STATION = "ORD"
FIRST_MONTH = "2000-01"
REFRESH_DAYS = 3
PRODUCTS = ("metar", "taf")
REPORT_TYPES = {"routine": 3, "special": 4, "hfmetar": 1}
KNOWLEDGE_LAG = timedelta(minutes=10)  # IEM's archive syncs from its real-time feed every 10 min
MAX_TAF_HOURS = 30  # longest US TAF validity
OLD_TAF_GROUP = r"^(?:FM\d{4}|\d{6})\b"  # pre-Nov-2008: "FM2300", or a "010606" validity


def _next_month(start: date) -> date:
    return date(start.year + start.month // 12, start.month % 12 + 1, 1)


def months(first: str, last: str) -> list[date]:
    """First days of the months ``first..last`` (``YYYY-MM``, inclusive)."""
    start, end = date.fromisoformat(f"{first}-01"), date.fromisoformat(f"{last}-01")
    out = []
    while start <= end:
        out.append(start)
        start = _next_month(start)
    return out


def _span(start: date) -> str:
    return f"sts={start:%Y-%m-%d}T00:00Z&ets={_next_month(start):%Y-%m-%d}T00:00Z"


def icao(station: str) -> str:
    return station if len(station) == 4 else f"K{station}"


def metar_url(station: str, report_type: int, start: date) -> str:
    return (
        f"{BASE}/cgi-bin/request/asos.py?station={station}&data=all&report_type={report_type}"
        f"&tz=Etc/UTC&format=onlycomma&latlon=no&elev=no&missing=empty&trace=T&{_span(start)}"
    )


def taf_groups_url(station: str, start: date) -> str:
    return f"{BASE}/cgi-bin/request/taf.py?station={station}&fmt=csv&tz=Etc/UTC&{_span(start)}"


def taf_products_url(station: str, start: date) -> str:
    return f"{BASE}/api/1/nws/taf_overview.json?station={icao(station)}&{_span(start)}"


def taf_bulletins_url(station: str, start: date) -> str:
    span = _span(start).replace("sts=", "sdate=").replace("ets=", "edate=")
    pil = f"TAF{station[-3:]}"
    return f"{BASE}/cgi-bin/afos/retrieve.py?pil={pil}&fmt=text&limit=9999&order=asc&{span}"


@dataclass(frozen=True)
class Request:
    """One monthly download: raw-zone key ``<station>/<kind>/<YYYY-MM>`` and where to store it."""

    source_id: str
    key: str
    url: str
    filename: str
    partition: str


def month_requests(product: str, station: str, start: date) -> list[Request]:
    month, partition = f"{start:%Y-%m}", f"{station}/{start:%Y}"
    if product == "metar":
        return [
            Request(METAR_SOURCE, f"{station}/{kind}/{month}", metar_url(station, code, start),
                    f"{station}-{kind}-{month}.csv", partition)
            for kind, code in REPORT_TYPES.items()
        ]  # fmt: skip
    return [
        Request(TAF_SOURCE, f"{station}/groups/{month}", taf_groups_url(station, start),
                f"{station}-taf-groups-{month}.csv", partition),
        Request(TAF_SOURCE, f"{station}/products/{month}", taf_products_url(station, start),
                f"{station}-taf-products-{month}.json", partition),
        Request(TAF_SOURCE, f"{station}/bulletins/{month}", taf_bulletins_url(station, start),
                f"{station}-taf-bulletins-{month}.txt", partition),
    ]  # fmt: skip


# --- crawl -----------------------------------------------------------------------------------


@dataclass
class CrawlStats:
    months: int = 0
    fetched: int = 0
    failures: int = 0


def crawl(
    first: str,
    last: str,
    *,
    client: httpx.Client,
    data_root: Path,
    products: Iterable[str] = PRODUCTS,
    station: str = STATION,
    pause: float = 1.0,
    today: date | None = None,
    log: Callable[[str], None] = print,
) -> CrawlStats:
    """Fetch every month of ``first..last`` not yet stored, plus the most recent months again."""
    today = today or datetime.now(UTC).date()
    indexes = {source: load_latest(data_root, source) for source in (METAR_SOURCE, TAF_SOURCE)}
    wanted = tuple(products)
    stats = CrawlStats()
    final = date.fromisoformat(f"{last}-01")
    for start in months(first, last):
        stats.months += 1
        recent = (today - _next_month(start)).days < REFRESH_DAYS
        for request in [r for product in wanted for r in month_requests(product, station, start)]:
            index = indexes[request.source_id]
            if request.key in index and not recent:
                continue
            try:
                dl = download(client, request.url, data_root / "tmp")
                commit_download(
                    data_root, request.source_id, request.key, request.filename, dl, LICENCE,
                    partition=request.partition, index=index,
                )  # fmt: skip
                stats.fetched += 1
            except Exception as exc:  # keep a long backfill going; failed months retry next run
                stats.failures += 1
                log(f"{request.key}: FAILED: {type(exc).__name__}: {exc}")
            if pause > 0:
                time.sleep(pause)
        if start.month == 1 or start == final:
            log(f"{start:%Y-%m}: months={stats.months} fetched={stats.fetched} "
                f"failures={stats.failures}")  # fmt: skip
    return stats


# --- staging ---------------------------------------------------------------------------------

UTC_TS = pl.Datetime("us", "UTC")
TRACE = 0.0001  # IEM's numeric value for a trace amount, reported as "T"
METAR_NUMBERS = (
    "tmpf", "dwpf", "relh", "drct", "sknt", "p01i", "alti", "mslp", "vsby", "gust",
    "skyl1", "skyl2", "skyl3", "skyl4", "ice_accretion_1hr", "ice_accretion_3hr",
    "ice_accretion_6hr", "peak_wind_gust", "peak_wind_drct", "feel", "snowdepth",
)  # fmt: skip
METAR_TEXT = ("skyc1", "skyc2", "skyc3", "skyc4", "wxcodes", "metar")
METAR_SCHEMA = pl.Schema(
    {
        "station": pl.String(),
        "valid": UTC_TS,
        "report_type": pl.String(),
        **{name: pl.Float64() for name in METAR_NUMBERS},
        **{name: pl.String() for name in METAR_TEXT},
        "peak_wind_time": UTC_TS,
        "raw_sha256": pl.String(),
    }
)
TAF_PRODUCT_SCHEMA = pl.Schema(
    {
        "station": pl.String(),
        "product_id": pl.String(),
        "issued": UTC_TS,
        "valid_from": UTC_TS,
        "valid_to": UTC_TS,
        "is_amendment": pl.Boolean(),
        "min_visibility": pl.Float64(),
        "raw_sha256": pl.String(),
    }
)
TAF_GROUP_SCHEMA = pl.Schema(
    {
        "station": pl.String(),
        "product_id": pl.String(),
        "issued": UTC_TS,
        "ftype": pl.String(),
        "fx_valid": UTC_TS,
        "fx_valid_end": UTC_TS,
        "raw": pl.String(),
        "sknt": pl.Float64(),
        "drct": pl.Float64(),
        "gust": pl.Float64(),
        "visibility": pl.Float64(),
        "presentwx": pl.List(pl.String()),
        "skyc": pl.List(pl.String()),
        "skyl": pl.List(pl.Int32()),
        "ws_level": pl.Float64(),
        "ws_drct": pl.Float64(),
        "ws_sknt": pl.Float64(),
        "is_amendment": pl.Boolean(),
        "raw_sha256": pl.String(),
    }
)


def _read_csv(path: Path) -> pl.DataFrame:
    """An IEM CSV with every column as text (empty fields become null)."""
    if path.stat().st_size == 0:
        return pl.DataFrame()
    return pl.read_csv(path, infer_schema_length=0, encoding="utf8-lossy")


def _column(frame: pl.DataFrame, name: str) -> pl.Expr:
    """A text column, or nulls if this response lacks it (IEM adds and retires columns)."""
    return pl.col(name) if name in frame.columns else pl.lit(None, dtype=pl.String)


def _timestamp(expr: pl.Expr) -> pl.Expr:
    return expr.str.to_datetime("%Y-%m-%d %H:%M", time_unit="us", time_zone="UTC", strict=False)


def _number(expr: pl.Expr) -> pl.Expr:
    text = expr.str.strip_chars()
    return pl.when(text == "T").then(pl.lit(TRACE)).otherwise(text.cast(pl.Float64, strict=False))


def _py_list(expr: pl.Expr, dtype: pl.DataType) -> pl.Expr:
    """IEM's Python-list text (``"['SCT', 'BKN']"``, ``"[5000, None]"``) as a typed list."""
    item = pl.element().str.strip_chars(" '\"")
    items = expr.str.strip_chars("[]").str.split(",")
    return items.list.eval(item.filter(item != "").cast(dtype, strict=False))


def read_metar(path: Path, report_type: str, raw_sha256: str = "") -> pl.DataFrame:
    """One raw METAR CSV as typed rows; ``report_type`` comes from the request."""
    frame = _read_csv(path)
    if frame.height == 0:
        return pl.DataFrame(schema=METAR_SCHEMA)
    col = partial(_column, frame)
    return frame.select(
        col("station").alias("station"),
        _timestamp(col("valid")).alias("valid"),
        pl.lit(report_type).alias("report_type"),
        *[_number(col(name)).alias(name) for name in METAR_NUMBERS],
        *[col(name).alias(name) for name in METAR_TEXT],
        _timestamp(col("peak_wind_time")).alias("peak_wind_time"),
        pl.lit(raw_sha256).alias("raw_sha256"),
    ).cast(METAR_SCHEMA)


def _iso(value: object) -> datetime | None:
    return datetime.fromisoformat(value) if isinstance(value, str) and value else None


def read_taf_products(path: Path, raw_sha256: str = "") -> pl.DataFrame:
    """One raw TAF overview (JSON) as one row per TAF product."""
    rows = json.loads(path.read_text(encoding="utf-8")).get("data", [])
    return pl.DataFrame(
        [
            {
                "station": row.get("station"),
                "product_id": row.get("product_id"),
                "issued": _iso(row.get("utc_issued")),
                "valid_from": _iso(row.get("utc_issue")),
                "valid_to": _iso(row.get("utc_expire")),
                "is_amendment": row.get("is_amendment"),
                "min_visibility": row.get("min_visibility"),
                "raw_sha256": raw_sha256,
            }
            for row in rows
        ],
        schema=TAF_PRODUCT_SCHEMA,
    )


def read_taf_groups(path: Path, raw_sha256: str = "") -> pl.DataFrame:
    """One raw TAF CSV as one row per forecast group."""
    frame = _read_csv(path)
    if frame.height == 0:
        return pl.DataFrame(schema=TAF_GROUP_SCHEMA)
    col = partial(_column, frame)
    return frame.select(
        col("station").alias("station"),
        col("product_id").alias("product_id"),
        _timestamp(col("valid")).alias("issued"),
        col("ftype").alias("ftype"),
        _timestamp(col("fx_valid")).alias("fx_valid"),
        _timestamp(col("fx_valid_end")).alias("fx_valid_end"),
        col("raw").alias("raw"),
        *[_number(col(name)).alias(name) for name in ("sknt", "drct", "gust", "visibility")],
        _py_list(col("presentwx"), pl.String()).alias("presentwx"),
        _py_list(col("skyc"), pl.String()).alias("skyc"),
        _py_list(col("skyl"), pl.Int32()).alias("skyl"),
        *[_number(col(name)).alias(name) for name in ("ws_level", "ws_drct", "ws_sknt")],
        (col("is_amendment") == "True").alias("is_amendment"),
        pl.lit(raw_sha256).alias("raw_sha256"),
    ).cast(TAF_GROUP_SCHEMA)


def stage_path(source_id: str, station: str, year: int, data_root: Path, table: str = "") -> Path:
    base = data_root / "stage" / source_id / table if table else data_root / "stage" / source_id
    return base / f"station={station}" / f"year={year:04d}" / "data.parquet"


def _write(frame: pl.DataFrame, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(".data.parquet.tmp")
    frame.write_parquet(tmp, compression="zstd")
    os.replace(tmp, target)
    return target


def _month_records(
    index: dict[str, RawRecord], station: str, year: int
) -> Iterable[tuple[str, RawRecord]]:
    """``(kind, record)`` for the station's months in ``year``."""
    for key, record in sorted(index.items()):
        key_station, kind, month = key.split("/")
        if key_station == station and month.startswith(f"{year:04d}-"):
            yield kind, record


def stage_metar_year(
    data_root: Path, year: int, station: str = STATION
) -> tuple[Path, dict[str, int]]:
    """All report types for one station-year, de-duplicated on (station, valid, report type)."""
    index = load_latest(data_root, METAR_SOURCE)
    frames = [
        read_metar(data_root / record.path, kind, record.sha256)
        for kind, record in _month_records(index, station, year)
    ]
    frame = pl.concat(frames) if frames else pl.DataFrame(schema=METAR_SCHEMA)
    unique = frame.unique(["station", "valid", "report_type"], keep="last", maintain_order=True)
    staged = unique.sort("valid", "report_type").with_columns(
        known_time=pl.col("valid") + KNOWLEDGE_LAG, licence_class=pl.lit(LICENCE)
    )
    counts = dict(staged.group_by("report_type").len().iter_rows())
    routine_hours = staged.filter(pl.col("report_type") == "routine")["valid"].dt.truncate("1h")
    summary = {
        "rows": staged.height,
        **{kind: int(counts.get(kind, 0)) for kind in REPORT_TYPES},
        "duplicates": frame.height - unique.height,
        "routine_hours": routine_hours.n_unique(),
    }
    return _write(staged, stage_path(METAR_SOURCE, station, year, data_root)), summary


def stage_taf_year(
    data_root: Path, year: int, station: str = STATION
) -> tuple[Path, Path, dict[str, int]]:
    """TAF products and groups for one station-year, with ``old_format`` and ``window_valid``.

    Prefer the ``periods`` table from ``ordfi.ingest.taf``, which parses the bulletins.
    """
    index = load_latest(data_root, TAF_SOURCE)
    products: list[pl.DataFrame] = []
    groups: list[pl.DataFrame] = []
    for kind, record in _month_records(index, station, year):
        path = data_root / record.path
        if kind == "products":
            products.append(read_taf_products(path, record.sha256))
        elif kind == "groups":
            groups.append(read_taf_groups(path, record.sha256))
    group_frame = pl.concat(groups) if groups else pl.DataFrame(schema=TAF_GROUP_SCHEMA)
    formats = group_frame.group_by("product_id").agg(
        old_format=pl.col("raw").str.contains(OLD_TAF_GROUP).any()
    )
    length = pl.col("valid_to") - pl.col("valid_from")
    product_frame = (
        (pl.concat(products) if products else pl.DataFrame(schema=TAF_PRODUCT_SCHEMA))
        .unique("product_id", keep="last", maintain_order=True)
        .join(formats, on="product_id", how="left")
        .with_columns(
            window_valid=(length > timedelta(0)) & (length <= timedelta(hours=MAX_TAF_HOURS))
        )
        .sort("issued")
    )
    group_frame = (
        group_frame.join(formats, on="product_id", how="left")
        .join(product_frame.select("product_id", "window_valid"), on="product_id", how="left")
        .sort("issued", "fx_valid", maintain_order=True)
    )
    extra = {"known_time": pl.col("issued") + KNOWLEDGE_LAG, "licence_class": pl.lit(LICENCE)}
    product_frame = product_frame.with_columns(**extra)
    group_frame = group_frame.with_columns(**extra)
    orphans = group_frame.join(product_frame, on="product_id", how="anti")
    summary = {
        "products": product_frame.height,
        "amendments": int(product_frame["is_amendment"].sum()),
        "old_format": int(product_frame["old_format"].sum()),
        "window_missing": product_frame["valid_to"].null_count(),
        "window_invalid": int((~product_frame["window_valid"]).sum()),
        "groups": group_frame.height,
        "groups_without_product": orphans.height,
    }
    return (
        _write(product_frame, stage_path(TAF_SOURCE, station, year, data_root, "products")),
        _write(group_frame, stage_path(TAF_SOURCE, station, year, data_root, "groups")),
        summary,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fetch and stage IEM METAR and TAF archives.")
    parser.add_argument("--product", choices=PRODUCTS, action="append", help="default: both")
    parser.add_argument("--station", default=STATION, help="FAA identifier, e.g. ORD")
    parser.add_argument("--from", dest="first", default=FIRST_MONTH, help="YYYY-MM")
    parser.add_argument("--to", dest="last", help="YYYY-MM (default: this month, UTC)")
    parser.add_argument("--pause", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--stage-only", action="store_true", help="skip downloading")
    args = parser.parse_args(argv)
    products = tuple(args.product or PRODUCTS)
    last = args.last or f"{datetime.now(UTC):%Y-%m}"
    root = data_dir()
    if not args.stage_only:
        sweep_partial_downloads(root / "tmp")
        with make_client() as client:
            stats = crawl(
                args.first, last, client=client, data_root=root, products=products,
                station=args.station, pause=args.pause, log=lambda line: print(line, flush=True),
            )  # fmt: skip
        print(f"crawl done: {stats}", flush=True)
    for year in range(int(args.first[:4]), int(last[:4]) + 1):
        try:
            if "metar" in products:
                _, metar = stage_metar_year(root, year, args.station)
                print(f"{year}: staged metar {metar}", flush=True)
            if "taf" in products:
                *_, summary = stage_taf_year(root, year, args.station)
                print(f"{year}: staged taf {summary}", flush=True)
                *_, summary = stage_taf_bulletins(root, year, args.station)
                print(f"{year}: parsed taf bulletins {summary}", flush=True)
        except Exception as exc:  # report and continue with the next year
            print(f"{year}: STAGE FAILED: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
