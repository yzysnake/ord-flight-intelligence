"""Gradient-boosted trees on the as-of features: the Outlook model (research study §6.4).

A LightGBM classifier of one event at one horizon, fitted per fold by the backtest harness.
The last ``validation_months`` of the training window, after a one-day embargo, choose the
number of trees (early stopping on log loss); the trees are then refit on the whole window.
Event rates drift from year to year, so a recalibration fitted on the held-out months'
forecasts can set their level (``calibration``).

Inputs keep their meaning: booleans become 0/1, flight categories their rank (LIFR lowest),
other strings categorical codes from the training rows, and nulls stay missing (LightGBM
learns which way each goes).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import lightgbm as lgb
import numpy as np
import polars as pl
from numpy.typing import NDArray
from sklearn.isotonic import IsotonicRegression

from ordfi.models.baselines import LABEL
from ordfi.models.metrics import calibration, logit

Floats = NDArray[np.float64]
Mask = NDArray[np.bool_]

PARAMS: Mapping[str, Any] = {
    "objective": "binary", "learning_rate": 0.05, "num_leaves": 15, "min_data_in_leaf": 200,
    "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 1, "lambda_l2": 10.0,
    "seed": 0, "deterministic": True, "force_row_wise": True, "num_threads": 1, "verbose": -1,
}  # fmt: skip
MAX_ROUNDS = 2000
PATIENCE = 100  # rounds without improvement on the held-out months before stopping
FALLBACK_ROUNDS = 100  # when the window is too short to hold months out
EMBARGO = timedelta(days=1)  # left out between the fitted and the held-out months
FLIGHT_CATEGORY_RANK = {"LIFR": 0, "IFR": 1, "MVFR": 2, "VFR": 3}

# Every feature of the hours spine (docs/features/), by group.
OUTLOOK_FEATURES = (
    "cal_local_hour", "cal_day_of_week", "cal_month", "cal_is_weekend", "cal_is_holiday",
    "cal_days_to_holiday", "cal_days_since_holiday",
    "wx_age_min", "wx_flight_category", "wx_visibility_mi", "wx_ceiling_ft", "wx_wind_speed_kt",
    "wx_wind_gust_kt", "wx_temp_c", "wx_thunder", "wx_snow", "wx_freezing",
    "wx_min_visibility_3h", "wx_min_ceiling_3h", "wx_thunder_3h", "wx_snow_3h",
    "taf_available", "taf_lead_min", "taf_is_amendment", "taf_flight_category",
    "taf_worst_flight_category", "taf_visibility_sm", "taf_ceiling_ft", "taf_wind_speed_kt",
    "taf_wind_gust_kt", "taf_thunder", "taf_snow", "taf_prob_pct",
    "atc_gdp_now", "atc_gdp_since_start_min", "atc_gdp_to_end_min", "atc_gdp_at_target",
    "atc_gs_now", "atc_gs_since_start_min", "atc_gs_to_end_min", "atc_gs_at_target",
    "atc_gdp_issued_24h", "atc_gs_issued_24h",
    "ops_dep_1h_n", "ops_dep_1h_delay_mean", "ops_dep_1h_late15_share", "ops_dep_3h_n",
    "ops_dep_3h_delay_mean", "ops_dep_3h_late15_share", "ops_arr_1h_n", "ops_arr_1h_delay_mean",
    "ops_arr_1h_late15_share", "ops_arr_3h_n", "ops_arr_3h_delay_mean", "ops_arr_3h_late15_share",
    "ops_sched_dep_1h_n", "ops_dep_flow_1h",
    "dem_departures", "dem_arrivals",
)  # fmt: skip
GROUPS = ("cal_", "wx_", "taf_", "atc_", "ops_", "dem_")


@dataclass(frozen=True)
class GBDT:
    name: str
    features: Sequence[str]
    calibration: str = "platt"  # "platt" (logistic), "isotonic" or "none"
    validation_months: int = 12
    half_life_years: float | None = None  # weight rows by recency (None: equal weights)
    params: Mapping[str, Any] = field(default_factory=lambda: dict(PARAMS))

    def columns(self) -> set[str]:
        return set(self.features)

    def fit_predict(self, train: pl.DataFrame, test: pl.DataFrame) -> Floats:
        y = train[LABEL].to_numpy().astype(np.float64)
        if np.unique(y).size < 2:  # nothing to learn: the training rate
            return np.full(test.height, y.mean())
        x, x_test, categorical = encode(train, test, self.features)
        weight = self._weights(train)
        params = dict(self.params)

        def data(rows: Mask) -> lgb.Dataset:
            return lgb.Dataset(x[rows], y[rows], weight=weight[rows],
                               categorical_feature=categorical)  # fmt: skip

        fit, held = split(train, self.validation_months)
        recalibrate: Callable[[Floats], Floats] = _identity
        rounds = FALLBACK_ROUNDS
        if fit.any() and held.any():
            first = lgb.train(params, data(fit), MAX_ROUNDS, valid_sets=[data(held)],
                              callbacks=[lgb.early_stopping(PATIENCE, verbose=False)])  # fmt: skip
            rounds = first.best_iteration
            recalibrate = recalibration(self.calibration, y[held], _predict(first, x[held]))
        final = lgb.train(params, data(np.ones(y.size, dtype=bool)), rounds)
        return recalibrate(_predict(final, x_test))

    def _weights(self, train: pl.DataFrame) -> Floats:
        if self.half_life_years is None:
            return np.ones(train.height)
        age = train.select((pl.col("target_utc").max() - pl.col("target_utc")).dt.total_days())
        years = age.to_series().to_numpy() / 365.25
        return np.asarray(0.5 ** (years / self.half_life_years), dtype=np.float64)


def outlook(name: str = "gbdt", groups: Sequence[str] = GROUPS, **options: Any) -> GBDT:
    """The Outlook GBDT on the hours spine's features of ``groups`` (prefixes)."""
    return GBDT(name, [f for f in OUTLOOK_FEATURES if f.startswith(tuple(groups))], **options)


def encode(
    train: pl.DataFrame, test: pl.DataFrame, features: Sequence[str]
) -> tuple[Floats, Floats, list[int]]:
    """Feature matrices (missing as NaN) and the positions of the categorical columns."""
    columns, categorical = [], []
    for i, name in enumerate(features):
        if name.endswith("flight_category"):
            columns.append(pl.col(name).replace_strict(FLIGHT_CATEGORY_RANK, default=None,
                                                       return_dtype=pl.Float64))  # fmt: skip
        elif train.schema[name] == pl.String:
            levels = train[name].drop_nulls().unique().sort().to_list()
            columns.append(pl.col(name).replace_strict(levels, range(len(levels)), default=None,
                                                       return_dtype=pl.Float64))  # fmt: skip
            categorical.append(i)
        else:
            columns.append(pl.col(name).cast(pl.Float64))
    return train.select(columns).to_numpy(), test.select(columns).to_numpy(), categorical


def split(train: pl.DataFrame, months: int) -> tuple[Mask, Mask]:
    """Rows to fit and rows held out: the last ``months`` training months (at most half of
    them), with the ``EMBARGO`` before them in neither."""
    distinct = train["month"].unique().sort()
    n = min(months, distinct.len() // 2)
    if n == 0:
        return np.ones(train.height, dtype=bool), np.zeros(train.height, dtype=bool)
    first = distinct[-n]
    start = datetime(first.year, first.month, first.day, tzinfo=UTC)
    held = (train["month"] >= first).to_numpy()
    fit = (train["target_utc"] < start - EMBARGO).to_numpy()
    return fit, held


def recalibration(kind: str, y: Floats, p: Floats) -> Callable[[Floats], Floats]:
    """A map from forecasts to recalibrated ones, fitted on held-out forecasts ``p``."""
    if kind == "none" or np.unique(y).size < 2:
        return _identity
    if kind == "isotonic":
        isotonic = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(p, y)
        return lambda q: np.asarray(isotonic.predict(q), dtype=np.float64)
    if kind != "platt":
        raise ValueError(f"unknown calibration {kind!r}")
    intercept, slope = calibration(y, p)
    if np.isnan(slope):
        return _identity
    return lambda q: 1 / (1 + np.exp(-(intercept + slope * logit(q))))


def _identity(p: Floats) -> Floats:
    return p


def _predict(booster: lgb.Booster, x: Floats) -> Floats:
    return np.asarray(booster.predict(x), dtype=np.float64)
