# airportsdata (airport reference: coordinates and time zones)

| Field | Value |
|---|---|
| id | `airportsdata` |
| publisher / URL / docs | [airportsdata](https://github.com/mborsetti/airportsdata) Python package (conda-forge / PyPI) |
| licence class / licence / attribution | `public-domain`-equivalent for our use: the package and its data are **MIT**-licensed. Keep the MIT notice if the table is redistributed |
| access | Installed package; `airportsdata.load("IATA")` returns ≈ 7,900 airports with IATA code, name, city, country, coordinates, elevation and an **IANA time zone** |
| history | Reference data (current snapshot; versioned by package release, e.g. 20260905) |
| cadence / latency | Package releases every few weeks to months |
| knowledge-time rule | Not applicable (static reference); the package version is pinned in `conda-lock.yml` |
| retention | Not stored separately: it ships with the environment |
| used for | Time zones for converting BTS local `hhmm` times to UTC (`ordfi.timeutil.airport_timezones`) |
| known issues | Codes BTS uses but airportsdata lacks are handled in `TIMEZONE_OVERRIDES`. Currently only **DJT** (Palm Beach, FL; BTS's code in 2026 data, formerly PBI) |
| verified on | 2026-10-27 (all airports in BTS Jul–Aug 2026 resolve) |
