"""IEM MOS archive: monthly requests, the crawl, and staging with aligned columns."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import polars as pl

from ordfi.ingest import mos
from ordfi.ingest.raw import read_manifest

GFS_CSV = (
    "runtime,ftime,model,n_x,tmp,dpt,cld,wdr,wsp,p06,p12,q06,q12,t06_1,t06_2,t12_1,t12_2,cig,"
    "vis,obv,station,t06,t12\n"
    "2019-07-15 00:00:00,2019-07-15 06:00:00,GFS,,72,65,BK,260,7,20,,0,,12.0,1.0,,,4,5,BR ,"
    "KORD,,\n"
    "2019-07-15 00:00:00,2019-07-15 09:00:00,GFS,,70,64,OV,250,6,,,,,,,,,3,7,N ,KORD,,\n"
)
# A winter month adds precipitation-type columns; -99 is missing.
GFS_WINTER_CSV = (
    "runtime,ftime,model,tmp,cig,vis,poz,pos,typ,snw,station\n"
    "2019-07-15 00:00:00,2019-07-15 06:00:00,GFS,30,2,3,10,85,S,2,KORD\n"
    "2019-07-15 06:00:00,2019-07-15 12:00:00,GFS,-99,6,7,,,,,KORD\n"
)
NBS_CSV = (
    "runtime,ftime,model,tmp,wsp,gst,t03,cig,vis,ifc,ifv,psn,station\n"
    "2019-07-15 01:00:00,2019-07-15 06:00:00,NBS,72,8,15,40,-88,100,0,0,0,KORD\n"
    "2019-07-15 01:00:00,2019-07-15 09:00:00,NBS,70,6,-99,10,8,25,60,35,0,KORD\n"
)


def mock_client(seen: list[str], body: dict[str, str]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, text=body[request.url.params["model"]])

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_month_urls_ask_for_one_model_and_month() -> None:
    url = mos.month_url(mos.NBS, date(2019, 12, 1))
    assert "station=KORD&model=NBS" in url and "sts=2019-12-01T00:00Z&ets=2020-01-01T00:00Z" in url
    assert mos.month_key(mos.GFS, date(2019, 7, 1)) == "KORD/GFS/2019-07"


def test_crawl_starts_at_each_models_first_month_and_fetches_once(tmp_path: Path) -> None:
    seen: list[str] = []
    later = date(2020, 1, 1)
    with mock_client(seen, {"GFS": GFS_CSV, "NBS": NBS_CSV}) as client:
        stats = mos.crawl("2018-10", "2018-11", client=client, data_root=tmp_path, pause=0,
                          today=later, log=lambda _: None)  # fmt: skip
        assert (stats.fetched, stats.failures) == (3, 0)  # GFS Oct and Nov, NBS from Nov only
        mos.crawl("2018-10", "2018-11", client=client, data_root=tmp_path, pause=0,
                  today=later, log=lambda _: None)  # fmt: skip
    assert len(seen) == 3  # past months are not fetched again
    stored = {record.path for record in read_manifest(tmp_path, mos.SOURCE_ID)}
    assert "raw/iem_mos/KORD/NBS/2018/KORD-NBS-2018-11.csv" in stored


def test_staging_aligns_columns_and_dates_knowledge(tmp_path: Path) -> None:
    seen: list[str] = []
    later = date(2020, 1, 1)
    with mock_client(seen, {"GFS": GFS_CSV, "NBS": NBS_CSV}) as client:
        mos.crawl("2019-07", "2019-07", client=client, data_root=tmp_path, pause=0,
                  today=later, log=lambda _: None)  # fmt: skip
    with mock_client(seen, {"GFS": GFS_WINTER_CSV, "NBS": NBS_CSV}) as client:
        mos.crawl("2019-08", "2019-08", client=client, data_root=tmp_path, pause=0,
                  today=later, models=[mos.GFS], log=lambda _: None)  # fmt: skip
    path, summary = mos.stage_year(tmp_path, mos.GFS, 2019)
    gfs = pl.read_parquet(path)
    assert summary["runs"] == 2 and summary["duplicates"] == 1  # August repeats a July row
    first = gfs.row(0, named=True)  # the later file wins: winter columns, no thunder
    assert (first["cig"], first["vis"], first["pos"], first["typ"], first["t06_1"]) == (
        2, 3, 85, "S", None
    )  # fmt: skip
    assert gfs["tmp"].to_list() == [30, 70, None]  # -99 is missing
    assert gfs["obv"].to_list()[1] == "N"  # trailing spaces stripped
    assert first["known_time"] == datetime(2019, 7, 15, 5, tzinfo=UTC)  # run + 5 h
    nbs_path, nbs_summary = mos.stage_year(tmp_path, mos.NBS, 2019)
    assert nbs_path.parts[-4:-2] == ("nbs", "station=KORD")
    nbs = pl.read_parquet(nbs_path)
    assert nbs["cig"].to_list() == [-88, 8] and nbs["gst"].to_list() == [15, None]
    assert nbs["known_time"].to_list()[0] == datetime(2019, 7, 15, 1, tzinfo=UTC) + timedelta(
        minutes=70
    )
    assert nbs_summary["max_lead_hours"] == 8


def test_a_run_on_new_years_day_is_staged_in_its_own_year(tmp_path: Path) -> None:
    december = (
        "runtime,ftime,model,cig,vis,station\n"
        "2019-12-31 18:00:00,2020-01-01 00:00:00,GFS,6,7,KORD\n"
        "2020-01-01 00:00:00,2020-01-01 06:00:00,GFS,5,7,KORD\n"  # also in January's file
    )
    january = (
        "runtime,ftime,model,cig,vis,station\n"
        "2020-01-01 00:00:00,2020-01-01 06:00:00,GFS,5,7,KORD\n"
    )
    for month, body in (("2019-12", december), ("2020-01", january)):
        with mock_client([], {"GFS": body}) as client:
            mos.crawl(month, month, client=client, data_root=tmp_path, pause=0,
                      today=date(2021, 1, 1), models=[mos.GFS], log=lambda _: None)  # fmt: skip
    years = [pl.read_parquet(mos.stage_year(tmp_path, mos.GFS, year)[0]) for year in (2019, 2020)]
    assert [frame["runtime"].dt.year().to_list() for frame in years] == [[2019], [2020]]
