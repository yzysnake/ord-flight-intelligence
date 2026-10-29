"""Gradient-boosted trees on the as-of features: the Outlook and departure models (research
study §6.4).

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

# One thread per fit: the backtest fits test months in parallel processes, which is faster at
# these sizes than threads within a fit.
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

# How often ORD has had programs lately, from the advisories known at as_of (both spines), and
# how often for staffing.
PROGRAM_CLIMATE = (
    "atc_gdp_days_7d", "atc_gdp_days_30d", "atc_gs_days_7d", "atc_gs_days_30d",
)  # fmt: skip
STAFFING_DAYS = ("atc_staffing_days_7d", "atc_staffing_days_30d")
# The hours spine's window of hours from the target (the windowed ground-stop task only).
WINDOW_FEATURES = (
    "taf_win_hours", "taf_win_thunder_hours", "taf_win_ifr_hours", "taf_win_snow_hours",
    "taf_win_worst_flight_category", "taf_win_max_gust_kt", "taf_win_min_ceiling_ft",
    "taf_win_min_visibility_sm", "taf_win_max_prob_pct",
    "mos_win_flight_category", "mos_win_wind_speed_kt", "mos_win_snow_pct",
    "mos_win_thunder_6h_pct", "mos_win_severe_6h_pct",
    "nbm_win_flight_category", "nbm_win_ifr_ceiling_pct", "nbm_win_ifr_visibility_pct",
    "nbm_win_snow_pct", "nbm_win_freezing_pct", "nbm_win_wind_gust_kt", "nbm_win_thunder_3h_pct",
    "atc_win_gdp_announced", "atc_win_gs_announced", "dem_win_departures", "dem_win_arrivals",
)  # fmt: skip
# Station guidance for the target hour or day, the same on both outlook spines.
GUIDANCE_FEATURES = (
    "mos_projections", "mos_flight_category", "mos_ceiling_category", "mos_visibility_category",
    "mos_wind_speed_kt", "mos_snow_pct", "mos_freezing_pct", "mos_thunder_6h_pct",
    "mos_severe_6h_pct", "mos_pop_6h_pct", "mos_age_min",
    "nbm_projections", "nbm_flight_category", "nbm_ceiling_ft", "nbm_visibility_mi",
    "nbm_ifr_ceiling_pct", "nbm_ifr_visibility_pct", "nbm_snow_pct", "nbm_freezing_pct",
    "nbm_sleet_pct", "nbm_wind_speed_kt", "nbm_wind_gust_kt", "nbm_thunder_3h_pct",
    "nbm_pop_6h_pct", "nbm_snow_6h_in", "nbm_ice_6h_in", "nbm_age_min",
)  # fmt: skip
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
    *GUIDANCE_FEATURES,
    "atc_gdp_now", "atc_gdp_since_start_min", "atc_gdp_to_end_min", "atc_gdp_at_target",
    "atc_gs_now", "atc_gs_since_start_min", "atc_gs_to_end_min", "atc_gs_at_target",
    "atc_gdp_issued_24h", "atc_gs_issued_24h", *PROGRAM_CLIMATE, *STAFFING_DAYS,
    "ops_dep_1h_n", "ops_dep_1h_delay_mean", "ops_dep_1h_late15_share", "ops_dep_3h_n",
    "ops_dep_3h_delay_mean", "ops_dep_3h_late15_share", "ops_arr_1h_n", "ops_arr_1h_delay_mean",
    "ops_arr_1h_late15_share", "ops_arr_3h_n", "ops_arr_3h_delay_mean", "ops_arr_3h_late15_share",
    "ops_sched_dep_1h_n", "ops_dep_flow_1h",
    "dem_departures", "dem_arrivals",
    *WINDOW_FEATURES,
)  # fmt: skip
# Every feature of the days spine, by group.
DAY_FEATURES = (
    "cal_day_of_week", "cal_month", "cal_is_weekend", "cal_is_holiday", "cal_days_to_holiday",
    "cal_days_since_holiday",
    "wx_age_min", "wx_flight_category", "wx_visibility_mi", "wx_ceiling_ft", "wx_wind_speed_kt",
    "wx_wind_gust_kt", "wx_temp_c", "wx_thunder", "wx_snow", "wx_freezing",
    "wx_min_visibility_3h", "wx_min_ceiling_3h", "wx_thunder_3h", "wx_snow_3h",
    "taf_day_hours", "taf_day_amendment", "taf_day_ifr_hours", "taf_day_thunder_hours",
    "taf_day_snow_hours", "taf_day_max_wind_kt", "taf_day_max_gust_kt", "taf_day_min_ceiling_ft",
    "taf_day_min_visibility_sm", "taf_day_max_prob_pct", "taf_day_age_min",
    "taf_day_flight_category", "taf_day_worst_flight_category",
    *GUIDANCE_FEATURES,
    "atc_gdp_now", "atc_gdp_since_start_min", "atc_gdp_to_end_min", "atc_gdp_at_target",
    "atc_gs_now", "atc_gs_since_start_min", "atc_gs_to_end_min", "atc_gs_at_target",
    "atc_gdp_issued_24h", "atc_gs_issued_24h", *PROGRAM_CLIMATE, *STAFFING_DAYS,
    "ops_dep_1h_n", "ops_dep_1h_delay_mean", "ops_dep_1h_late15_share", "ops_dep_3h_n",
    "ops_dep_3h_delay_mean", "ops_dep_3h_late15_share", "ops_arr_1h_n", "ops_arr_1h_delay_mean",
    "ops_arr_1h_late15_share", "ops_arr_3h_n", "ops_arr_3h_delay_mean", "ops_arr_3h_late15_share",
    "ops_sched_dep_1h_n", "ops_dep_flow_1h", "ops_dep_24h_n", "ops_dep_24h_delay_mean",
    "ops_dep_24h_late15_share", "ops_arr_24h_n", "ops_arr_24h_delay_mean",
    "ops_arr_24h_late15_share",
    "dem_departures", "dem_peak_departures", "dem_arrivals", "dem_peak_arrivals",
)  # fmt: skip
# Every feature of the departures spine: the airport's state, as for the hours, and the flight's
# schedule and inbound aircraft (flt_, inb_).
DEPARTURE_FEATURES = (
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
    "atc_gdp_issued_24h", "atc_gs_issued_24h", *PROGRAM_CLIMATE, *STAFFING_DAYS,
    "ops_dep_1h_n", "ops_dep_1h_delay_mean", "ops_dep_1h_late15_share", "ops_dep_3h_n",
    "ops_dep_3h_delay_mean", "ops_dep_3h_late15_share", "ops_arr_1h_n", "ops_arr_1h_delay_mean",
    "ops_arr_1h_late15_share", "ops_arr_3h_n", "ops_arr_3h_delay_mean", "ops_arr_3h_late15_share",
    "ops_sched_dep_1h_n", "ops_dep_flow_1h",
    "dem_departures", "dem_arrivals",
    "flt_carrier", "flt_marketing_carrier", "flt_dest", "flt_distance", "flt_sched_block_min",
    "inb_found", "inb_origin", "inb_sched_turn_min", "inb_departed", "inb_arrived",
    "inb_dep_delay", "inb_arr_delay", "inb_known_late_min", "inb_slack_min",
)  # fmt: skip
FEATURES = {"hours": OUTLOOK_FEATURES, "days": DAY_FEATURES, "departures": DEPARTURE_FEATURES}
# Months held out for early stopping and recalibration: a year of hours, but two years of days,
# which give 30 times fewer rows (chosen on the development months, docs/backtests/).
VALIDATION_MONTHS = {"hours": 12, "days": 24, "departures": 12}
# Threads per departure fit: on 2.6 M rows LightGBM's threads scale poorly past six, so the
# backtest fits three departure folds at once instead (backtest.default_workers).
DEPARTURE_THREADS = 6
GROUPS = ("cal_", "wx_", "taf_", "mos_", "nbm_", "atc_", "ops_", "dem_")


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


def outlook(name: str = "gbdt", groups: Sequence[str] = GROUPS, spine: str = "hours",
            without: Sequence[str] = (), **options: Any) -> GBDT:  # fmt: skip
    """The Outlook GBDT on the ``spine``'s features (hours or days) of ``groups``, less those
    ``without`` (prefixes both)."""
    features = [f for f in FEATURES[spine]
                if f.startswith(tuple(groups)) and not f.startswith(tuple(without))]  # fmt: skip
    return GBDT(name, features, **{"validation_months": VALIDATION_MONTHS[spine], **options})


def departure(name: str = "gbdt", without: Sequence[str] = ()) -> GBDT:
    """The departure GBDT: every feature of the departures spine less those ``without``
    (prefixes), with ``DEPARTURE_THREADS`` threads per fit."""
    features = [f for f in DEPARTURE_FEATURES if not f.startswith(tuple(without))]
    params = {**PARAMS, "num_threads": DEPARTURE_THREADS}
    return GBDT(name, features, validation_months=VALIDATION_MONTHS["departures"], params=params)


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
