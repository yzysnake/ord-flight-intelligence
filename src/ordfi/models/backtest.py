"""Rolling-origin backtests of event forecasts on the as-of feature snapshots (study §6.5).

Each test month M is forecast by models fitted on the months BTS had published by then: every
month up to M - 3, since BTS releases a month 6–8 weeks after it ends (``LABEL_LAG``). The
COVID months are left out of training. Scores are pooled over the test months and split by
regime (season, program and storm days, the FAA cap), with Brier skill against the calendar
climatology and intervals from resampling whole days.

``python -m ordfi.models.backtest --task dep_late15 --from 2024-09 --to 2026-08`` writes
``backtests/<task>/<run>/``: ``predictions.parquet``, ``metrics.parquet``,
``reliability.parquet`` and ``run.json``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl

from ordfi.features.spines import HORIZONS
from ordfi.models import baselines
from ordfi.models.baselines import LABEL, Model
from ordfi.models.metrics import reliability, scores, skill
from ordfi.settings import data_dir

LABEL_LAG = 2  # months between the last training month and the test month (BTS release lag)
EXCLUDED = (date(2020, 3, 1), date(2021, 6, 1))  # COVID: left out of training (months, inclusive)
CAP = (date(2026, 6, 2), date(2027, 10, 30))  # FAA ORD operations cap, its own regime
REFERENCE = "calendar"
LOCAL_TZ = "America/Chicago"
BAD_HOUR_SHARE = 0.2  # an outlook "bad hour": 20 %+ of departures 60+ min late or cancelled
BAD_HOUR_MIN_DEPARTURES = 10


@dataclass(frozen=True)
class Task:
    name: str
    spine: str
    label: pl.Expr  # the event, from the y_ columns
    models: Callable[[], list[Model]]
    rows: pl.Expr = field(default_factory=lambda: pl.lit(True))  # spine rows scored
    description: str = ""


def _late(minutes: int) -> pl.Expr:
    return (pl.col("y_dep_delay") >= minutes) | pl.col("y_cancelled")


def _departure_models() -> list[Model]:
    return [baselines.base_rate(), baselines.calendar(), baselines.route(),
            baselines.persistence(), baselines.slack_rule()]  # fmt: skip


TASKS = {
    task.name: task
    for task in (
        Task("dep_late15", "departures", _late(15), _departure_models,
             description="An ORD departure leaves 15+ min late or is cancelled (T2)"),
        Task("dep_late60", "departures", _late(60), _departure_models,
             description="An ORD departure leaves 60+ min late or is cancelled (T2)"),
        Task("dep_cancelled", "departures", pl.col("y_cancelled"), _departure_models,
             description="An ORD departure is cancelled (T5)"),
        Task("hour_bad60", "hours", pl.col("y_late60_share") >= BAD_HOUR_SHARE,
             lambda: [baselines.base_rate(), baselines.calendar(), baselines.persistence()],
             rows=pl.col("y_n_departures") >= BAD_HOUR_MIN_DEPARTURES,
             description="20 %+ of an hour's ORD departures leave 60+ min late or are cancelled "
                         "(hours with 10+ departures; T1)"),
        Task("hour_gdp", "hours", pl.col("y_gdp"),
             lambda: [baselines.base_rate(), baselines.calendar(), baselines.announced("gdp")],
             description="A general ORD GDP is in effect during the hour (T1)"),
        Task("hour_ground_stop", "hours", pl.col("y_ground_stop"),
             lambda: [baselines.base_rate(), baselines.calendar(), baselines.announced("gs")],
             description="A general ORD ground stop is in effect during the hour (T1)"),
    )
}  # fmt: skip


def add_months(month: date, n: int) -> date:
    index = month.year * 12 + month.month - 1 + n
    return date(index // 12, index % 12 + 1, 1)


def training_months(test: date, available: list[date]) -> list[date]:
    """Months a model forecasting ``test`` may learn from: published by then, COVID left out."""
    last = add_months(test, -(LABEL_LAG + 1))
    return [m for m in available if m <= last and not EXCLUDED[0] <= m <= EXCLUDED[1]]


def _key(task: Task) -> str:
    return "flight_key" if task.spine == "departures" else "target_utc"


def load(task: Task, horizon: str, models: list[Model], root: Path) -> pl.DataFrame:
    """The task's scored rows at one horizon: key, times, the event ``y`` and model inputs."""
    needed = {_key(task), "as_of", "target_utc", *task.label.meta.root_names(),
              *task.rows.meta.root_names()}  # fmt: skip
    for model in models:
        needed |= model.columns()
    local = pl.col("target_utc").dt.convert_time_zone(LOCAL_TZ)
    return (
        pl.scan_parquet(root / "features" / task.spine / f"horizon={horizon}" / "*.parquet")
        .select(sorted(needed))
        .filter(task.rows)
        .with_columns(**{LABEL: task.label.cast(pl.Int8)})
        .filter(pl.col(LABEL).is_not_null())
        .with_columns(
            month=pl.col("target_utc").dt.truncate("1mo").dt.date(), local_date=local.dt.date()
        )
        .collect()
    )


def predict(task: Task, horizons: list[str], test_months: list[date], root: Path) -> pl.DataFrame:
    """Every model's forecasts for every test month and horizon."""
    models = task.models()
    parts = []
    for horizon in horizons:
        frame = load(task, horizon, models, root)
        available = sorted(frame["month"].unique().to_list())
        for month in test_months:
            test = frame.filter(pl.col("month") == month)
            train = frame.filter(pl.col("month").is_in(training_months(month, available)))
            if test.is_empty() or train.is_empty():
                continue
            for model in models:
                parts.append(
                    test.select(_key(task), "local_date", LABEL).with_columns(
                        horizon=pl.lit(horizon),
                        model=pl.lit(model.name),
                        test_month=pl.lit(month),
                        p=model.fit_predict(train, test),
                    )
                )
    return pl.concat(parts)


def day_flags(core: Path) -> pl.DataFrame:
    """Post-hoc regimes of each local day, for evaluation only: a general GDP or ground stop
    at ORD, thunder, and snow or freezing precipitation."""
    local = pl.col("valid_time").dt.convert_time_zone(LOCAL_TZ).dt.date()
    weather = (
        pl.scan_parquet(core / "weather_obs.parquet")
        .group_by(local_date=local)
        .agg(
            thunder_day=pl.col("has_thunder").any(),
            snow_day=(pl.col("has_snow") | pl.col("has_freezing")).any(),
        )
    )
    programs = (
        pl.scan_parquet(core / "atc_program_interval.parquet")
        .filter(
            (pl.col("airport") == "ORD")
            & (pl.col("scope") == "general")
            & (pl.col("end_utc") > pl.col("start_utc"))
        )
        .select(
            local_date=pl.date_ranges(
                pl.col("start_utc").dt.convert_time_zone(LOCAL_TZ).dt.date(),
                pl.col("end_utc").dt.convert_time_zone(LOCAL_TZ).dt.date(),
            )
        )
        .explode("local_date")
        .unique()
        .with_columns(program_day=pl.lit(True))
    )
    return (
        weather.join(programs, on="local_date", how="left")
        .with_columns(pl.col("program_day").fill_null(False))
        .collect()
    )


SEASONS = {
    month: season
    for season, months in (
        ("winter", (12, 1, 2)), ("spring", (3, 4, 5)), ("summer", (6, 7, 8)),
        ("autumn", (9, 10, 11)),
    )
    for month in months
}  # fmt: skip
SLICES: dict[str, pl.Expr] = {
    "all": pl.lit("all"),
    "season": pl.col("local_date").dt.month().replace_strict(SEASONS),
    "program_day": pl.col("program_day").cast(pl.String),
    "thunder_day": pl.col("thunder_day").cast(pl.String),
    "snow_day": pl.col("snow_day").cast(pl.String),
    "faa_cap": pl.col("local_date").is_between(*CAP).cast(pl.String),
    "test_month": pl.col("test_month").dt.strftime("%Y-%m"),
}


def evaluate(
    predictions: pl.DataFrame, days: pl.DataFrame, key: str
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Scores per horizon, model and slice (skill against ``REFERENCE``), and the pooled
    reliability bins."""
    reference = predictions.filter(pl.col("model") == REFERENCE).select(
        key, "horizon", "test_month", p_ref="p"
    )
    frame = (
        predictions.join(reference, on=[key, "horizon", "test_month"], how="left")
        .join(days, on="local_date", how="left")
        .with_columns(day=pl.col("local_date").cast(pl.Int64), **SLICES)
    )
    metrics, bins = [], []
    for (horizon, model), group in frame.group_by("horizon", "model", maintain_order=True):
        for name in SLICES:
            for (value,), part in group.group_by(name, maintain_order=True):
                y, p = part[LABEL].to_numpy().astype(float), part["p"].to_numpy()
                bss, low, high = skill(y, p, part["p_ref"].to_numpy(), part["day"].to_numpy())
                metrics.append({"horizon": horizon, "model": model, "slice": name,
                                "value": str(value), **scores(y, p), "bss": bss,
                                "bss_low": low, "bss_high": high})  # fmt: skip
                if name == "all":
                    bins += [{"horizon": horizon, "model": model, "bin": i, "mean_p": mean_p,
                              "observed": rate, "n": n}
                             for i, (mean_p, rate, n) in enumerate(reliability(y, p))]  # fmt: skip
    return pl.DataFrame(metrics), pl.DataFrame(bins)


def _git_commit() -> str | None:
    found = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                           text=True, check=False)  # fmt: skip
    return found.stdout.strip() or None


def run(task_name: str, horizons: list[str], test_months: list[date], root: Path,
        run_name: str | None = None) -> Path:  # fmt: skip
    """Backtest one task and write its outputs; returns the run directory."""
    task = TASKS[task_name]
    began = time.monotonic()
    predictions = predict(task, horizons, test_months, root)
    metrics, bins = evaluate(predictions, day_flags(root / "core"), _key(task))
    name = run_name or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = root / "backtests" / task.name / name
    out.mkdir(parents=True, exist_ok=True)
    predictions.write_parquet(out / "predictions.parquet", compression="zstd")
    metrics.write_parquet(out / "metrics.parquet")
    bins.write_parquet(out / "reliability.parquet")
    (out / "run.json").write_text(json.dumps({
        "task": task.name, "description": task.description, "spine": task.spine,
        "horizons": horizons, "test_months": [m.isoformat() for m in test_months],
        "label_lag_months": LABEL_LAG,
        "excluded_from_training": {"from": f"{EXCLUDED[0]:%Y-%m}", "to": f"{EXCLUDED[1]:%Y-%m}"},
        "reference": REFERENCE, "models": sorted(predictions["model"].unique().to_list()),
        "git_commit": _git_commit(), "seconds": round(time.monotonic() - began, 1),
    }, indent=2) + "\n")  # fmt: skip
    return out


def summary(metrics: pl.DataFrame) -> pl.DataFrame:
    """The pooled scores, one row per horizon and model."""
    pooled = metrics.filter(pl.col("slice") == "all")
    return pooled.select(
        "horizon", "model", pl.col("n").cast(pl.Int64), "base_rate", "brier",
        pl.format("{} [{}, {}]", *(pl.col(c).round(3) for c in ("bss", "bss_low", "bss_high")))
        .alias("bss_95ci"),
        "roc_auc", "ece",
    ).with_columns(pl.col("base_rate", "brier", "roc_auc", "ece").round(3))  # fmt: skip


def _month(text: str) -> date:
    return date.fromisoformat(f"{text}-01")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Rolling-origin backtest of the baselines.")
    parser.add_argument("--task", choices=[*TASKS, "all"], default="all")
    parser.add_argument("--from", dest="first", required=True, help="first test month, YYYY-MM")
    parser.add_argument("--to", dest="last", required=True, help="last test month, YYYY-MM")
    parser.add_argument("--horizons", default=",".join(HORIZONS), help="e.g. 24h,6h,1h")
    parser.add_argument("--run", help="run name (default: a UTC timestamp)")
    args = parser.parse_args(argv)
    months, month = [], _month(args.first)
    while month <= _month(args.last):
        months.append(month)
        month = add_months(month, 1)
    names = list(TASKS) if args.task == "all" else [args.task]
    with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=160, tbl_hide_dataframe_shape=True):
        for name in names:
            out = run(name, args.horizons.split(","), months, data_dir(), args.run)
            print(f"{name}: {TASKS[name].description}\n  -> {out}", flush=True)
            print(summary(pl.read_parquet(out / "metrics.parquet")), flush=True)


if __name__ == "__main__":
    main()
