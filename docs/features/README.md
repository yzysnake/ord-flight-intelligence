# As-of features

`ordfi.features` builds point-in-time feature snapshots from the dbt core tables (research study §6.4 and §7.5). Each row is a prediction to make: about `target_utc`, made at `as_of = target_utc − horizon`. Its features use only what was known at `as_of`; its labels (`y_` columns) are the outcomes, never features. The same functions are meant for live scoring with `as_of = now`.

```bash
make features SPINE=departures FROM=2015-01 TO=2026-08   # also SPINE=hours; HORIZONS=24h,6h,...
```

Output: `data/features/<spine>/horizon=<h>/<yyyy-mm>.parquet`. The full 2015 – Aug 2026 backfill takes about 35 seconds for both spines.

## Spines

| Spine | One row per | Horizons | Rows (2015 – Aug 2026) | For |
|---|---|---|---|---|
| `departures` | scheduled ORD departure, cancelled ones included | 24h, 6h, 3h, 1h, 15m | 18.3 M (3.66 M flights × 5) | Departure-delay distribution (T2), cancellation (T5) |
| `hours` | UTC hour at ORD | same | 511 k | Airport outlook (T1) |

## Knowledge-time rules

Defined once in `ordfi.features.knowledge`, which also gives `visible(tables, as_of)`: the inputs exactly as they were known at one instant.

| Input | Known at |
|---|---|
| METAR (`weather_obs`), TAF (`taf_hourly`) | `known_time`: issued + 10 min |
| ATC program versions (`atc_program_interval_version`) | the advisory's send time; a version's `valid_to` only once the next version is known |
| Flight schedule: times, carriers, route, block time | 7 days before scheduled departure (schedules are published months ahead) |
| Tail number | 6 hours before scheduled departure |
| Actual departure / arrival time and delay | when the departure / arrival happened |
| Cancellation, diversion, delay causes | never: labels only |
| Calendar | always |

## Feature groups

| Prefix | Spines | What (as known at `as_of`) |
|---|---|---|
| `cal_` | both | Target's local hour, weekday, month, weekend, holiday and distance to holidays |
| `wx_` | both | Latest ORD METAR (age, flight category, visibility, ceiling, wind, gusts, temperature, thunder, snow, freezing) and the last three hours' minimum visibility and ceiling, thunder and snow |
| `taf_` | both | Latest TAF covering the target's hour: lead time, flight category and the worst it allows, visibility, ceiling, wind, thunder and snow (prevailing, TEMPO or PROB), PROB percentage. Null beyond the TAF's 30 hours |
| `atc_` | both | ORD's general GDP and ground stop: in effect now, minutes since the start and to the announced end, announced to cover the target, and how many were issued in the last 24 hours |
| `ops_` | both | ORD departures and arrivals that happened in the last one and three hours (count, mean delay, share 15+ min late), and departures scheduled in the last hour against those that left (`ops_dep_flow_1h`) |
| `dem_` | both | ORD departures and arrivals scheduled in the target's hour |
| `flt_` | departures | Operating and marketing carrier, destination, distance, scheduled block time |
| `inb_` | departures | The aircraft's previous ORD arrival, from 6 hours out: scheduled turn, the inbound's departure and arrival delay so far, its known lateness and the turn slack left |

Null means unknown or absent: no ceiling reported (unlimited), no gusts, no TAF for the hour, no program in effect, no tail yet. A program version without an end (an open ground stop) is taken to last 2 hours.

## Labels

- `departures`: `y_dep_delay` (min), `y_cancelled`, `y_diverted`, `y_dep_bucket` (cancelled, ≤ 0, 1–14, 15–29, 30–59, 60–119, 120–179, ≥ 180 min), and `y_no_tail` (see the caveats).
- `hours`: `y_n_departures`, shares delayed 15+ or 60+ min or cancelled (`y_late15_share`, `y_late60_share`), `y_cancelled_share`, and whether a general GDP or ground stop was in effect in the hour (`y_gdp`, `y_ground_stop`).

## Validation

- **No leakage, by property test** (`tests/property/test_features_no_leakage.py`). For random small worlds, every sampled row gets the same features from the full tables as from `visible(tables, as_of)`. The test catches each of five deliberately injected leaks:
  - METARs matched by valid time;
  - tails always known;
  - events up to 30 minutes ahead;
  - the final program version;
  - the TAF regardless of its send time.
- **No leakage on real data.** The same check on 300 rows per spine in Jan 2016, Jul 2019 and Feb 2024 finds 0 mismatches in 1,800 rows.
- **Signal** (2015 – Aug 2026, 3.66 M departures per horizon, 23 % departing 15+ min late or cancelled):

| At 1 h | Late or cancelled |
|---|---|
| GDP in effect / not | 74 % / 21 % |
| Ground stop in effect / not | 66 % / 22 % |
| TAF thunder at the departure hour / not | 54 % / 22 % |
| Inbound known on time / 30–59 min late / 60+ min late | 13 % / 53 % / 66 % |

Single-feature AUCs at 1 h: the inbound's known lateness 0.73, the last three hours' ORD departure delay 0.68. At 24 h, TAF thunder still separates 46 % from 22 % late.

## Caveats

- **Tails are post-hoc.** BTS records the aircraft that actually flew, so aircraft swaps leak into the inbound features. Flights whose inbound is not found are late twice as often (44 % vs 21 %), partly because swaps and inbound cancellations remove the original inbound. Measure the inbound features' value with an ablation (with and without them; research study §6.5).
- **BTS gives no tail for 30 % of cancelled flights, and only for cancelled ones.** Their inbound features are null, which would reveal the cancellation. They are marked `y_no_tail`; leave them out when training with inbound features, and keep them for cancellation models without inbound features.
- **In-day operations** (`ops_`, `inb_`) assume a departure or arrival was known when it happened (study §7.5). The live archive will measure the real reporting lag.
