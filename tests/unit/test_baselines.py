"""Climatology baselines: shrinkage toward coarser cells, unseen and unknown cells."""

from collections.abc import Sequence

import polars as pl
import pytest

from ordfi.models.baselines import INBOUND, Climatology


def frame(rows: Sequence[tuple[object, ...]], columns: list[str]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=columns, orient="row")


def test_cells_shrink_toward_the_parent_rate() -> None:
    train = frame([("a", 1)] * 10 + [("b", 0)] * 10, ["k", "y"])
    test = frame([("a",), ("b",), ("unseen",)], ["k"])
    model = Climatology("c", [["k"]], strength=10)
    # Base rate 0.5; a: (10 + 10 * 0.5) / (10 + 10).
    assert model.fit_predict(train, test).tolist() == [0.75, 0.25, 0.5]


def test_nested_levels_shrink_step_by_step() -> None:
    rows = [("x", "a", 1)] * 4 + [("x", "b", 0)] * 4 + [("z", "c", 0)] * 8
    model = Climatology("c", [["g"], ["g", "k"]], strength=4)
    p = model.fit_predict(frame(rows, ["g", "k", "y"]), frame([("x", "a")], ["g", "k"]))
    base = 4 / 16
    group = (4 + 4 * base) / (8 + 4)
    assert p.tolist() == [pytest.approx((4 + 4 * group) / (4 + 4))]


def test_unknown_keys_keep_the_parent_rate_and_do_not_count() -> None:
    train = frame([("a", 1), ("a", 1), (None, 0), (None, 0)], ["k", "y"])
    test = frame([("a",), (None,)], ["k"])
    p = Climatology("c", [["k"]], strength=2).fit_predict(train, test)
    assert p.tolist() == [pytest.approx((2 + 2 * 0.5) / 4), 0.5]


def test_inbound_buckets_known_slack_and_keep_unknown_null() -> None:
    rows = frame(
        [(True, -5), (True, 20), (True, 75), (False, None), (None, None)],
        ["inb_found", "inb_slack_min"],
    )
    assert rows.select(INBOUND).to_series().to_list() == [
        "<0", "15-29", ">=60", "no inbound", None,
    ]  # fmt: skip


def test_columns_lists_raw_inputs_of_derived_keys() -> None:
    model = Climatology("c", [["cal_month"], ["cal_month", "b"]], derived={"b": INBOUND})
    assert model.columns() == {"cal_month", "inb_found", "inb_slack_min"}
