# Backtests

`ordfi.models.backtest` scores probability forecasts on the as-of feature snapshots (`docs/features/`) with the research study's protocol (§6.5, §6.6). The baselines here are the bar every model must beat. The Outlook GBDT is the first model to beat them, hourly and daily.

```bash
make backtest FROM=2024-09 TO=2026-08                       # every task; TASK=dep_late15 for one
make backtest TASK=hour_gdp FROM=2024-09 TO=2026-08 HORIZONS=6h,1h NAME=my-run
make backtest TASK=hour_bad60 FROM=2024-09 TO=2026-08 MODELS=gbdt,persistence   # calendar always runs
make backtest TASK=day_bad60 FROM=2024-09 TO=2026-08 HORIZONS=d1_1900          # daily tasks: issue times
```

A run writes `data/backtests/<task>/<run>/`:

- `predictions.parquet`: every model's forecast for every scored row;
- `metrics.parquet`: scores per horizon, model and slice;
- `reliability.parquet`: equal-mass reliability bins;
- `alerts.parquet` (outlook tasks): the alerts, with each month's threshold set on its track record;
- `run.json`: the settings, the track-record months and the git commit.

## Protocol

- **Rolling origin by month.** Each test month M is forecast by models fitted on every month up to M − 3. BTS publishes a month 6–8 weeks after it ends, so that is what was available at the start of M. The training window expands, and the folds keep whole days together.
- **COVID months** (Mar 2020 – Jun 2021) are left out of training.
- **Skill** is the Brier skill score against the calendar climatology. Its 95 % interval comes from resampling whole local days (200 bootstrap draws), since a day's flights share its weather and programs.
- **Scores:**
  - Brier score and log loss;
  - ROC and precision-recall AUC;
  - the hit rate: the share of events flagged at a false-alarm budget of 10 % of non-events (study §10.3), with the best threshold for the scored rows;
  - expected calibration error over 10 equal-mass bins;
  - the logistic calibration slope and intercept (1 and 0 when calibrated).
- **Slices** (all post hoc, for evaluation only):
  - season;
  - days with a general ORD GDP or ground stop;
  - days with thunder, and days with snow or freezing precipitation;
  - the FAA operations cap (from 2 Jun 2026);
  - each test month.
- **Track record** (outlook tasks). The 14 months before the first test month are forecast too, but not scored. Each test month's alert threshold is set on the forecasts and outcomes of the 12 months that end with the last month BTS has published (below).
- **Workers.** Test months are independent, so their folds run in parallel worker processes (`WORKERS`). The default is one per CPU for the hourly tasks and a single process for the departure tasks, whose fits take seconds and whose rows would be copied to every worker. Results do not depend on the number of workers. Threads are not used: LightGBM keeps its thread count in process-wide state, and boosters trained in concurrent threads crash or corrupt memory.

## Tasks

| Task | Spine | Event | Study target |
|---|---|---|---|
| `dep_late15` | departures | leaves 15+ min late or is cancelled | T2 |
| `dep_late60` | departures | leaves 60+ min late or is cancelled | T2 |
| `dep_cancelled` | departures | cancelled | T5 |
| `hour_bad60` | hours with 10+ departures | 20 %+ of the hour's departures 60+ min late or cancelled | T1 |
| `hour_gdp` | hours | a general GDP in effect during the hour | T1 |
| `hour_ground_stop` | hours | a general ground stop in effect during the hour | T1 |
| `day_bad60` | local days | a bad day: 20 %+ of the day's departures 60+ min late or cancelled (the top decile of 2015 – Aug 2024) | T1 |
| `day_gdp` | local days | a general GDP in effect at some time in the day | T1 |
| `day_ground_stop` | local days | a general ground stop in effect at some time in the day | T1 |

All rows are scored, cancelled flights included.

## Baselines

All are `Climatology` models. Each is a ladder of nested cells, and each cell's rate is shrunk toward its parent cell by 50 pseudo-rows. A row whose key is unknown keeps the parent's rate: an inbound slack with no tail yet, or no tail in BTS.

| Baseline | Cells | Tasks |
|---|---|---|
| `base_rate` | none | all |
| `calendar` | month, then local hour, then weekday (for days: month, then weekday) | all (the skill reference) |
| `route` | month and local hour, then carrier, then destination | departures |
| `persistence` | ORD's mean departure delay in the hour before `as_of` (6 buckets); for days, in the 24 hours before | departures, `hour_bad60`, `day_bad60` |
| `slack_rule` | the inbound aircraft's known turn slack (no inbound, < 0, 0–14, 15–29, 30–59, ≥ 60 min) | departures |
| `announced` | a GDP (ground stop) in effect at `as_of`, and announced to cover the target | `hour_gdp`, `day_gdp` (`hour_ground_stop`, `day_ground_stop`) |

## Baseline results

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

## Outlook GBDT

`ordfi.models.gbdt`: one LightGBM classifier per task and horizon, refit for every test month (study §6.4). It runs on the three hourly tasks (T1); the daily outlook below uses the same model on the days spine.

> **Since the station guidance was added, `gbdt` also reads GFS MOS and NBM (86 hourly and 94 daily features). The GDP and ground-stop models have since added the program climate and the staffing cause (92 and 100).** The results in this section and the next two are for the model before the guidance, which the run `outlook-guidance-…` scores as `gbdt_no_guidance`. The current model's results are under *Station guidance* and *Calibration of GDP and ground-stop days* below.

- **Inputs:** all 59 features of the hours spine (`docs/features/`), as known at `as_of`. Booleans become 0/1 and flight categories their rank (LIFR lowest); missing values stay missing.
- **Number of trees:** the last 12 training months are held out, after a one-day embargo. Early stopping on their log loss picks the number of trees (at most 2,000, patience 100), and the trees are then refit on the whole training window.
- **Recalibration:** a logistic (Platt) map, fitted on the held-out months' forecasts, sets the forecasts' level. Event rates drift: GDPs covered 0.9–1.6 % of hours in 2022–24, against 2.7–7.0 % in 2015–19 and 3.5–6.3 % in 2025–26.
- **Parameters:** learning rate 0.05, 15 leaves, at least 200 rows per leaf, 80 % row and feature sampling, an L2 penalty of 10. Single-threaded, seeded and deterministic.

| Model | Features | Purpose |
|---|---|---|
| `gbdt` | all | the Outlook |
| `gbdt_schedule` | calendar and scheduled demand | the study's schedule-only GBDT baseline (§6.5) |
| `gbdt_no_taf`, `gbdt_no_atc`, `gbdt_no_ops` | all but the TAF, the FAA programs or the in-day operations | each group's value (ablations, §6.5) |

### Settings were frozen on earlier months

The settings were chosen on development test months (Sep 2022 – Aug 2024, same protocol) before the reported months were run. Brier skill against the calendar climatology:

| Task | Horizon | No recalibration | Platt | Isotonic | Platt, 3-year half-life |
|---|---|---|---|---|---|
| `hour_bad60` | 24 h | 0.170 | 0.161 | 0.150 | 0.151 |
| | 6 h | 0.300 | 0.294 | 0.288 | 0.297 |
| `hour_gdp` | 24 h | 0.077 | 0.158 | 0.146 | 0.158 |
| | 6 h | 0.144 | 0.216 | 0.202 | 0.221 |
| `hour_ground_stop` | 24 h | 0.052 | 0.050 | 0.044 | 0.053 |
| | 6 h | 0.091 | 0.088 | 0.085 | 0.079 |

- **Platt recalibration was adopted.** Summed over all 15 task-horizons, it scores 5.005, against 4.852 without recalibration and 4.900 with isotonic regression.
  - It costs bad hours up to 0.009 and ground stops up to 0.004.
  - It gains GDP hours 0.07–0.08 at 24 h and 6 h, where the training years' GDP rate was too high.
  - It also cuts the GDP calibration error at 24 h from 0.013 to 0.002.
- **Recency weighting was not adopted** (rows weighted by a 3-year half-life). It helps GDP hours and hurts bad hours, for a net 0.013 over the 15 cases.
- **Tree size was not changed.** Larger trees (31 leaves, 100 rows per leaf) and smaller ones (7 leaves, 400 rows) were tested at 24 h and 6 h. The defaults were best or tied in five of six cases, and the exception gained 0.002.

### Results

Run `outlook-gbdt-2024-09-to-2026-08`: the baselines' 24 test months, about 2.5 minutes per task on 12 workers. Brier skill against the calendar climatology, pooled, with the 95 % interval at 24 h and 6 h, beside each task's best baseline:

| Task (base rate) | Model | 24 h | 6 h | 3 h | 1 h | 15 min |
|---|---|---|---|---|---|---|
| `hour_bad60` (14.3 %) | `gbdt` | 0.249 [0.205, 0.284] | 0.431 [0.372, 0.477] | 0.523 | 0.580 | 0.621 |
| | `persistence` | 0.030 | 0.015 | 0.162 | 0.295 | 0.314 |
| `hour_gdp` (3.9 %) | `gbdt` | 0.141 [0.094, 0.183] | 0.292 [0.227, 0.341] | 0.505 | 0.735 | 0.836 |
| | `announced` | −0.006 | 0.155 | 0.367 | 0.652 | 0.795 |
| `hour_ground_stop` (3.2 %) | `gbdt` | 0.089 [0.060, 0.117] | 0.146 [0.107, 0.185] | 0.153 | 0.234 | 0.434 |
| | `announced` | −0.017 | −0.014 | 0.011 | 0.106 | 0.374 |

**Findings:**

- **The v0.1 Outlook targets are met for bad hours.** The targets (study §10.3) are a Brier skill above 0.10 at 24 h and above 0.25 at 6 h, with a calibration error of at most 0.03.
  - Bad hours score 0.249 and 0.431, with calibration errors of 0.012 and 0.009.
  - GDP hours reach 0.141 and 0.292, though their intervals dip below the targets.
  - Ground-stop hours fall short, at 0.089 and 0.146.
- **The GBDT beats every baseline at every horizon.** At 24 h and 6 h, its interval lies above the best baseline's skill.
- **It stays calibrated.** The calibration error is at most 0.012 at every horizon, and the calibration slopes are 0.90–1.02.
- **The skill is broad, not a few storms.**
  - Bad hours: positive in 21 of 24 test months at 24 h (median 0.18), and in all 24 at 6 h (median 0.39).
  - GDP hours: positive in 22 of 24 months at both horizons.
- **By regime**, for bad hours at 24 h:
  - program days 0.351, other days 0.102;
  - thunder days 0.341, against 0.195;
  - snow days 0.317, against 0.220;
  - FAA cap months 0.243, against 0.251 (0.371 against 0.445 at 6 h).
- **Calibration on disruption days.** The GBDT's calibration error on program, thunder and snow days is 0.11–0.19 at 24 h, against the climatology's 0.21–0.32. Those days are picked after the fact, which no forecast can know.

### Where the skill comes from

Brier skill without each feature group (change from `gbdt` in brackets):

| Task | Horizon | `gbdt` | `gbdt_schedule` | Without TAF | Without programs | Without operations |
|---|---|---|---|---|---|---|
| `hour_bad60` | 24 h | 0.249 | 0.016 | 0.133 (−0.117) | 0.252 (+0.003) | 0.218 (−0.032) |
| | 6 h | 0.431 | 0.016 | 0.363 (−0.068) | 0.406 (−0.024) | 0.365 (−0.066) |
| | 1 h | 0.580 | 0.016 | 0.569 (−0.011) | 0.567 (−0.014) | 0.431 (−0.150) |
| `hour_gdp` | 24 h | 0.141 | 0.008 | 0.022 (−0.119) | 0.143 (+0.002) | 0.141 (−0.000) |
| | 6 h | 0.292 | 0.008 | 0.214 (−0.078) | 0.222 (−0.070) | 0.290 (−0.001) |
| | 1 h | 0.735 | 0.008 | 0.725 (−0.010) | 0.431 (−0.304) | 0.729 (−0.007) |
| `hour_ground_stop` | 24 h | 0.089 | 0.004 | 0.006 (−0.082) | 0.087 (−0.002) | 0.092 (+0.003) |
| | 6 h | 0.146 | 0.004 | 0.051 (−0.095) | 0.136 (−0.010) | 0.147 (+0.001) |
| | 1 h | 0.234 | 0.004 | 0.207 (−0.027) | 0.195 (−0.039) | 0.234 (−0.000) |

- **At 24 h the skill is mostly the TAF's.** Without it, the GDP and ground-stop skill nearly vanishes (0.022 and 0.006). Bad hours keep 0.133, from the weather and the airport's state a day earlier, as the literature found (study §6.1).
- **A better calendar adds little.** The schedule-only GBDT scores 0.004–0.016, so the skill comes from forecasts and the airport's state.
- **FAA programs count from 6 h** for GDP hours (−0.070 without them), and an announced GDP decides the hour at 1 h (−0.304).
- **In-day operations carry the short-range bad-hour skill:** −0.150 at 1 h and −0.066 at 6 h.
- **The strongest inputs** (mean absolute SHAP contribution) of the final fold's 24 h bad-hour model are:
  - the temperature at `as_of`, a proxy for the air mass (convective afternoons, snow);
  - the share of departures late in the three hours before `as_of`, i.e. the same time the day before;
  - the TAF's ceiling, thunder and wind.

**Caveats:**

- **The development months were calmer, and skill was lower there.** Their base rates were 10.3 % for bad hours, 1.3 % for GDP hours and 2.1 % for ground-stop hours. With Platt recalibration, the skill at 24 h and 6 h was:
  - bad hours: 0.161 and 0.294;
  - GDP hours: 0.158 and 0.216;
  - ground-stop hours: 0.050 and 0.088.

  Expect skill to move with each season's weather.
- **The FAA cap regime is not in any training window yet.** It began on 2 Jun 2026, and a test month trains on months up to three months before it, so even August 2026 trains on months up to May.
- **In-day operations assume each departure and arrival is known when it happens** (`docs/features/`). The live archive will measure the real lag.
- **There is no daily outlook yet.** The study's decision criterion is to flag at least 60 % of the top-decile bad days 24 h ahead, at no more than 1 false alarm per 10 normal days. Measuring it needs a daily spine with a fixed issue time.

## Daily outlook

The same GBDT on the days spine (`docs/features/`): one forecast per local day at each of five issue times, from 19:00 three days before to 05:00 on the day. A bad day uses the hourly cut (20 %+ of the day's departures 60+ min late or cancelled), which marks the top decile of days in 2015 – Aug 2024.

### Settings were frozen on earlier months

As for hours, the settings were chosen on the development months (Sep 2022 – Aug 2024) before the reported run. There are about 3,000 training days per fold, and a 12-month hold-out leaves about 30 bad days to stop and recalibrate on, so the daily models hold out 24 months. Brier skill on the development months:

| Task | Issue | Hourly settings (12 months) | 24 held-out months | Leaves of 50 rows | No recalibration |
|---|---|---|---|---|---|
| `day_bad60` | `d1_0700` | 0.096 | 0.091 | 0.099 | 0.105 |
| | `d1_1900` | 0.189 | 0.207 | 0.170 | 0.223 |
| | `d0_0500` | 0.173 | 0.221 | 0.167 | 0.223 |
| `day_gdp` | `d1_0700` | 0.111 | 0.112 | 0.102 | 0.065 |
| | `d1_1900` | 0.221 | 0.246 | 0.215 | 0.181 |
| | `d0_0500` | 0.275 | 0.274 | 0.292 | 0.225 |
| `day_ground_stop` | `d1_0700` | 0.089 | 0.089 | 0.107 | 0.084 |
| | `d1_1900` | 0.208 | 0.217 | 0.218 | 0.199 |
| | `d0_0500` | 0.239 | 0.244 | 0.243 | 0.242 |

Summed over all 15 task-issues, 24 held-out months score 1.981, against:

- 1.824 with the hourly settings;
- 1.843 with leaves of 50 rows;
- 1.769 without recalibration, whose GDP calibration error reaches 0.05.

### Results

Run `daily-outlook-2024-09-to-2026-08`: the same 24 test months (730 days), 2 minutes for the three tasks. Brier skill against the month-and-weekday climatology, with the 95 % interval for the two issues on the day before:

| Task (base rate) | Model | `d3_1900` | `d2_1900` | `d1_0700` | `d1_1900` | `d0_0500` |
|---|---|---|---|---|---|---|
| `day_bad60` (13.7 %) | `gbdt` | 0.036 | 0.046 | 0.208 [0.125, 0.280] | 0.354 [0.278, 0.415] | 0.419 |
| | `persistence` | 0.017 | 0.025 | 0.021 | 0.056 | 0.089 |
| `day_gdp` (14.4 %) | `gbdt` | 0.023 | 0.024 | 0.131 [0.084, 0.174] | 0.249 [0.171, 0.300] | 0.305 |
| | `announced` | −0.002 | 0.000 | −0.007 | 0.028 | 0.072 |
| `day_ground_stop` (18.8 %) | `gbdt` | 0.015 | 0.028 | 0.164 [0.105, 0.215] | 0.266 [0.199, 0.332] | 0.302 |
| | `announced` | −0.022 | −0.024 | −0.024 | −0.009 | 0.002 |

**Findings:**

- **The skill starts the day before.**
  - At the evening-before issue (`d1_1900`, after the 00Z TAF), bad days score 0.354, against 0.056 for persistence. Their ROC AUC is 0.915.
  - The morning before (`d1_0700`, with the TAF only to noon), they score 0.208.
  - Two and three days ahead, with no TAF, skill falls to 0.036–0.046, little above the previous day's state.
- **The GBDT beats every baseline from the morning before.** On both day-before issues, its interval lies above each task's best baseline.
- **The skill is broad.** At `d1_1900` it is positive in:
  - 22 of 24 months for bad and GDP days, and 20 of 24 for ground stops;
  - every season, from 0.224 in summer to 0.521 in autumn for bad days;
  - the FAA cap months (0.271).
- **The TAF is the daily outlook.** Without it, bad days at `d1_1900` fall from 0.354 to 0.109, and GDP and ground-stop days lose 0.20–0.23. The previous day's operations add 0.02–0.05 for bad days. Programs announced by the issue time add nothing.
- **Calibration:**
  - Bad days are within the 0.03 target from the morning before (0.021–0.025).
  - GDP and ground-stop days are not (0.031–0.052). They covered 14 % and 19 % of days in the reported months, against 7 % and 15 % in the development months, so the forecasts run low (10 % on average for GDP days).

### The bad-day criterion

The study's decision criterion (§10.3) is to flag at least 60 % of bad days 24 h ahead, at no more than 1 false alarm per 10 normal days. The share of bad days flagged:

| Issue | Best threshold for the reported months, at ≤ 1 false alarm per 10 | Threshold fixed on the development months |
|---|---|---|
| `d1_0700` (07:00 the day before) | 55 % | 76 %, at 2.0 false alarms per 10 (p ≥ 0.137) |
| `d1_1900` (19:00 the evening before) | 71 % | 72 %, at 1.05 per 10 (p ≥ 0.221) |
| `d0_0500` (05:00 on the day) | 80 % | 85 %, at 1.4 per 10 (p ≥ 0.142) |

- **Met the evening before.** The best threshold flags 71 % of bad days at 1 false alarm per 10 normal days. A threshold fixed beforehand on the development months flags 72 % at 1.05 per 10, and half its flags are right.
- **Not met at least 24 h ahead of the day's flights.** The morning before, when the TAF reaches only noon, the best threshold flags 55 %. The development months' threshold flags 76 %, but at twice the false alarms: the reported months were stormier, and the forecasts higher.

**Caveats:**

- **Best-threshold hit rates are points on the ROC curve.** A live alert must fix its threshold beforehand, as in the right column.
- **A threshold fixed on calmer months flags more in stormier ones.** Resetting it each month on the track record is measured below.
- **The three daily events overlap.** A GDP day is often a bad day, so they are not independent evidence.
- **Two and three days ahead need forecasts beyond the TAF's 30 hours** (NBM).

## Alerts and recalibration from the track record

Live, the outlook's forecasts are checked against their outcomes once BTS publishes each month. `ordfi.models.recent` uses that track record. At the start of each test month M, the record is the forecasts and outcomes of the 12 months ending with M − 3, the last month BTS has published. Every record forecast was out of sample when it was made.

- **The alert threshold** is the lowest forecast that would have flagged at most 10 % of the record's normal days (or hours), the study's false-alarm budget. It is reset every month, without seeing the test month.
- **Recalibration** (`gbdt_recent`, scored but not adopted): the GBDT's forecasts shifted on the logit scale, so that over the record their mean matches the observed rate.

### Settings were frozen on earlier months

Both were compared on the development months (Sep 2022 – Aug 2024), with forecasts from Jul 2021 to build the record. False alarms realized by the GBDT's alerts, over the 30 outlook task-horizons:

| Track record | False alarms (range) | Mean | Task-horizons over 11 % |
|---|---|---|---|
| 6 months | 9.0 – 23.8 % | 12.4 % | 21 of 30 |
| **12 months** | **6.4 – 11.8 %** | **9.3 %** | **3 of 30** |

Brier skill summed over the task-horizons, and the mean calibration error:

| Forecasts | Hourly skill | Hourly calibration error | Daily skill | Daily calibration error |
|---|---|---|---|---|
| **GBDT as is** | **5.005** | **0.0028** | **1.981** | 0.0285 |
| shifted on 6 months | 4.914 | 0.0033 | 1.856 | 0.0271 |
| shifted on 12 months | 4.924 | 0.0035 | 1.822 | 0.0272 |
| Platt on 6 months | 4.814 | 0.0047 | 1.357 | 0.0305 |
| Platt on 12 months | 4.873 | 0.0041 | 1.769 | 0.0287 |

- **Alerts use a 12-month record.** Six months give too few normal days for a stable cut: false alarms ran up to 23.8 %, worst two and three days ahead, where skill is low.
- **Recalibration was not adopted.** Every variant lost skill, hourly and daily. In these months, the level errors seen three or more months back did not persist, so correcting them added noise. The 12-month shift is still scored, as `gbdt_recent`.

### Results

Run `outlook-track-record-2024-09-to-2026-08`, the six outlook tasks on the same 24 test months (with forecasts from Jul 2023 for the record), in 13 minutes. The original models' scores are identical to their earlier runs. The GBDT's alerts, each month's threshold set on its record:

| Task | Horizon | Events | Caught | False alarms per 10 | Flags right | Best threshold (≤ 1 per 10) |
|---|---|---|---|---|---|---|
| `hour_bad60` | 24 h | 1,780 | 66 % | 1.22 | 47 % | 61 % |
| | 6 h | 1,780 | 81 % | 1.18 | 53 % | 79 % |
| `hour_gdp` | 24 h | 679 | 71 % | 1.55 | 16 % | 63 % |
| | 6 h | 679 | 85 % | 1.46 | 19 % | 80 % |
| `hour_ground_stop` | 24 h | 553 | 59 % | 1.23 | 14 % | 55 % |
| | 6 h | 553 | 72 % | 1.16 | 17 % | 69 % |
| `day_bad60` | `d1_0700` | 100 | 71 % | 1.67 | 40 % | 55 % |
| | `d1_1900` | 100 | 77 % | 1.19 | 51 % | 71 % |
| | `d0_0500` | 100 | 86 % | 1.37 | 50 % | 80 % |
| `day_gdp` | `d1_0700` | 105 | 58 % | 1.62 | 38 % | 44 % |
| | `d1_1900` | 105 | 70 % | 1.34 | 46 % | 59 % |
| | `d0_0500` | 105 | 69 % | 1.12 | 51 % | 66 % |
| `day_ground_stop` | `d1_0700` | 137 | 47 % | 1.06 | 50 % | 45 % |
| | `d1_1900` | 137 | 60 % | 1.10 | 56 % | 58 % |
| | `d0_0500` | 137 | 63 % | 0.89 | 62 % | 66 % |

**Findings:**

- **The alerts overshoot their budget when disruption rises.**
  - False alarms ran 8.9 – 27.5 % over the 30 task-horizons (mean 13.7 %).
  - Without the two- and three-day issues, they ran 8.9 – 16.7 % (mean 12.7 %).
  - The reported months were stormier than the year before each of them, so a threshold set on last year's normal days flags more of this year's. On the calmer development months, the same rule landed at 9.3 %.
  - The alerts also catch more events than the best threshold at exactly 1 in 10.
- **The bad-day criterion, with a rule fixed beforehand:**
  - The evening before, the alert catches 77 % of bad days at 1.19 false alarms per 10 normal days, and half its flags are right. That is above 60 %, but over the budget by a fifth.
  - The morning before, it catches 71 % at 1.67.
- **Recalibration fixes the level but not the score.**
  - In the reported months, `gbdt_recent` lowers the calibration error: daily from 0.040 to 0.035 on average, and for GDP days the evening before from 0.043 to 0.025, its mean forecast 14.5 % against 14.4 % observed.
  - It still loses Brier skill (0.08 summed, both hourly and daily), as on the development months. It stays an alternative, not the default.

**Caveats:**

- **The rule needs a year of forecasts with published outcomes before its first alert.** Live, the outlook must run (or be backfilled) for 14 months first.
- **With the lag, a trend always leads the threshold.** The record ends three months before the alert, and disruption at ORD has risen since 2023. Targeting the budget with a margin, or a threshold set on the latest forecasts' own expected false alarms (which needs no outcomes), are the next candidates. Both must be chosen on the development months.
- **A month's threshold is one number for all its hours or days.** A seasonal threshold would need several years of record.

## Station guidance (GFS MOS and NBM)

The outlook GBDT reads the `mos_` and `nbm_` features (`docs/features/`): GFS MOS from 2014-12 and NBM from 2018-11, for the target hour or day, from the latest run known at `as_of`. They are the only forecast weather beyond the TAF's 30 hours. In the run below, `gbdt_no_guidance` is the model without them, which is the model of the sections above.

### Adopted on the development months

On the development months (Sep 2022 – Aug 2024), the guidance added skill almost everywhere. Summed over the task-horizons:

- hourly, from 5.005 to 5.294;
- daily, from 1.981 to 3.004.

| Daily task | `d3_1900` | `d2_1900` | `d1_0700` | `d1_1900` | `d0_0500` |
|---|---|---|---|---|---|
| `day_bad60` | 0.027 → 0.139 | 0.033 → 0.170 | 0.091 → 0.173 | 0.207 → 0.235 | 0.221 → 0.248 |
| `day_gdp` | 0.102 → 0.137 | 0.083 → 0.171 | 0.112 → 0.164 | 0.246 → 0.274 | 0.274 → 0.270 |
| `day_ground_stop` | 0.003 → 0.124 | 0.031 → 0.189 | 0.089 → 0.208 | 0.217 → 0.241 | 0.244 → 0.263 |

Hourly, the gains were 0.01–0.06 at 24 h and 6 h for every task, and ground stops gained at every horizon. Calibration errors stayed near the targets (at most 0.032).

### Results

Run `outlook-guidance-2024-09-to-2026-08`: the six outlook tasks on the same 24 test months, with every model and the track-record alerts, in 18 minutes. Brier skill against the calendar climatology, with the 95 % interval:

| Task (base rate) | Horizon | With guidance | Without | Gain |
|---|---|---|---|---|
| `hour_bad60` (14.3 %) | 24 h | 0.297 [0.244, 0.341] | 0.249 | +0.047 |
| | 6 h | 0.445 [0.381, 0.493] | 0.431 | +0.014 |
| `hour_gdp` (3.9 %) | 24 h | 0.177 [0.122, 0.220] | 0.141 | +0.036 |
| | 6 h | 0.321 [0.243, 0.374] | 0.292 | +0.030 |
| `hour_ground_stop` (3.2 %) | 24 h | 0.135 [0.097, 0.167] | 0.089 | +0.046 |
| | 6 h | 0.165 [0.126, 0.206] | 0.146 | +0.020 |
| `day_bad60` (13.7 %) | `d3_1900` | 0.229 [0.159, 0.284] | 0.036 | +0.193 |
| | `d2_1900` | 0.250 [0.186, 0.305] | 0.046 | +0.204 |
| | `d1_0700` | 0.293 [0.216, 0.355] | 0.208 | +0.085 |
| | `d1_1900` | 0.341 [0.262, 0.405] | 0.354 | −0.014 |
| | `d0_0500` | 0.430 [0.342, 0.498] | 0.419 | +0.011 |
| `day_gdp` (14.4 %) | `d3_1900` | 0.149 [0.103, 0.199] | 0.023 | +0.126 |
| | `d2_1900` | 0.212 [0.148, 0.269] | 0.024 | +0.188 |
| | `d1_0700` | 0.217 [0.156, 0.272] | 0.131 | +0.086 |
| | `d1_1900` | 0.264 [0.196, 0.324] | 0.249 | +0.015 |
| | `d0_0500` | 0.289 [0.213, 0.360] | 0.305 | −0.016 |
| `day_ground_stop` (18.8 %) | `d3_1900` | 0.174 [0.121, 0.239] | 0.015 | +0.159 |
| | `d2_1900` | 0.217 [0.162, 0.282] | 0.028 | +0.189 |
| | `d1_0700` | 0.238 [0.181, 0.296] | 0.164 | +0.074 |
| | `d1_1900` | 0.302 [0.237, 0.371] | 0.266 | +0.036 |
| | `d0_0500` | 0.324 [0.256, 0.392] | 0.302 | +0.022 |

**Findings:**

- **Two and three days ahead, the guidance is the outlook.**
  - Bad days score 0.250 and 0.229, up from 0.046 and 0.036.
  - GDP and ground-stop days gain 0.13–0.19.
  - Without the guidance, those issues barely beat the calendar.
- **The morning before gains most among the day-before issues.** That is when the TAF reaches only noon: bad days go from 0.208 to 0.293.
- **The evening before and on the day, the TAF already covers the day.** The guidance changes skill by 0.01–0.04, within the intervals.
- **Hourly, the gains are mostly at 24 h and 6 h** (+0.014 to +0.047). Within 3 hours they shrink to 0.00–0.02, as the in-day state takes over.
- **The TAF and the guidance overlap.** Hourly at 24 h, bad hours lose nothing without the TAF (0.301) once the guidance is in, and the guidance is worth 0.047 without it. The evening before, the TAF still adds 0.03 for bad days.
- **The v0.1 Outlook targets** (above 0.10 at 24 h and 0.25 at 6 h, calibration error at most 0.03):
  - Bad hours meet them (0.297 and 0.445).
  - GDP hours meet them (0.177 and 0.321), and the 24 h interval now clears 0.10.
  - Ground-stop hours reach the 24 h target (0.135) but not the 6 h one (0.165).
  - Hourly calibration errors are at most 0.014.
- **The bad-day criterion two days ahead,** with each month's alert threshold set on its track record:
  - The alert catches 59 % of bad days at 0.97 false alarms per 10 normal days, and half its flags are right (49 %).
  - That is within the false-alarm budget and one point short of 60 %, by a forecast issued at least 24 h before every one of the day's flights. Without the guidance, the same alert caught 21 %.
  - The morning before, it catches 75 % at 1.22 false alarms per 10 (71 % at 1.67 without the guidance). The evening before, 77 % at 1.14.

**Caveats:**

- **NBM is short.** It starts in 2018-11 and its IFR probabilities in 2020-09, so the early training years have only GFS MOS.
- **NBM changed versions often** (v4.0 2020-09 to v5.0 2026-05), and the model cannot see which version a row came from.
- **The knowledge times are the catalog cards' estimates,** not measured on IEM's feed: the GFS MOS run + 5 h (conservative) and the NBM cycle + 70 min.
- **Three days ahead, GFS MOS reaches only about midday** of the target day.
- **Daily GDP and ground-stop days are still miscalibrated** (errors 0.035–0.057): they doubled in the reported months against the years the models learned from. The next section looks into why.

## Calibration of GDP and ground-stop days

In the reported months, the daily GDP and ground-stop forecasts ran low. The evening before, the GBDT forecast a GDP on 9.6 % of days on average, and 14.4 % of days had one. Calibration errors were 0.035–0.057, against the 0.03 target. This section finds why, tests three fixes on two development windows, and adopts one: the recent program climate.

### Why they ran low

- **ORD's programs came back.**
  - GDP days were 12–22 % of days in 2015–19 and 5–8 % in 2022–24, then 13 % in 2025 and 22 % in 2026 so far.
  - Ground-stop days moved the same way, by less: 15 % in 2022–24, 18 % in 2025 and 24 % in 2026.
- **The models' level came from the calm years.** The daily models' Platt recalibration sets their level on the 24 held-out months before the training cut. For the reported months, 73 % of those months fell in 2022–24.
- **Programs for staffing were new.**
  - From 2015 to 2024 there were three: two GDPs and a ground stop, all in 2023.
  - 2025 had 12 GDPs and 11 ground stops for staffing, and 2026 so far 11 and 12.
  - In October 2025 (the federal shutdown), six of the month's seven GDPs cited staffing. The evening before, the forecast averaged 3 % against 23 % of days.

### Three fixes, on two development windows

The development months used so far (Sep 2022 – Aug 2024) had fewer programs than the years before them: GDPs on 6.6 % of days, against 10.5 % from Jul 2021 to Aug 2022. A fix for a rising rate must also be tried where the rate rose, so a second window was added: Sep 2018 – Feb 2020, with GDPs on 19.4 % of days against 14.7 % in 2015 – Aug 2018. The rule was fixed before the runs: adopt a fix if, over the four GDP and ground-stop tasks (20 task-horizons), the mean calibration error falls and the summed Brier skill does not, in both windows.

1. **The recent program climate.** Four features: the local days among the last 7 and 30 with a GDP, and with a ground stop, from the advisories known at `as_of` (`docs/features/`). Advisories are known as they are sent, so the counts follow a change in how often programs run within days.
2. **Training up to the month before** (a label lag of 0 instead of 2). The GDP and ground-stop labels come from the advisories, which are known the same day, not from BTS. Live, the in-day operations of those months would come from the live feed.
3. **A shift to a recent track record.** The forecasts are shifted on the logit scale to the level of the last 3, 6 or 12 months, with the record ending the month before. The 12-month record ending with M − 3 is `gbdt_recent`. The shifts were applied to the model with the climate.

| Fix | Skill, Sep 2018 – Feb 2020 | Calibration error | Skill, Sep 2022 – Aug 2024 | Calibration error |
|---|---|---|---|---|
| None (the guidance model) | 5.275 | 0.02737 | 5.400 | 0.01234 |
| **The program climate** | **5.316** | **0.02723** | **5.408** | **0.01228** |
| Training to the month before | 5.385 | 0.02825 | 5.238 | 0.01195 |
| Both | 5.419 | 0.02635 | 5.209 | 0.01185 |
| Climate, shifted on 3 months | 5.497 | 0.02675 | 4.778 | 0.01598 |
| Climate, shifted on 6 months | 5.389 | 0.03027 | 5.149 | 0.01303 |
| Climate, shifted on 12 months | 5.056 | 0.03587 | 5.157 | 0.01401 |
| Climate, `gbdt_recent` (12 months to M − 3) | 4.751 | 0.03746 | 5.157 | 0.01336 |

- **The program climate passed, narrowly.**
  - It gained 0.041 and 0.008 in skill, and lowered the calibration error by 0.00015 and 0.00006.
  - Most of the gain was hourly. The daily calibration error barely moved (0.04737 → 0.04739 and 0.02324 → 0.02317).
- **The bad-delay events leave it out.** On the same windows, the climate cost `hour_bad60` and `day_bad60` 0.013 in summed skill in 2018–20 and nothing in 2022–24, and raised their calibration error in both.
- **Training to the month before was rejected.** With the climate, it lowered the calibration error in both windows and gained 0.10 in skill in 2018–20, but lost 0.20 in 2022–24.
- **No shift was adopted.**
  - The 3-month shift was the best fix in 2018–20 (+0.18) and the worst in 2022–24 (−0.63).
  - The 6-month shift gained skill in 2018–20 but raised its calibration error. The 12-month shifts lost skill in both.

### Results

Run `outlook-climate-2024-09-to-2026-08`: the four GDP and ground-stop tasks on the same 24 test months, with every model and the track-record alerts, in 14 minutes. `gbdt_no_climate` reproduces the guidance run's GBDT exactly. The bad-delay models did not change (their forecasts match the guidance run's), so their results are still those of `outlook-guidance-…`. Brier skill against the calendar climatology, with the 95 % interval:

| Task (base rate) | Horizon | With the climate | Without | Gain | Calibration error (with / without) | Mean forecast (with / without) |
|---|---|---|---|---|---|---|
| `hour_gdp` (3.9 %) | 24 h | 0.186 [0.115, 0.242] | 0.177 | +0.008 | 0.008 / 0.011 | 3.1 % / 2.7 % |
| | 6 h | 0.324 [0.238, 0.383] | 0.321 | +0.002 | 0.005 / 0.007 | 3.5 % / 3.2 % |
| `hour_ground_stop` (3.2 %) | 24 h | 0.132 [0.092, 0.164] | 0.135 | −0.003 | 0.005 / 0.006 | 2.7 % / 2.6 % |
| | 6 h | 0.167 [0.125, 0.208] | 0.165 | +0.002 | 0.004 / 0.005 | 2.8 % / 2.7 % |
| `day_gdp` (14.4 %) | `d3_1900` | 0.158 [0.111, 0.208] | 0.149 | +0.009 | 0.048 / 0.055 | 9.6 % / 9.0 % |
| | `d2_1900` | 0.227 [0.163, 0.286] | 0.212 | +0.015 | 0.047 / 0.054 | 9.7 % / 9.3 % |
| | `d1_0700` | 0.235 [0.175, 0.289] | 0.217 | +0.017 | 0.050 / 0.055 | 9.4 % / 8.9 % |
| | `d1_1900` | 0.276 [0.207, 0.336] | 0.264 | +0.012 | 0.049 / 0.050 | 9.6 % / 9.6 % |
| | `d0_0500` | 0.310 [0.236, 0.375] | 0.289 | +0.021 | 0.054 / 0.056 | 9.5 % / 9.0 % |
| `day_ground_stop` (18.8 %) | `d3_1900` | 0.172 [0.119, 0.233] | 0.174 | −0.002 | 0.037 / 0.035 | 15.5 % / 15.6 % |
| | `d2_1900` | 0.211 [0.158, 0.276] | 0.217 | −0.006 | 0.043 / 0.036 | 15.3 % / 15.7 % |
| | `d1_0700` | 0.245 [0.184, 0.302] | 0.238 | +0.007 | 0.039 / 0.043 | 15.4 % / 15.2 % |
| | `d1_1900` | 0.307 [0.243, 0.373] | 0.302 | +0.005 | 0.050 / 0.057 | 15.7 % / 15.9 % |
| | `d0_0500` | 0.329 [0.260, 0.395] | 0.324 | +0.005 | 0.041 / 0.040 | 15.8 % / 15.8 % |

**Findings:**

- **GDPs gain, and their calibration improves.**
  - GDP days gain 0.009–0.021 at every issue, and their calibration error falls to 0.047–0.054 (from 0.050–0.056).
  - GDP hours gain at every horizon but 15 min (−0.0001), and their calibration improves at all five. At 24 h they reach 0.186, with a calibration error of 0.008 (from 0.011).
- **Ground stops are mixed.**
  - Their skill moves by −0.006 to +0.007, within the intervals.
  - Daily calibration improves the day before (0.050 from 0.057 the evening before), but not two and three days ahead or on the day.
- **The cost falls on quiet days in busy spells.**
  - On days with no program at all, hourly skill at 24 h falls from 0.286 to −0.003 for GDPs and from 0.046 to −0.098 for ground stops. At 6 h, ground stops fall from 0.045 to −0.021.
  - Those days' Brier score is tiny (0.001–0.002), so a small lift in their forecasts turns their skill negative: for GDPs at 24 h, the mean forecast goes from 1.35 % to 1.55 %.
  - For GDP hours, the program days gain more than the quiet days lose. For ground-stop hours at 24 h they do not, which is why that horizon slips to 0.132.
- **The rule would have adopted the climate on these months too.** Over the 20 task-horizons, summed skill is 6.235 against 6.126 without it, and the mean calibration error 0.0248 against 0.0263.
- **The daily level is still low.**
  - GDP days are forecast at 9.5 % on average against 14.4 %, and ground-stop days at 15.5 % against 18.8 %.
  - Calibration errors stay at 0.037–0.054, above the 0.03 target.
- **Staffing programs account for about half of the shortfall.**
  - The evening before, days with a staffing program hold 50 % of the GDP days' shortfall (events less forecasts) and 53 % of the ground-stop days'.
  - The 19 days whose GDPs all cited staffing were forecast at 17 % on average, against 32 % for the 82 GDP days without staffing.
  - Ground-stop days for staffing alone were forecast at 25 %, those without staffing at 39 %.
  - In October and November 2025, GDPs ran on 23 % and 30 % of days, against forecasts of 3 % and 7 %.
- **The rest of the shortfall is the stormier months.** In March and April 2026, GDPs ran on 35 % and 30 % of days, against forecasts of 15 % and 21 %. Ground stops were over-forecast in July 2026 (13 % against 26 %).
- **The rejected shift would have done better on the daily level here.**
  - `gbdt_recent` brings the daily calibration errors to 0.025–0.042 for GDP days and 0.028–0.037 for ground-stop days, at skill within 0.015 of the GBDT's.
  - It still loses 0.017–0.021 for GDP hours at 24 h and 6 h, and 0.08 in skill summed over the 20 task-horizons (6.155).
  - Adopting it now would mean choosing on the test months.
- **Alerts change little.** Catches move by −3 to +4 points and false alarms by −0.08 to +0.11 per 10 normal days or hours. The largest change is GDP hours at 24 h: 82 % caught at 1.63 false alarms per 10, from 78 % at 1.52.

**Caveats:**

- **Daily GDP and ground-stop calibration is still above the target.** The weather cannot forecast a staffing program, and before 2025 the models had almost none to learn from.
- **The training windows will catch up.** Models fitted from November 2026 on learn from the 38 staffing programs of January 2025 – August 2026. Whether that is enough is for the monitoring to show.
- **The next candidates,** each to be chosen on both development windows:
  - the advisories' stated cause as a feature, such as the days among the last 7 and 30 with a staffing program (tried next, below);
  - a shift that waits for evidence, such as one shrunk by the record's size or triggered by a run of misses.

### The staffing cause

The first candidate: `atc_staffing_days_7d` and `atc_staffing_days_30d`, the days among the last 7 and 30 with a GDP or ground stop whose advisories had cited staffing, as known at `as_of` (`docs/features/`).

- **A program's cause can change between its advisories.** Of the 59 ORD programs that cited staffing (2023–26), 10 were first issued for weather or another cause and extended for staffing.
- So each program version keeps the cause its own advisory states, and a program counts from the first advisory that cited staffing.
- Only the GDP and ground-stop models read them: 92 hourly and 100 daily features.

**The development windows cannot test it.**

- They hold three staffing programs, all in Aug–Sep 2023, and none at all in 2018–20.
- So the rule fixed beforehand was that it must do no harm there. It is adopted unless, in either window, summed skill over the 20 task-horizons falls by more than 0.01 or the mean calibration error rises by more than 0.0005.
- The reported months were then its first real test, with no other variant tried on them.

| Window | Change in summed skill | Change in calibration error |
|---|---|---|
| Sep 2018 – Feb 2020 | 0 (identical: the counts are all zero) | 0 |
| Sep 2022 – Aug 2024 | −0.007 (hourly models only) | −0.00001 |

It passed and was adopted. In both windows `gbdt_no_staffing` reproduces the program-climate model exactly.

#### Results

Run `outlook-staffing-2024-09-to-2026-08`: the four GDP and ground-stop tasks on the same 24 test months, in 15 minutes. `gbdt_no_staffing` reproduces the climate run's GBDT exactly.

| Task (base rate) | Horizon | With the staffing cause | Without | Gain | Calibration error (with / without) | Mean forecast (with / without) |
|---|---|---|---|---|---|---|
| `hour_gdp` (3.9 %) | 24 h | 0.187 [0.116, 0.244] | 0.186 | +0.002 | 0.008 / 0.008 | 3.1 % / 3.1 % |
| | 6 h | 0.317 [0.228, 0.378] | 0.324 | −0.007 | 0.005 / 0.005 | 3.5 % / 3.5 % |
| `hour_ground_stop` (3.2 %) | 24 h | 0.132 [0.091, 0.165] | 0.132 | +0.000 | 0.004 / 0.005 | 2.8 % / 2.7 % |
| | 6 h | 0.170 [0.132, 0.212] | 0.167 | +0.003 | 0.004 / 0.004 | 2.8 % / 2.8 % |
| `day_gdp` (14.4 %) | `d3_1900` | 0.157 [0.109, 0.204] | 0.158 | −0.002 | 0.048 / 0.048 | 9.6 % / 9.6 % |
| | `d2_1900` | 0.222 [0.156, 0.279] | 0.227 | −0.005 | 0.046 / 0.047 | 9.7 % / 9.7 % |
| | `d1_0700` | 0.238 [0.177, 0.293] | 0.235 | +0.003 | 0.053 / 0.050 | 9.4 % / 9.4 % |
| | `d1_1900` | 0.274 [0.203, 0.335] | 0.276 | −0.002 | 0.048 / 0.049 | 9.7 % / 9.6 % |
| | `d0_0500` | 0.306 [0.231, 0.371] | 0.310 | −0.004 | 0.055 / 0.054 | 9.4 % / 9.5 % |
| `day_ground_stop` (18.8 %) | `d3_1900` | 0.167 [0.112, 0.228] | 0.172 | −0.005 | 0.037 / 0.037 | 15.7 % / 15.5 % |
| | `d2_1900` | 0.209 [0.154, 0.273] | 0.211 | −0.002 | 0.046 / 0.043 | 15.5 % / 15.3 % |
| | `d1_0700` | 0.244 [0.184, 0.301] | 0.245 | −0.001 | 0.038 / 0.039 | 15.3 % / 15.4 % |
| | `d1_1900` | 0.311 [0.246, 0.377] | 0.307 | +0.005 | 0.041 / 0.050 | 15.9 % / 15.7 % |
| | `d0_0500` | 0.324 [0.254, 0.390] | 0.329 | −0.005 | 0.044 / 0.041 | 15.8 % / 15.8 % |

**Findings:**

- **It did not help.**
  - Over the 20 task-horizons, summed skill is 6.209 against 6.235 without it, and the mean calibration error 0.0246 against 0.0248.
  - Every change is within the intervals, and the forecasts' level does not move.
- **The daily models could not use it until March 2026.**
  - A split needs 200 training days on each side. The training windows held fewer days after a staffing program until they reached December 2025: 66 in 2023, then 2025's as they entered.
  - So through February 2026 the daily forecasts are identical with and without it. The hourly models, with 24 rows a day, could use it from the start.
  - Over January – August 2026, the Brier score is 0.3–0.6 % worse with it on each of the four tasks.
- **Staffing days are still missed.**
  - The evening before, the 41 days with a staffing program had a GDP on 88 % of them. They were forecast at 27 % on average, with the feature and without it.
  - At 24 h, their hours had a GDP 28 % of the time and were forecast at 9 %.
- **Alerts do not change:** catches move by −1.0 to +1.5 points, false alarms by at most 0.06 per 10.

**Caveats:**

- **It stays by the rule, not by the result.** It did no harm where it could be tested and no good where it could.
- **The training windows are filling.** The 47 staffing programs of January 2025 – August 2026 enter the models fitted from November 2026. The monitoring should check the feature then, against fresh months.
- **The counts look back.** Staffing programs come in spells, but how many recent days had one says little about which day is next. A signal from other airports' advisories, where staffing programs may show first, would need a crawl beyond ORD's.
- **The next candidate** is the shift that waits for evidence, listed above.
