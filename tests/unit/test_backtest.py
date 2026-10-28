"""Rolling-origin folds, and a backtest run on a synthetic feature store."""

import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from ordfi.features.spines import days
from ordfi.models import backtest
from ordfi.models.gbdt import FEATURES


def test_training_stops_before_the_release_lag_and_skips_covid() -> None:
    available = [backtest.add_months(date(2019, 1, 1), i) for i in range(36)]
    months = backtest.training_months(date(2021, 12, 1), available)
    assert months[0] == date(2019, 1, 1) and months[-1] == date(2021, 9, 1)  # 3 months back
    assert date(2020, 2, 1) in months and date(2021, 7, 1) in months
    assert date(2020, 3, 1) not in months and date(2021, 6, 1) not in months  # COVID
    assert backtest.training_months(date(2019, 9, 1), available)[-1] == date(2019, 6, 1)


HORIZON = {"hours": "1h", "days": "d1_1900"}


def write_store(root: Path, months: list[date], gdp: dict[date, bool],
                spine: str = "hours") -> None:  # fmt: skip
    """Hourly feature files at the 1h horizon (or daily ones at the d1_1900 issue), a GDP in
    every target of the months in ``gdp`` that are True, and the core files the regime slices
    read. Features the baselines do not read are missing (VFR for flight categories)."""
    for month in months:
        start = datetime(month.year, month.month, 1, tzinfo=UTC)
        following = backtest.add_months(month, 1)
        end = datetime(following.year, following.month, 1, tzinfo=UTC)
        if spine == "days":
            frame = days(month, following, ["d1_1900"]).with_columns(cal_local_hour=pl.lit(0))
        else:
            hours = pl.datetime_range(start, end, "1h", closed="left", eager=True)
            frame = pl.DataFrame({"target_utc": hours}).with_columns(
                as_of=pl.col("target_utc") - timedelta(hours=1),
                cal_local_hour=pl.col("target_utc").dt.hour(),
            )
        frame = frame.with_columns(
            cal_month=pl.lit(month.month), cal_day_of_week=pl.col("target_utc").dt.weekday(),
            atc_gdp_now=pl.lit(False), atc_gdp_at_target=pl.lit(False),
            y_gdp=pl.lit(gdp.get(month, False)),
        )  # fmt: skip
        unread = [name for name in FEATURES[spine] if name not in frame.columns]
        frame = frame.with_columns(
            pl.lit("VFR" if name.endswith("flight_category") else None).alias(name)
            for name in unread
        ).with_columns(pl.col(pl.Null).cast(pl.Float64))
        path = root / "features" / spine / f"horizon={HORIZON[spine]}" / f"{month:%Y-%m}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(path)
    core = root / "core"
    core.mkdir(parents=True, exist_ok=True)
    utc = pl.Datetime("us", "UTC")
    pl.DataFrame(
        {"valid_time": [datetime(2019, 1, 1, tzinfo=UTC)], "has_thunder": [False],
         "has_snow": [False], "has_freezing": [False]},
        schema={"valid_time": utc, "has_thunder": pl.Boolean(), "has_snow": pl.Boolean(),
                "has_freezing": pl.Boolean()},
    ).write_parquet(core / "weather_obs.parquet")  # fmt: skip
    pl.DataFrame(
        schema={"airport": pl.String(), "scope": pl.String(), "start_utc": utc, "end_utc": utc}
    ).write_parquet(core / "atc_program_interval.parquet")


@pytest.mark.parametrize(("task", "spine"), [("hour_gdp", "hours"), ("day_gdp", "days")])
def test_a_run_never_learns_from_months_it_could_not_have_seen(
    tmp_path: Path, task: str, spine: str
) -> None:
    months = [date(2019, m, 1) for m in range(1, 9)]
    # GDPs only in months a July or August forecast may not use (the two months of release
    # lag before each and the test months), so any leaked label would lift a forecast above 0.
    write_store(tmp_path, months, {m: m >= date(2019, 6, 1) for m in months}, spine)
    test_months = [date(2019, 7, 1), date(2019, 8, 1)]
    out = backtest.run(task, [HORIZON[spine]], test_months, tmp_path, "t")
    predictions = pl.read_parquet(out / "predictions.parquet")
    assert predictions["p"].max() == 0.0
    assert set(predictions["model"]) == {
        "base_rate", "calendar", "announced", "gbdt_schedule", "gbdt", "gbdt_no_taf",
        "gbdt_no_atc", "gbdt_no_ops", "gbdt_recent",
    }  # fmt: skip
    metrics = pl.read_parquet(out / "metrics.parquet")
    assert set(metrics["slice"]) == set(backtest.SLICES)
    assert json.loads((out / "run.json").read_text())["label_lag_months"] == 2


def test_outlook_runs_forecast_a_track_record_and_score_only_the_test_months(
    tmp_path: Path,
) -> None:
    months = [backtest.add_months(date(2017, 1, 1), i) for i in range(32)]
    write_store(tmp_path, months, {m: m.month in (6, 7) for m in months})
    out = backtest.run("hour_gdp", ["1h"], [date(2019, 7, 1), date(2019, 8, 1)], tmp_path, "t",
                       ["announced"])  # fmt: skip
    record = json.loads((out / "run.json").read_text())["track_record_months"]
    assert record[0] == "2018-05-01" and record[-1] == "2019-06-01" and len(record) == 14
    predictions = pl.read_parquet(out / "predictions.parquet")
    assert predictions["test_month"].min() == date(2018, 5, 1)
    scored = pl.read_parquet(out / "metrics.parquet").filter(pl.col("slice") == "all")
    assert set(scored["n"]) == {(31 + 31) * 24.0}  # July and August only
    alerts = pl.read_parquet(out / "alerts.parquet")
    assert set(alerts["model"]) == {"calendar", "announced"} and set(alerts["months"]) == {2}


def test_worker_processes_forecast_as_one_process_does(tmp_path: Path) -> None:
    write_store(tmp_path, [date(2019, m, 1) for m in range(1, 9)], {date(2019, 2, 1): True})
    months = [date(2019, 7, 1), date(2019, 8, 1)]
    one, two = (
        pl.read_parquet(backtest.run("hour_gdp", ["1h"], months, tmp_path, f"w{n}", ["gbdt"],
                                     workers=n) / "predictions.parquet")
        for n in (1, 2)
    )  # fmt: skip
    assert set(one["model"]) == {"calendar", "gbdt", "gbdt_recent"} and one.equals(two)


def test_the_cli_writes_the_run_and_prints_its_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_store(tmp_path, [date(2019, m, 1) for m in range(1, 9)], {date(2019, 2, 1): True})
    monkeypatch.setenv("ORDFI_DATA_DIR", str(tmp_path))
    args = ["--task", "hour_gdp", "--from", "2019-07", "--to", "2019-08", "--horizons", "1h",
            "--workers", "1", "--run", "cli"]  # fmt: skip
    backtest.main([*args, "--models", "announced"])
    printed = capsys.readouterr().out
    assert "hour_gdp: A general ORD GDP" in printed and "announced" in printed
    metrics = pl.read_parquet(tmp_path / "backtests" / "hour_gdp" / "cli" / "metrics.parquet")
    assert set(metrics["model"]) == {"calendar", "announced"}  # with the skill reference
    with pytest.raises(SystemExit):
        backtest.main([*args, "--models", "oracle"])
    with pytest.raises(SystemExit):  # a daily task has issue times, not 1h
        backtest.main([*args[:1], "day_gdp", *args[2:]])


def test_only_the_departure_tasks_run_in_one_process_by_default() -> None:
    for task in ("hour_gdp", "day_bad60"):
        assert backtest.default_workers(backtest.TASKS[task]) == (os.cpu_count() or 1)
    assert backtest.default_workers(backtest.TASKS["dep_late15"]) == 1
