"""The Outlook GBDT: inputs, the held-out months, recalibration and its feature list."""

from datetime import UTC, date, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from ordfi.features import build
from ordfi.features.spines import days, departures, hours
from ordfi.models.backtest import add_months
from ordfi.models.gbdt import (
    DAY_FEATURES,
    DEPARTURE_FEATURES,
    GBDT,
    OUTLOOK_FEATURES,
    departure,
    encode,
    outlook,
    recalibration,
    split,
)
from ordfi.models.metrics import brier
from tests.feature_tables import tables


def monthly(months: list[date], rows_per_month: int, seed: int = 0) -> pl.DataFrame:
    """Rows spread over ``months``: a signal ``x``, noise ``z``, and ``y`` driven by ``x``."""
    rng = np.random.default_rng(seed)
    parts = []
    for month in months:
        start = datetime(month.year, month.month, 1, tzinfo=UTC)
        offsets = np.sort(rng.integers(0, 28 * 24, rows_per_month))
        x = rng.normal(size=rows_per_month)
        parts.append(pl.DataFrame({
            "target_utc": [start + timedelta(hours=int(h)) for h in offsets],
            "month": [month] * rows_per_month,
            "x": x,
            "z": rng.normal(size=rows_per_month),
            "y": (rng.uniform(size=rows_per_month) < 1 / (1 + np.exp(-2 * x))).astype(np.int8),
        }))  # fmt: skip
    return pl.concat(parts)


MONTHS = [add_months(date(2018, 1, 1), i) for i in range(24)]


def test_it_learns_the_signal_and_predicts_the_same_each_time() -> None:
    train, test = monthly(MONTHS[:20], 500), monthly(MONTHS[22:], 2_000, seed=1)
    model = GBDT("g", ["x", "z"])
    p = model.fit_predict(train, test)
    y = test["y"].to_numpy().astype(float)
    assert brier(y, p) < 0.8 * brier(y, np.full(y.size, train["y"].mean()))
    assert np.array_equal(p, model.fit_predict(train, test))


def test_one_outcome_gives_its_rate() -> None:
    train = monthly(MONTHS[:4], 50).with_columns(y=pl.lit(0, dtype=pl.Int8))
    assert GBDT("g", ["x"]).fit_predict(train, monthly(MONTHS[5:6], 10)).tolist() == [0.0] * 10


def test_inputs_keep_their_meaning() -> None:
    train = pl.DataFrame({
        "wx_flight_category": ["VFR", "LIFR", None], "flag": [True, False, None],
        "carrier": ["UA", "AA", "UA"], "n": [1, None, 3],
    })  # fmt: skip
    test = pl.DataFrame({
        "wx_flight_category": ["IFR"], "flag": [True], "carrier": ["WN"], "n": [2],
    })  # fmt: skip
    x, x_test, categorical = encode(train, test, list(train.columns))
    assert np.array_equal(
        x, np.array([[3, 1, 1, 1], [0, 0, 0, np.nan], [np.nan, np.nan, 1, 3]]), equal_nan=True
    )
    assert np.array_equal(x_test, np.array([[1, 1, np.nan, 2]]), equal_nan=True)  # unseen: NaN
    assert categorical == [2]


def test_the_last_months_are_held_out_after_an_embargo() -> None:
    train = monthly(MONTHS[:6], 200)
    fit, held = split(train, 2)
    held_months = set(train.filter(pl.Series(held))["month"])
    assert held_months == {MONTHS[4], MONTHS[5]}
    fitted = train.filter(pl.Series(fit))
    last_fitted = fitted.select(pl.col("target_utc").max()).item()
    assert last_fitted < datetime(2018, 5, 1, tzinfo=UTC) - timedelta(days=1)
    assert not (fit & held).any()
    # Never more than half the window, and nothing held out of a single month.
    assert set(train.filter(pl.Series(split(train, 12)[1]))["month"]) == set(MONTHS[3:6])
    one = monthly(MONTHS[:1], 50)
    assert split(one, 12)[0].all() and not split(one, 12)[1].any()


def test_recalibration_corrects_the_level_of_held_out_forecasts() -> None:
    rng = np.random.default_rng(2)
    p = rng.uniform(0.05, 0.5, 50_000)
    y = (rng.uniform(size=p.size) < np.minimum(2 * p, 1)).astype(float)  # twice as likely
    for kind in ("platt", "isotonic"):
        fixed = recalibration(kind, y, p)(p)
        assert abs(fixed.mean() - y.mean()) < 0.01 and brier(y, fixed) < brier(y, p)
    assert recalibration("none", y, p)(p) is p
    assert recalibration("platt", np.zeros(p.size), p)(p) is p  # one outcome: left as is
    with pytest.raises(ValueError, match="unknown calibration"):
        recalibration("beta", y, p)


def test_the_outlook_reads_every_feature_of_the_hours_spine() -> None:
    start = datetime(2019, 7, 15, 12, tzinfo=UTC)
    frame = build.build("hours", hours(start, start + timedelta(hours=2), ["1h"]),
                        tables(date(2019, 7, 15)))  # fmt: skip
    keys = {"target_utc", "horizon", "as_of", "licence_class"}
    produced = {c for c in frame.columns if c not in keys and not c.startswith("y_")}
    assert produced == set(OUTLOOK_FEATURES) and len(OUTLOOK_FEATURES) == len(produced)
    schedule = outlook("s", ("cal_", "dem_")).columns()
    assert schedule == {f for f in OUTLOOK_FEATURES if f.startswith(("cal_", "dem_"))}


def test_the_daily_outlook_reads_every_feature_of_the_days_spine() -> None:
    day = date(2019, 7, 16)
    frame = build.build("days", days(day, day + timedelta(days=1), ["d1_1900"]),
                        tables(date(2019, 7, 15)))  # fmt: skip
    keys = {"target_date", "target_utc", "target_end_utc", "horizon", "as_of", "licence_class"}
    produced = {c for c in frame.columns if c not in keys and not c.startswith("y_")}
    assert produced == set(DAY_FEATURES) and len(DAY_FEATURES) == len(produced)
    daily = outlook("d", spine="days")
    assert daily.columns() == set(DAY_FEATURES) and daily.validation_months == 24
    assert outlook("h").validation_months == 12


def test_the_departure_model_reads_every_feature_of_the_departures_spine() -> None:
    start = datetime(2019, 7, 15, 12, tzinfo=UTC)
    flight = {"flight_key": "f", "direction": "departure", "operating_carrier": "UA",
              "origin": "ORD", "dest": "LGA", "sched_dep_utc": start,
              "sched_arr_utc": start + timedelta(hours=2), "cancelled": False}  # fmt: skip
    t = tables(date(2019, 7, 15), legs=[flight])
    frame = build.build("departures", departures(t.legs, start, start + timedelta(hours=1),
                                                 ["1h"]), t)  # fmt: skip
    keys = {"flight_key", "target_utc", "horizon", "as_of", "licence_class"}
    produced = {c for c in frame.columns if c not in keys and not c.startswith("y_")}
    assert produced == set(DEPARTURE_FEATURES) and len(DEPARTURE_FEATURES) == len(produced)
    assert departure().columns() == set(DEPARTURE_FEATURES)
    assert not any(f.startswith("inb_") for f in departure("n", without=("inb_",)).features)
    assert departure().params["num_threads"] > 1  # folds run three at a time, not one per CPU
