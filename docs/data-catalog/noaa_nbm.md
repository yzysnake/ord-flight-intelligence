# National Blend of Models (NBM)

| Field | Value |
|---|---|
| id | `noaa_nbm` |
| publisher / URL / docs | NOAA/NWS (MDL). [Text archives](https://vlab.noaa.gov/web/mdl/nbm-text-archives), [versions](https://vlab.noaa.gov/web/mdl/nbm-versions), [v5.0 text card](https://vlab.noaa.gov/web/mdl/nbm-textcard-v5.0); AWS bucket `noaa-nbm-grib2-pds` |
| licence class / licence / attribution | `public-domain`: NOAA Open Data Dissemination, "open to the public and can be used as desired" |
| access | Anonymous S3/HTTPS. Station text: `blend.<YYYYMMDD>/<HH>/text/blend_nb{h,s,e,x,p}tx.t<HH>z`. Gridded GRIB2 under `core/` (layout changed from `grib2/` in 2020) |
| history | AWS from **2020-05-18**; IEM's parsed NBS copy from 2018-11-07 |
| cadence / latency | Hourly. Text ≈ +62–65 min, grids ≈ +94 min after cycle (single-cycle measurement) |
| knowledge-time rule | Cycle + 70 min (text), + 100 min (grids) |
| retention | Permanent (station extracts) |
| used for | Core 6–72 h features: probabilistic ceiling and visibility (MVFR/IFR/LIFR thresholds), thunder (T01), precipitation-type probabilities, snow (S01), ice (I01), gusts. These drive the airport-level Outlook |
| known issues | **Version regimes:** v4.0 2020-09-29, v4.1 2023-01-17, v4.2 2024-05-15, v4.3 2025-05-27, v5.0 2026-04-30 / 05-05 (sources disagree). RRFS replaces the NAM/HiresW inputs on 2026-11-03. Do not infer historical availability from S3 `LastModified` (backfilled objects) |
| verified on | 2026-10-26 (research study §4.3) |

## Ingestion notes

- Prefer NBH (hourly) and NBS (short-range) text bulletins for station features.
- Use GRIB2 only for spatial features (route corridors), via byte-range reads from the `.idx` files.
