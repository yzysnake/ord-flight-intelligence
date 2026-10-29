"""Property test: no feature uses anything unknown at its as_of.

For random small worlds (METARs, TAFs, program versions, flights), every sampled spine row gets
the same features from the full tables as from the tables as known at its as_of
(``knowledge.visible``). A feature that read a future row or field would differ.
"""

from datetime import UTC, datetime, timedelta

import polars as pl
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ordfi.features import groups
from ordfi.features.build import features, spine_for
from ordfi.features.knowledge import Tables, visible
from ordfi.features.spines import horizons
from tests.feature_tables import tables as make_tables

BASE = datetime(2019, 7, 15, tzinfo=UTC)
SPAN_MIN = 36 * 60  # every time falls in a 36-hour window, so events overlap

minutes = st.integers(min_value=0, max_value=SPAN_MIN)
categories = st.sampled_from(["VFR", "MVFR", "IFR", "LIFR"])
maybe_bool = st.none() | st.booleans()
causes = st.sampled_from([None, "WEATHER / WIND", "STAFFING / STAFFING"])
# Program advisories are also sent close to the days spine's issues inside the world (19:00,
# 07:00, 19:00 and 05:00 CDT), so that a forecast often falls between two versions.
DAY_ISSUES = (0, 12 * 60, 24 * 60, 34 * 60)
advisory_times = minutes | st.sampled_from(DAY_ISSUES).flatmap(
    lambda m: st.integers(max(m - 60, 0), min(m + 60, SPAN_MIN))
)


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
def guidance_runs(draw: st.DrawFn, lag_min: int, nbm: bool) -> list[dict[str, object]]:
    """A few runs of 3-hourly projections, known ``lag_min`` after their run time."""
    rows: list[dict[str, object]] = []
    hours = st.integers(-24, 36)  # runs from a day before the world into it
    for hour in draw(st.lists(hours, max_size=3, unique=True)):
        runtime = BASE + timedelta(hours=hour)
        for lead in range(6, 73, 3):
            row: dict[str, object] = {
                "runtime": runtime,
                "known_time": runtime + timedelta(minutes=lag_min),
                "valid_time": runtime + timedelta(hours=lead),
                "flight_category": draw(categories),
                "wind_speed_kt": draw(st.integers(0, 30)),
                "snow_pct": draw(st.none() | st.integers(0, 100)),
                "freezing_pct": draw(st.none() | st.integers(0, 100)),
                "pop_6h_pct": draw(st.none() | st.integers(0, 100)),
            }
            if nbm:
                ceiling = draw(st.none() | st.integers(1, 50))  # 100s of ft; None unlimited
                row |= {
                    "ceiling_ft": None if ceiling is None else 100 * ceiling,
                    "visibility_mi": draw(st.floats(0, 10)),
                    "ifr_ceiling_pct": draw(st.integers(0, 100)),
                    "thunder_3h_pct": draw(st.none() | st.integers(0, 100)),
                    "wind_gust_kt": draw(st.none() | st.integers(10, 50)),
                }
            else:
                row |= {
                    "ceiling_category": draw(st.integers(1, 8)),
                    "thunder_6h_pct": draw(st.none() | st.integers(0, 100)),
                }
            rows.append(row)
    return rows


@st.composite
def program_versions(
    draw: st.DrawFn, min_programs: int = 0, max_programs: int = 4
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for p in range(draw(st.integers(min_programs, max_programs))):
        kind = draw(st.sampled_from(["gdp", "ground_stop"]))
        scope = draw(st.sampled_from(["general", "general", "carrier"]))
        known = sorted(draw(st.lists(advisory_times, min_size=1, max_size=3, unique=True)))
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
                    "reason": draw(causes),
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
        gfs_mos=draw(guidance_runs(5 * 60, nbm=False)),
        nbm=draw(guidance_runs(70, nbm=True)),
        versions=draw(program_versions()),
        legs=draw(flights()),
    )


def world_spine(spine_name: str, tables: Tables) -> pl.DataFrame:
    """The spine's rows for the world: for days, the world's second day at each issue, most of
    them inside the world."""
    if spine_name == "days":
        start, end = BASE + timedelta(days=1), BASE + timedelta(days=2)
    else:
        start, end = BASE, at(SPAN_MIN)
    return spine_for(spine_name, tables, start, end, horizons(spine_name))


def check(spine_name: str, tables: Tables, picks: list[int]) -> None:
    """Each picked spine row (for days, every row): features from the full tables == from the
    tables as known."""
    spine = world_spine(spine_name, tables)
    if spine.is_empty():
        return
    full = features(spine_name, spine, tables)
    chosen = range(spine.height) if spine_name == "days" else {p % spine.height for p in picks}
    for r in chosen:
        row = spine.slice(r, 1)
        known = features(spine_name, row, visible(tables, row["as_of"].item()))
        expected = full.filter(pl.col("row") == r)
        assert known.drop("row").row(0, named=True) == expected.drop("row").row(0, named=True)


PROGRAM_GROUPS = {"hours": groups.programs, "days": groups.day_programs}


def check_programs(spine_name: str, tables: Tables, picks: list[int]) -> None:
    """The program features alone, for every row at each picked as_of (for days, every
    as_of): from the full tables == from the tables as known then."""
    group = PROGRAM_GROUPS[spine_name]
    spine = world_spine(spine_name, tables).with_row_index("row")
    full = group(spine, tables)
    times = spine["as_of"].unique().sort()
    if spine_name == "hours":
        times = times.gather([p % len(times) for p in picks]).unique()
    for as_of in times:
        rows = spine.filter(pl.col("as_of") == as_of)
        known = group(rows, visible(tables, as_of)).sort("row")
        expected = full.join(rows.select("row"), on="row", how="semi").sort("row")
        assert known.rows(named=True) == expected.rows(named=True)


picks = st.lists(st.integers(min_value=0, max_value=10_000), min_size=1, max_size=5)
relaxed = settings(deadline=None, max_examples=30, suppress_health_check=[HealthCheck.too_slow])
# A day's features, and the program climate, depend on fewer of the world's events, so leaks
# need more worlds to show.
thorough = settings(relaxed, max_examples=60)


@relaxed
@given(worlds(), picks)
def test_departure_features_use_only_what_was_known(tables: Tables, rows: list[int]) -> None:
    check("departures", tables, rows)


@thorough
@given(worlds(), picks)
def test_hour_features_use_only_what_was_known(tables: Tables, rows: list[int]) -> None:
    check("hours", tables, rows)


@thorough
@given(worlds(), picks)
def test_day_features_use_only_what_was_known(tables: Tables, rows: list[int]) -> None:
    check("days", tables, rows)


# Program histories in full worlds are small, and a leak through a later version (a cause that
# changed, a revised end) shows only at a forecast between two versions. Worlds of versions
# alone, checked at many forecast times, find those.
@thorough
@given(program_versions(1, 6), st.lists(st.integers(0, 10_000), max_size=12))
def test_program_features_use_only_what_was_known(versions: list[dict[str, object]],
                                                  times: list[int]) -> None:  # fmt: skip
    tables = make_tables(BASE.date(), versions=versions)
    check_programs("days", tables, times)
    check_programs("hours", tables, times)
