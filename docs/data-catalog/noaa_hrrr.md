# HRRR: High-Resolution Rapid Refresh

| Field | Value |
|---|---|
| id | `noaa_hrrr` |
| publisher / URL / docs | NOAA/NCEP. [AWS registry](https://registry.opendata.aws/noaa-hrrr-pds/) (bucket `noaa-hrrr-bdp-pds`; also Google Cloud and Azure from 2021-03-21). Tooling: [Herbie](https://herbie.readthedocs.io/en/stable/) |
| licence class / licence / attribution | `public-domain` (NOAA Open Data Dissemination) |
| access | Anonymous S3/HTTPS; byte-range downloads guided by the `.idx` files |
| history | **2014-07-30 →**. Versions: v2 2016-08-23, v3 2018-07-12, v4 2020-12-02 (the last HRRR upgrade) |
| cadence / latency | Hourly cycles to 18 h; 00/06/12/18z cycles to 48 h; 15-min sub-hourly files. Measured lag: f00 ≈ +51 min, f18 ≈ +75 min, f48 ≈ +108 min |
| knowledge-time rule | Cycle + 55 min (f00), + 80 min (f18), + 115 min (f48) |
| retention | Permanent for **extracted features only** (ORD point and rings, route corridors). Never store full grids |
| used for | 0–18 h (48 h) gridded features: ceiling, visibility, composite reflectivity, echo tops, VIL, lightning, gusts, precipitation-type flags; also convective coverage near the departure and arrival fixes |
| known issues | Field encodings drift between versions. Early 2014 files look duplicated, so start no earlier than 2014-10. Sub-hourly files have no lightning field. S3 `LastModified` is unreliable for availability. HRRR is not on the retirement list, but RRFS becomes operational 2026-11-03 (monitor) |
| verified on | 2026-10-26 (research study §4.3) |
