# IEM TAF archive

| Field | Value |
|---|---|
| id | `iem_taf` |
| publisher / URL / docs | Iowa Environmental Mesonet. [TAF request page](https://mesonet.agron.iastate.edu/request/taf.php), [`taf.py` help](https://mesonet.agron.iastate.edu/cgi-bin/request/taf.py?help), [API spec](https://mesonet.agron.iastate.edu/api/1/openapi.json) |
| licence class / licence / attribution | `public-domain` (IEM terms, as `iem_asos_metar`) |
| access | Bulk CSV (`taf.py`: the time range filters on **issuance** time) and an as-of API: `/api/1/nws/taf.json?station=KORD&issued=<ISO8601>` returns the latest TAF issued before that time. Same throttle as other IEM APIs |
| history | **From 1996-01-01** |
| cadence / latency | 4 routine issuances per day plus amendments; archive sync about every 10 min |
| knowledge-time rule | Issuance time (`valid` field / `product_id`) + 10 min |
| retention | Permanent |
| used for | Core 0–30 h forecast features: probabilities of the ORD capacity breakpoints (ceiling/visibility < 1,000 ft / 3 mi and < 5,500 ft / 7 mi), wind components, thunderstorm and precipitation groups |
| known issues | Visibility above 6 mi is stored as 6.01. **Old-format TAFs parse imperfectly** (e.g., `BECMG` tokens in the present-weather field), so re-parse the raw text for early years. The `is_amendment` flag was added 2026-02-13 |
| verified on | 2026-10-26 (research study §4.3) |

## Ingestion notes

- Expand each TAF into hourly forecast rows keyed by (issue_time, valid_time), so as-of selection is a simple filter.
- Keep FM/BECMG/TEMPO/PROB semantics as separate columns, not merged.
