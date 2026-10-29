"""Track records: their months, the level shift, recalibrated forecasts and alert thresholds."""

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest
from numpy.typing import NDArray

from ordfi.models.metrics import brier
from ordfi.models.recent import (
    alerts,
    recalibrate,
    recalibration,
    record_months,
    shift,
    shift_error,
    threshold,
    warm_up,
)


def test_a_track_record_ends_with_the_last_month_whose_outcomes_are_known() -> None:
    assert record_months(date(2024, 9, 1), 3, 3) == [date(2024, 4, 1), date(2024, 5, 1),
                                                     date(2024, 6, 1)]  # fmt: skip
    first = warm_up(date(2024, 9, 1), 12, 3)
    assert first[0] == date(2023, 7, 1) and first[-1] == date(2024, 8, 1) and len(first) == 14


def test_the_shift_matches_the_forecasts_level_to_the_outcomes() -> None:
    rng = np.random.default_rng(0)
    p = rng.uniform(0.05, 0.3, 100_000)
    truth = 1 / (1 + np.exp(-(np.log(p / (1 - p)) + 0.7)))  # events more likely than forecast
    y = (rng.uniform(size=p.size) < truth).astype(float)
    assert shift(y, p) == pytest.approx(0.7, abs=0.03)
    fixed = recalibration("shift", y, p)(p)
    assert fixed.mean() == pytest.approx(y.mean(), abs=1e-6) and brier(y, fixed) < brier(y, p)
    assert recalibration("platt", np.zeros(4), p[:4])(p[:4]) is not None
    q = p[:4]
    assert recalibration("shift", np.zeros(4), q)(q) is q  # one outcome: as is
    with pytest.raises(ValueError, match="unknown recalibration"):
        recalibration("isotonic", y, p)


Record = tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int64]]


def record(days: int, hours: int, offset: float, seed: int = 0) -> Record:
    """A track record of ``days`` days of ``hours`` rows each, forecasting 10 %, whose events
    come a day at a time: each day's rows all have one, at the rate the offset gives."""
    rng = np.random.default_rng(seed)
    rate = 1 / (1 + np.exp(-(np.log(0.1 / 0.9) + offset)))
    daily = (rng.uniform(size=days) < rate).astype(float)
    return np.repeat(daily, hours), np.full(days * hours, 0.1), np.repeat(np.arange(days), hours)


def test_a_days_rows_count_once_as_evidence() -> None:
    y, p, days = record(300, 1, 0.5)
    b, error = shift_error(y, p, days)
    assert b == pytest.approx(shift(y, p)) and error == pytest.approx(0.19, abs=0.03)
    y24, p24, days24 = record(300, 24, 0.5)  # the same days, each as 24 hours
    b24, error24 = shift_error(y24, p24, days24)
    assert b24 == pytest.approx(b) and error24 == pytest.approx(error, rel=1e-6)


def test_the_shifts_that_wait_for_evidence() -> None:
    def moved(kind: str, y: NDArray[np.float64], p: NDArray[np.float64],
              days: NDArray[np.int64]) -> float:  # fmt: skip
        q = recalibration(kind, y, p, days)(np.array([0.1]))[0]
        return float(np.log(q / (1 - q)) - np.log(0.1 / 0.9))

    strong, weak = record(3000, 1, 0.7), record(60, 1, 0.7, seed=3)
    full_strong, full_weak = shift(*strong[:2]), shift(*weak[:2])
    # Shrunk by its uncertainty: little with much evidence, much with little.
    assert moved("shrunk", *strong) == pytest.approx(full_strong, rel=0.05)
    assert 0 < moved("shrunk", *weak) < 0.75 * full_weak
    # Tested: the whole shift once it clears two standard errors, else none.
    assert moved("tested", *strong) == pytest.approx(full_strong)  # 16 standard errors
    assert moved("tested", *weak) == 0  # 0.46 is 1.3 standard errors: not yet
    assert moved("tested", *record(3000, 1, 0.0, seed=5)) == 0  # calibrated: left as is
    with pytest.raises(ValueError, match="needs the record's days"):
        recalibration("shrunk", strong[0], strong[1])


def predictions(rates: dict[date, float], p: float = 0.1, rows: int = 400) -> pl.DataFrame:
    """Model "m" forecasting ``p`` every row of each month, 20 rows a day; events at the
    month's rate."""
    parts = []
    for month, rate in rates.items():
        y = np.zeros(rows, dtype=np.int8)
        y[: round(rate * rows)] = 1
        days = [month + timedelta(days=i // 20) for i in range(rows)]
        parts.append(
            pl.DataFrame({"y": y, "p": np.full(rows, p), "local_date": days}).with_columns(
                model=pl.lit("m"), horizon=pl.lit("d1_1900"), test_month=pl.lit(month)
            )
        )
    return pl.concat(parts)


def test_recalibrated_forecasts_follow_the_track_record() -> None:
    months = [date(2024, m, 1) for m in range(1, 10)]
    frame = predictions({m: 0.3 for m in months})  # forecast 10 %, observed 30 %
    fixed = recalibrate(frame, ["m"], [date(2024, 8, 1), date(2024, 9, 1)], record=6, lag=3)
    assert set(fixed["model"]) == {"m_recent"}
    by_month = dict(fixed.group_by("test_month").agg(pl.col("p").mean()).iter_rows())
    assert by_month[date(2024, 8, 1)] == pytest.approx(0.1)  # only 5 months of record: as is
    assert by_month[date(2024, 9, 1)] == pytest.approx(0.3)


def test_the_shrunk_shift_follows_the_month_before_part_way() -> None:
    months = [date(2024, m, 1) for m in range(1, 8)]
    frame = predictions({m: 0.3 for m in months})  # forecast 10 %, observed 30 %
    fixed = recalibrate(frame, ["m"], [date(2024, 7, 1)], record=6, lag=1, kind="shrunk",
                        suffix="_shrunk", prior_sd=0.25)  # fmt: skip
    assert set(fixed["model"]) == {"m_shrunk"}
    full = recalibrate(frame, ["m"], [date(2024, 7, 1)], record=6, lag=1)["p"].to_numpy()
    assert 0.1 < fixed["p"].to_numpy().mean() < full.mean() == pytest.approx(0.3)
    # Ending three months before, a six-month record would start before the forecasts do.
    late = recalibrate(frame, ["m"], [date(2024, 7, 1)], 6, 3, "shrunk")["p"].to_numpy()
    assert late.mean() == pytest.approx(0.1)


def test_the_threshold_keeps_false_alarms_within_the_budget() -> None:
    y = np.array([0] * 20 + [1] * 2, dtype=float)
    p = np.array([i / 100 for i in range(20)] + [0.5, 0.05])
    t = threshold(y, p, false_alarms=0.1)  # 2 of 20 may be flagged: 0.18 and 0.19
    assert ((p >= t) & (y == 0)).sum() == 2 and 0.17 < t < 0.18
    ties = np.array([0.3] * 10)
    assert threshold(np.zeros(10), ties, 0.1) > 0.3  # flagging any tie would flag all ten


def test_alerts_take_each_months_threshold_from_its_track_record() -> None:
    rng = np.random.default_rng(1)
    months = [date(2024, m, 1) for m in range(1, 8)]
    parts = []
    for month in months:
        y = (rng.uniform(size=500) < 0.2).astype(np.int8)
        p = np.clip(0.1 + 0.5 * y + rng.normal(0, 0.15, 500), 0.001, 0.999)
        parts.append(
            pl.DataFrame({"y": y, "p": p}).with_columns(
                model=pl.lit("m"), horizon=pl.lit("1h"), test_month=pl.lit(month)
            )
        )
    got = alerts(pl.concat(parts), [date(2024, 7, 1)], record=3, lag=3).row(0, named=True)
    assert got["months"] == 1 and got["rows"] == 500
    assert 0.05 < got["false_alarm_rate"] < 0.15 and got["hit_rate"] > 0.8
    assert alerts(pl.concat(parts), [date(2024, 3, 1)], record=3, lag=3).is_empty()
