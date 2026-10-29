# Departure GBDT

**Status:** research model, not planned for v0.1. The study puts flight-level probabilities at v1+, since their skill needs live inbound-aircraft data (§10.4). Code: `ordfi.models.gbdt` (`departure`). Results: run `departure-gbdt-2024-09-to-2026-08` (`docs/backtests/`).

## 1. Target and horizon

Three events for a scheduled ORD departure (study T2 and T5):

| Task | Event | Rows |
|---|---|---|
| `dep_late15` | leaves 15+ min late or is cancelled | departures with a tail in BTS |
| `dep_late60` | leaves 60+ min late or is cancelled | departures with a tail in BTS |
| `dep_cancelled` | is cancelled | every departure |

There is one model per task and horizon: 24 h, 6 h, 3 h, 1 h and 15 min before the scheduled departure. Delays are BTS's gate departure delays.

## 2. Training data

- **Sources:** as-of feature snapshots from 2015 on, built from:
  - BTS on-time records (schedules, tails, actual times);
  - IEM METARs and TAFs;
  - FAA ATCSCC advisories.
- **Labels:** BTS's departure delay and cancellation flag.
- **Window:** a quarter starting in month M is forecast by models trained on every month up to M − 3, which is what BTS has published by then.
  - March 2020 – June 2021 (COVID) are left out.
  - The last 12 months are held out to choose the number of trees and to fit the recalibration, then everything is refit together.
- **Rows:** up to 2.6 M departures per fit. The delay tasks leave out the departures BTS gives no tail: 0.7 % of departures, all of them cancelled (section 5).
- **Regimes:** the FAA operations cap (from 2 June 2026) has not reached a training window in the reported backtest.

## 3. Features

The departures spine's 79 features (`docs/features/`), each as known at `as_of`:

- the departure hour's calendar;
- the latest METAR and the worst of the last three hours;
- the latest TAF for the departure hour;
- ORD's GDPs and ground stops as announced, the program climate (days with a GDP or ground stop among the last 7 and 30) and the staffing cause;
- ORD departures and arrivals in the last one and three hours;
- departures and arrivals scheduled in the departure hour;
- the flight: operating and marketing carrier, destination, distance and scheduled block time;
- the inbound aircraft, from 6 h out: whether its previous ORD arrival is found, its origin, the scheduled turn, whether it has left and landed, its delays so far, its known lateness and the turn slack left.

The cancellation model leaves out the inbound aircraft (70 features). The departures spine has no station guidance yet.

The knowledge-time rules are in `ordfi.features.knowledge`, and a property test checks that no feature uses what was not yet known. Tails count as known 6 h before departure, but BTS records the aircraft that actually flew (section 5).

## 4. Evaluation

The backtest uses rolling quarterly origins over Sep 2024 – Aug 2026 (24 months). Brier skill is measured against the calendar climatology, with 95 % intervals from resampling whole days. The settings are the Outlook GBDT's, and nothing was chosen on these months.

| Task | 24 h | 6 h | 3 h | 1 h | 15 min | Calibration error (worst) |
|---|---|---|---|---|---|---|
| `dep_late15` | 0.067 [0.050, 0.082] | 0.190 [0.173, 0.205] | 0.283 | 0.377 [0.363, 0.392] | 0.448 | 0.011 |
| `dep_late60` | 0.064 [0.044, 0.081] | 0.199 [0.176, 0.218] | 0.294 | 0.407 [0.385, 0.427] | 0.430 | 0.007 |
| `dep_cancelled` | 0.051 [0.030, 0.071] | 0.123 [0.082, 0.157] | 0.172 | 0.206 [0.146, 0.252] | 0.216 | 0.006 |

Without the inbound aircraft, `dep_late15` scores 0.067, 0.118, 0.144, 0.161 and 0.165, and `dep_late60` 0.064, 0.134, 0.170, 0.191 and 0.196.

- **It beats every baseline at every horizon:** the base rate, the calendar and route climatologies, persistence and the slack rule.
- **A day ahead, the skill is the disruption days'.** For `dep_late15` it is 0.16–0.18 on program, thunder and snow days, and 0.014 on days without a program.
- **From 6 h, the inbound aircraft carries most of it.** At 1 h this is mostly the inbound's known lateness. At 6 h it is the rotation (the inbound's origin and scheduled turn) and the flights whose inbound is not found.
- **The strongest inputs** a day ahead are the departure hour, the temperature, the airport's state at the same time the day before, the carrier and the TAF's ceiling. At 1 h the inbound's turn slack dominates, and for cancellations, how many of the last hour's departures have left.
- **It is positive in every month from 6 h** for the delay tasks, in 22–23 of 24 a day ahead, and in 21–23 of 24 for cancellations.
- **There is no study target for single flights** (§10.3).

## 5. Intended use and limitations

- **For:**
  - research on what drives ORD departure delays and cancellations;
  - the value of inbound-aircraft data;
  - a later flight-level product (study §10.4, v1+).
- **Not for:**
  - travel or operational decisions: airlines know the aircraft and crew;
  - telling whether a flight is already cancelled (BTS has no decision time);
  - more than 24 h ahead.
- **Limitations:**
  - **Tails are post-hoc.** BTS records the aircraft that flew, after any swap, so the inbound skill is an upper bound, more so at 6 h. Live, it needs the planned aircraft from a licensed feed.
  - **The delay forecasts cover departures with a tail in BTS.** 20 % of the reported months' cancellations are outside them.
  - **The level drifts.** Delay forecasts ran high in the FAA cap months (37–38 % against 31 % at 24 h and 6 h). Most of that is the recalibration: its map, fitted on a held-out year with more delays than the years before it, lifted refit trees that had already learned that year (32 % on their own). Cancellation forecasts ran low from November 2025: 1.5 % against 2.0 % at 24 h over the 24 months.
  - **The thresholds are not ordered.** Each event has its own model, so P(60+ min late) can exceed P(15+ min late) for a flight (0.03–0.33 % of flights). The study's ordered-bucket model would rule that out.
  - **In-day operations and the inbound's progress** assume each departure and arrival is known when it happens.
  - **The settings were chosen for the hourly tasks' smaller fits.** Larger trees, and the station guidance, are untried.

## 6. Monitoring

Planned, not built yet:

- skill and calibration each month once BTS publishes it, by carrier and weather regime;
- the forecasts' level against the latest months, to catch drifts like the cap months and 2025–26's cancellations, and the recalibration's lift against the refit trees' own level;
- the live tail feed: how often the planned aircraft differs from the one BTS records, which prices the post-hoc gap;
- a fall back to the model without the inbound aircraft when the tail feed is stale, and to the calendar climatology when the airport's inputs are.
