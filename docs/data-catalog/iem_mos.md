# IEM MOS archive (GFS MOS; legacy NAM MOS)

| Field | Value |
|---|---|
| id | `iem_mos` |
| publisher / URL / docs | Iowa Environmental Mesonet. [MOS archive](https://mesonet.agron.iastate.edu/mos/); API `/api/1/mos.json?station=KORD&model=<MODEL>&runtime=<ISO8601>` (up to 6 stations per request) |
| licence class / licence / attribution | `public-domain` (IEM terms) |
| access | JSON API (one run per request) and CSV `/cgi-bin/request/mos.py?station=KORD&model=<MODEL>&sts=…&ets=…&format=csv` (a month of runs, about 250 KB). IEM answers HTTP 429 when asked faster than about one request per second; the ingest pauses 3 s. Model codes: `AVN`, `GFS`, `ETA`, `NAM`, `NBS`, `NBE`, `ECM`, `LAV`, `MEX`. IEM leaves out elements that are empty in a month, so CSV columns vary |
| history | AVN 2000-06 → 2003-12-16, then **GFS 2003-12-16 →**. ETA 2002-02-24 → 2008-12-09, then NAM 2008-12-09 → **2026-11-03 (scheduled retirement)**. IEM also stores NBS from 2018-11-07 and LAV (LAMP) from 2020-07-12 (4 cycles/day only) |
| cadence / latency | 4 cycles per day (GFS 00, 06, 12, 18Z; IEM's NBS copy 01, 07, 13, 19Z), 3-hourly projections to 72 h |
| knowledge-time rule | Run time + 5 h (conservative estimate [U]; measure live) |
| retention | Permanent |
| used for | **Ingested** (`ordfi.ingest.mos`, `make ingest-mos`; dbt `gfs_mos`, `nbm`): GFS MOS from 2014-12 and NBS from 2018-11, for ORD. GFS MOS is the long-baseline stack for 6–72 h features across the whole training window: ceiling and visibility categories, thunder, precipitation and precipitation-type probabilities. NBS adds IFR probabilities, 3-hour thunder and gusts from 2018 |
| known issues | **NBS codes change with NBM's versions** (see the `noaa_nbm` card); decoded in dbt `nbm`. IEM's month files also hold the next month's first run, and 2018 files repeat some rows identically; staging keeps one row per run and projection. **Validated:** GFS MOS flight categories at up to 12 h agree with ORD's METAR 83.2 % of the time, and its 6-hour thunder probabilities are reliable (34 % forecasts verified 32 %, 54 % verified 55 %). NAM MOS ends 2026-11-03 (NWS SCN 26-47). The effect of the GFS v17 changes on MOS is unknown [U]. For hourly LAMP history use `mdl_lamp` (MDL archive), not IEM's 4-cycle copy |
| verified on | 2026-10-28 (CSV service, throttle, NBS cycles and history start checked by request) |
