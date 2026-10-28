"""FAA ATCSCC advisory archive: daily listings, ORD-relevant full texts, staged tables.

Endpoints on fly.faa.gov (public domain):

- **listing**: ``/adv/adv_list?...&date=YYYY-MM-DD`` returns every ATCSCC advisory of a UTC day
  (number, control element, brief title, send time);
- **detail**: ``/adv/adv_otherdis?adv_date=MMDDYYYY&advn=N`` returns one advisory. Program
  advisories are ``KEY: value`` lines (program period, rates, average/maximum delay, cause…).

The crawl is sequential and polite (default one request per second). Raw HTML is stored
verbatim, partitioned by advisory date. Past days are fetched once; the most recent
``REFRESH_DAYS`` are re-fetched because they can still grow.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import polars as pl

from ordfi.ingest.http import download, make_client, sweep_partial_downloads
from ordfi.ingest.raw import LicenceClass, RawRecord, commit_download, load_latest
from ordfi.settings import data_dir

SOURCE_ID = "faa_atcscc_advisories"
LICENCE: LicenceClass = "public-domain"
BASE = "https://www.fly.faa.gov"
FIRST_DAY = date(2001, 6, 1)
REFRESH_DAYS = 2
_LIST_QUERY = (
    "whichAdvisories=ATCSCC&advisoryCategory=All&airflow=true&_airflow=on&ctop=true&_ctop=on"
    "&gStop=true&_gStop=on&gDelay=true&_gDelay=on&route=true&_route=on&other=true&_other=on"
)


def listing_url(day: date) -> str:
    return f"{BASE}/adv/adv_list?{_LIST_QUERY}&date={day.isoformat()}"


def detail_url(day: date, number: int) -> str:
    return f"{BASE}/adv/adv_otherdis?adv_date={day:%m%d%Y}&advn={number}"


# --- parsing ---------------------------------------------------------------------------------

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_LINK = re.compile(r"adv_otherdis\?adv_date=(\d{8})&(?:amp;)?advn=(\d+)", re.I)
_PRE = re.compile(r"<pre[^>]*>(.*?)</pre>", re.I | re.S)
_FIELD = re.compile(r"^([A-Z][A-Z0-9 /()'.-]{1,60}):\s*(.*)$")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", fragment))).strip()


@dataclass(frozen=True)
class ListingRow:
    """One advisory as listed on its day's index page."""

    adv_date: date
    number: int
    control_element: str
    title: str
    send_time: datetime


def parse_listing(page: str) -> list[ListingRow]:
    """Advisories on a listing page (rows with five cells whose first links to a detail)."""
    rows: list[ListingRow] = []
    for row in _ROW.findall(page):
        cells = _CELL.findall(row)
        link = _LINK.search(cells[0]) if len(cells) == 5 else None
        if link is None:
            continue
        adv_date = datetime.strptime(link.group(1), "%m%d%Y").date()
        sent = datetime.strptime(_text(cells[4]), "%m/%d/%y %H:%M").replace(tzinfo=UTC)
        rows.append(
            ListingRow(adv_date, int(link.group(2)), _text(cells[1]), _text(cells[3]), sent)
        )
    return rows


def advisory_text(page: str) -> str:
    """The advisory body (the ``<pre>`` block), or the page text if there is none."""
    block = _PRE.search(page)
    return html.unescape(_TAG.sub("", block.group(1) if block else page)).strip()


def parse_fields(text: str) -> dict[str, str]:
    """``KEY: value`` lines of an advisory.

    Indented lines continue the previous value. Other free-standing lines (e.g. "DISREGARD EDCTS
    FOR DEST ORD", route tables) are collected, in order, under ``NOTES``.
    """
    fields: dict[str, str] = {}
    notes: list[str] = []
    last: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _FIELD.match(stripped)
        if match:
            last = match.group(1).strip()
            fields[last] = match.group(2).strip()
        elif last is not None and line[:1].isspace():
            fields[last] = f"{fields[last]} {stripped}".strip()
        else:
            notes.append(stripped)
    if notes:
        fields["NOTES"] = " / ".join(notes)
    return fields


_PERIOD_KEYS = ("CUMULATIVE PROGRAM PERIOD", "PROGRAM PERIOD", "GROUND STOP PERIOD")


def first_field(fields: dict[str, str], *names: str) -> str | None:
    """Value of the first of ``names`` present in ``fields``."""
    return next((fields[name] for name in names if fields.get(name)), None)


def period_field(fields: dict[str, str]) -> str | None:
    """Program/stop period, cancellation period or reroute validity, whichever is present.

    GDP advisories before November 2006 have no ``PROGRAM PERIOD``; their ``ARRIVALS ESTIMATED
    FOR`` window is used instead (for a revision it starts at the revision, not the program start).
    """
    preferred = first_field(fields, *_PERIOD_KEYS)
    if preferred:
        return preferred
    others = [value for key, value in fields.items() if key.endswith("PERIOD") and value]
    return others[0] if others else first_field(fields, "ARRIVALS ESTIMATED FOR", "VALID")


def category(title: str) -> str:
    """Coarse advisory category from its brief title."""
    upper = title.upper()
    rules = [
        ("gdp", r"GROUND DELAY|\bGDP\b"),
        ("ground_stop", r"GROUND STOP|\bGS\b"),
        ("afp", r"AIRSPACE FLOW|\bAFP\b"),
        ("ctop", r"\bCTOP\b"),
        ("ops_plan", r"OPERATIONS PLAN"),
        ("reroute", r"ROUTE"),
    ]
    for name, pattern in rules:
        if re.search(pattern, upper):
            return name
    return "other"


def is_ord_related(row: ListingRow) -> bool:
    """ORD airport, Chicago Center (ZAU) or Chicago TRACON (C90) in the element or title."""
    tokens = set(re.split(r"[^A-Z0-9]+", f"{row.control_element} {row.title}".upper()))
    return bool(tokens & {"ORD", "KORD", "ZAU", "C90"})


# --- crawl -----------------------------------------------------------------------------------


@dataclass
class CrawlStats:
    days: int = 0
    listings_fetched: int = 0
    details_fetched: int = 0
    failures: int = 0


def _days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def _fetch(
    client: httpx.Client,
    url: str,
    key: str,
    filename: str,
    partition: str,
    root: Path,
    index: dict[str, RawRecord],
) -> RawRecord:
    dl = download(client, url, root / "tmp")
    record, _ = commit_download(
        root, SOURCE_ID, key, filename, dl, LICENCE, partition=partition, index=index
    )
    return record


def crawl(
    first: date,
    last: date,
    *,
    client: httpx.Client,
    data_root: Path,
    select: Callable[[ListingRow], bool] = is_ord_related,
    pause: float = 1.0,
    today: date | None = None,
    log: Callable[[str], None] = print,
) -> CrawlStats:
    """Fetch listings for ``first..last`` and full texts for advisories chosen by ``select``."""
    today = today or datetime.now(UTC).date()
    index = load_latest(data_root, SOURCE_ID)
    stats = CrawlStats()

    def polite() -> None:
        if pause > 0:
            time.sleep(pause)

    for day in _days(first, last):
        stats.days += 1
        partition = f"{day:%Y}/{day:%m}"
        key = f"listing/{day.isoformat()}"
        record = index.get(key)
        try:
            if record is None or (today - day).days <= REFRESH_DAYS:
                record = _fetch(
                    client, listing_url(day), key, f"listing-{day.isoformat()}.html",
                    f"listings/{partition}", data_root, index,
                )  # fmt: skip
                stats.listings_fetched += 1
                polite()
            page = (data_root / record.path).read_text(encoding="utf-8", errors="replace")
            wanted = [row for row in parse_listing(page) if select(row)]
            for row in wanted:
                detail_key = f"advisory/{row.adv_date.isoformat()}/{row.number:03d}"
                if detail_key in index:
                    continue
                _fetch(
                    client, detail_url(row.adv_date, row.number), detail_key,
                    f"advisory-{row.adv_date.isoformat()}-{row.number:03d}.html",
                    f"advisories/{partition}", data_root, index,
                )  # fmt: skip
                stats.details_fetched += 1
                polite()
        except Exception as exc:  # keep a long crawl going; failed days are retried next run
            stats.failures += 1
            log(f"{day}: FAILED: {type(exc).__name__}: {exc}")
            continue
        if day.day == 1 or day == last:
            log(
                f"{day}: days={stats.days} listings={stats.listings_fetched} "
                f"details={stats.details_fetched} failures={stats.failures}"
            )
    return stats


# --- staging ---------------------------------------------------------------------------------

UTC_TS = pl.Datetime("us", "UTC")
INDEX_SCHEMA = pl.Schema(
    {
        "adv_date": pl.Date(),
        "number": pl.Int32(),
        "control_element": pl.String(),
        "title": pl.String(),
        "category": pl.String(),
        "is_cancellation": pl.Boolean(),
        "ord_related": pl.Boolean(),
        "send_time": UTC_TS,
        "known_time": UTC_TS,
        "listing_fetched_at": UTC_TS,
    }
)
ADVISORY_SCHEMA = pl.Schema(
    {
        "adv_date": pl.Date(),
        "number": pl.Int32(),
        "text": pl.String(),
        "ctl_element": pl.String(),
        "element_type": pl.String(),
        "period": pl.String(),
        "program_rate": pl.String(),
        "average_delay": pl.String(),
        "maximum_delay": pl.String(),
        "reason": pl.String(),
        "fields_json": pl.String(),
        "raw_sha256": pl.String(),
    }
)


def _records(data_root: Path, prefix: str, year: int) -> Iterable[RawRecord]:
    for key, record in sorted(load_latest(data_root, SOURCE_ID).items()):
        if key.startswith(f"{prefix}/{year:04d}-"):
            yield record


def stage_year(data_root: Path, year: int) -> tuple[Path, Path]:
    """Build the year's ``index`` (all listed advisories) and ``advisories`` (full texts) tables."""
    listed: list[dict[str, object]] = []
    for record in _records(data_root, "listing", year):
        page = (data_root / record.path).read_text(encoding="utf-8", errors="replace")
        for row in parse_listing(page):
            listed.append(
                {
                    "adv_date": row.adv_date,
                    "number": row.number,
                    "control_element": row.control_element,
                    "title": row.title,
                    "category": category(row.title),
                    "is_cancellation": bool(re.search(r"\bCNX\b|CANCEL", row.title.upper())),
                    "ord_related": is_ord_related(row),
                    "send_time": row.send_time,
                    "known_time": row.send_time,
                    "listing_fetched_at": record.fetched_at_dt,
                }
            )
    details: list[dict[str, object]] = []
    for record in _records(data_root, "advisory", year):
        _, day, number = record.key.split("/")
        text = advisory_text(
            (data_root / record.path).read_text(encoding="utf-8", errors="replace")
        )
        fields = parse_fields(text)
        details.append(
            {
                "adv_date": date.fromisoformat(day),
                "number": int(number),
                "text": text,
                "ctl_element": first_field(
                    fields, "CTL ELEMENT", "DESTINATION AIRPORT", "CONSTRAINED AREA", "AIRPORT"
                ),
                "element_type": fields.get("ELEMENT TYPE"),
                "period": period_field(fields),
                # Labelled "PROGRAM AAR" until May 2004.
                "program_rate": first_field(fields, "PROGRAM RATE", "PROGRAM AAR"),
                "average_delay": fields.get("AVERAGE DELAY"),
                "maximum_delay": fields.get("MAXIMUM DELAY"),
                "reason": first_field(fields, "IMPACTING CONDITION", "REASON"),
                "fields_json": json.dumps(fields, sort_keys=True),
                "raw_sha256": record.sha256,
            }
        )
    out_dir = data_root / "stage" / SOURCE_ID
    paths = []
    tables = (("index", listed, INDEX_SCHEMA), ("advisories", details, ADVISORY_SCHEMA))
    for name, rows, schema in tables:
        target = out_dir / name / f"year={year:04d}" / "data.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        frame = pl.DataFrame(rows, schema=schema).with_columns(licence_class=pl.lit(LICENCE))
        tmp = target.with_name(".data.parquet.tmp")
        frame.write_parquet(tmp, compression="zstd")
        os.replace(tmp, target)
        paths.append(target)
    return paths[0], paths[1]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Crawl and stage the FAA ATCSCC advisory archive.")
    parser.add_argument("--from", dest="first", default=FIRST_DAY.isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--to", dest="last", help="YYYY-MM-DD (default: yesterday, UTC)")
    parser.add_argument("--pause", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--stage-only", action="store_true", help="skip crawling")
    args = parser.parse_args(argv)
    first = date.fromisoformat(args.first)
    last = date.fromisoformat(args.last) if args.last else datetime.now(UTC).date() - timedelta(1)
    root = data_dir()
    if not args.stage_only:
        sweep_partial_downloads(root / "tmp")
        with make_client() as client:
            stats = crawl(
                first, last, client=client, data_root=root, pause=args.pause,
                log=lambda line: print(line, flush=True),
            )  # fmt: skip
        print(f"crawl done: {stats}", flush=True)
    for year in range(first.year, last.year + 1):
        index_path, detail_path = stage_year(root, year)
        rows = pl.scan_parquet(index_path).select(pl.len()).collect().item()
        texts = pl.scan_parquet(detail_path).select(pl.len()).collect().item()
        print(f"{year}: staged index rows={rows} advisories={texts}", flush=True)


if __name__ == "__main__":
    main()
