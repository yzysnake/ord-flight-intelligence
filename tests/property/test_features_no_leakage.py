"""Property test: no feature uses anything unknown at its as_of.

For random small worlds (METARs, TAFs, program versions, flights), every sampled spine row gets
the same features from the full tables as from the tables as known at its as_of
(``knowledge.visible``). A feature that read a future row or field would differ.
"""

from datetime import UTC, datetime, timedelta

import polars as pl
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ordfi.features.build import features, spine_for
from ordfi.features.knowledge import Tables, visible
from ordfi.features.spines import HORIZONS
from tests.feature_tables import tables as make_tables

BASE = datetime(2019, 7, 15, tzinfo=UTC)
SPAN_MIN = 36 * 60  # every time falls in a 36-hour window, so events overlap

minutes = st.integers(min_value=0, max_value=SPAN_MIN)
categories = st.sampled_from(["VFR", "MVFR", "IFR", "LIFR"])
maybe_bool = st.none() | st.booleans()


def at(minute: int) -> datetime:
    return BASE + timedelta(minutes=minute)


@st.composite
def observations(draw: st.DrawFn) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "valid_time": at(m),
            "known_time": at(m + 10),
            "report_type": draw(st.sampled_from(["routine", "special"])),
            "flight_category": draw(categories),
            "visibility_mi": draw(st.floats(0, 10)),
            "ceiling_ft": draw(st.none() | st.floats(100, 5000)),
            "wind_speed_kt": draw(st.floats(0, 30)),
            "wind_gust_kt": draw(st.none() | st.floats(15, 50)),
            "temp_c": draw(st.floats(-20, 35)),
            "has_thunder": draw(st.booleans()),
            "has_snow": draw(st.booleans()),
            "has_freezing": draw(st.booleans()),
        }
        for m in draw(st.lists(minutes, max_size=12, unique=True))
    ]
    return rows


@st.composite
def forecasts(draw: st.DrawFn) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for i, sent in enumerate(draw(st.lists(minutes, max_size=4, unique=True))):
        first_hour = at(sent).replace(minute=0)
        for h in range(draw(st.integers(1, 30))):
            rows.append(
                {
                    "product_id": f"taf{i}",
                    "sent_at": at(sent),
                    "known_time": at(sent + 10),
                    "valid_time": first_hour + timedelta(hours=h),
                    "is_amendment": draw(st.booleans()),
                    "flight_category": draw(categories),
                    "worst_flight_category": draw(categories),
                    "visibility_sm": draw(st.floats(0, 6.01)),
                    "ceiling_ft": draw(st.none() | st.integers(100, 5000)),
                    "wind_speed_kt": draw(st.integers(0, 30)),
                    "wind_gust_kt": draw(st.none() | st.integers(15, 50)),
                    "has_thunder": draw(st.booleans()),
                    "tempo_thunder": draw(maybe_bool),
                    "prob_thunder": draw(maybe_bool),
                    "has_snow": draw(st.booleans()),
                    "tempo_snow": draw(maybe_bool),
                    "prob_pct": draw(st.none() | st.sampled_from([30, 40])),
                }
            )
    return rows


@st.composite
def program_versions(draw: st.DrawFn) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for p in range(draw(st.integers(0, 4))):
        kind = draw(st.sampled_from(["gdp", "ground_stop"]))
        scope = draw(st.sampled_from(["general", "general", "carrier"]))
        known = sorted(draw(st.lists(minutes, min_size=1, max_size=3, unique=True)))
        for v, k in enumerate(known):
            start = draw(minutes)
            end = draw(st.none() | st.integers(start, start + 600))
            rows.append(
                {
                    "program_id": f"p{p}",
                    "airport": "ORD",
                    "program_type": kind,
                    "scope": scope,
                    "version": v + 1,
                    "start_utc": at(start),
                    "end_utc": None if end is None else at(end),
                    "known_time": at(k),
                    "valid_to": at(known[v + 1]) if v + 1 < len(known) else None,
                }
            )
    return rows


@st.composite
def flights(draw: st.DrawFn) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for i in range(draw(st.integers(0, 30))):
        arriving = draw(st.booleans())
        sched_dep = draw(minutes)
        sched_arr = sched_dep + draw(st.integers(30, 300))
        dep_delay = draw(st.none() | st.integers(-10, 240))  # None: cancelled
        arr_delay = None if dep_delay is None else dep_delay + draw(st.integers(-30, 30))
        rows.append(
            {
                "flight_key": f"f{i}",
                "direction": "arrival" if arriving else "departure",
                "operating_carrier": draw(st.sampled_from(["UA", "AA"])),
                "flight_number": i,
                "marketing_carrier": "UA",
                "origin": "DEN" if arriving else "ORD",
                "dest": "ORD" if arriving else "LGA",
                "sched_dep_utc": at(sched_dep),
                "sched_arr_utc": at(sched_arr),
                "distance": 900.0,
                "crs_elapsed_time": sched_arr - sched_dep,
                "tail_number": draw(st.none() | st.sampled_from(["N1", "N2", "N3"])),
                "dep_utc": None if dep_delay is None else at(sched_dep + dep_delay),
                "dep_delay": dep_delay,
                "arr_utc": None if arr_delay is None else at(sched_arr + arr_delay),
                "arr_delay": arr_delay,
                "cancelled": dep_delay is None,
                "diverted": False,
            }
        )
    return rows


@st.composite
def worlds(draw: st.DrawFn) -> Tables:
    return make_tables(
        BASE.date(),
        weather=draw(observations()),
        taf=draw(forecasts()),
        versions=draw(program_versions()),
        legs=draw(flights()),
    )


def check(spine_name: str, tables: Tables, picks: list[int]) -> None:
    """Each picked spine row: features from the full tables == from the tables as known."""
    spine = spine_for(spine_name, tables, BASE, at(SPAN_MIN), list(HORIZONS))
    if spine.is_empty():
        return
    full = features(spine_name, spine, tables)
    for pick in picks:
        r = pick % spine.height
        row = spine.slice(r, 1)
        known = features(spine_name, row, visible(tables, row["as_of"].item()))
        expected = full.filter(pl.col("row") == r)
        assert known.drop("row").row(0, named=True) == expected.drop("row").row(0, named=True)


picks = st.lists(st.integers(min_value=0, max_value=10_000), min_size=1, max_size=5)
relaxed = settings(deadline=None, max_examples=30, suppress_health_check=[HealthCheck.too_slow])


@relaxed
@given(worlds(), picks)
def test_departure_features_use_only_what_was_known(tables: Tables, rows: list[int]) -> None:
    check("departures", tables, rows)


@relaxed
@given(worlds(), picks)
def test_hour_features_use_only_what_was_known(tables: Tables, rows: list[int]) -> None:
    check("hours", tables, rows)
