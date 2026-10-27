# airportsdata (airport reference: coordinates and time zones)

| Field | Value |
|---|---|
| id | `airportsdata` |
| publisher / URL / docs | [airportsdata](https://github.com/mborsetti/airportsdata) Python package (conda-forge / PyPI) |
| licence class / licence / attribution | `public-domain`-equivalent for our use: the package and its data are **MIT**-licensed. Keep the MIT notice if the table is redistributed |
| access | Installed package; `airportsdata.load("IATA")` returns ≈ 7,900 airports with IATA code, name, city, country, coordinates, elevation and an **IANA time zone**; `load("LID")` returns ≈ 12,600 airports keyed by FAA location identifier |
| history | Reference data (current snapshot; versioned by package release, e.g. 20260905) |
| cadence / latency | Package releases every few weeks to months |
| knowledge-time rule | Not applicable (static reference); the package version is pinned in `conda-lock.yml` |
| retention | Not stored separately: it ships with the environment |
| used for | Time zones for converting BTS local `hhmm` times to UTC (`ordfi.timeutil.airport_timezones`) |
| known issues | BTS uses FAA location identifiers for airports without an IATA code (**TKI**, McKinney, TX) and for Palm Beach since 2026 (**DJT**; IATA `PBI`), so lookups fall back from IATA to LID. Codes in neither table go in `TIMEZONE_OVERRIDES`: currently only **ISN** (Williston, ND; closed 2019). 419 codes have different zones in the two tables (e.g. `AAA` is Anaa, Tahiti, as IATA but Logan County, IL, as LID); IATA wins, and none of them occurs in BTS data |
| verified on | 2026-10-27 (all 404 airport codes in BTS 2015-01..2026-08, both tables, resolve) |
