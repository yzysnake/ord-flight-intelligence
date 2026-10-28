# Outlook GBDT

**Status:** candidate for v0.1, not yet released. Code: `ordfi.models.gbdt`. Results: run `outlook-gbdt-2024-09-to-2026-08` (`docs/backtests/`).

## 1. Target and horizon

Three hourly events at ORD (study T1), each for one UTC hour:

| Task | Event | Rows |
|---|---|---|
| `hour_bad60` | 20 %+ of the hour's departures leave 60+ min late or are cancelled | hours with 10+ scheduled departures |
| `hour_gdp` | a general ORD ground delay program is in effect during the hour | every hour |
| `hour_ground_stop` | a general ORD ground stop is in effect during the hour | every hour |

There is one model per task and horizon: 24 h, 6 h, 3 h, 1 h and 15 min before the hour.

## 2. Training data

- **Sources:** as-of feature snapshots from 2015 on, built from:
  - BTS on-time records;
  - IEM METARs and TAFs;
  - FAA ATCSCC advisories.
- **Labels:** from the same BTS records and from the reconstructed program intervals.
- **Window:** for a forecast month M, every month up to M − 3, which is what BTS has published by then.
  - March 2020 – June 2021 (COVID) are left out.
  - The last 12 months are held out to choose the number of trees and to fit the recalibration, then everything is refit together.
- **Regimes:** the FAA operations cap (from 2 June 2026) has not reached a training window in the reported backtest.

## 3. Features

All 59 features of the hours spine (`docs/features/`), each as known at `as_of`:

- the target hour's calendar;
- the latest METAR and the worst of the last three hours;
- the latest TAF for the target hour;
- ORD's GDPs and ground stops as announced;
- departures and arrivals in the last one and three hours;
- departures and arrivals scheduled in the target hour.

The knowledge-time rules are in `ordfi.features.knowledge`, and a property test checks that no feature uses what was not yet known.

## 4. Evaluation

Rolling monthly origins over Sep 2024 – Aug 2026 (24 months). Brier skill is measured against the calendar climatology, with 95 % intervals from resampling whole days. The settings were frozen on Sep 2022 – Aug 2024 first.

| Task | 24 h | 6 h | 1 h | Calibration error (24 h / 6 h) |
|---|---|---|---|---|
| `hour_bad60` | 0.249 [0.205, 0.284] | 0.431 [0.372, 0.477] | 0.580 | 0.012 / 0.009 |
| `hour_gdp` | 0.141 [0.094, 0.183] | 0.292 [0.227, 0.341] | 0.735 | 0.012 / 0.009 |
| `hour_ground_stop` | 0.089 [0.060, 0.117] | 0.146 [0.107, 0.185] | 0.234 | 0.006 / 0.004 |

- It beats every baseline (climatology, persistence, announced programs) at every horizon.
- It meets the v0.1 skill targets (above 0.10 at 24 h and 0.25 at 6 h, calibration error at most 0.03) for bad hours. GDP hours meet them on the point estimate. Ground-stop hours do not.
- Skill is positive in every season and regime: on program, thunder and snow days, on other days, and in the FAA cap months.
- Ablations: the 24 h skill is mostly the TAF's; FAA programs and in-day operations drive the short horizons.

## 5. Intended use and limitations

- **For:** the public ORD Outlook, i.e. how likely a bad hour, a GDP or a ground stop is from a day to 15 minutes ahead. Also for research on what drives ORD disruption.
- **Not for:**
  - individual flights (see the departure tasks);
  - operational decisions by airlines or the FAA;
  - beyond 24 h (the TAF runs out at 30 h).
- **Limitations:**
  - Skill moves with the season's weather: it was lower on the calmer development months.
  - In-day operations assume departures and arrivals are known as they happen. The live feed's lag is not yet measured.
  - The FAA cap regime is untrained.
  - No daily outlook exists yet, so the study's bad-day criterion is unmeasured.

## 6. Monitoring

Planned for v0.1, not built yet:

- Brier skill and calibration on each month once BTS publishes it, on the public track-record page;
- feature freshness, i.e. how late the METAR, TAF and advisories arrive;
- a fall back to the calendar climatology when inputs are stale.
