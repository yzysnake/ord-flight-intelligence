"""Climatology baselines: event rates in the training window, by cell, shrunk toward coarser
cells (research study §6.4, §6.5).

A ``Climatology`` is a ladder of nested cells, from the base rate (no keys) to the finest key
set. A cell's estimate is ``(events + m * parent estimate) / (rows + m)`` with ``m =
strength`` pseudo-rows, so sparse cells lean on their parent. A null key means unknown: the row
keeps its parent's estimate, and it does not count toward that level's cells. Keys may be
derived from as-of features (e.g. a turn-slack bucket), which makes a calibrated rule.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import polars as pl
from numpy.typing import NDArray

LABEL = "y"


class Model(Protocol):
    @property
    def name(self) -> str: ...

    def columns(self) -> set[str]:
        """Feature columns the model reads."""
        ...

    def fit_predict(self, train: pl.DataFrame, test: pl.DataFrame) -> NDArray[np.float64]:
        """Fit on ``train`` (with its ``y`` label, ``month`` and ``target_utc``) and return P(y)
        for each ``test`` row."""
        ...


@dataclass(frozen=True)
class Climatology:
    name: str
    levels: Sequence[Sequence[str]]  # nested key sets, coarse to fine; the base rate is implied
    derived: Mapping[str, pl.Expr] = field(default_factory=dict)  # keys computed from features
    strength: float = 50.0

    def columns(self) -> set[str]:
        keys = {k for level in self.levels for k in level} - set(self.derived)
        return keys | {c for expr in self.derived.values() for c in expr.meta.root_names()}

    def fit_predict(self, train: pl.DataFrame, test: pl.DataFrame) -> NDArray[np.float64]:
        derived = [expr.alias(name) for name, expr in self.derived.items()]
        train, test = train.with_columns(derived), test.with_columns(derived)
        m = self.strength
        # Working columns start with "_", so they cannot clash with a key.
        keys_used = sorted({k for level in self.levels for k in level})
        rows = test.select(pl.int_range(pl.len()).alias("_row"), *keys_used).with_columns(
            _p=pl.lit(train[LABEL].mean(), dtype=pl.Float64)
        )
        for level in self.levels:
            keys = list(level)
            cells = train.drop_nulls(keys).group_by(keys).agg(_n=pl.len(), _k=pl.col(LABEL).sum())
            rows = (
                rows.join(cells, on=keys, how="left", maintain_order="left")
                .with_columns(
                    _p=(pl.col("_k").fill_null(0) + m * pl.col("_p"))
                    / (pl.col("_n").fill_null(0) + m)
                )
                .drop("_n", "_k")
            )
        return rows["_p"].to_numpy()


def _buckets(column: str, edges: Sequence[float], labels: Sequence[str]) -> pl.Expr:
    """Label of the bucket ``[edges[i - 1], edges[i])`` holding ``column`` (null stays null)."""
    value = pl.col(column)
    parts = []
    for low, high, label in zip([None, *edges], [*edges, None], labels, strict=True):
        inside = value.is_not_null()
        if low is not None:
            inside &= value >= low
        if high is not None:
            inside &= value < high
        parts.append(pl.when(inside).then(pl.lit(label)))
    return pl.coalesce(parts)


CALENDAR_LEVELS = [
    ["cal_month"],
    ["cal_month", "cal_local_hour"],
    ["cal_month", "cal_local_hour", "cal_day_of_week"],
]
# Known inbound turn slack; null (tail not known yet, or no tail in BTS) falls back.
INBOUND = (
    pl.when(~pl.col("inb_found"))
    .then(pl.lit("no inbound"))
    .otherwise(_buckets("inb_slack_min", [0, 15, 30, 60], ["<0", "0-14", "15-29", "30-59", ">=60"]))
)
RECENT_DELAY = _buckets(
    "ops_dep_1h_delay_mean", [0, 10, 20, 40, 60], ["<0", "0-9", "10-19", "20-39", "40-59", ">=60"]
)


def base_rate() -> Climatology:
    return Climatology("base_rate", [])


def calendar() -> Climatology:
    """By month, local hour and weekday: the climatology that skill is measured against."""
    return Climatology("calendar", CALENDAR_LEVELS)


def route() -> Climatology:
    """By month and local hour, then carrier and destination (departures)."""
    return Climatology(
        "route",
        [*CALENDAR_LEVELS[:2], ["cal_month", "cal_local_hour", "flt_carrier"],
         ["cal_month", "cal_local_hour", "flt_carrier", "flt_dest"]],
    )  # fmt: skip


def slack_rule() -> Climatology:
    """The rate by the inbound aircraft's known turn slack (departures, from 6 h out)."""
    return Climatology("slack_rule", [["inbound"]], derived={"inbound": INBOUND})


def persistence() -> Climatology:
    """The rate by ORD's departure delay in the hour before as_of."""
    return Climatology("persistence", [["recent_delay"]], derived={"recent_delay": RECENT_DELAY})


def announced(kind: str) -> Climatology:
    """The rate by whether a GDP or ground stop (``kind``: gdp, gs) is in effect at as_of and
    announced to cover the target."""
    return Climatology("announced", [[f"atc_{kind}_now", f"atc_{kind}_at_target"]])
