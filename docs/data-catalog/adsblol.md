# adsb.lol (ADS-B positions and history)

| Field | Value |
|---|---|
| id | `adsblol` |
| publisher / URL / docs | adsb.lol (community network). [API spec](https://api.adsb.lol/api/openapi.json), [API docs](https://www.adsb.lol/docs/open-data/api/), [2026 archive](https://github.com/adsblol/globe_history_2026) (also 2023–2025 repositories) |
| licence class / licence / attribution | `open-share-alike`: **ODbL** for the API and data (some archives are also marked CC0). Attribution: "Contains data from adsb.lol, available under the ODbL". Any **published derived database** must also be ODbL |
| access | REST API: anonymous today. API keys are planned, and production users are asked to contact the maintainer. Queries by hex, callsign, registration or type; point radius ≤ 250 nm; routeset; `/v2/ladd`; `/v2/pia`. History: daily global archives as GitHub releases |
| history | **2023 →** (≈ 1–2 TB per year globally; filter to the ORD region on ingest). No 2022 repository |
| cadence / latency | Live positions within seconds; daily archive releases |
| knowledge-time rule | Live: position timestamp + 5 s. Archive reconstruction: an event is known at its occurrence time (+ processing lag measured live) |
| retention | Raw tracks for the ORD box (≈ 100 nm): 30–90 days. Derived events (takeoff, landing, runway, holding, go-around, gate proxy): permanent |
| used for | Takeoff and landing ground truth for **all** operators (incl. international), en-route ETA features, runway-use inference, taxi-time estimates where ground coverage allows |
| known issues | **Does not filter LADD aircraft.** Use its `/v2/ladd` list to remove them from any display. Coverage gaps and MLAT quality vary. Callsign ↔ flight-number mapping is needed (regional and codeshare operators, alphanumeric callsigns). It is a single community provider, so keep the adapter swappable (ADR-0004) |
| verified on | 2026-10-26 (research study §4.5) |

## Ingestion notes

- The live collector polls a point-radius query around ORD every 5–10 s and writes raw JSON lines.
- A daily job derives events.
- History: download only the needed daily releases, stream-filter to the ORD region, and discard the global files.

## Open questions

- Email the maintainer about production use, rate limits and key timing.
