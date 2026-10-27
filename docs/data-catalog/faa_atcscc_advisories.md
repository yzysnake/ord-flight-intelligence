# FAA ATCSCC advisories

| Field | Value |
|---|---|
| id | `faa_atcscc_advisories` |
| publisher / URL / docs | FAA Air Traffic Control System Command Center. [Advisory search](https://www.fly.faa.gov/adv/advAdvisoryForm), which covers only the last 15 days |
| licence class / licence / attribution | `public-domain` (FAA) |
| access | HTML text pages, no API or key. Older advisories are served by direct URL: `https://www.fly.faa.gov/adv/adv_otherdis.jsp?advn=<N>&adv_date=<MMDDYYYY>` |
| history | **Jun 2001 →** by direct URL (spot-checked 2001, 2003, 2005, 2007, 2010, 2014, 2019, 2024, 2026) |
| cadence / latency | Real time; the listing refreshes about every 5 min. Roughly 100 advisories per day nationally [U] |
| knowledge-time rule | The advisory's issuance timestamp, plus 5 min dissemination lag |
| retention | Permanent |
| used for | Labels and features for ground delay programs, ground stops, airspace flow programs and reroutes at ORD and destinations; planning advisories ("possible" programs); plain-language explanations |
| known issues | Semi-structured text whose formats changed over 25 years. Revisions and cancellations (`CNX`) must be chained to the original program. Completeness before 2001 is unknown |
| verified on | 2026-10-26 (research study §4.2) |

## Ingestion notes

- Crawl politely: sequential requests, a pause between them, a descriptive User-Agent, and a cached daily index.
- Parse into `atc_program` (element, type, issued_at, start/end, average/maximum delay, scope, revision number).
- Store raw HTML verbatim. Parsers must be regression-tested on samples from each format era.

## Open questions

- Whether advisory numbers reset daily, and how to enumerate a day's advisories without gaps [U].
- An acceptable crawl rate. Consider contacting the FAA if the historical backfill is large.
