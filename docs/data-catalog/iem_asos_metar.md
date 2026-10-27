# IEM ASOS / METAR archive

| Field | Value |
|---|---|
| id | `iem_asos_metar` |
| publisher / URL / docs | Iowa Environmental Mesonet (Iowa State University). [Download page](https://mesonet.agron.iastate.edu/request/download.phtml), [API help](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?help), [ORD station](https://mesonet.agron.iastate.edu/sites/site.php?station=ORD&network=IL_ASOS) |
| licence class / licence / attribution | `public-domain`: "may be used freely by anyone for any lawful purpose"; attribution "would be appreciated" ([disclaimer](https://mesonet.agron.iastate.edu/disclaimer.php)) |
| access | CSV via `asos.py` (station=ORD, tz=UTC; report types 3 routine, 4 specials, 1 HFMETAR 5-minute). The CSV has **no report-type column**, so each type is a separate request. Limits: **1 s per-IP throttle** (since 2026-04-21); ≤ 1,000 station-years per request (HTTP 422); 429 when throttled; 503 under load |
| history | ORD from **1946-10-01** (backfilled from 2000-01). 5-minute HFMETAR rows from **2016-04-30** |
| cadence / latency | Hourly METARs plus specials; HFMETAR every 5 min. The archive syncs from IEM's real-time ingest every 10 min |
| knowledge-time rule | Observation time + 10 min |
| retention | Permanent |
| used for | Observed weather for nowcasts (≤ 1 h), labels and diagnostics, climatology. **Never a feature for future hours** (use forecasts) |
| known issues | Very little quality control; duplicates and corrections occur (6 duplicate rows in 2000–2026). **Report-type labels are unreliable**: in 2001 and Jan–Jul 2006, ORD's hourly observations (at :56 and :53) are labelled specials. Use routine and specials together; that combination covers ≥ 99.4 % of hours in every year except 2000 (98.0 %). IEM asks that its API not be called from high-traffic websites, so **serve the public site from our cache**. For live use, the AWC Data API (100 requests/min, 30-day window) is the alternative |
| verified on | 2026-10-27 (backfill 2000-01..2026-10: 1.36 M rows: 229 k routine, 62 k specials, 1.07 M HFMETAR; 0 failed requests) |

## Ingestion notes

- Implemented in `ordfi.ingest.iem` (`make ingest-iem`).
  - One request per month and report type; raw CSVs are partitioned by data month.
  - Months that ended less than 3 days ago are re-fetched.
- Staged at `stage/iem_asos_metar/station=ORD/year=YYYY/`:
  - typed fields (trace precipitation `T` → 0.0001, as IEM's numeric default);
  - the raw METAR string;
  - `report_type`, `known_time`, and the raw file's checksum.
- Deduplicated on (station, valid time, report type).

## Related

- ASOS 1-minute data (NCEI/IEM) arrive about 24 h late, so they are for labels and diagnostics only.
