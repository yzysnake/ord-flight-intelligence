"""IEM METAR/TAF backfill: request plan, typed parsing, IEM fault flags, polite resumable crawl."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import polars as pl

from ordfi.ingest import iem
from ordfi.ingest.raw import read_manifest

JULY = date(2019, 7, 1)
LATER = date(2026, 10, 27)

METAR_HEADER = (
    "station,valid,tmpf,dwpf,relh,drct,sknt,p01i,alti,mslp,vsby,gust,skyc1,skyc2,skyc3,skyc4,"
    "skyl1,skyl2,skyl3,skyl4,wxcodes,ice_accretion_1hr,ice_accretion_3hr,ice_accretion_6hr,"
    "peak_wind_gust,peak_wind_drct,peak_wind_time,feel,metar,snowdepth"
)
ROUTINE = {
    "station": "ORD", "valid": "2019-07-15 00:51", "tmpf": "78.00", "sknt": "3.00", "p01i": "T",
    "vsby": "10.00", "skyc1": "FEW", "skyl1": "4500.00", "peak_wind_gust": "32.00",
    "peak_wind_time": "2019-07-15 00:31",
    "metar": "KORD 150051Z 18003KT 10SM FEW045 26/18 A3006 RMK AO2 PK WND 27032/0031 P0000",
}  # fmt: skip
SPECIAL = {"station": "ORD", "valid": "2019-07-15 00:09", "wxcodes": "TSRA",
           "metar": "KORD 150009Z 16003KT 10SM TSRA FEW042"}  # fmt: skip
HFMETAR = {"station": "ORD", "valid": "2019-07-15 00:05", "sknt": "2.00",
           "metar": "KORD 150005Z AUTO 16002KT 10SM MADISHF"}  # fmt: skip


def metar_csv(*rows: dict[str, str]) -> str:
    columns = METAR_HEADER.split(",")
    return "\n".join([METAR_HEADER, *(",".join(row.get(c, "") for c in columns) for row in rows)])


GOOD = "201907150521-KLOT-FTUS43-TAFORD"
BOUNDARY = "201907311720-KLOT-FTUS43-TAFORD"  # IEM dates its window end in the wrong month
OLD = "201907200900-KLOT-FTUS43-TAFORD-AAA"  # stands in for a pre-2008 TAF: FMhhmm, no window
TAF_CSV = f"""station,valid,fx_valid,raw,is_tempo,fx_valid_end,sknt,drct,gust,visibility,\
presentwx,skyc,skyl,ws_level,ws_drct,ws_sknt,product_id,ftype,is_amendment
KORD,2019-07-15 05:21,2019-07-15 05:21,20004KT P6SM FEW050 SCT250,False,,4.0,200.0,0.0,6.01,[],\
"['FEW', 'SCT']","[5000, 25000]",,,,{GOOD},Observation,False
KORD,2019-07-15 05:21,2019-07-15 15:00,PROB30 1515/1518 TSRA BKN040CB,False,2019-07-15 18:00,\
,,,,"['TSRA']","['BKN']",[4000],,,,{GOOD},Probability 30,False
KORD,2019-07-31 17:20,2019-07-31 17:20,03011KT P6SM SKC,False,,11.0,30.0,0.0,6.01,[],\
['SKC'],[None],,,,{BOUNDARY},Observation,False
KORD,2019-07-20 09:00,2019-07-23 00:00,FM2300 17010KT P6SM OVC050,False,,10.0,170.0,0.0,6.01,[],\
['OVC'],[5000],,,,{OLD},Forecast,True
KORD,2019-07-20 10:00,2019-07-20 10:00,00000KT P6SM SKC,False,,0.0,0.0,0.0,6.01,[],\
['SKC'],[None],,,,ORPHAN,Observation,False
"""
OVERVIEW = {
    "data": [
        {"station": "KORD", "product_id": GOOD, "is_amendment": False,
         "utc_issued": "2019-07-15T05:21:00Z", "utc_issue": "2019-07-15T06:00:00Z",
         "utc_expire": "2019-07-16T12:00:00Z", "min_visibility": 6.01},
        {"station": "KORD", "product_id": BOUNDARY, "is_amendment": False,
         "utc_issued": "2019-07-31T17:20:00Z", "utc_issue": "2019-07-31T18:00:00Z",
         "utc_expire": "2019-07-02T00:00:00Z", "min_visibility": 6.01},
        {"station": "KORD", "product_id": OLD, "is_amendment": True,
         "utc_issued": "2019-07-20T09:00:00Z", "utc_issue": None, "utc_expire": None,
         "min_visibility": None},
    ]
}  # fmt: skip
BULLETINS = "\x01\n255 \nFTUS43 KLOT 150521\nTAFORD\nTAF\nKORD 150521Z 1506/1612 20004KT=\n\x03\n"


def mock_client(seen: list[str], fail: str | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        seen.append(url)
        if fail and fail in url:
            return httpx.Response(404)
        path = request.url.path
        if path.endswith("asos.py"):
            rows = {"3": (ROUTINE, ROUTINE), "4": (SPECIAL,), "1": (HFMETAR,)}
            return httpx.Response(200, text=metar_csv(*rows[request.url.params["report_type"]]))
        if path.endswith("taf.py"):
            return httpx.Response(200, text=TAF_CSV)
        if path.endswith("taf_overview.json"):
            return httpx.Response(200, json=OVERVIEW)
        return httpx.Response(200, text=BULLETINS)

    return httpx.Client(transport=httpx.MockTransport(handler))


def run_crawl(root: Path, seen: list[str], today: date = LATER, fail: str | None = None) -> None:
    with mock_client(seen, fail) as client:
        iem.crawl("2019-07", "2019-07", client=client, data_root=root, pause=0, today=today,
                  log=lambda _: None)  # fmt: skip


def test_month_requests() -> None:
    metar = iem.month_requests("metar", "ORD", JULY)
    assert [r.key for r in metar] == ["ORD/routine/2019-07", "ORD/special/2019-07",
                                      "ORD/hfmetar/2019-07"]  # fmt: skip
    assert all(f"report_type={code}" in r.url for r, code in zip(metar, (3, 4, 1), strict=True))
    assert "sts=2019-07-01T00:00Z&ets=2019-08-01T00:00Z" in metar[0].url
    groups, products, bulletins = iem.month_requests("taf", "ORD", date(2019, 12, 1))
    assert "station=ORD" in groups.url and "ets=2020-01-01T00:00Z" in groups.url
    assert "station=KORD" in products.url  # the overview needs the ICAO code
    assert "pil=TAFORD" in bulletins.url and "edate=2020-01-01T00:00Z" in bulletins.url
    assert {r.partition for r in metar} == {"ORD/2019"}


def test_read_metar_types_trace_and_missing(tmp_path: Path) -> None:
    path = tmp_path / "routine.csv"
    path.write_text(metar_csv(ROUTINE))
    row = iem.read_metar(path, "routine", "abc").row(0, named=True)
    assert row["valid"] == datetime(2019, 7, 15, 0, 51, tzinfo=UTC)
    assert row["report_type"] == "routine" and row["raw_sha256"] == "abc"
    assert row["p01i"] == iem.TRACE and row["tmpf"] == 78.0 and row["dwpf"] is None
    assert row["peak_wind_time"] == datetime(2019, 7, 15, 0, 31, tzinfo=UTC)
    empty = tmp_path / "empty.csv"
    empty.write_text(METAR_HEADER + "\n")
    assert iem.read_metar(empty, "hfmetar").schema == iem.METAR_SCHEMA


def test_crawl_fetches_each_month_once_and_refreshes_recent(tmp_path: Path) -> None:
    seen: list[str] = []
    run_crawl(tmp_path, seen)
    assert len(seen) == 6  # three METAR report types + TAF groups, products and bulletins
    run_crawl(tmp_path, seen)
    assert len(seen) == 6  # a past month is not fetched again
    run_crawl(tmp_path, seen, today=date(2019, 8, 2))
    assert len(seen) == 12  # a month that ended < REFRESH_DAYS ago is re-checked
    stored = {r.path for r in read_manifest(tmp_path, iem.TAF_SOURCE)}
    assert "raw/iem_taf/ORD/2019/ORD-taf-bulletins-2019-07.txt" in stored
    assert len(read_manifest(tmp_path, iem.METAR_SOURCE)) == 3  # unchanged payloads not re-stored


def test_failed_request_is_counted_and_retried_next_run(tmp_path: Path) -> None:
    seen: list[str] = []
    with mock_client(seen, fail="report_type=1") as client:
        stats = iem.crawl("2019-07", "2019-07", client=client, data_root=tmp_path, pause=0,
                          today=LATER, log=lambda _: None)  # fmt: skip
    assert (stats.fetched, stats.failures) == (5, 1)
    run_crawl(tmp_path, seen)
    assert seen[-1].count("report_type=1") == 1 and len(seen) == 7  # only the failed one


def test_stage_metar_year(tmp_path: Path) -> None:
    run_crawl(tmp_path, [])
    path, summary = iem.stage_metar_year(tmp_path, 2019)
    assert path == tmp_path / "stage/iem_asos_metar/station=ORD/year=2019/data.parquet"
    assert summary == {"rows": 3, "routine": 1, "special": 1, "hfmetar": 1, "duplicates": 1,
                       "routine_hours": 1}  # fmt: skip
    frame = pl.read_parquet(path)
    assert frame["report_type"].to_list() == ["hfmetar", "special", "routine"]  # by valid time
    assert (frame["known_time"] - frame["valid"]).unique().to_list() == [timedelta(minutes=10)]
    assert frame["licence_class"].unique().to_list() == ["public-domain"]


def test_stage_taf_year_flags_iem_faults(tmp_path: Path) -> None:
    run_crawl(tmp_path, [])
    products_path, groups_path, summary = iem.stage_taf_year(tmp_path, 2019)
    assert summary == {"products": 3, "amendments": 1, "old_format": 1, "window_missing": 1,
                       "window_invalid": 1, "groups": 5, "groups_without_product": 1}  # fmt: skip
    products = {r["product_id"]: r for r in pl.read_parquet(products_path).iter_rows(named=True)}
    assert (products[GOOD]["old_format"], products[GOOD]["window_valid"]) == (False, True)
    assert (products[BOUNDARY]["old_format"], products[BOUNDARY]["window_valid"]) == (False, False)
    assert products[OLD]["old_format"] is True and products[OLD]["window_valid"] is None
    groups = pl.read_parquet(groups_path)
    orphan = groups.filter(pl.col("product_id") == "ORPHAN").row(0, named=True)
    assert (orphan["old_format"], orphan["window_valid"]) == (False, None)  # format from its text
    first = groups.filter(pl.col("product_id") == GOOD).row(0, named=True)
    assert (first["skyc"], first["skyl"], first["presentwx"]) == (["FEW", "SCT"], [5000, 25000], [])
    prob = groups.filter(pl.col("ftype") == "Probability 30").row(0, named=True)
    assert prob["presentwx"] == ["TSRA"]
    assert prob["fx_valid_end"] == datetime(2019, 7, 15, 18, 0, tzinfo=UTC)
    assert groups.filter(pl.col("product_id") == BOUNDARY)["skyl"].to_list() == [[None]]
    assert groups["known_time"].min() == datetime(2019, 7, 15, 5, 31, tzinfo=UTC)


def test_read_taf_products_parses_overview(tmp_path: Path) -> None:
    path = tmp_path / "overview.json"
    path.write_text(json.dumps(OVERVIEW))
    frame = iem.read_taf_products(path)
    assert frame.schema == iem.TAF_PRODUCT_SCHEMA and frame.height == 3
    assert frame["valid_to"].null_count() == 1
