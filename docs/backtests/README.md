# Backtests

`ordfi.models.backtest` scores probability forecasts on the as-of feature snapshots (`docs/features/`) with the research study's protocol (§6.5, §6.6). The baselines here are the bar every model must beat.

```bash
make backtest FROM=2024-09 TO=2026-08                       # every task; TASK=dep_late15 for one
make backtest TASK=hour_gdp FROM=2024-09 TO=2026-08 HORIZONS=6h,1h NAME=my-run
```

A run writes `data/backtests/<task>/<run>/`:

- `predictions.parquet`: every model's forecast for every scored row;
- `metrics.parquet`: scores per horizon, model and slice;
- `reliability.parquet`: equal-mass reliability bins;
- `run.json`: the settings and the git commit.

## Protocol

- **Rolling origin by month.** Each test month M is forecast by models fitted on every month up to M − 3. BTS publishes a month 6–8 weeks after it ends, so that is what was available at the start of M. The training window expands, and the folds keep whole days together.
- **COVID months** (Mar 2020 – Jun 2021) are left out of training.
- **Skill** is the Brier skill score against the calendar climatology. Its 95 % interval comes from resampling whole local days (200 bootstrap draws), since a day's flights share its weather and programs.
- **Scores:**
  - Brier score and log loss;
  - ROC and precision-recall AUC;
  - expected calibration error over 10 equal-mass bins;
  - the logistic calibration slope and intercept (1 and 0 when calibrated).
- **Slices** (all post hoc, for evaluation only):
  - season;
  - days with a general ORD GDP or ground stop;
  - days with thunder, and days with snow or freezing precipitation;
  - the FAA operations cap (from 2 Jun 2026);
  - each test month.

## Tasks

| Task | Spine | Event | Study target |
|---|---|---|---|
| `dep_late15` | departures | leaves 15+ min late or is cancelled | T2 |
| `dep_late60` | departures | leaves 60+ min late or is cancelled | T2 |
| `dep_cancelled` | departures | cancelled | T5 |
| `hour_bad60` | hours with 10+ departures | 20 %+ of the hour's departures 60+ min late or cancelled | T1 |
| `hour_gdp` | hours | a general GDP in effect during the hour | T1 |
| `hour_ground_stop` | hours | a general ground stop in effect during the hour | T1 |

All rows are scored, cancelled flights included.

## Baselines

All are `Climatology` models. Each is a ladder of nested cells, and each cell's rate is shrunk toward its parent cell by 50 pseudo-rows. A row whose key is unknown keeps the parent's rate: an inbound slack with no tail yet, or no tail in BTS.

| Baseline | Cells | Tasks |
|---|---|---|
| `base_rate` | none | all |
| `calendar` | month, then local hour, then weekday | all (the skill reference) |
| `route` | month and local hour, then carrier, then destination | departures |
| `persistence` | ORD's mean departure delay in the hour before `as_of` (6 buckets) | departures, `hour_bad60` |
| `slack_rule` | the inbound aircraft's known turn slack (no inbound, < 0, 0–14, 15–29, 30–59, ≥ 60 min) | departures |
| `announced` | a GDP (ground stop) in effect at `as_of`, and announced to cover the target | `hour_gdp` (`hour_ground_stop`) |

## First results

Run `baselines-2024-09-to-2026-08`: 24 test months, Sep 2024 – Aug 2026, in 3.3 minutes (about a minute per departure task, 3 s per hourly task). Brier skill against the calendar climatology, pooled; the 95 % interval is shown at 1 h:

| Task (base rate) | Baseline | 24 h | 6 h | 3 h | 1 h | 15 min |
|---|---|---|---|---|---|---|
| `dep_late15` (26.1 %) | `slack_rule` | † | −0.012 | 0.050 | 0.195 [0.185, 0.204] | 0.215 |
| | `persistence` | 0.002 | −0.007 | 0.036 | 0.072 [0.053, 0.091] | 0.085 |
| `dep_late60` (12.2 %) | `slack_rule` | † | −0.003 | 0.047 | 0.237 [0.220, 0.251] | 0.243 |
| | `persistence` | 0.006 | 0.004 | 0.050 | 0.094 [0.069, 0.116] | 0.109 |
| `dep_cancelled` (2.0 %) | `persistence` | 0.008 | 0.009 | 0.036 | 0.062 [0.030, 0.088] | 0.069 |
| `hour_bad60` (14.3 %) | `persistence` | 0.030 | 0.015 | 0.162 | 0.295 [0.251, 0.331] | 0.314 |
| `hour_gdp` (3.9 %) | `announced` | −0.006 | 0.155 | 0.367 | 0.652 [0.586, 0.698] | 0.795 |
| `hour_ground_stop` (3.2 %) | `announced` | −0.017 | −0.014 | 0.011 | 0.106 [0.082, 0.130] | 0.374 |

† No tails are known 24 h out, so the slack rule falls back to the base rate.

**Findings:**

- **The calendar climatology is a real bar.** Its ROC AUC is 0.63 for the departure events and 0.68–0.71 for the hourly ones. The route climatology adds nothing measurable (+0.002 to +0.003).
- **At 24 h nothing beats it.** The v0.1 Outlook targets (study §10.3) are a Brier skill above 0.10 at 24 h and above 0.25 at 6 h. Against them, the best bad-hour baseline scores 0.03 and 0.015, so that skill has to come from forecasts (TAF, and later NBM and LAMP).
- **Short-horizon skill is the airport's and the aircraft's state.** The inbound's known turn slack is the strongest flight-level baseline from 3 h, and ORD's last hour of delays drives the bad-hour outlook. Announced programs predict GDP hours from 6 h out, and ground stops only within the hour.
- **Skill concentrates on disruption days.** For `dep_late15` at 1 h:
  - on days with a GDP or ground stop, the slack rule scores 0.248 and persistence 0.217, against 0.168 and 0.001 on other days;
  - the climatology's calibration error rises to 0.15–0.20 on program, thunder and snow days, because it cannot see the day's state;
  - `hour_bad60` persistence reaches 0.42–0.44 on program, thunder and snow days.
- **The FAA cap months** (Jun – Aug 2026) score like the rest: the slack rule 0.188 against 0.196.

**Caveats:**

- **The slack rule's skill is optimistic.** Its tails are post-hoc (see `docs/features/`).
- **A pooled base rate can show an AUC away from 0.5,** because its rate changes from fold to fold.
- **Calibration slopes are unstable in slices where a forecast barely varies,** e.g. a rule that falls back to the base rate.
