# BTS Marketing Carrier On-Time Performance

| Field | Value |
|---|---|
| id | `bts_ontime_marketing` |
| publisher / URL / docs | US DOT BTS (TranStats). [Field list](https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=FGK) |
| licence class / licence / attribution | `public-domain` (as `bts_ontime_reporting`) |
| access | Monthly ZIP (CSV): `https://transtats.bts.gov/PREZIP/On_Time_Marketing_Carrier_On_Time_Performance_Beginning_January_2018_<YYYY>_<M>.zip` (Aug 2026 ≈ 38 MB) |
| history | Jan 2018 → |
| cadence / latency | Same as the reporting-carrier file (6–8 weeks) |
| knowledge-time rule | Same as `bts_ontime_reporting` |
| retention | Permanent |
| used for | **Primary ORD flight table.** It adds `Marketing_Airline_Network`, `Operated_or_Branded_Code_Share_Partners`, `Operating_Airline` and its flight number, and a `Duplicate` flag. This matters because branded regional partners fly about 49 % of ORD domestic arrivals |
| known issues | **Source corruption:** Aug 2018 has a row with a truncated UTF-8 byte-order mark in place of the marketing-carrier code (SkyWest 3300, SJC, 2018-08-01). Files are decoded lossily and such rows are counted as `rows_invalid_text`. Codeshare duplicates: de-duplicate on the operating flight, using the `Duplicate` flag (it is never set in 2018-01..2026-08). **Verified: flights by non-reporting operators appear only in this file**, and the share is large: 14.5 % of ORD rows in 2018, 15–16 % in 2019–2021, 12 % in 2022–2024, 8.5 % in 2025 and 7.1 % in Jan–Aug 2026. The operators are mainly Air Wisconsin `ZW`, GoJet `G7`, Trans States `AX` and Piedmont `PT`. In Aug 2026 it was 4,705 of 71,074 ORD rows (6.6 %), mostly GoJet for United (4,507) and Endeavor `9E` for Delta (196). The header has a trailing space (`"Operating_Airline "`); names are stripped on read. All other caveats are as in `bts_ontime_reporting` |
| verified on | 2026-10-27 (full backfill 2018-01..2026-08: 104 months, 62.1 M rows, 5.7 M at ORD; every airport code resolves to a time zone; UTC derivation reproduces BTS local times for ≥ 99.95 % of rows in every month; one duplicate key, not at ORD) |

## Ingestion notes

- Same pipeline as `bts_ontime_reporting`. Build a `flight_leg` key on the operating carrier, and keep a marketing-to-operating mapping table for flight-number search.

## Open questions

- What share of ORD operations is missing from both files (foreign carriers, cargo, international)? Quantify with ADS-B.
