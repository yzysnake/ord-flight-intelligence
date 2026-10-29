# Outlook GBDT

**Status:** candidate for v0.1, not yet released. Code: `ordfi.models.gbdt`. Results (`docs/backtests/`): runs `outlook-guidance-2024-09-to-2026-08` (bad hours and days) and `outlook-staffing-2024-09-to-2026-08` (GDPs and ground stops). The earlier runs `outlook-gbdt-…` and `daily-outlook-…` are of the model before station guidance.

## 1. Target and horizon

Three hourly events at ORD (study T1), each for one UTC hour:

| Task | Event | Rows |
|---|---|---|
| `hour_bad60` | 20 %+ of the hour's departures leave 60+ min late or are cancelled | hours with 10+ scheduled departures |
| `hour_gdp` | a general ORD ground delay program is in effect during the hour | every hour |
| `hour_ground_stop` | a general ORD ground stop is in effect during the hour | every hour |

There is one model per task and horizon: 24 h, 6 h, 3 h, 1 h and 15 min before the hour.

The daily outlook has the same three events for a local day (America/Chicago): a bad day (20 %+ of the day's departures 60+ min late or cancelled, the top decile of 2015 – Aug 2024), and a GDP or ground stop at some time in the day. Its models are issued at five local times: 19:00 three and two days before, 07:00 and 19:00 the day before, and 05:00 on the day.

## 2. Training data

- **Sources:** as-of feature snapshots from 2015 on, built from:
  - BTS on-time records;
  - IEM METARs and TAFs;
  - IEM's GFS MOS (2014-12 →) and NBM (2018-11 →) station guidance;
  - FAA ATCSCC advisories.
- **Labels:** from the same BTS records and from the reconstructed program intervals.
- **Window:** for a forecast month M, every month up to M − 3, which is what BTS has published by then.
  - March 2020 – June 2021 (COVID) are left out.
  - The last 12 months (24 for the daily models) are held out to choose the number of trees and to fit the recalibration, then everything is refit together.
- **Regimes:**
  - The FAA operations cap (from 2 June 2026) has not reached a training window in the reported backtest.
  - NBM exists only from 2018-11, and its IFR probabilities from 2020-09.

## 3. Features

The hours spine's features (`docs/features/`), each as known at `as_of`. The daily models use the days spine's, which sum the TAF and the guidance over the day and add the previous 24 hours of operations. The bad-hour and bad-day models read 86 and 94 features; the GDP and ground-stop models add the program climate and the staffing cause (92 and 100):

- the target hour's calendar;
- the latest METAR and the worst of the last three hours;
- the latest TAF for the target hour;
- GFS MOS and NBM guidance for the target hour, from each projection's latest run;
- ORD's GDPs and ground stops as announced;
- the program climate: how many of the last 7 and 30 days had a GDP or a ground stop, and how many had one whose advisories cited staffing (GDP and ground-stop models only);
- departures and arrivals in the last one and three hours;
- departures and arrivals scheduled in the target hour.

The knowledge-time rules are in `ordfi.features.knowledge`, and a property test checks that no feature uses what was not yet known.

## 4. Evaluation

Rolling monthly origins over Sep 2024 – Aug 2026 (24 months). Brier skill is measured against the calendar climatology, with 95 % intervals from resampling whole days. The settings were frozen on Sep 2022 – Aug 2024 first, and so was the decision to add the guidance. The program climate was chosen on those months and on Sep 2018 – Feb 2020, when programs were becoming more frequent. The staffing cause was adopted on a rule of no harm there, since neither window has staffing programs to learn from.

| Task | 24 h | 6 h | 1 h | Calibration error (24 h / 6 h) |
|---|---|---|---|---|
| `hour_bad60` | 0.297 [0.244, 0.341] | 0.445 [0.381, 0.493] | 0.581 | 0.014 / 0.008 |
| `hour_gdp` | 0.187 [0.116, 0.244] | 0.317 [0.228, 0.378] | 0.742 | 0.008 / 0.005 |
| `hour_ground_stop` | 0.132 [0.091, 0.165] | 0.170 [0.132, 0.212] | 0.243 | 0.004 / 0.004 |

Daily, Brier skill on the same months (730 days):

| Task | `d3_1900` | `d2_1900` | `d1_0700` | `d1_1900` | `d0_0500` | Calibration error (`d1_1900`) |
|---|---|---|---|---|---|---|
| `day_bad60` | 0.229 | 0.250 [0.186, 0.305] | 0.293 [0.216, 0.355] | 0.341 [0.262, 0.405] | 0.430 | 0.029 |
| `day_gdp` | 0.157 | 0.222 [0.156, 0.279] | 0.238 [0.177, 0.293] | 0.274 [0.203, 0.335] | 0.306 | 0.048 |
| `day_ground_stop` | 0.167 | 0.209 [0.154, 0.273] | 0.244 [0.184, 0.301] | 0.311 [0.246, 0.377] | 0.324 | 0.041 |

- It beats every baseline (climatology, persistence, announced programs) at every horizon and issue.
- **The v0.1 skill targets** (above 0.10 at 24 h and 0.25 at 6 h, calibration error at most 0.03):
  - Bad hours and GDP hours meet them.
  - Ground-stop hours meet the 24 h one but not the 6 h one (0.170). That one is out of reach: forecasts that knew for certain whether the day had a ground stop, or whether ORD had thunder within an hour, would score at most 0.20 (`docs/backtests/`).
- **The study's bad-day criterion** (60 %+ of bad days flagged at ≤ 1 false alarm per 10 normal days), with each month's alert threshold set on the year before it:
  - Two days ahead, the alert catches 59 % at 0.97 false alarms per 10, issued at least 24 h before every flight of the day.
  - The morning before, it catches 75 % at 1.22, and the evening before, 77 % at 1.14.
- **Skill is positive in every season and regime:** on program, thunder and snow days, and in the FAA cap months.
  - On days with no program at all, it is positive too, except for ground-stop hours 24 h ahead (−0.165).
  - Those days' Brier score is tiny, and the program climate lifts their forecasts in busy spells.
- **Ablations:** two and three days ahead the skill is the guidance's. On the day before, the TAF and the guidance overlap. FAA programs and in-day operations drive the short horizons. The program climate adds 0.01–0.02 for GDP days and changes skill by less than 0.01 elsewhere. The staffing cause changes it by less than 0.01 everywhere.

## 5. Intended use and limitations

- **For:** the public ORD Outlook, i.e. how likely a bad hour, a GDP or a ground stop is from three days to 15 minutes ahead. Also for research on what drives ORD disruption.
- **Not for:**
  - individual flights (see the departure tasks);
  - operational decisions by airlines or the FAA;
  - beyond 72 h (the guidance runs out).
- **Limitations:**
  - Skill moves with the season's weather: it was lower on the calmer development months.
  - In-day operations assume departures and arrivals are known as they happen. The live feed's lag is not yet measured.
  - The guidance's knowledge times are estimates from the catalog cards, not measured on the live feed.
  - The FAA cap regime is untrained.
  - Daily GDP and ground-stop forecasts run low when programs become more frequent. In the reported months they averaged 9.6 % for GDP days (14.4 % observed) and 15.6 % for ground-stop days (18.8 %), with calibration errors of 0.037–0.055.
  - About half of the shortfall is days with staffing programs, which the training years barely had. The staffing cause did not lift them: those days were forecast at 27 % the evening before, and 88 % of them had a GDP.
  - A shift of the level that waits for evidence (`gbdt_shrunk`) would have brought the daily calibration error to 0.029 in the reported months, with more skill. It lost skill on 2022–24, though, and was not adopted (`docs/backtests/`).
  - The alert thresholds lag a rising trend: false alarms ran up to 1.6 per 10 normal days in the reported months.

## 6. Monitoring

Planned for v0.1, not built yet:

- Brier skill and calibration on each month once BTS publishes it, on the public track-record page;
- feature freshness, i.e. how late the METAR, TAF, guidance and advisories arrive;
- a fall back to the calendar climatology when inputs are stale;
- the level of the daily GDP and ground-stop forecasts against the latest months' programs, to catch a regime change like 2025's staffing programs, and whether the staffing cause helps once those programs are in the training windows (from November 2026);
- the alert threshold, reset each month on the last 12 months with published outcomes. In the backtest it held false alarms at 9.3 % on the development months, but higher in the stormier reported months (`docs/backtests/`).
