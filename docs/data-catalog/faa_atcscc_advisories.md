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
| known issues | Advisory text is semi-structured `KEY: value` lines; keys vary by type (e.g. `CTL ELEMENT` vs `DESTINATION AIRPORT`, `CUMULATIVE PROGRAM PERIOD` vs `GDP CNX PERIOD`, reroute `VALID`). Revisions and cancellations (`CNX`) must be chained to their program. Formats changed over 25 years. **In 2015-era listings, reroute titles are truncated** (e.g. `ATCSCC ADVZY 022 DCC 01/01/15`), so some reroutes index as `other` and ORD reroutes of that era are not selected for full text. ORD GDP and ground-stop advisories are unaffected (control element `ORD/ZAU`). **Older layouts:** before 6 Nov 2006, GDPs have no `PROGRAM PERIOD`, only `ARRIVALS ESTIMATED FOR` (for a revision, from the revision); until 9 May 2004 the rate is `PROGRAM AAR`; until 2011 the element is often `AIRPORT`. Some ground stops, mostly before 2007 (up to a quarter in 2002), state no period (`EXPECT UPDATE` only): in effect from issuance until cancelled. **Typed days are occasionally wrong** (e.g. `142056Z-182230Z` for 2056Z–2230Z on the 18th) |
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
- **Typed fields** fall back to the older labels (`ARRIVALS ESTIMATED FOR`, `PROGRAM AAR`, `AIRPORT`). For 2001–2006 ORD GDPs, 95 % have a period and 88 % a rate.
- **Periods** are parsed to UTC in dbt `atc_program`. Implausible ones (a mistyped day) are left null rather than guessed: 1 of 16,435 dated periods.

## Open questions

- Completeness before 2001 (the form allows 1980).
- An acceptable sustained crawl rate (currently 1 request/s). Contact the FAA if a faster backfill is ever needed.
- Ground stops without a stated period (mostly before 2007) and revisions: to be resolved into in-effect intervals by a later model.
