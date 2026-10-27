# FAA NAS Status

| Field | Value |
|---|---|
| id | `faa_nas_status` |
| publisher / URL / docs | FAA. [nasstatus.faa.gov](https://nasstatus.faa.gov/); [user guide](https://nasstatus.faa.gov/static/media/NASStatusUserGuide.cccc6d48.pdf) |
| licence class / licence / attribution | `public-domain` (FAA) |
| access | **Documented XML:** `https://nasstatus.faa.gov/api/airport-status-information`. **Undocumented JSON:** `https://nasstatus.faa.gov/api/airport-events`, which adds `airportConfig` (arrival and departure runways, arrival rate) for airports with active events. No key |
| history | **None published: self-archive from day one** |
| cadence / latency | Updates every minute; delays are tracked in 15-minute increments |
| knowledge-time rule | Our fetch time (`observed_at`). Also keep the feed's `Update_Time` |
| retention | Permanent. Store a payload only when it changes, plus an hourly heartbeat |
| used for | Real-time features (GDP average/max delay and reason, ground stops, arrival/departure delay trend, closures, deicing, runway configuration, arrival rate); the "ORD Today" display; the live label archive |
| known issues | The JSON is undocumented and may change without notice. Its `airportConfig` appears only while an airport has active events. Legacy ASWS endpoints (`services.faa.gov`, `soa.smext.faa.gov/asws`) are dead |
| verified on | 2026-10-26 (XML HEAD-checked; JSON fields per the research study §4.2) |

## Ingestion notes

- The collector polls both endpoints every 60 s with a descriptive User-Agent.
- Validate the schema on every poll and alert on drift.
- Parse into `atc_program` and `runway_config` with `known_time = observed_at`.
