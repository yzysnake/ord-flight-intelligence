# FAA ATCSCC advisories

| Field | Value |
|---|---|
| id | `faa_atcscc_advisories` |
| publisher / URL / docs | FAA Air Traffic Control System Command Center. [Advisory search](https://www.fly.faa.gov/adv/advAdvisoryForm) |
| licence class / licence / attribution | `public-domain` (FAA) |
| access | HTML, no API or key. **Daily listing:** `https://www.fly.faa.gov/adv/adv_list?whichAdvisories=ATCSCC&advisoryCategory=All&date=YYYY-MM-DD&…` lists every advisory of a UTC day (number, control element, brief title, send time). **Detail:** `https://www.fly.faa.gov/adv/adv_otherdis?adv_date=MMDDYYYY&advn=N` |
| history | **Jun 2001 →** (the form accepts dates back to 1980; 2001 is the earliest verified) |
| cadence / latency | Real time; days can grow until they end, so the crawler re-fetches the last 2 days |
| knowledge-time rule | The advisory's **send time** (listing, UTC), plus a few minutes of dissemination |
| retention | Permanent |
| used for | Labels and features for ground delay programs (period, hourly rates, average/maximum delay, cause), ground stops, AFPs, CTOPs and reroutes; planning advisories; plain-language explanations |
| known issues | Advisory text is semi-structured `KEY: value` lines; keys vary by type (e.g. `CTL ELEMENT` vs `DESTINATION AIRPORT`, `CUMULATIVE PROGRAM PERIOD` vs `GDP CNX PERIOD`, reroute `VALID`). Revisions and cancellations (`CNX`) must be chained to their program. Formats changed over 25 years. **In 2015-era listings, reroute titles are truncated** (e.g. `ATCSCC ADVZY 022 DCC 01/01/15`), so some reroutes index as `other` and ORD reroutes of that era are not selected for full text. ORD GDP and ground-stop advisories are unaffected (control element `ORD/ZAU`). **Older layouts:** before 6 Nov 2006, GDPs have no `PROGRAM PERIOD`, only `ARRIVALS ESTIMATED FOR` (for a revision, from the revision); until 9 May 2004 the rate is `PROGRAM AAR`; until 2011 the element is often `AIRPORT`. Old ground stops state only an `EXPECT UPDATE` time, and informal ones since 2016 an `EVENT TIME` (`12/2120 - 2230`, sometimes with no end). **Ground stops issued during a GDP also state the GDP's `CUMULATIVE PROGRAM PERIOD`** (1,468 advisories, 2006 →). Cancellation titles vary (`CNX`, `CANCELLATION`, `CNCL'D`, `CANCLED`), and a few release only some facilities (`PARTIAL`, `CNX FOR ZBW/ZDC`). Some ground stops cover one carrier only (`EGF ONLY`, `UAL SUBS`) or aircraft not cleared for low-visibility approaches (`CAT I`). **Typed days are occasionally wrong** (e.g. `142056Z-182230Z` for 2056Z–2230Z on the 18th) |
| verified on | 2026-10-28 (full crawl 2001-06-01..2026-10-26: 9,279 days, 723 k listed advisories, 42,480 ORD-related texts; 0 failures after re-fetching 69 days lost to a local network outage) |

## Ingestion notes

- Implemented in `ordfi.ingest.atcscc` (`make ingest-atcscc FROM=… TO=…`).
- **Politeness:** sequential requests, 1 s apart, with the project User-Agent.
- **Resumable:** past days are fetched once; the last 2 days are re-fetched.
- **Raw zone:** `raw/faa_atcscc_advisories/{listings,advisories}/<yyyy>/<mm>/…html`, verbatim, partitioned by advisory date.
- **Full texts:** fetched only for ORD-related advisories (ORD, KORD, Chicago Center ZAU or Chicago TRACON C90 in the element or title). Other categories (e.g. national Operations Plans) can be added later with a different selector.
- **Staged tables**, under `stage/faa_atcscc_advisories/`:
  - `index/year=YYYY` (every listed advisory: category, cancellation flag, ORD relevance, send/known time);
  - `advisories/year=YYYY` (full text, `fields_json`, and typed `ctl_element`, `period`, `program_rate`, `average_delay`, `maximum_delay`, `reason`).
- **Typed fields** fall back to the older and informal labels (`ARRIVALS ESTIMATED FOR`, `EVENT TIME`, `EXPECT UPDATE`, `PROGRAM AAR`, `AIRPORT`); a ground stop's own `GROUND STOP PERIOD` comes first. For 2001–2006 ORD GDPs, 95 % have a period and 88 % a rate; 98.8 % of ORD ground-stop advisories (other than cancellations) have one.
- **Periods** are parsed to UTC in dbt `atc_program`. Implausible ones (a mistyped day) are left null rather than guessed: 1 of 18,571 periods.
- **Programs:** dbt `atc_program_interval` chains ORD's advisories into 5,333 GDPs and ground stops (2001-06..2026-10), and `atc_program_interval_version` keeps each program as known after each advisory, with the cause that advisory states (a program's cause can change: a GDP for thunderstorms extended for staffing). Validated against BTS flights to ORD, 2015 – Aug 2026 (1,114 general ground stops and 538 GDPs):
  - of the flights scheduled to leave for ORD during a ground stop, 54 % left during it and 14 % were cancelled, against 83 % and 3 % in the same window a week earlier;
  - for stops of an hour or more, departures to ORD per scheduled departure fall from 0.85 in the hour before a stop to 0.60–0.63 from 15 minutes after its start, and surge to 1.04 15–45 minutes after its end (the released backlog), so starts and ends line up within 15 minutes;
  - flights scheduled to arrive during a GDP left 77 minutes late on average (61 % 15+ minutes late), against 17 minutes (22 %) a week earlier.

## Open questions

- Completeness before 2001 (the form allows 1980).
- An acceptable sustained crawl rate (currently 1 request/s). Contact the FAA if a faster backfill is ever needed.
- Partial releases stated only in the text (`RELEASED FACILITIES: ZID`) count as full cancellations; tiers and facility scopes are not tracked.
