# CBP Airport Wait Times (ORD Terminal 5)

| Field | Value |
|---|---|
| id | `cbp_awt` |
| publisher / URL / docs | US Customs and Border Protection. [awt.cbp.gov](https://awt.cbp.gov/) (React app; no API documentation) |
| licence class / licence / attribution | `public-domain` (provisional: federal work; no AWT-specific terms page found [U]) |
| access | **Undocumented JSON endpoints** used by the site: `GET /api/airport` (airport and terminal list), `GET /api/waitTime` (list + `FlightDateRange`), `POST /api/waitTime` with `{"Id":"A392","FromDate":"YYYY-MM-DD","ToDate":"YYYY-MM-DD"}`. **ORD = `A392`, Terminal 5 only** (MDW = `A398`) |
| history | **2023-05-03 →**, a rolling window of about 3.5 years. Older data likely requires FOIA [U] |
| cadence / latency | Hourly rows, published about 1.5–2 days later (`LastUpdated`) |
| knowledge-time rule | `LastUpdated` (or our fetch time if earlier) |
| retention | **Permanent: archive daily, because the window rolls off** |
| used for | Customs-processing priors for international pickups at T5: waits by hour, weekday, season and citizenship, scaled by scheduled international arrivals |
| known issues | Times "do not include time to retrieve baggage or navigate through the airport". Hours with no arrivals are omitted. **Structural break:** Enhanced Passenger Processing (May 2025) cut US-citizen processing from about 60 s to about 10 s (74 % lower waits reported). The endpoints are undocumented and may change |
| verified on | 2026-10-26 (research study §4.4) |

**Fields per hour:**

- `FlightDate`, `HourRange`
- `AverageWait`, `MaxWait`
- `UsaPassenger{AverageWait,MaxWait,Count}`, `NonUsaPassenger{…}`
- `GlobalEntryPassengerCount`
- wait buckets: 0–15, 16–30, 31–45, 46–60, 61–90, 91–120, 121+
- `ExcludedPassengerCount`, `TotalPassengerCount`, `FlightCount`, `BoothsUsed`, `LastUpdated`

## Ingestion notes

- Make one POST per day covering the trailing 7 days, upsert by (date, hour), and log revisions.
- Use a polite, descriptive User-Agent.

## Collection

- Archived continuously by `ordfi.collector` since 2026-10-27, as daily `snapshots.jsonl` (changes only) and `polls.jsonl` (every poll) under `data/raw/cbp_awt/ord_t5/`. See `infra/README.md`.
