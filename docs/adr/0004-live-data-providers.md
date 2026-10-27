# ADR-0004: Live data providers

- **Status:** Accepted (PR #1)
- **Date:** 2026-10-26

## Context

**What the live product needs** (research study §4–5, §10):

- airport state: programs, runway configuration, arrival rate;
- aircraft positions and takeoff/landing times for *all* operators, including international flights;
- optionally gates, terminals and airline estimates;
- customs-wait priors;
- drive times (Phase 2).

**Constraints:**

- public display on a website;
- licence **retention** and **no-mixing** clauses (FlightAware AeroAPI: raw data ≤ 30 days, no use "in conjunction with" other real-time feeds; Flightradar24: ≤ 30 days, no backfill, no "competing services");
- OpenSky requires a written licence for **any** live product;
- ODbL share-alike;
- FAA LADD privacy filtering;
- a Phase 2 budget of about $0–100/month;
- no single-vendor dependency.

## Options considered

The source research is in study §4.5–4.6. In short:

- **Free public sources:** FAA NAS Status, ATCSCC, FAA SWIM, D-ATIS (atis.info), adsb.lol, CBP AWT, AWC.
- **Community ADS-B under non-commercial terms:** OpenSky, airplanes.live, adsb.fi, ADS-B Exchange Community.
- **Commercial providers:** AeroDataBox, AeroAPI, FR24, Cirium, OAG.

## Decision

| Function | Choice | Terms we commit to |
|---|---|---|
| Airport state | **FAA NAS Status XML** (primary) + **NAS Status `/api/airport-events` JSON** (runway configuration and arrival rate, supplementary) + **ATCSCC advisories** | Public domain. Archive permanently. Treat the undocumented JSON as fragile and monitor its schema |
| Runway in use (text) | **atis.info D-ATIS** for research archiving only | No published terms: classed as `non-commercial` until the operator confirms. Raw text is not displayed publicly. Migrate to **FAA SWIM (STDDS/TDLS)** once approved |
| Aircraft positions and events | **adsb.lol** (live API + daily GitHub archives) | ODbL: attribution, and share-alike for any published derived database. Contact the maintainer before production use, as they request. Filter LADD aircraft from any display using its `/v2/ladd` list |
| Research-only ADS-B | **OpenSky** (historical database, only if eligible for academic access); **ADS-B Exchange** free monthly samples for prototyping | Never in the live product or public outputs without a written licence |
| Flight status, gates, schedules | **None in Phase 1.** In Phase 2, evaluate an **AeroDataBox** airport board (≈ $15–40/month) after licence review | Display-time use only; TTL ≤ 7 days; never used to build training archives |
| Flight-level public archive | **Apply now for FAA SWIM** (TFMS, TBFM, STDDS); adopt in Phase 3 | Free; approval required; "not intended for NAS-impacting usage"; LADD filtering |
| Customs | **CBP Airport Wait Times** (undocumented JSON), daily pull | Public domain (provisional). Archive permanently, because the window rolls |
| Routing (Phase 2) | **Mapbox Directions** (traffic-aware) on the free tier; Google Routes as fallback | Confirm caching and storage terms before integration. Routing results are never archived |
| Rejected or deferred | **AeroAPI** (deferred: Personal tier is personal/academic only; the no-mixing clause conflicts with ADS-B use); **FR24 API** (rejected: no schedules; competing-services clause); **airplanes.live / adsb.fi** (non-commercial; airplanes.live now gated); **CDA flychicago JSON** (not used without written CDA permission) | – |

## Consequences

**Easier:**

- Phases 1–2 run with **$0 data cost**.
- Every source shown publicly is public domain or ODbL.
- The project's permanent archive contains only data it is allowed to keep.

**Harder:**

- Without airline status feeds we must map ADS-B callsigns to flight numbers, including regional and codeshare operators. Mapping tables come from BTS schedules.
- The Pickup Planner beta works at terminal level unless the AeroDataBox evaluation passes licence review.
- Any **published** derived ADS-B dataset (for example, ORD landing times) must be released under ODbL, separately from other data.
- adsb.lol is a single community provider. The adapter interface keeps a switch to a licensed source (ADS-B Exchange Enterprise, or an OpenSky licence) possible.

**Actions:**

- The project owner applies for FAA SWIM access and, if eligible, OpenSky's academic database access.
- Email adsb.lol and the atis.info operator about production use.
- Verify Mapbox caching terms at the start of Phase 2.

**Revisit:**

- before any public launch (Phase 3 go/no-go);
- whenever a provider changes terms or pricing;
- if a value-of-information ablation (study §6.5) shows a licensed feed would materially improve accuracy.

## References

- Research study §4.2, §4.5–4.6, §11.3.
- Data-catalog cards: [`docs/data-catalog/`](../data-catalog/README.md).
