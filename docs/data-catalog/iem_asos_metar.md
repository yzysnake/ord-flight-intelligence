# IEM ASOS / METAR archive

| Field | Value |
|---|---|
| id | `iem_asos_metar` |
| publisher / URL / docs | Iowa Environmental Mesonet (Iowa State University). [Download page](https://mesonet.agron.iastate.edu/request/download.phtml), [API help](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?help), [ORD station](https://mesonet.agron.iastate.edu/sites/site.php?station=ORD&network=IL_ASOS) |
| licence class / licence / attribution | `public-domain`: "may be used freely by anyone for any lawful purpose"; attribution "would be appreciated" ([disclaimer](https://mesonet.agron.iastate.edu/disclaimer.php)) |
| access | CSV via `asos.py` (station=ORD, tz=UTC, report types: 3 routine, 4 specials, 1 HFMETAR 5-minute). Limits: **1 s per-IP throttle** (since 2026-04-21); ≤ 1,000 station-years per request (HTTP 422); 429 when throttled; 503 under load |
| history | ORD from **1946-10-01**; 5-minute HFMETAR rows from about 2019 |
| cadence / latency | Hourly METARs plus specials; HFMETAR every 5 min. The archive syncs from IEM's real-time ingest every 10 min |
| knowledge-time rule | Observation time + 10 min |
| retention | Permanent |
| used for | Observed weather for nowcasts (≤ 1 h), labels and diagnostics, climatology. **Never a feature for future hours** (use forecasts) |
| known issues | Very little quality control; duplicates and corrections occur. IEM asks that its API not be called from high-traffic websites, so **serve the public site from our cache**. For live use, the AWC Data API (100 requests/min, 30-day window) is the alternative |
| verified on | 2026-10-26 (research study §4.3) |

## Ingestion notes

- Daily backfill partitions. Store the raw METAR string and the parsed fields: wind, gust, visibility, sky layers, present weather, precipitation, ice accretion.
- Deduplicate on (station, valid time, report type).

## Related

- ASOS 1-minute data (NCEI/IEM) arrive about 24 h late, so they are for labels and diagnostics only.
