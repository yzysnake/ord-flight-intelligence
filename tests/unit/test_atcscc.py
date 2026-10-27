"""ATCSCC advisory crawler: listing/detail parsing, selection, polite resumable crawl, staging."""

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import polars as pl
import pytest

from ordfi.ingest import atcscc
from ordfi.ingest.raw import read_manifest

DAY = date(2019, 7, 15)


def listing_row(number: int, element: str, title: str, sent: str) -> str:
    href = f"/adv/adv_otherdis?adv_date=07152019&advn={number}"
    return (
        f'<tr> <td> <a href="{href}">{number:03d}</a> </td> <td>{element}</td> '
        f"<td>07/15/19</td> <td>{title}</td> <td>07/15/19 {sent}</td> </tr>"
    )


LISTING = (
    "<table><tr><th>NUMBER</th><th>CONTROL<BR>ELEMENT</th><th>DATE</th><th>BRIEF TITLE</th>"
    "<th>SEND TIME</th></tr>"
    + listing_row(3, "ORD/ZAU", "CDM GROUND DELAY PROGRAM", "00:57")
    + listing_row(2, "DCC", "OCEANIC_ROUTE_CLOSURES_OPEN_FYI", "00:34")
    + listing_row(1, "ORD/ZAU", "ORD GROUND STOP CNX FOR ZBW/ZDC/ZNY/CZY", "00:26")
    + "<tr><td>spacer</td></tr></table>"
)

DETAIL = """<html><body><pre>
CTL ELEMENT: ORD
ELEMENT TYPE: APT
ARRIVALS ESTIMATED FOR: 15/0039Z - 15/0259Z
CUMULATIVE PROGRAM PERIOD: 14/2219Z - 15/0259Z
PROGRAM RATE: 76/76/96
MAXIMUM DELAY: 758
AVERAGE DELAY: 130
IMPACTING CONDITION: WEATHER / THUNDERSTORMS
COMMENTS: GROUND STOP CANCELED.
  TRAFFIC RELEASED ON EDCTS.
</pre></body></html>"""


def test_parse_listing() -> None:
    rows = atcscc.parse_listing(LISTING)
    assert [r.number for r in rows] == [3, 2, 1]
    first = rows[0]
    assert first.adv_date == DAY and first.control_element == "ORD/ZAU"
    assert first.title == "CDM GROUND DELAY PROGRAM"
    assert first.send_time == datetime(2019, 7, 15, 0, 57, tzinfo=UTC)


def test_parse_detail_fields() -> None:
    fields = atcscc.parse_fields(atcscc.advisory_text(DETAIL))
    assert fields["CTL ELEMENT"] == "ORD"
    assert fields["PROGRAM RATE"] == "76/76/96"
    assert fields["AVERAGE DELAY"] == "130"
    assert fields["IMPACTING CONDITION"] == "WEATHER / THUNDERSTORMS"
    assert fields["COMMENTS"] == "GROUND STOP CANCELED. TRAFFIC RELEASED ON EDCTS."


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("CDM GROUND DELAY PROGRAM", "gdp"),
        ("CDM GROUND DELAY PROGRAM CNX", "gdp"),
        ("CDM GROUND STOP", "ground_stop"),
        ("CDM GS CNX", "ground_stop"),
        ("OPERATIONS PLAN", "ops_plan"),
        ("REROUTE CANCELLATION", "reroute"),
        ("AFP FCAA05 CONTROL", "afp"),
        ("VOLCANIC ACTIVITY BULLETIN - POPOCATEPETL", "other"),
    ],
)
def test_category(title: str, expected: str) -> None:
    assert atcscc.category(title) == expected


def test_ord_selection() -> None:
    rows = atcscc.parse_listing(LISTING)
    assert [atcscc.is_ord_related(r) for r in rows] == [True, False, True]
    reroute = atcscc.ListingRow(DAY, 76, "DCC", "ROUTE RQD NAME: ORD_CDR_SWAP AREA: KORD KMDW",
                                datetime(2019, 7, 15, 21, 42, tzinfo=UTC))  # fmt: skip
    assert atcscc.is_ord_related(reroute)


def mock_client(seen: list[str]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if "adv_list" in request.url.path:
            page = LISTING if request.url.params["date"] == DAY.isoformat() else "<table></table>"
            return httpx.Response(200, text=page)
        return httpx.Response(200, text=DETAIL)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_crawl_fetches_listing_and_selected_details_once(tmp_path: Path) -> None:
    seen: list[str] = []
    later = date(2026, 10, 27)
    with mock_client(seen) as client:
        stats = atcscc.crawl(DAY, DAY, client=client, data_root=tmp_path, pause=0, today=later,
                             log=lambda _: None)  # fmt: skip
        assert (stats.listings_fetched, stats.details_fetched, stats.failures) == (1, 2, 0)
        assert sum("adv_otherdis" in u for u in seen) == 2  # only the two ORD advisories
        again = atcscc.crawl(DAY, DAY, client=client, data_root=tmp_path, pause=0, today=later,
                             log=lambda _: None)  # fmt: skip
    assert (again.listings_fetched, again.details_fetched) == (0, 0)
    keys = {r.key for r in read_manifest(tmp_path, atcscc.SOURCE_ID)}
    assert keys == {"listing/2019-07-15", "advisory/2019-07-15/003", "advisory/2019-07-15/001"}
    stored = [r.path for r in read_manifest(tmp_path, atcscc.SOURCE_ID)]
    assert "raw/faa_atcscc_advisories/listings/2019/07/listing-2019-07-15.html" in stored


def test_recent_days_are_refetched(tmp_path: Path) -> None:
    seen: list[str] = []
    with mock_client(seen) as client:
        for _ in range(2):
            atcscc.crawl(DAY, DAY, client=client, data_root=tmp_path, pause=0, today=DAY,
                         log=lambda _: None)  # fmt: skip
    assert sum("adv_list" in u for u in seen) == 2
    assert len([r for r in read_manifest(tmp_path, atcscc.SOURCE_ID) if "listing" in r.key]) == 1


def test_stage_year(tmp_path: Path) -> None:
    with mock_client([]) as client:
        atcscc.crawl(DAY, DAY, client=client, data_root=tmp_path, pause=0,
                     today=date(2026, 10, 27), log=lambda _: None)  # fmt: skip
    index_path, detail_path = atcscc.stage_year(tmp_path, 2019)
    index = pl.read_parquet(index_path)
    assert index.height == 3
    assert index.filter(pl.col("number") == 3)["category"].item() == "gdp"
    assert index.filter(pl.col("number") == 1)["is_cancellation"].item() is True
    details = pl.read_parquet(detail_path).sort("number")
    assert details["number"].to_list() == [1, 3]
    assert details["average_delay"].to_list() == ["130", "130"]
    assert details["licence_class"].unique().to_list() == ["public-domain"]


def test_typed_fields_across_advisory_kinds() -> None:
    gs_cnx = {"DESTINATION AIRPORT": "ORD", "RELEASED FACILITIES": "ZBW/ZDC/ZNY/CZY"}
    gdp_cnx = {"CTL ELEMENT": "ORD", "GDP CNX PERIOD": "15/0257Z - 15/1814Z"}
    reroute = {
        "CONSTRAINED AREA": "KORD KMDW",
        "REASON": "WEATHER",
        "VALID": "ETD 152030 TO 160100",
    }
    assert atcscc.first_field(gs_cnx, "CTL ELEMENT", "DESTINATION AIRPORT") == "ORD"
    assert atcscc.period_field(gdp_cnx) == "15/0257Z - 15/1814Z"
    assert atcscc.period_field(reroute) == "ETD 152030 TO 160100"
    assert atcscc.first_field(reroute, "IMPACTING CONDITION", "REASON") == "WEATHER"


def test_free_standing_lines_become_notes() -> None:
    text = "CTL ELEMENT: ORD\nGDP CNX PERIOD: 15/0257Z - 15/1814Z\nDISREGARD EDCTS FOR DEST ORD\n"
    fields = atcscc.parse_fields(text)
    assert fields["GDP CNX PERIOD"] == "15/0257Z - 15/1814Z"
    assert fields["NOTES"] == "DISREGARD EDCTS FOR DEST ORD"
