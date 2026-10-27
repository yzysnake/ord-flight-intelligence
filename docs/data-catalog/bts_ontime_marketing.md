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
| known issues | Codeshare duplicates: de-duplicate on the operating flight, using the `Duplicate` flag. That flights by *non-reporting* regional operators appear only here is an inference from the reporting rules [U]: verify in Phase 1a against ADS-B counts. All other caveats are as in `bts_ontime_reporting` |
| verified on | 2026-10-26 (URL HEAD-checked; fields per the research study §4.2) |

## Ingestion notes

- Same pipeline as `bts_ontime_reporting`. Build a `flight_leg` key on the operating carrier, and keep a marketing-to-operating mapping table for flight-number search.

## Open questions

- What share of ORD operations is missing from both files (foreign carriers, cargo, non-reporting operators)? Quantify with ADS-B in Phase 1a.
