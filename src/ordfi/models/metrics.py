"""Scores for probability forecasts of binary events (research study §6.6).

Proper scores (Brier, log loss) and their skill against a reference forecast, discrimination
(ROC and precision-recall AUC) and calibration (equal-mass reliability bins, ECE and the
logistic calibration slope and intercept). Skill intervals resample whole days, because the
flights of one day share its weather and programs (§6.5).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

Floats = NDArray[np.float64]
EPS = 1e-6
BINS = 10


def brier(y: Floats, p: Floats) -> float:
    return float(np.mean((p - y) ** 2))


def log_loss(y: Floats, p: Floats) -> float:
    q = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))


def reliability(y: Floats, p: Floats, bins: int = BINS) -> list[tuple[float, float, int]]:
    """Equal-mass bins by forecast: (mean forecast, observed rate, rows) per bin."""
    order = np.argsort(p, kind="stable")
    return [
        (float(p[part].mean()), float(y[part].mean()), int(part.size))
        for part in np.array_split(order, min(bins, p.size))
        if part.size
    ]


def ece(y: Floats, p: Floats, bins: int = BINS) -> float:
    """Expected calibration error over equal-mass bins."""
    return float(
        sum(n * abs(mean_p - rate) for mean_p, rate, n in reliability(y, p, bins)) / y.size
    )


def calibration(y: Floats, p: Floats) -> tuple[float, float]:
    """Intercept and slope of logit P(y) on logit(p): (0, 1) when calibrated; a slope below 1
    means forecasts too extreme."""
    if np.unique(y).size < 2 or np.unique(p).size < 2:
        return float("nan"), float("nan")
    q = np.clip(p, EPS, 1 - EPS)
    fit = LogisticRegression(C=np.inf).fit(np.log(q / (1 - q)).reshape(-1, 1), y)  # unpenalized
    return float(fit.intercept_[0]), float(fit.coef_[0, 0])


def scores(y: Floats, p: Floats) -> dict[str, float]:
    """Every score of one forecast set (AUCs are NaN when only one outcome occurs)."""
    both = np.unique(y).size == 2
    intercept, slope = calibration(y, p)
    return {
        "n": float(y.size),
        "base_rate": float(y.mean()),
        "mean_p": float(p.mean()),
        "brier": brier(y, p),
        "log_loss": log_loss(y, p),
        "roc_auc": float(roc_auc_score(y, p)) if both else float("nan"),
        "pr_auc": float(average_precision_score(y, p)) if both else float("nan"),
        "ece": ece(y, p),
        "cal_intercept": intercept,
        "cal_slope": slope,
    }


def skill(
    y: Floats, p: Floats, reference: Floats, days: NDArray[np.int64], n_boot: int = 200,
    seed: int = 0,
) -> tuple[float, float, float]:  # fmt: skip
    """Brier skill score of ``p`` against ``reference`` and a 95 % interval from resampling
    whole days (``days`` labels each row's day)."""
    _, day = np.unique(days, return_inverse=True)
    sse = np.bincount(day, weights=(p - y) ** 2)
    sse_ref = np.bincount(day, weights=(reference - y) ** 2)
    if sse_ref.sum() == 0:
        return float("nan"), float("nan"), float("nan")
    point = 1 - sse.sum() / sse_ref.sum()
    weights = np.random.default_rng(seed).multinomial(
        sse.size, np.full(sse.size, 1 / sse.size), size=n_boot
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        boot = 1 - (weights @ sse) / (weights @ sse_ref)
    low, high = np.nanpercentile(boot, [2.5, 97.5])
    return float(point), float(low), float(high)
