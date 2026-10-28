"""Rolling-origin folds, and a backtest run on a synthetic feature store."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from ordfi.models import backtest


def test_training_stops_before_the_release_lag_and_skips_covid() -> None:
    available = [backtest.add_months(date(2019, 1, 1), i) for i in range(36)]
    months = backtest.training_months(date(2021, 12, 1), available)
    assert months[0] == date(2019, 1, 1) and months[-1] == date(2021, 9, 1)  # 3 months back
    assert date(2020, 2, 1) in months and date(2021, 7, 1) in months
    assert date(2020, 3, 1) not in months and date(2021, 6, 1) not in months  # COVID
    assert backtest.training_months(date(2019, 9, 1), available)[-1] == date(2019, 6, 1)


def write_store(root: Path, months: list[date], gdp: dict[date, bool]) -> None:
    """Hourly feature files at the 1h horizon, a GDP in every hour of the months in ``gdp``
    that are True, and the core files the regime slices read."""
    for month in months:
        start = datetime(month.year, month.month, 1, tzinfo=UTC)
        following = backtest.add_months(month, 1)
        end = datetime(following.year, following.month, 1, tzinfo=UTC)
        hours = pl.datetime_range(start, end, "1h", closed="left", eager=True)
        frame = pl.DataFrame({"target_utc": hours}).with_columns(
            as_of=pl.col("target_utc") - timedelta(hours=1),
            cal_month=pl.lit(month.month), cal_local_hour=pl.col("target_utc").dt.hour(),
            cal_day_of_week=pl.col("target_utc").dt.weekday(), atc_gdp_now=pl.lit(False),
            atc_gdp_at_target=pl.lit(False), y_gdp=pl.lit(gdp.get(month, False)),
        )  # fmt: skip
        path = root / "features" / "hours" / "horizon=1h" / f"{month:%Y-%m}.parquet"
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


def test_a_run_never_learns_from_months_it_could_not_have_seen(tmp_path: Path) -> None:
    months = [date(2019, m, 1) for m in range(1, 9)]
    # GDPs only in months a July or August forecast may not use (the two months of release
    # lag before each and the test months), so any leaked label would lift a forecast above 0.
    write_store(tmp_path, months, {m: m >= date(2019, 6, 1) for m in months})
    out = backtest.run("hour_gdp", ["1h"], [date(2019, 7, 1), date(2019, 8, 1)], tmp_path, "t")
    predictions = pl.read_parquet(out / "predictions.parquet")
    assert predictions["p"].max() == 0.0
    assert set(predictions["model"]) == {"base_rate", "calendar", "announced"}
    metrics = pl.read_parquet(out / "metrics.parquet")
    assert set(metrics["slice"]) == set(backtest.SLICES)
    assert json.loads((out / "run.json").read_text())["label_lag_months"] == 2


def test_the_cli_writes_the_run_and_prints_its_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_store(tmp_path, [date(2019, m, 1) for m in range(1, 9)], {date(2019, 2, 1): True})
    monkeypatch.setenv("ORDFI_DATA_DIR", str(tmp_path))
    backtest.main(["--task", "hour_gdp", "--from", "2019-07", "--to", "2019-08",
                   "--horizons", "1h", "--run", "cli"])  # fmt: skip
    printed = capsys.readouterr().out
    assert "hour_gdp: A general ORD GDP" in printed and "announced" in printed
    assert (tmp_path / "backtests" / "hour_gdp" / "cli" / "metrics.parquet").is_file()
