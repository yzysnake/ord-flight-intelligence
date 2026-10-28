"""IEM's MOS archive for ORD: GFS MOS and NBM station guidance, for forecasts beyond the TAF.

``/cgi-bin/request/mos.py`` CSV on mesonet.agron.iastate.edu (public domain; IEM answers HTTP
429 when asked too fast), one request per model and month:

- **GFS MOS** (``GFS``, the MAV bulletin): runs at 00, 06, 12 and 18Z, with 3-hourly
  projections from 6 to 72 h: ceiling and visibility categories, 6- and 12-hour thunderstorm
  and precipitation probabilities, precipitation type, snowfall and wind. IEM has it from
  2003-12; the feature store needs it from 2014-12.
- **NBM** (``NBS``, the National Blend of Models' short-range text bulletin): IEM keeps the 01,
  07, 13 and 19Z cycles, 3-hourly to 72 h: ceiling (100s of ft, -88 unlimited) and visibility
  (1/10 mi), the probabilities of IFR ceiling and visibility, 3- to 12-hour thunder and
  precipitation probabilities, precipitation-type probabilities, snow and ice amounts, wind and
  gusts. From 2018-11-08.

IEM leaves out elements that are empty in a month, so staging aligns the columns by name and
turns the products' missing value, -99, into null. ``known_time`` follows the data-catalog
cards: the GFS MOS run + 5 h and the NBM cycle + 70 min.
"""

from __future__ import annotations

import argparse
import os
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import polars as pl

from ordfi.ingest.http import download, make_client, sweep_partial_downloads
from ordfi.ingest.iem import CrawlStats, months, stage_path
from ordfi.ingest.raw import LicenceClass, commit_download, load_latest
from ordfi.settings import data_dir

SOURCE_ID = "iem_mos"
LICENCE: LicenceClass = "public-domain"
BASE = "https://mesonet.agron.iastate.edu"
STATION = "KORD"  # IEM's MOS archive is keyed by the ICAO code
REFRESH_DAYS = 3
MISSING = -99  # both products' missing value


@dataclass(frozen=True)
class Model:
    code: str  # IEM's model code
    table: str  # staged table name
    first_month: str  # YYYY-MM, the first month fetched
    lag: timedelta  # from the run (cycle) time to the knowledge time
    numbers: tuple[str, ...]  # numeric elements staged
    texts: tuple[str, ...] = ()  # coded elements staged as text

    @property
    def schema(self) -> dict[str, pl.DataType]:
        return {
            "station": pl.String(), "runtime": pl.Datetime("us", "UTC"),
            "ftime": pl.Datetime("us", "UTC"), **{c: pl.Int32() for c in self.numbers},
            **{c: pl.String() for c in self.texts}, "raw_sha256": pl.String(),
        }  # fmt: skip


GFS = Model(
    "GFS", "gfs", "2014-12", timedelta(hours=5),
    ("tmp", "dpt", "wdr", "wsp", "p06", "p12", "q06", "q12", "t06_1", "t06_2", "t12_1",
     "t12_2", "snw", "cig", "vis", "poz", "pos"),
    ("cld", "obv", "typ"),
)  # fmt: skip
NBS = Model(
    "NBS", "nbs", "2018-11", timedelta(minutes=70),
    ("tmp", "dpt", "sky", "wdr", "wsp", "gst", "p06", "p12", "q06", "q12", "dur", "t03",
     "t06_1", "t12_1", "pzr", "psn", "ppl", "pra", "s06", "slv", "i06", "cig", "ifc", "lcb",
     "vis", "ifv"),
)  # fmt: skip
MODELS = {model.code: model for model in (GFS, NBS)}


def _next_month(start: date) -> date:
    return date(start.year + start.month // 12, start.month % 12 + 1, 1)


def month_url(model: Model, start: date, station: str = STATION) -> str:
    span = f"sts={start:%Y-%m-%d}T00:00Z&ets={_next_month(start):%Y-%m-%d}T00:00Z"
    return f"{BASE}/cgi-bin/request/mos.py?station={station}&model={model.code}&{span}&format=csv"


def month_key(model: Model, start: date, station: str = STATION) -> str:
    return f"{station}/{model.code}/{start:%Y-%m}"


# --- crawl -----------------------------------------------------------------------------------


def crawl(
    first: str | None,
    last: str,
    *,
    client: httpx.Client,
    data_root: Path,
    models: Iterable[Model] = MODELS.values(),
    station: str = STATION,
    pause: float = 3.0,
    today: date | None = None,
    log: Callable[[str], None] = print,
) -> CrawlStats:
    """Fetch every month from ``first`` (default: each model's first month) to ``last`` not yet
    stored, plus the most recent months again."""
    today = today or datetime.now(UTC).date()
    index = load_latest(data_root, SOURCE_ID)
    stats = CrawlStats()
    for model in models:
        start = max(first or model.first_month, model.first_month)
        for month in months(start, last) if start <= last else []:
            stats.months += 1
            key = month_key(model, month, station)
            if key in index and (today - _next_month(month)).days >= REFRESH_DAYS:
                continue
            try:
                dl = download(client, month_url(model, month, station), data_root / "tmp")
                commit_download(
                    data_root, SOURCE_ID, key, f"{station}-{model.code}-{month:%Y-%m}.csv", dl,
                    LICENCE, partition=f"{station}/{model.code}/{month:%Y}", index=index,
                )  # fmt: skip
                stats.fetched += 1
            except (httpx.HTTPError, OSError) as exc:
                stats.failures += 1
                log(f"{key}: FAILED {type(exc).__name__}: {exc}")
            if pause:
                time.sleep(pause)
        log(f"{model.code}: crawled to {last} ({stats})")
    return stats


# --- stage -----------------------------------------------------------------------------------


def read_month(path: Path, model: Model, raw_sha256: str = "") -> pl.DataFrame:
    """One month's CSV, aligned to the model's staged columns (missing elements null)."""
    if path.stat().st_size == 0:
        return pl.DataFrame(schema=model.schema)
    frame = pl.read_csv(path, infer_schema=False)
    if frame.is_empty():
        return pl.DataFrame(schema=model.schema)

    def column(name: str) -> pl.Expr:
        return pl.col(name) if name in frame.columns else pl.lit(None, dtype=pl.String())

    def when(name: str) -> pl.Expr:
        return column(name).str.to_datetime("%Y-%m-%d %H:%M:%S", time_zone="UTC")

    number = {
        name: column(name).str.strip_chars().cast(pl.Float64, strict=False).round().cast(pl.Int32)
        for name in model.numbers
    }
    return frame.select(
        station=column("station").str.strip_chars(),
        runtime=when("runtime"),
        ftime=when("ftime"),
        **{name: pl.when(value != MISSING).then(value) for name, value in number.items()},
        **{name: column(name).str.strip_chars().replace("", None) for name in model.texts},
        raw_sha256=pl.lit(raw_sha256),
    ).cast(model.schema)  # type: ignore[arg-type]


def _write(frame: pl.DataFrame, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(".data.parquet.tmp")
    frame.write_parquet(tmp, compression="zstd")
    os.replace(tmp, target)
    return target


def stage_year(
    data_root: Path, model: Model, year: int, station: str = STATION
) -> tuple[Path, dict[str, object]]:
    """A model's runs of one station-year, de-duplicated on (run, valid time), with
    ``known_time``. A month's file also holds the next month's first run, so the year is the
    run's, not the file's; IEM's own files repeat some rows (2018), identically."""
    index = load_latest(data_root, SOURCE_ID)
    prefix = f"{station}/{model.code}/{year:04d}-"
    frames = [read_month(data_root / record.path, model, record.sha256)
              for key, record in sorted(index.items()) if key.startswith(prefix)]  # fmt: skip
    frame = (pl.concat(frames) if frames else pl.DataFrame(schema=model.schema)).filter(
        pl.col("runtime").dt.year() == year
    )
    unique = frame.unique(["runtime", "ftime"], keep="last", maintain_order=True)
    staged = unique.sort("runtime", "ftime").with_columns(
        known_time=pl.col("runtime") + model.lag, licence_class=pl.lit(LICENCE)
    )
    lead = (staged["ftime"] - staged["runtime"]).dt.total_hours()
    summary: dict[str, object] = {
        "rows": staged.height,
        "runs": staged["runtime"].n_unique(),
        "months": staged["runtime"].dt.month().n_unique(),
        "duplicates": frame.height - unique.height,
        "max_lead_hours": int(lead.max()) if staged.height else None,  # type: ignore[arg-type]
    }
    target = stage_path(SOURCE_ID, station, year, data_root, model.table)
    return _write(staged, target), summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fetch and stage IEM's GFS MOS and NBM archives.")
    parser.add_argument("--model", choices=MODELS, action="append", help="default: all")
    parser.add_argument("--station", default=STATION, help="ICAO identifier, e.g. KORD")
    parser.add_argument("--from", dest="first", help="YYYY-MM (default: each model's first)")
    parser.add_argument("--to", dest="last", help="YYYY-MM (default: this month, UTC)")
    parser.add_argument("--pause", type=float, default=3.0, help="seconds between requests")
    parser.add_argument("--stage-only", action="store_true", help="skip downloading")
    args = parser.parse_args(argv)
    chosen = [MODELS[code] for code in (args.model or MODELS)]
    last = args.last or f"{datetime.now(UTC):%Y-%m}"
    root = data_dir()
    if not args.stage_only:
        sweep_partial_downloads(root / "tmp")
        with make_client() as client:
            stats = crawl(args.first, last, client=client, data_root=root, models=chosen,
                          station=args.station, pause=args.pause,
                          log=lambda line: print(line, flush=True))  # fmt: skip
        print(f"crawl done: {stats}", flush=True)
    for model in chosen:
        first_year = int(max(args.first or model.first_month, model.first_month)[:4])
        for year in range(first_year, int(last[:4]) + 1):
            _, summary = stage_year(root, model, year, args.station)
            print(f"{model.code} {year}: staged {summary}", flush=True)


if __name__ == "__main__":
    main()
