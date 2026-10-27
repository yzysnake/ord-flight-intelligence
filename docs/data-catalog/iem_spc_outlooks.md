# SPC convective outlooks (via IEM)

| Field | Value |
|---|---|
| id | `iem_spc_outlooks` |
| publisher / URL / docs | NOAA Storm Prediction Center; archived by IEM. [Outlook archive](https://mesonet.agron.iastate.edu/request/gis/outlooks.phtml); as-of point API `/api/1/nws/outlook_by_point.json?lat=41.96&lon=-87.93&valid=<ISO8601>` |
| licence class / licence / attribution | `public-domain` |
| access | Point API (as-of queries) and GIS downloads, which are limited to 10 single outlook type-years per request |
| history | Convective outlooks **1987 →**; WPC excessive-rainfall outlook from 2015-11 |
| cadence / latency | About 5 Day-1 issuances per day; Day-2 and Day-3 outlooks less often |
| knowledge-time rule | Product issuance time (`product_issue` / `PRODISS`) + 5 min |
| retention | Permanent |
| used for | 6–72 h thunderstorm-risk features for the airport-level Outlook (risk category, probabilities at ORD) |
| known issues | Duplicate issuances: IEM flags the official one (`CYCLE=20` vs −1). **"SIGN" hatching was replaced by CIG1–3 conditional-intensity groups around 2026-03-02**, a category regime break |
| verified on | 2026-10-26 (research study §4.3) |
