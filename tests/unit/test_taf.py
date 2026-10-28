"""TAF bulletin parser: both formats, time resolution, typos, periods and staging."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from ordfi.ingest import taf
from ordfi.ingest.http import Download
from ordfi.ingest.raw import commit_download

# A current-format amendment whose window ends at hour 24 in the next month (IEM misdates it).
CURRENT = """688
FTUS43 KLOT 312057 AAA
TAFORD
TAF AMD
KORD 312057Z 3121/0124 03011KT P6SM FEW050
     FM010200 15005KT 5SM -SHRA BKN025 OVC050
      TEMPO 0104/0106 2SM TSRA BKN015CB
     PROB30 0110/0114 1 1/2SM +TSRA OVC008CB
     FM011500 22012G25KT P6SM SCT050 AMD NOT SKED="""

# An old-format TAF (24 h, FMHHMM, TEMPO/BECMG HHHH) with typing slips (BKNO25, VRBO3KT).
OLD = """000
TTAA00 KCHI 312340
TAF
KORD 312335Z 010024 25015KT P6SM SCT025 BKN150
      TEMPO 0102 BKNO25
     FM0200 29015KT P6SM OVC025
      TEMPO 0206 5SM -SNSH
     FM0600 30015KT P6SM OVC025
      BECMG 1214 33015KT
     FM1800 VRBO3KT P6SM BKN030="""


def at(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def test_resolve_day_time_and_next_time() -> None:
    anchor = at(2019, 8, 1, 0, 5)
    assert taf.resolve_day_time(anchor, 31, 23, 39) == at(2019, 7, 31, 23, 39)
    assert taf.resolve_day_time(at(2019, 7, 31, 18), 1, 24) == at(2019, 8, 2, 0)
    assert taf.resolve_day_time(at(2019, 2, 27, 0), 30, 12) == at(2019, 1, 30, 12)  # no Feb 30
    assert taf.next_time(at(2000, 1, 1, 6), 4) == at(2000, 1, 2, 4)
    assert taf.next_time(at(2000, 1, 1, 0), 24, strict=True) == at(2000, 1, 2, 0)
    assert taf.next_time(at(2000, 1, 1, 18), 18, strict=True) == at(2000, 1, 2, 18)


def test_current_format_bulletin() -> None:
    bulletin = taf.parse_bulletin(CURRENT, at(2019, 7, 31, 12))
    assert bulletin is not None
    assert bulletin.product_id == "201907312057-KLOT-FTUS43-TAFORD-AAA"
    assert (bulletin.taf_format, bulletin.is_amendment, bulletin.is_correction) == (
        "current", True, False
    )  # fmt: skip
    assert (bulletin.valid_from, bulletin.valid_to) == (at(2019, 7, 31, 21), at(2019, 8, 2, 0))
    kinds = [(group.kind, group.start, group.end) for group in bulletin.groups]
    assert kinds == [
        ("initial", at(2019, 7, 31, 21), None),
        ("FM", at(2019, 8, 1, 2), None),
        ("TEMPO", at(2019, 8, 1, 4), at(2019, 8, 1, 6)),
        ("PROB30", at(2019, 8, 1, 10), at(2019, 8, 1, 14)),
        ("FM", at(2019, 8, 1, 15), None),
    ]
    prob = bulletin.groups[3].conditions
    assert (prob.visibility_sm, prob.weather, prob.ceiling_ft) == (1.5, ("+TSRA",), 800)
    assert bulletin.groups[-1].unparsed == ("AMD", "NOT", "SKED")


def test_current_format_periods() -> None:
    bulletin = taf.parse_bulletin(CURRENT, at(2019, 7, 31, 12))
    assert bulletin is not None
    rows = taf.periods(bulletin)
    prevailing = [(r["start_utc"], r["end_utc"], r["visibility_sm"], r["ceiling_ft"], r["weather"])
                  for r in rows if r["role"] == "prevailing"]  # fmt: skip
    assert prevailing == [
        (at(2019, 7, 31, 21), at(2019, 8, 1, 2), 6.01, None, []),  # FEW is not a ceiling
        (at(2019, 8, 1, 2), at(2019, 8, 1, 15), 5.0, 2500, ["-SHRA"]),
        (at(2019, 8, 1, 15), at(2019, 8, 2, 0), 6.01, None, []),
    ]
    overlays = [(r["kind"], r["has_thunder"], r["wind_speed_kt"]) for r in rows
                if r["role"] == "overlay"]  # fmt: skip
    assert overlays == [("TEMPO", True, None), ("PROB30", True, None)]  # wind not stated


def test_old_format_resolves_forward_and_applies_becmg_to_stated_elements() -> None:
    bulletin = taf.parse_bulletin(OLD, at(2000, 1, 1, 0))
    assert bulletin is not None
    assert bulletin.taf_format == "old" and bulletin.sent_at == at(1999, 12, 31, 23, 40)
    assert (bulletin.valid_from, bulletin.valid_to) == (at(2000, 1, 1, 0), at(2000, 1, 2, 0))
    rows = taf.periods(bulletin)
    columns = ("kind", "start_utc", "end_utc", "wind_dir_deg", "wind_speed_kt", "ceiling_ft")
    prevailing = [tuple(r[c] for c in columns) for r in rows if r["role"] == "prevailing"]
    jan1 = (2000, 1, 1)
    assert prevailing == [
        ("initial", at(*jan1, 0), at(*jan1, 2), 250, 15, 15000),
        ("FM", at(*jan1, 2), at(*jan1, 6), 290, 15, 2500),
        ("FM", at(*jan1, 6), at(*jan1, 12), 300, 15, 2500),
        ("BECMG", at(*jan1, 12), at(*jan1, 18), 330, 15, 2500),  # wind changes; sky carries over
        ("FM", at(*jan1, 18), at(2000, 1, 2, 0), None, 3, 3000),  # "VRBO3KT": variable, 3 kt
    ]
    overlays = [tuple(r[c] for c in ("start_utc", "end_utc", "ceiling_ft", "has_snow"))
                for r in rows if r["role"] == "overlay"]  # fmt: skip
    assert overlays == [
        (at(*jan1, 1), at(*jan1, 2), 2500, None),  # "BKNO25" read as BKN025
        (at(*jan1, 2), at(*jan1, 6), None, True),
    ]


def test_unreadable_window_gives_no_periods() -> None:
    product = "FTUS43 KLOT 150756\nTAFORD\nTAF\nKORD 150756Z 15085KT 6SM BR OVC020="
    bulletin = taf.parse_bulletin(product, at(2000, 2, 15, 0))
    assert bulletin is not None and bulletin.taf_format is None
    assert taf.periods(bulletin) == []


def test_collective_takes_the_station_section() -> None:
    product = (
        "TTAA00 KCHI 041130\nTAF\nKMDW 041125Z 041212 18010KT P6SM SKC=\n"
        "KORD 041127Z 041212 20012KT P6SM SCT250="
    )
    bulletin = taf.parse_bulletin(product, at(2000, 3, 4, 0))
    assert bulletin is not None and bulletin.groups[0].conditions.wind_speed_kt == 12


def test_parse_file_resolves_month_boundary_and_keeps_resends_once() -> None:
    text = "\x01\n" + CURRENT + "\n\x03\n\x01\n" + CURRENT + "\n\x03\n"
    bulletins = taf.parse_file(text, at(2019, 8, 1, 0))
    assert [b.sent_at for b in bulletins] == [at(2019, 7, 31, 20, 57)]


def test_stage_year(tmp_path: Path) -> None:
    payload = ("\x01\n" + OLD + "\n\x03\n").encode("latin-1")
    upload = tmp_path / ".dl-bulletins"
    upload.write_bytes(payload)
    dl = Download(
        url="https://example.test/retrieve.py", tmp_path=upload, fetched_at=at(2026, 10, 27, 5),
        status=200, sha256=hashlib.sha256(payload).hexdigest(), size_bytes=len(payload),
        content_type="text/plain", last_modified=None, etag=None,
    )  # fmt: skip
    root = tmp_path / "data"
    commit_download(root, taf.SOURCE_ID, "ORD/bulletins/2000-01", "b.txt", dl, "public-domain",
                    partition="ORD/2000")  # fmt: skip
    bulletins_path, periods_path, summary = taf.stage_year(root, 2000)
    assert summary == {"bulletins": 1, "unreadable": 0, "old_format": 1, "periods": 7,
                       "unparsed_tokens": 0}  # fmt: skip
    periods = pl.read_parquet(periods_path)
    assert periods["known_time"].unique().to_list() == [at(1999, 12, 31, 23, 50)]
    assert set(periods["role"]) == {"prevailing", "overlay"}
    assert pl.read_parquet(bulletins_path)["valid_to"].to_list() == [at(2000, 1, 2, 0)]
