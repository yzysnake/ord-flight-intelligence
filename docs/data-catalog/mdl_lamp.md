# LAMP: Localized Aviation MOS Program (station guidance)

| Field | Value |
|---|---|
| id | `mdl_lamp` |
| publisher / URL / docs | NWS Meteorological Development Laboratory. [LAMP](https://vlab.noaa.gov/web/mdl/lamp), [elements](https://vlab.noaa.gov/web/mdl/lamp-elements), [archives](https://vlab.noaa.gov/web/mdl/lamp-archived-bulletins-year) |
| licence class / licence / attribution | `public-domain` (NOAA/NWS product [U]: no specific terms found) |
| access | **History:** yearly tar files `https://lamp.mdl.nws.noaa.gov/lamp/Data/archives/lmp_lavtxt.<YYYY>.tar` (2025 ≈ 4.1 GB). **Live:** NOMADS (v2.7 flight-category bulletins are on NOMADS only) |
| history | Hourly bulletins from **Aug 2006**; yearly tars 2006–2025. The current year must be collected live [U] |
| cadence / latency | Hourly cycles; 15-min ceiling/visibility to 6 h (since v2.6); v2.7 bulletins at nominal HH:30 |
| knowledge-time rule | Cycle time + 45 min ([U]: measure live) |
| retention | Permanent (station extracts for ORD and the network airports; full tars may be discarded after extraction) |
| used for | Core 1–25 h features: ceiling, visibility, wind (1–38 h), lightning/convection (1–25 h), precipitation type and probability. Also the DrivenData KORD challenges' forecast input |
| known issues | **v2.7 (2025-09-16) re-derived the visibility category thresholds**, which is a regime break. The bulletin text format needs a parser |
| verified on | 2026-10-26 (2025 tar HEAD-checked; rest per research study §4.3) |

## Ingestion notes

- **Not ingested yet** (deferred 2026-10-28). The hourly archive is about 4 GB of tars per year, 2026 is not archived yet, and LAMP's 1–25 h range is where the TAF already serves the outlook. IEM's `LAV` copy is lighter but has only 4 cycles per day, from 2020-07-12 (`iem_mos` card).

- Stream each yearly tar once and extract station blocks for ORD and about 40 network airports into Parquet keyed by (issue_time, valid_time).
- Do not keep the full tars.
