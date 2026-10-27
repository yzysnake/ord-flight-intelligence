# Data catalog

Every external data source gets one card (`<source-id>.md`) **before** any code ingests it. The card is the contract the pipelines, the archiver and the website must respect.

## Licence classes

| Class | Meaning | Examples | Retention | Public display |
|---|---|---|---|---|
| `public-domain` | US government works and similar | BTS, FAA NAS Status, NOAA/IEM, CBP | Permanent | Yes |
| `open-share-alike` | Open licence with attribution and share-alike | adsb.lol (ODbL), OpenStreetMap (ODbL) | Permanent | Yes, with attribution; derived databases share-alike |
| `non-commercial` | Research or personal use only | OpenSky Network | Per terms | Only with a written licence |
| `commercial-restricted` | Paid licence with display, retention or mixing limits | AeroAPI, AeroDataBox | TTL per contract | Per contract |

## Card template

```markdown
# <Source name>

| Field | Value |
|---|---|
| id | e.g. `bts_ontime_reporting` |
| publisher / URL / docs | … |
| licence class / licence / attribution text | … |
| access | bulk file / REST / stream; auth; rate limits |
| history | start date, gaps |
| cadence / latency | how often it updates; how late it lands |
| knowledge-time rule | when a row could have been known (e.g., "issuance time + 10 min") |
| retention | permanent / TTL n days (licence) |
| used for | training / real time / display |
| known issues | regime breaks, quality problems |
| verified on | YYYY-MM-DD (terms and prices re-checked) |
```

## Cards

Cards to write in Phase 0, prioritized by Phase 1 needs:

- BTS On-Time (reporting carrier and marketing carrier)
- FAA ATCSCC advisories
- FAA NAS Status
- IEM METAR/TAF/MOS
- NBM
- LAMP
- HRRR
- CBP Airport Wait Times
- adsb.lol
- D-ATIS
- FAA aircraft registry
