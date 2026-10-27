# BTS Reporting Carrier On-Time Performance

| Field | Value |
|---|---|
| id | `bts_ontime_reporting` |
| publisher / URL / docs | US DOT Bureau of Transportation Statistics (TranStats). [Profile](https://www.transtats.bts.gov/DatabaseInfo.asp?QO_VQ=EFD&Yv0x=D), [field list](https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=FGJ) |
| licence class / licence / attribution | `public-domain`: US government work (17 U.S.C. 105). Courtesy attribution: "Source: U.S. DOT, Bureau of Transportation Statistics" |
| access | Monthly ZIP (CSV), no authentication: `https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_<YYYY>_<M>.zip` (Aug 2026 ≈ 32 MB) |
| history | Oct 1987 →. Cause-of-delay minutes from Jun 2003. Diversion and gate-return fields from Oct 2008 |
| cadence / latency | Monthly. Carriers file within 15 days, but public release lands **6–8 weeks** after month end (Aug 2026 was the latest month on 2026-10-26). Files can be re-published: the Aug 2026 file showed `Last-Modified` 2026-10-26 |
| knowledge-time rule | **As labels:** known at our first successful fetch of that month's file. Record fetch time and checksum, and treat a checksum change as a revision. **As in-day state** (historical reconstruction): an event is known at its actual time. This approximates a live feed; document it |
| retention | Permanent (raw ZIP + Parquet) |
| used for | Training labels (delays, cancellations, diversions), aircraft rotations, reliability statistics (display), climatology baselines |
| known issues | See the list below |
| verified on | 2026-10-26 (URL HEAD-checked; fields, rules and lag from the research study §4.2) |

**Known issues:**

1. **Scope.** Domestic flights of US *reporting* carriers only; international and transborder flights are excluded. Reporting carriers are those above 0.5 % of domestic scheduled passenger revenue. The 2026 list names 14 carriers on 13 certificates. Spirit ceased operations 2026-05-02.
2. **Cancellations.** Only flights listed in reservation systems within **7 days** of departure count, so earlier schedule cuts (2025 shutdown cuts, 2026 cap trims) are invisible.
3. **Cause fields.** Cause minutes are reported only for arrivals ≥ 15 min late. The DOT OIG found 22–43 % NAS-cause mismatches with FAA data.
4. **Diversions.** `ArrDelay` is NULL for diverted flights; use `DivArrDelay`.
5. **Time format.** Local `hhmm` times, including `2400`.
6. **Tail numbers.** Tails are the *actual* aircraft, so they are post-hoc for long-horizon models, and occasionally wrong.
7. **Cause-code break.** For flights from **2027-01-01** (Section 511(b)), a new delay category and cancellation code E are added.

## Ingestion notes

- Keep all 110+ columns in the raw zone. In staging, convert local times to UTC per airport time zone, handling DST and `2400`. Store the release month and fetch time.
- ORD subset: `Origin == 'ORD' or Dest == 'ORD'`. Keep national rows for network features.
- Pair with `bts_ontime_marketing` for codeshare and regional coverage.

## Open questions

- BTS revision policy for past months: how often files are re-published and what changes.
