# FAA Releasable Aircraft Registry

| Field | Value |
|---|---|
| id | `faa_aircraft_registry` |
| publisher / URL / docs | FAA Civil Aviation Registry. [Download page](https://www.faa.gov/licenses_certificates/aircraft_certification/aircraft_registry/releasable_aircraft_download); [file layout](https://registry.faa.gov/database/ardata.pdf) (dated 2025-05-08) |
| licence class / licence / attribution | `public-domain` |
| access | Daily ZIP (≈ 60 MB): `https://registry.faa.gov/database/ReleasableAircraft.zip`. **Scripted requests returned HTTP 403 on 2026-10-26.** Do not spoof browsers. Use the documented manual download, or ask the FAA about automated access |
| history | Current registry plus a deregistered-aircraft file |
| cadence / latency | Refreshed daily at 11:30 pm Central |
| knowledge-time rule | File date |
| retention | Weekly snapshots of the **minimized** extract (see known issues) |
| used for | Joining ADS-B `icao24` (Mode S hex, MASTER positions 602–611) ↔ N-number ↔ aircraft make, model and seats; enriching BTS tails with aircraft type |
| known issues | **Personal data:** registrant names and addresses for privately owned aircraft. Drop all registrant fields at ingestion (data minimization); keep only N-number, Mode S hex, manufacturer/model codes and year. Aircraft using FAA privacy ICAO addresses (PIA) will not map |
| verified on | 2026-10-26 (layout per research study §4.2; download returned 403 to `curl`) |
