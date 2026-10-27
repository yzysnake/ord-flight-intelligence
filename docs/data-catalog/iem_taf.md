# IEM TAF archive

| Field | Value |
|---|---|
| id | `iem_taf` |
| publisher / URL / docs | Iowa Environmental Mesonet. [TAF request page](https://mesonet.agron.iastate.edu/request/taf.php), [`taf.py` help](https://mesonet.agron.iastate.edu/cgi-bin/request/taf.py?help), [API spec](https://mesonet.agron.iastate.edu/api/1/openapi.json) |
| licence class / licence / attribution | `public-domain` (IEM terms, as `iem_asos_metar`) |
| access | Bulk CSV of IEM's parsed forecast groups (`taf.py`: the time range filters on **issuance** time). Per-TAF overview with validity window and amendment flag (`/api/1/nws/taf_overview.json`; needs the ICAO code `KORD`). **Verbatim bulletins** via `/cgi-bin/afos/retrieve.py?pil=TAFORD&fmt=text`. As-of API: `/api/1/nws/taf.json?station=KORD&issued=<ISO8601>` returns the latest TAF issued before that time. Same throttle as other IEM APIs |
| history | **From 1996-01-01** (backfilled from 2000-01). ORD switched to the current format between the TAFs issued 2008-11-04 17:30Z and 23:34Z |
| cadence / latency | 4 routine issuances per day plus amendments; archive sync about every 10 min |
| knowledge-time rule | Issuance time (`valid` field / `product_id`) + 10 min |
| retention | Permanent |
| used for | Core 0–30 h forecast features: probabilities of the ORD capacity breakpoints (ceiling/visibility < 1,000 ft / 3 mi and < 5,500 ft / 7 mi), wind components, thunderstorm and precipitation groups |
| known issues | Visibility above 6 mi is stored as 6.01. The `is_amendment` flag was added 2026-02-13. **IEM's parse has faults, so the hourly expansion must re-derive windows from the bulletins:** (1) **Old-format TAFs** (15,098 up to 2008-11-04) have no validity window, and their `FMhhmm` times can be misdated (e.g. `FM2300` placed on 23 Dec). (2) **Windows are missing for 3,669 of 4,406 TAFs in 2011**: IEM left the `DDHH/DDHH` group in the initial group's text. (3) **Windows ending in the next month or at hour 24 on a month's last day are misdated** (e.g. a TAF valid from 31 Jul 18Z "ends" 2 Jul): 1,090 of 60,691 windows (1.8 %), almost all on TAFs issued on day 28 or later. (4) **IEM's parsed tables miss pre-2009 TAFs**: e.g. 2001 has 3,324 bulletins but 1,898 parsed TAFs |
| verified on | 2026-10-27 (backfill 2000-01..2026-10: 79,462 TAFs, 432,169 forecast groups, every month's bulletins; 0 failed requests) |

## Ingestion notes

- Implemented in `ordfi.ingest.iem` (`make ingest-iem`): per month, the groups CSV, the overview JSON and the bulletin text, partitioned by data month.
- Staged at `stage/iem_taf/{products,groups}/station=ORD/year=YYYY/`. Products and groups carry `known_time` (issuance + 10 min).
- Two flags mark IEM's faults:
  - `old_format`: detected from the group text;
  - `window_valid`: null without a window; false if the window is not 0–30 h long.
- Next: expand each TAF into hourly forecast rows keyed by (issue_time, valid_time), so as-of selection is a simple filter. Windows come from the bulletins; FM/BECMG/TEMPO/PROB semantics stay in separate columns, not merged.
