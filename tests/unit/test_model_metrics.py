"""Forecast scores on inputs with known answers."""

import math

import numpy as np

from ordfi.models.metrics import (
    brier,
    calibration,
    ece,
    hit_rate,
    log_loss,
    reliability,
    scores,
    skill,
)


def test_proper_scores() -> None:
    y = np.array([1.0, 0.0, 1.0, 0.0])
    p = np.array([0.8, 0.2, 0.6, 0.4])
    assert math.isclose(brier(y, p), (0.04 + 0.04 + 0.16 + 0.16) / 4)
    assert math.isclose(log_loss(y, p), -(2 * math.log(0.8) + 2 * math.log(0.6)) / 4)


def test_reliability_bins_hold_equal_counts() -> None:
    p = np.linspace(0.0, 0.9, 10)
    y = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1], dtype=float)
    bins = reliability(y, p, bins=2)
    assert [n for *_, n in bins] == [5, 5]
    assert [rate for _, rate, _ in bins] == [0.0, 1.0]
    assert math.isclose(ece(y, p, bins=2), (abs(0.2 - 0) + abs(0.7 - 1)) / 2)


def test_calibration_slope_flags_overconfidence() -> None:
    rng = np.random.default_rng(1)
    truth = rng.uniform(0.05, 0.95, 200_000)
    y = (rng.uniform(size=truth.size) < truth).astype(float)
    logit = np.log(truth / (1 - truth))
    calibrated = calibration(y, truth)
    overconfident = calibration(y, 1 / (1 + np.exp(-2 * logit)))
    assert abs(calibrated[0]) < 0.03 and abs(calibrated[1] - 1) < 0.03
    assert abs(overconfident[1] - 0.5) < 0.03


def test_skill_is_zero_against_itself_and_one_when_perfect() -> None:
    y = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
    reference = np.full(6, 0.5)
    days = np.array([1, 1, 2, 2, 3, 3])
    assert skill(y, reference, reference, days) == (0.0, 0.0, 0.0)
    point, low, high = skill(y, y, reference, days)
    assert (point, low, high) == (1.0, 1.0, 1.0)


def test_one_outcome_leaves_discrimination_undefined() -> None:
    result = scores(np.zeros(4), np.array([0.1, 0.2, 0.3, 0.4]))
    assert math.isnan(result["roc_auc"]) and math.isnan(result["cal_slope"])
    assert result["base_rate"] == 0.0 and result["n"] == 4.0


def test_hit_rate_is_the_events_caught_within_the_false_alarm_budget() -> None:
    y = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=float)
    p = np.array([0.9, 0.8, 0.3, 0.1, 0.85, 0.5, 0.2, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0, 0.0])
    # Flagging p >= 0.8 catches 2 of the 4 events with 1 false alarm in 10 non-events; going
    # down to 0.5 adds a second false alarm. With no false alarms, only p >= 0.9 is flagged.
    assert hit_rate(y, p, false_alarms=0.1) == 0.5
    assert hit_rate(y, p, false_alarms=0.0) == 0.25
    assert math.isnan(hit_rate(np.zeros(3), np.array([0.1, 0.2, 0.3])))
