# IEM MOS archive (GFS MOS; legacy NAM MOS)

| Field | Value |
|---|---|
| id | `iem_mos` |
| publisher / URL / docs | Iowa Environmental Mesonet. [MOS archive](https://mesonet.agron.iastate.edu/mos/); API `/api/1/mos.json?station=KORD&model=<MODEL>&runtime=<ISO8601>` (up to 6 stations per request) |
| licence class / licence / attribution | `public-domain` (IEM terms) |
| access | JSON API and CSV; same throttle as other IEM APIs. Model codes: `AVN`, `GFS`, `ETA`, `NAM`, `NBS`, `NBE`, `ECM`, `LAV`, `MEX` |
| history | AVN 2000-06 → 2003-12-16, then **GFS 2003-12-16 →**. ETA 2002-02-24 → 2008-12-09, then NAM 2008-12-09 → **2026-11-03 (scheduled retirement)**. IEM also stores NBS from 2018-11-07 and LAV (LAMP) from 2020-07-12 (4 cycles/day only) |
| cadence / latency | 4 cycles per day |
| knowledge-time rule | Run time + 5 h (conservative estimate [U]; measure live) |
| retention | Permanent |
| used for | The long-baseline forecast stack for 24–72 h features before NBM exists (2003 → 2020): ceiling, visibility, thunder and precipitation-type guidance |
| known issues | NAM MOS ends 2026-11-03 (NWS SCN 26-47). The effect of the GFS v17 changes on MOS is unknown [U]. For hourly LAMP history use `mdl_lamp` (MDL archive), not IEM's 4-cycle copy |
| verified on | 2026-10-26 (research study §4.3) |
