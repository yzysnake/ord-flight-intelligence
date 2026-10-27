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

| Card | Licence class | Training | Real time | First used |
|---|---|---|---|---|
| [BTS On-Time: reporting carrier](bts_ontime_reporting.md) | `public-domain` | ✓ labels | – | Phase 1a |
| [BTS On-Time: marketing carrier](bts_ontime_marketing.md) | `public-domain` | ✓ labels | – | Phase 1a |
| [FAA ATCSCC advisories](faa_atcscc_advisories.md) | `public-domain` | ✓ (2001 →) | ✓ | Phase 1a |
| [FAA NAS Status](faa_nas_status.md) | `public-domain` | self-archive | ✓ | Phase 1a |
| [IEM ASOS/METAR](iem_asos_metar.md) | `public-domain` | ✓ (1946 →) | ✓ | Phase 1a |
| [IEM TAF](iem_taf.md) | `public-domain` | ✓ (1996 →) | ✓ | Phase 1a |
| [IEM MOS (GFS; legacy NAM)](iem_mos.md) | `public-domain` | ✓ (2003 →) | ✓ | Phase 1b |
| [LAMP station guidance](mdl_lamp.md) | `public-domain` | ✓ (2006 →) | ✓ | Phase 1b |
| [National Blend of Models](noaa_nbm.md) | `public-domain` | ✓ (2020 →) | ✓ | Phase 1b |
| [HRRR](noaa_hrrr.md) | `public-domain` | ✓ (2014 →) | ✓ | Phase 1b |
| [SPC convective outlooks](iem_spc_outlooks.md) | `public-domain` | ✓ (1987 →) | ✓ | Phase 1b |
| [CBP Airport Wait Times](cbp_awt.md) | `public-domain` (provisional) | ✓ (2023-05 →) | lagged ≈ 2 d | Phase 1a (archive) / Phase 2 |
| [adsb.lol](adsblol.md) | `open-share-alike` (ODbL) | ✓ (2023 →) | ✓ | Phase 1a (archive) / Phase 2 |
| [D-ATIS via atis.info](atis_info_datis.md) | `non-commercial` (provisional) | self-archive | ✓ | Phase 1a (archive) |
| [FAA aircraft registry](faa_aircraft_registry.md) | `public-domain` | reference | – | Phase 1a |

**Provisional classes.** When a provider publishes no terms, classify it as `non-commercial`, or as `public-domain` for clearly federal works, until the terms are confirmed. Keep an open question on the card.

**Not yet carded** (add before first use): BTS T-100 / DB1C / B-43, TSA throughput, Chicago Data Portal trips, CTA/Metra, routing provider, OpenStreetMap, GOES GLM / MRMS, OpenSky (research only), any licensed status API.
