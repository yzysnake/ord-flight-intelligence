# Digital ATIS via atis.info

| Field | Value |
|---|---|
| id | `atis_info_datis` |
| publisher / URL / docs | atis.info (operator and upstream source unpublished; formerly `datis.clowd.io`, which now redirects). Endpoints: `https://atis.info/api/KORD`, `/api/stations` (≈ 70 US airports, incl. KORD and KMDW) |
| licence class / licence / attribution | `non-commercial` (**provisional: no published terms**). Research archiving only; raw text is not displayed publicly until the operator confirms |
| access | Anonymous JSON: `{"airport","type","code","datis","time","updatedAt"}` |
| history | None: self-archive |
| cadence / latency | ATIS updates about hourly plus specials; poll every 5 min |
| knowledge-time rule | `updatedAt` (or our fetch time) |
| retention | Permanent for research use (raw text); parsed runway configuration permanent |
| used for | Runway configuration labels and features (arrival and departure runways, approach types), e.g. "ARR EXP VECTORS ILS RWY 10C APCH … DEPS EXP RWYS 9C … 10L" |
| known issues | Free-text parsing; unknown provenance and reliability. **The official route is FAA SWIM STDDS (TDLS)**; migrate when SWIM access is approved |
| verified on | 2026-10-26 (endpoint HEAD-checked; content per research study §4.5) |

## Open questions

- Contact the operator about terms, upstream source and acceptable polling rate.
