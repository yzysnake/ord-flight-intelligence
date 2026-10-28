"""Recalibration and alert thresholds set on a model's recent track record (study §6.4, §10.3).

Live, the outlook publishes forecasts every day, and their outcomes are known once BTS
publishes the month. At the start of test month M, a model's track record is its forecasts for
the last ``record`` months whose outcomes are known, ending ``lag`` months before M:
out-of-sample forecasts, made by the models of the time. Two things are reset on it each month:

- the forecasts' level (``recalibrate``): a logistic shift (or a Platt map) fitted to the track
  record, so the probabilities follow drifts in how often events happen;
- the alert threshold (``alerts``): the lowest forecast that would have flagged at most
  ``false_alarms`` of the track record's non-events.

A month without a full track record keeps its forecasts as they are and gets no alerts.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date

import numpy as np
import polars as pl
from numpy.typing import NDArray

from ordfi.models.baselines import LABEL
from ordfi.models.metrics import EPS, FALSE_ALARMS, calibration, logit

Floats = NDArray[np.float64]
SUFFIX = "_recent"  # recalibrated forecasts are scored as another model, e.g. gbdt_recent
ALERTS = {
    "model": pl.String(), "horizon": pl.String(), "months": pl.Int64(), "rows": pl.Int64(),
    "events": pl.Int64(), "flags": pl.Int64(), "hit_rate": pl.Float64(),
    "false_alarm_rate": pl.Float64(), "precision": pl.Float64(), "threshold_min": pl.Float64(),
    "threshold_max": pl.Float64(),
}  # fmt: skip


def _index(month: date) -> int:
    return month.year * 12 + month.month - 1


def _month_index() -> pl.Expr:
    return pl.col("test_month").dt.year().cast(pl.Int64) * 12 + pl.col("test_month").dt.month() - 1


def record_months(month: date, record: int, lag: int) -> list[date]:
    """The months of ``month``'s track record, oldest first."""
    last = _index(month) - lag
    return [date(i // 12, i % 12 + 1, 1) for i in range(last - record + 1, last + 1)]


def warm_up(first: date, record: int, lag: int) -> list[date]:
    """The months to forecast before ``first``, so that it and every later month have a full
    track record: from the start of ``first``'s record to the month before ``first``."""
    start = _index(record_months(first, record, lag)[0])
    return [date(i // 12, i % 12 + 1, 1) for i in range(start, _index(first))]


def shift(y: Floats, p: Floats) -> float:
    """The logit shift that makes the forecasts' mean match the outcomes' (maximum likelihood,
    by Newton's method)."""
    z, b = logit(p), 0.0
    for _ in range(100):
        q = 1 / (1 + np.exp(-(z + b)))
        step = float((y - q).sum() / max(float((q * (1 - q)).sum()), EPS))
        b += step
        if abs(step) < 1e-10:
            break
    return b


def recalibration(kind: str, y: Floats, p: Floats) -> Callable[[Floats], Floats]:
    """A map from forecasts to recalibrated ones, fitted on a track record."""
    if np.unique(y).size < 2:  # no event, or nothing else: no level to learn
        return _identity
    if kind == "shift":
        b = shift(y, p)
        return lambda q: 1 / (1 + np.exp(-(logit(q) + b)))
    if kind == "platt":
        intercept, slope = calibration(y, p)
        if np.isnan(slope):
            return _identity
        return lambda q: 1 / (1 + np.exp(-(intercept + slope * logit(q))))
    raise ValueError(f"unknown recalibration {kind!r}")


def recalibrate(predictions: pl.DataFrame, models: Sequence[str], months: Sequence[date],
                record: int, lag: int, kind: str = "shift") -> pl.DataFrame:  # fmt: skip
    """The forecasts of ``models`` for ``months``, recalibrated on each month's track record,
    as models named with ``SUFFIX``."""
    frame = predictions.filter(pl.col("model").is_in(models)).with_columns(_m=_month_index())
    parts = []
    for (model, _), group in frame.group_by("model", "horizon", maintain_order=True):
        for month in months:
            m = _index(month)
            now = group.filter(pl.col("_m") == m)
            past = group.filter(pl.col("_m").is_between(m - lag - record + 1, m - lag))
            if now.is_empty():
                continue
            fitted: Callable[[Floats], Floats] = _identity
            if past["_m"].n_unique() == record:
                y = past[LABEL].to_numpy().astype(np.float64)
                fitted = recalibration(kind, y, past["p"].to_numpy())
            parts.append(now.with_columns(model=pl.lit(f"{model}{SUFFIX}"),
                                          p=pl.Series(fitted(now["p"].to_numpy()))))  # fmt: skip
    return pl.concat(parts).drop("_m") if parts else predictions.clear()


def _identity(q: Floats) -> Floats:
    return q


def threshold(y: Floats, p: Floats, false_alarms: float = FALSE_ALARMS) -> float:
    """The lowest threshold whose flags (``p >= threshold``) include at most ``false_alarms``
    of the non-events."""
    normal = np.sort(p[y == 0])
    allowed = int(np.floor(false_alarms * normal.size + 1e-9))
    if allowed >= normal.size:
        return 0.0
    return float(np.nextafter(normal[normal.size - allowed - 1], np.inf))


def alerts(predictions: pl.DataFrame, months: Sequence[date], record: int, lag: int,
           false_alarms: float = FALSE_ALARMS) -> pl.DataFrame:  # fmt: skip
    """Alerts over ``months``, each month's threshold set on its track record: for each model
    and horizon, the events, the share of them flagged (``hit_rate``), the share of non-events
    flagged (``false_alarm_rate``), the share of flags that were events (``precision``) and the
    thresholds used."""
    frame = predictions.with_columns(_m=_month_index())
    rows = []
    for (model, horizon), group in frame.group_by("model", "horizon", maintain_order=True):
        flagged = []
        for month in months:
            m = _index(month)
            now = group.filter(pl.col("_m") == m)
            past = group.filter(pl.col("_m").is_between(m - lag - record + 1, m - lag))
            if now.is_empty() or past["_m"].n_unique() < record:
                continue
            t = threshold(past[LABEL].to_numpy().astype(np.float64), past["p"].to_numpy(),
                          false_alarms)  # fmt: skip
            flagged.append(now.select(LABEL, flag=pl.col("p") >= t, threshold=pl.lit(t)))
        if not flagged:
            continue
        f = pl.concat(flagged)
        event, flag = f[LABEL] == 1, f["flag"]
        n_events, n_flags = int(event.sum()), int(flag.sum())
        rows.append({
            "model": model, "horizon": horizon, "months": len(flagged), "rows": f.height,
            "events": n_events, "flags": n_flags,
            "hit_rate": (flag & event).sum() / n_events if n_events else float("nan"),
            "false_alarm_rate": (flag & ~event).sum() / max(f.height - n_events, 1),
            "precision": (flag & event).sum() / n_flags if n_flags else float("nan"),
            "threshold_min": f["threshold"].min(), "threshold_max": f["threshold"].max(),
        })  # fmt: skip
    return pl.DataFrame(rows, schema=ALERTS)
