# ORD Flight Intelligence: Research and Feasibility Study

**Predicting delays and improving the airport experience at Chicago O'Hare (ORD)**

*Version 1.0, 26 October 2026. Prepared for github.com/yzysnake (planning phase). Research only: no code was written, no data was collected, and no repository or environment was created.*

---

### How to read this report

- **Scope.** This report answers the ten deliverables of the project brief:
  - §1 executive summary
  - §2 ORD operations
  - §3 use cases
  - §4 data sources
  - §5 feature matrix
  - §6 modeling
  - §7 architecture
  - §8 competition
  - §9 directions compared
  - §10 MVP
  - §11 roadmap

  §12 covers the GitHub/environment plan. §13 lists unknowns and challenges to the brief.
- **Evidence.** Claims link directly to primary sources (BTS/TranStats, DOT, FAA, Federal Register, NOAA/NWS, CBP, TSA, City of Chicago, CDA, peer-reviewed papers, official product pages). Sources were checked in October 2026.
  - Most figures were verified on the linked page during this research.
  - **[S]** marks secondary-source-only claims.
  - **[U]** marks unverified claims or inferences.
  - Some government sites (bts.gov, faa.gov, transportation.gov) block automated access. For those, figures were taken from TranStats, ROSA P archives, govinfo.gov, or archived copies of the same official pages.
- **Volatility.** Prices, API terms and operational rules changed repeatedly in 2025–26: the FAA ORD cap, Spirit's shutdown, Southwest's exit from ORD, Amadeus decommissioning its APIs, and NOAA model retirements. Re-verify anything cost- or terms-related before building.

### Contents

- [1. Executive summary](#1-executive-summary)
- [2. ORD operational analysis: what actually causes disruption](#2-ord-operational-analysis-what-actually-causes-disruption)
- [3. Stakeholder and use-case analysis](#3-stakeholder-and-use-case-analysis)
- [4. Data source inventory](#4-data-source-inventory)
- [5. Feature feasibility matrix](#5-feature-feasibility-matrix)
- [6. Data science and modeling strategy](#6-data-science-and-modeling-strategy)
- [7. Data engineering and platform architecture](#7-data-engineering-and-platform-architecture)
- [8. Competitive landscape and differentiation](#8-competitive-landscape-and-differentiation)
- [9. Project directions compared](#9-project-directions-compared)
- [10. MVP proposal](#10-mvp-proposal)
- [11. Development roadmap](#11-development-roadmap)
- [12. GitHub organization and development environment (plan only; nothing created)](#12-github-organization-and-development-environment-plan-only-nothing-created)
- [13. Challenging the brief: unknowns, questionable assumptions and further research](#13-challenging-the-brief-unknowns-questionable-assumptions-and-further-research)
- [Appendix A. Reproducing the headline BTS figures](#appendix-a-reproducing-the-headline-bts-figures)
- [Appendix B. Selected primary sources](#appendix-b-selected-primary-sources)
- [Appendix C. Glossary](#appendix-c-glossary)
- [Appendix D. How this research was done](#appendix-d-how-this-research-was-done)

---

## 1. Executive summary

### 1.1 What to build, why, and for whom

**Recommendation.** Build *ORD Flight Intelligence* as a **transparent, ORD-specific decision tool, not a flight tracker**. Sequence it in two releases.

1. **v0.1 "ORD Outlook & Reliability Lab"** (public data only). Four parts:
   - calibrated 1–72-hour forecasts of airport-level disruption ("will ORD have a bad afternoon?", P(ground delay program or ground stop), expected cancellation rate) with plain-language drivers;
   - a historical reliability explorer for flights, routes, airlines and hours, including historical connection-pair reliability;
   - research write-ups explaining ORD's delays;
   - a **public track record** of the project's own forecast accuracy.
2. **v0.2 "Pickup Planner"** (live beta). It estimates **when an arriving passenger will actually be at the curb**, domestic or Terminal 5 international, and tells the person picking them up when to leave home or the cell-phone lot.

**For whom:**

- people picking up ORD arrivals (core segment; unserved);
- ORD travelers on high-risk days who must decide whether to rebook or leave early;
- journalists and researchers;
- later, self-transfer connectors and limo dispatchers.

**Why this, and not a general delay predictor:**

1. **The ORD problem is real, current and explainable.**
   - ORD ranks **24th–25th of 30 major US airports** for on-time departures and arrivals (71 %) and 24th for cancellations (2.80 %) over Sep 2025 – Aug 2026.
   - In 2023 it *beat* the national average (79.2 % vs. 78.3 %). The decline is recent and has identifiable causes.
2. **The causes are mostly the system, not the airlines.**
   - ORD's excess delay is FAA "NAS" delay, plus cancellations. NAS delay hit 9.5 % of ORD arrivals vs. 6.3 % nationally in 2025.
   - Behind it: a **10.5 % surge in operations in 2025 to 857 k, the most of any airport in the world**, driven by the United–American capacity contest; airfield construction; and summer storms.
   - The FAA responded with a **2,708-operations/day cap** (June 2026 → 30 Oct 2027), stating that "surface constraints at ORD are the limiting factor".
   - Airport-level disruption is exactly what can be forecast and explained with public data.
3. **Free public data supports leakage-safe training.**
   - BTS flight-level outcomes with tail numbers (1987 →).
   - Archived weather *forecasts* as they existed at the time: TAF 1996 →, LAMP 2006 →, HRRR 2014 →, NBM 2020 →.
   - FAA traffic-management advisories back to 2001.
   - CBP hourly Terminal 5 customs waits (2023 →).
   - Open ADS-B archives (2023 →).

   Almost every core input is public domain or openly licensed.
4. **Prediction realism favors this scope.**
   - Honest chronological evaluations show flight-level delay prediction from schedule and weather alone is weak (AUC ≈ 0.56–0.62).
   - Airport-level capacity outcomes are far more predictable, and en-route ETA is the most mature target. The en-route ETA is the foundation of the Pickup Planner.
5. **The market gap is narrow but real.**
   - Flighty, FlightAware and the United app already cover tracking, inbound aircraft, delay predictions and connection guidance.
   - Nobody estimates **gate-to-curb timing**, nobody publishes **calibration of their probabilities**, and nobody explains **ORD's disruption in context**.
   - A consumer business is unlikely; a credible public-interest data product and portfolio piece is very achievable.

### 1.2 Key findings at a glance

| Area | Finding |
|---|---|
| ORD vs. peers | On-time arrivals: ORD 74.5 % (2019) → **79.2 % (2023, 4th of 15 large peers)** → 77.9 % (2024) → 73.0 % (2025) → **70.2 % (Jan–Aug 2026, 13th of 15)**. National: 79.0 → 78.3 → 78.1 → 76.4 → 74.7 % |
| Delay causes | ORD's gap is **NAS delay + cancellations**. Carrier-caused and late-aircraft delay are at or below national. **Volume** makes up 44–51 % of ORD's ATC-attributed delay (2023–25), the highest of nine airports checked in 2024–25 |
| Delay severity | 21.2 delay minutes per scheduled arrival vs. 16.1 nationally (2025). The average delayed ORD arrival runs 80–96 min |
| Capacity | 8 runways after the O'Hare Modernization Program. The capacity breakpoints are ceiling/visibility ≥ 5,500 ft & 7 mi and < 1,000 ft or 3 mi. Wind forces east or west flow ~47 % of the time; a flow change "can take an hour or more" |
| Surface | Extra taxi-out time of 9.5 min per departure, **3rd worst of 34 US airports** (2022). Construction removed instrument approaches and taxiways in 2025–26 |
| Structure | **Two comparable-size hub carriers** (United ≈ 47 %, American ≈ 33 % on a marketing basis [S]), **≈ 49 % of domestic arrivals flown by regional partners**, ≈ 99 passengers per movement (ATL ≈ 132). Spirit (shut down May 2026) and Southwest (left ORD Jun 2026) exited |
| Time patterns | Summer evening collapse: 22:00 departures **23.5 % on time** in Jul 2024 (30-airport average 49.6 %). Summer convection and winter storms dominate the worst months |
| Data | BTS lags 6–8 weeks; excludes international and foreign carriers; excludes cancellations decided > 7 days out. The cause-code taxonomy changes for flights from **1 Jan 2027** (Section 511(b)). DB1B ended mid-2025 (now DB1C) |
| Live data | Free: FAA NAS Status (incl. runway configuration and AAR when programs are active), ATCSCC advisories, D-ATIS, adsb.lol ADS-B (ODbL). Licensed: gates, airline ETAs, schedules. AeroDataBox board ≈ $15–40/mo; AeroAPI board ≈ $400–1,100/mo with ≤ 30-day storage and no mixing with other feeds; OpenSky bars live products without a licence |
| Competition | Flighty (delay predictions; Connection Assistant, Jul 2026), United app (walk times, ConnectionSaver, TSA waits at hubs, Sep 2026), FlightAware (free inbound tracking). **Unserved:** curb-ready timing, published calibration, ORD-specific explanation |
| Modeling | GBDTs (CatBoost/LightGBM) won both NASA challenges that included KORD. Use ordered-bucket and quantile GBDTs with conformal intervals, rolling-origin backtests and Brier/CRPS skill vs. climatology |
| Cost | Phase 1 ≈ $0–15/mo; live beta ≈ $10–100/mo; a commercial-data public launch ≈ $250–2,500+/mo, dominated by licensing |

### 1.3 Biggest risks and unknowns

1. **Live data licensing**, not engineering, is the binding constraint for any public live feature:
   - storage limits (≤ 30 days, or none);
   - no-mixing clauses (AeroAPI, FR24);
   - OpenSky's live-use ban;
   - ODbL share-alike.
2. **Regime shifts** in the training data:
   - COVID; runway openings (2020–21); Nov 2025 shutdown cuts;
   - the **2026–27 FAA cap**; Spirit and Southwest exits; continuing construction;
   - the 2027 BTS cause-code change;
   - NOAA's RRFS transition on 3 Nov 2026.
3. **Unobservable passenger segments** (deplaning, bags, curb) need a deliberate measurement and feedback program before Pickup Planner claims can be validated.
4. **Federal data fragility.** 2025–26 shutdowns, staffing cuts at BTS, and service retirements argue for mirroring every source.
5. **Fast followers.** Visible features can be copied. The durable assets are ORD-specific data (live archive, curb-time feedback) and transparency.

### 1.4 Decision requested and immediate next steps

If you approve the direction, implementation starts with **Phase 0** (§11): repository and Conda environment per §12, data-catalog cards with licence classes, and three architecture decisions (storage, orchestrator, ADS-B/status provider). **Phase 1a** follows. It ingests BTS and weather history, and **starts the free live archivers in its first week**: NAS Status, ATCSCC, METAR/TAF/NBM/LAMP, adsb.lol landings, D-ATIS and CBP AWT. Those snapshots cannot be recovered later.

---

## 2. ORD operational analysis: what actually causes disruption

### 2.1 Bottom line

- **ORD's poor reputation is period-dependent.** In 2023 ORD *beat* the national on-time arrival rate (79.2 % vs. 78.3 %) and ranked 4th of 15 large peers. Since mid-2025 it has been in the bottom fifth. Over Sep 2025 – Aug 2026, BTS ranks ORD **24th of 30 major airports for departures (71 % on time), 25th for arrivals (71 %), 24th for cancellations (2.80 %)**, and 27th for average arrival delay (91 min per delayed arrival) ([BTS airport profile](https://www.transtats.bts.gov/airports.asp?20=E&Nv42146=beQ&Nv42146_anzr=Puvpnt1%2C+VY%3A+Puvpnt1+bUn4r+V06r40n6v10ny&pn44vr4=SNPgf)).
- **The gap is the system, not the airlines.** ORD's excess delay is *National Aviation System* (NAS) delay (airfield, airspace, volume, non-extreme weather) plus cancellations. Carrier-caused and late-aircraft delay at ORD are at or below national rates.
- **Demand pressure plus construction explain 2025–26.**
  - Tower-counted operations rose **+10.5 % in 2025 to 857,392**, the most of any airport in the world. This happened during the United–American gate and capacity contest.
  - Airfield construction removed instrument approaches and taxiways.
  - The FAA responded with a **2,708-operations-per-day cap** (June 2026 → 30 Oct 2027), stating that "surface constraints at ORD are the limiting factor and represent a lower total airport capacity than the runway system, alone" ([FAA order, 91 FR 21071](https://www.govinfo.gov/content/pkg/FR-2026-04-20/pdf/2026-07665.pdf); [extension](https://www.govinfo.gov/content/pkg/FR-2026-07-14/pdf/2026-14147.pdf)).
- **Weather is an amplifier, not ORD's unique flaw.** Summer convection and isolated winter storms create the worst days. The weather share of ORD delay roughly equals the national share in normal years.

### 2.2 How ORD compares

**On-time arrival % (and cancellation %) of scheduled arrivals.** Source: BTS TranStats cause-of-delay pages (reporting, marketing and codeshare carriers). The national series matches DOT's headline series (78.10 % in 2024, 78.34 % in 2023).

| Airport | 2019 | 2023 | 2024 | 2025 | 2026 Jan–Aug |
|---|---|---|---|---|---|
| National | 78.97 (1.90) | 78.34 (1.29) | 78.10 (1.36) | 76.42 (1.53) | 74.66 (2.27) |
| **ORD** | **74.53 (3.37)** | **79.17 (1.33)** | **77.86 (1.41)** | **72.95 (1.84)** | **70.22 (3.27)** |
| ATL | 85.06 (0.63) | 82.41 (0.87) | 81.62 (1.05) | 79.64 (1.55) | 78.69 (2.14) |
| DFW | 77.07 (2.70) | 77.29 (1.62) | 74.00 (1.93) | 72.75 (2.83) | 75.14 (3.12) |
| DEN | 77.68 (2.18) | 77.10 (1.53) | 80.10 (1.27) | 75.41 (0.85) | 77.13 (0.95) |
| JFK | 78.26 (1.63) | 74.25 (2.37) | 77.03 (1.91) | 75.43 (2.40) | 71.40 (5.35) |
| EWR | 66.01 (3.17) | 75.94 (3.03) | 76.20 (2.63) | 70.00 (2.81) | 75.08 (4.17) |
| LGA | 70.44 (2.85) | 78.22 (2.73) | 78.36 (2.32) | 71.75 (3.12) | 67.52 (6.37) |
| SFO | 72.22 (2.16) | 76.08 (1.09) | 68.89 (1.38) | 75.05 (0.86) | 61.72 (1.16) |
| MSP | 83.38 (1.03) | 83.97 (1.22) | 81.12 (0.90) | 80.16 (0.86) | 79.56 (1.63) |
| MDW | 80.10 (3.93) | 78.51 (1.44) | 79.89 (1.20) | 78.92 (1.14) | 72.45 (1.57) |
| *ORD rank among 15 large peers (on time)* | *12* | ***4*** | *8* | *12* | *13* |

The 15-peer set also includes LAX, CLT, IAH, MCO and LAS. Snapshots that cut against the stereotype: Cirium ranked ORD **6th of 20 global airports** for departure on-time in Dec 2023 (85.1 %), and in Jul 2024 ORD arrivals (68.6 % on time) beat ATL (63.9 %) and DFW (66.6 %) in DOT's monthly report.

**Delays at ORD are longer.** The average delayed ORD arrival runs 80–96 min, against 70–75 min nationally. In 2025 ORD accrued **21.2 delay minutes per scheduled arrival** vs. 16.1 nationally (ATL 15.0, DFW 21.6, DEN 17.2, JFK 18.5).

### 2.3 Why: decomposing ORD's delays

**Cause shares, ORD vs. national** (% of scheduled arrivals; BTS cause codes):

| Year (ORD / national) | Air carrier | Extreme weather | **NAS** | Late aircraft | **Cancelled** |
|---|---|---|---|---|---|
| 2019 | 4.12 / 5.22 | 0.67 / 0.62 | **9.13 / 5.98** | 7.89 / 7.03 | **3.37 / 1.90** |
| 2023 | 6.47 / 6.78 | 0.69 / 0.68 | 5.56 / 5.22 | 6.49 / 7.38 | 1.33 / 1.29 |
| 2024 | 5.97 / 6.44 | 0.83 / 0.76 | 6.69 / 5.52 | 6.91 / 7.51 | 1.41 / 1.36 |
| 2025 | 6.75 / 6.59 | 1.02 / 0.88 | **9.51 / 6.32** | 7.63 / 7.96 | 1.84 / 1.53 |
| 2026 Jan–Aug | 6.60 / 7.00 | 1.19 / 0.88 | **10.03 / 6.14** | 8.04 / 8.66 | **3.27 / 2.27** |

**What is inside "NAS"?** FAA OPSNET records ATC-reportable delays of ≥ 15 min. Their split shows ORD's NAS delay is unusually *volume*-driven:

- **2023:** 46 % weather / 45 % volume.
- **2024:** 41 % weather / **51 % volume**. Of nine airports checked, ORD had the highest volume share in 2024–25.
- **2025:** 42 % weather / 44 % volume / 6 % closed runway.
- **2026 YTD:** the closed-runway share rose to **12 %**, reaching 16–19 % in some months.

OPSNET records "volume" only when the airport is in its optimum configuration ([OPSNET definitions](https://www.aspm.faa.gov/aspmhelp/index/OPSNET__Delays.html)). Demand at ORD therefore presses against capacity even in good conditions.

**Weather's true share.** Weather appears in several BTS categories: extreme weather, the weather portion of NAS, and the weather-caused part of late-aircraft delay. BTS's composite "weather's share of delayed flights" for ORD was close to national in 2023–24 (24–26 %). It was above national in 2019 (50.5 % vs. 36.1 %), 2025 (31.9 % vs. 29.6 %) and 2026 YTD (37.7 % vs. 28.4 %). Nationally, the FAA attributes ~74 % of system-impacting delays ≥ 15 min to weather (Jun 2017 – May 2023), a different measure than BTS's.

**Carrier differences at ORD** (2025, % of scheduled arrivals):

| Carrier | On time | NAS delay | Late aircraft | Carrier-caused |
|---|---|---|---|---|
| United | 76.4 | **11.6** | 5.4 | 4.7 |
| American | 72.1 | 8.7 | **9.8** | 6.1 |
| SkyWest (United Express / American Eagle) | 68.2 | 6.2 | 6.9 | **14.0** |

United's ORD problem is the system (NAS). American's is propagation (late aircraft). SkyWest's is its own operation.

**Caveat on cause codes.** The DOT Inspector General found that 22–43 % of carrier-reported NAS delays did not match FAA data in 2018–22, and that reporting guidance "lack[s] clarity" ([OIG AV2025003](https://www.oig.dot.gov/library-item/46490)). On top of that, the **Section 511(b) final rule** moves ten event types out of "Air Carrier" into a new cause category (and cancellation code E) for **flights from 1 Jan 2027** (rule effective 1 Feb 2027; [delay notice](https://public-inspection.federalregister.gov/2026-21058.pdf)). Treat cause codes as noisy labels for analysis, never as model features. Model physical drivers (weather, volume, configuration) instead.

### 2.4 Capacity, runways and the surface

- **Runway system after the O'Hare Modernization Program (OMP):** eight active runways as of 1 Apr 2026. Six are east–west parallels: 9L/27R, 9C/27C, 9R/27L, 10L/28R, 10C/28C, 10R/28L. Two are diagonals: 4L/22R and 4R/22L. 10C/28C opened in 2013 and 10R/28L in 2015. **9C/27C was commissioned 5 Nov 2020** (mostly arrivals). The **9R/27L extension was commissioned 2 Dec 2021** (mostly departures). The diagonals 18/36, 14L/32R and 14R/32L were decommissioned in 2008, 2016 and 2018 ([CDA facility data](https://www.flychicago.com/business/CDA/factsfigures/Pages/facility.aspx); [9C/27C FAQ](https://oharenoise.org/sitemedia/documents/resources/modernization/FAQ_New_Runway_9C-27C_FINAL_09102020.pdf)).
- **The OMP was promised, and partly delivered.** The FAA forecast (2005) was average delay falling "from … nearly 18 minutes to less than six minutes per flight." The record shows real but partial gains:
  - GAO found ORD had the largest drop in delayed arrivals among 34 airports in 2007→09 (−11.7 pp), with poor-weather arrival capacity rising to 84/h from 68–72 ([GAO](https://www.gao.gov/assets/a304866.html)).
  - FAA/EUROCONTROL found ORD was the only large US airport to improve on-time performance in 2015–17.
  - The "< 6 min" target was not met, and taxi-out inefficiency remains top-3 nationally.
- **Capacity by weather and flow** (FAA 2018 capacity profile, total operations per hour, facility-reported / model-estimated):
  - Visual (≥ 5,500 ft ceiling and 7 mi visibility): 214/223 east flow, 214/224 west flow.
  - Instrument (< 1,000 ft or < 3 mi): 214/197 east flow, 206/182 west flow.

  Current throughput is "approximately 100 hourly departures and arrivals respectively… approximately 2,800 total daily operations" ([FAA notice, Mar 2026](https://www.govinfo.gov/content/pkg/FR-2026-03-03/pdf/2026-04198.pdf)). The 2018 profile predates 9C/27C, so current called rates are not public.
- **Wind decides the flow.** The FAA accepts ≤ 5 kt tailwind. Winds *require* west flow 29.9 % of the time and east flow 16.9 %, either flow works 51.9 %, and the diagonals are needed 1.3 %. West flow dominates in winter, and a flow change "can take an hour or more" ([CDA analysis](https://oharenoise.org/resources/presentations/technical/403-east-west-flow-operations/file)).
- **2025–27 construction.**
  - Tollway work took out the **10R glide slope and approach lights and the 28L localizer from 1 May to 17 Nov 2025**.
  - Taxiway A was closed 1 Jul – 16 Nov 2025 ([ONCC construction briefing](https://oharenoise.org/sitemedia/documents/2024/ORD-ONCC-2025-Airfield-Construction-110725.pdf)).
  - Taxiway A/B rehabilitation, Terminal Area Plan concrete work and the Taxiway LL/N reconstruction continue into 2027.
  - ORDNext/O'Hare 21 terminal work (Concourse D, the Global Terminal ≈ 2032) adds long-term gate and walking-path changes [S].
- **Level 2 → capped.** ORD has been an IATA Level 2 (schedule-facilitated, not slot-controlled) airport since 2008/09. Published Summer 2026 schedules exceeded **3,080 daily operations on peak days (+14.9 %)**. The FAA cited "competitive scheduling dynamics occurring between the two largest carriers" and capped operations at **2,708/day (06:00–23:59), 30–84 per half-hour**. The order took effect in June 2026 (originally 17 May; amended to 2 Jun) and has been extended through **30 Oct 2027**.

### 2.5 Demand and hub structure: what makes ORD unusual

| Metric | ORD | ATL | DFW | DEN | JFK |
|---|---|---|---|---|---|
| Aircraft movements 2025 (ACI) | **857,392 (#1 world)** | 807,625 | 743,394 | 701,335 | – |
| Passengers 2025 | 84.9 M | 106.3 M | 85.7 M | 82.4 M | – |
| Passengers per movement (derived) | **≈ 99** | ≈ 132 | ≈ 115 | ≈ 118 | – |
| Largest carriers (share of enplaned passengers by operating carrier, Aug 2025–Jul 2026) | United 39 %, American 23 %, SkyWest 10 %, Envoy 8 % | Delta 75 % | American 67 %, Envoy 11 % | United 41 %, Southwest 30 % | Delta 33 %, JetBlue 31 % (US carriers only) |
| Two comparable-size hub carriers? | **Yes** (UA ≈ 47 %, AA ≈ 33 % on a marketing basis [S]) | No | No | Partly (UA + WN, but WN is point-to-point) | No |

Sources: [ACI 2025](https://aci.aero/2026/07/15/worlds-busiest-airports-atlanta-holds-asia-climbs-strong-demand-while-asia-pacific-growth-reshape-the-rankings/), [ACI-NA 2025](https://airportscouncil.org/press_release/airports-council-releases-2025-north-american-airport-traffic-rankings/), [CDA 2025 summary](https://www.flychicago.com/SiteCollectionDocuments/Business/AccessiblePDFs/FactsandFigures/AirTraffic/1225%20ORD%20SUMMARY%20REVISED.pdf), [FAA ATADS via CDA](https://www.flychicago.com/SiteCollectionDocuments/Community/AccessiblePDFs/Noise/O%27Hare/AR/ORD_Annual_Operations_%282006-2025%29.pdf), BTS airport profiles.

- **Traffic history:** 919,704 operations (2019) → 720,582 (2023) → 776,036 (2024) → **857,392 (2025)**, still 6.8 % below 2019. Passengers reached 84.86 M in 2025, a record. CBP processed **5.99 M** passengers in customs.
- **Regional dependence:** **48.7 %** of reported ORD domestic arrivals were flown by branded regional partners (Dec 2024; [ATCR](https://rosap.ntl.bts.gov/view/dot/82026)). That means smaller aircraft (≈ 99 passengers per movement), more movements per passenger, and more exposure to the first-cancelled-under-GDP pattern.
- **The United–American contest:** 199 gates (UA 99, AA 66 as of Apr 2026). The 2025 gate "redetermination" litigation, and American's pledge to "add as many flights as are required to keep our gate count", drove schedule growth that the FAA ultimately capped.
- **Connecting share:** no verified current figure [U]. Measure it from DB1B/DB1C in Phase 1. Network studies treat ORD as one of the most connection-heavy nodes in the US system.

### 2.6 Weather regime

- **Normals (1991–2020):** 38.4 in snow per year (Dec–Feb peak); precipitation peaks in May and Aug ([NWS](https://www.weather.gov/lot/ord_rfd_monthly_yearly_normals)).
- **Thunderstorm days:** 37 (2023), **52 (2024)**, 46 (2025). For comparison in 2025: DEN 65, EWR 22, JFK 18. Dense-fog days at ORD run 4–13 per year (NWS annual climate reports).
- **Ground delay program (GDP) causes at ORD** (2007–09, pre-OMP): wind 29 %, low ceilings 25 %, thunderstorms 15 %, snow/ice 14 %, low visibility 8 %, rain 6 % ([Wang 2011](https://ntrs.nasa.gov/api/citations/20140008304/downloads/20140008304.pdf)). Wind matters because of flow constraints; ceilings matter because of the 1,000 ft / 3 mi breakpoint.
- **Seasonality:** the worst months are summer convection (Jun–Aug) and individual winter storms (Jan 2024: 7.5 % cancelled; Nov 29 2025: ≈ 1,160 cancellations [S]). Sep–Nov and Feb–Apr are usually the best months, though 2025–26 broke the pattern (Mar 2026: 63.5 % on time, −9.9 pp vs. national).
- **Lightning:** ramp closures are not standardized and ORD publishes no policy. Use lightning-ring proxies (§4.3).

### 2.7 Temporal patterns

- **Evening collapse.** In July, ORD departures scheduled in the 22:00 hour were only **23.5 % on time (2024)** and 32.4 % (2023), against 49.6 % across the 30 largest airports. Arrivals in the 19:00 hour were 38.0 % on time (Jul 2024). Early-morning flights are the most reliable (06:00 departures 81–92 % on time). This is classic propagation through the day plus the late bank ([ATCR Jul 2024](https://rosap.ntl.bts.gov/view/dot/77999)).
- **Month-to-month volatility is high.** ORD on-time arrival % / cancelled %, with the gap to the national on-time rate in parentheses (TranStats):

  | Month | 2024 | 2025 (gap) | 2026 (gap) |
  |---|---|---|---|
  | Jan | 66.4 / 7.46 | 78.1 / 2.03 (−0.2) | 67.4 / 3.98 (−7.8) |
  | Feb | 87.7 / 0.39 | 76.8 / 1.19 (−1.0) | 76.7 / 1.22 (−1.8) |
  | Mar | 82.9 / 0.46 | 77.0 / 1.15 (−2.4) | **63.5 / 5.84 (−9.9)** |
  | Apr | 82.4 / 0.45 | 78.7 / 1.39 (−0.9) | 69.9 / 3.76 (−9.3) |
  | May | 69.7 / 1.78 | 78.4 / 0.67 (+3.1) | 76.9 / 1.12 (−0.8) |
  | Jun | 73.6 / 1.42 | 70.5 / 1.02 (+0.4) | 71.5 / 3.40 (−1.7) |
  | Jul | 69.4 / 2.61 | **63.0** / 2.71 (−6.2) | 70.4 / 4.44 (+0.9) |
  | Aug | 72.0 / 1.36 | 71.1 / 2.59 (−5.7) | 65.7 / 2.34 (−5.8) |
  | Sep | 84.3 / 0.29 | 79.1 / 0.40 (−4.0) | – |
  | Oct | 86.1 / 0.38 | 73.9 / 0.31 (−5.6) | – |
  | Nov | 83.8 / 0.33 | 67.9 / **5.71** (−9.4) | – |
  | Dec | 77.5 / 0.62 | 63.7 / 2.78 (−8.1) | – |

  Nov 2025 combines the shutdown flight cuts and the 29 Nov snowstorm. The spring 2026 slump coincides with construction-related runway closures (the closed-runway share of NAS delay was 17–19 % in Mar–Apr 2026); its full cause is an open question.
- **Day of week and holidays:** no ORD-specific published analysis was found. Measure in EDA (hypothesis: Thu/Fri/Sun peaks; Thanksgiving and winter holidays).

### 2.8 Taxi times and surface congestion

- **Additional taxi-out time** (vs. unimpeded): **ORD 9.5 min per departure in 2022, 3rd worst of 34 US airports**; LGA 11.7, EWR 11.6, JFK 9.0, DFW 6.5, DEN 6.3, ATL 2.4, US average 6.3. ORD's figure was ≈ 11.9 in 2019 ([FAA–EUROCONTROL comparison](https://www.eurocontrol.int/sites/default/files/2024-01/eurocontrol-comparison-atm-related-performance-us-europe.pdf)).
- **Trend:** local reporting claims taxi-out rose from 22.5 min (2018) to > 28 min, and taxi-in from 13.6 to > 18 min (2026) [S]. Oct 2026 reports describe long post-landing waits [S]. *Taxi-in directly affects the pickup use case*: verify with BTS `TaxiIn` in Phase 1.
- Remote runways (e.g., 10R/28L, about 20 min from the terminals [S]) and the 9C/27C arrival runway lengthen taxi-in by design.

### 2.9 Propagation and ORD's network role

- Late-aircraft delay is **36.5 %** of ORD delay minutes (national 40.0 %, 2025). ORD *imports* less propagated delay than average but *generates* more of its own system delay.
- GAO (2009 data): ORD was among the seven airports generating ≈ 80 % of US departure delays, and **71.6 % of ORD-attributed delays materialized at other airports**. ORD is a delay exporter.
- Network studies place ORD among the most connected nodes (second-most destinations in a 305-airport network) and identify passenger and crew connectivity as the main propagation channel ([Fleurquin et al. 2013](https://doi.org/10.1038/srep01159)). For passengers, ORD was among the six worst US transfer airports in 2007: 12.2 % of connecting passengers were disrupted ([Barnhart et al. 2014](https://doi.org/10.1287/opre.2014.1268)).

### 2.10 ORD vs. ATL, DFW, DEN, JFK: what is unique

| Factor | ORD | ATL | DFW | DEN | JFK |
|---|---|---|---|---|---|
| Hub structure | **Two competing hubs** (UA, AA) of comparable size | Single dominant hub (DL) | Single dominant hub (AA) | UA hub + WN focus city | Fragmented; international gateway |
| Movements vs. passengers | Most movements in the world; **fewest passengers per movement** (regional-heavy) | Highest passengers | High | High | Lower movements |
| Binding constraint (2025–26) | **Surface/taxiways + construction**; volume share of NAS delay highest among peers | Volume + weather | Weather + volume | Weather (convective, snow) | Weather + airspace (NY) |
| Schedule regulation | Level 2 → **FAA cap 2026–27** | Level 1 | Level 1 | Level 1 | Level 3 slot-controlled |
| Weather signature | Summer convection + winter storms; wind-driven flow changes | Summer convection | Convection, ice storms | Convection (more storm days), snow, wind | Convection, fog, wind; NY airspace |
| Extra taxi-out (2022) | 9.5 min (3rd worst) | 2.4 | 6.5 | 6.3 | 9.0 |
| International processing | Single FIS facility at **T5** for most international arrivals (5.99 M customs passengers in 2025); T5 is not airside-connected to T1–T3 | n/c | n/c | n/c | n/c |

Notes: peer "binding constraint" entries follow their 2025 OPSNET weather/volume shares of NAS delay (ATL 46/39, DFW 52/30, DEN 61/22, JFK 68/26 %). Peer weather signatures and scheduling levels are general background [U]. n/c = not compared.

### 2.11 What the evidence supports and what it doesn't

**Supported:**

- ORD is a below-average performer in stressed periods (2019, 2025, 2026).
- The cause is primarily the airfield/airspace system: volume against capacity, and construction-reduced surface capacity.
- Weather amplifies the problem.
- Delays at ORD run long.
- ORD exports delay to the network.

**Not supported:**

- "ORD is always among the worst." It was near the top in 2023.
- "Airlines cause ORD's delays." Not in aggregate; specific carriers do have specific problems.
- "Snow is the main problem." Summer is usually worse.
- "The OMP fixed O'Hare." Gains were real but partial, and the binding constraint has moved from runways to the surface.

### 2.12 Hypotheses for Phase 1 exploratory analysis (raw BTS + weather + FAA advisories)

1. **Construction event study:** throughput falls and NAS delay and taxi-in rise around 1 May / 17 Nov 2025 and around taxiway-closure dates.
2. **Volume nonlinearity:** NAS delay per flight rises convexly with scheduled operations per 30 min. Find the knee and compare it with the 84-per-half-hour cap.
3. **Excluding thunderstorm days** closes most of the ORD–national gap in summer.
4. **East flow and flow-change hours** have lower throughput and higher delay.
5. **The evening collapse** is explained by tail-rotation chains, so rotation features predict last-bank delay.
6. **Regional-first cancellation:** on disrupted days, regional operators' cancellation odds exceed mainline odds.
7. **Delay export:** ORD GDP days raise departure delay at origin airports for ORD-bound flights.
8. **The cap reduced volume delay but not storm-day cancellations.** Early Summer 2026 data show on-time 68.2 → 69.2 % but cancellations 2.1 → 3.4 % and NAS delay minutes +50 % (Jun–Aug, 2025 → 2026). Control for weather and reporting changes.
9. **BTS `TaxiOut`/`TaxiIn` trends** 2018 → 2026, by likely runway.
10. **MDW contrast:** low NAS delay but high late-aircraft delay, i.e., Southwest network effects.
11. **Observable drivers outperform cause codes:** models on weather, volume and configuration beat models on cause codes.
12. **Day-of-week and holiday effects.**

> **Data caveat for every comparison:** BTS products use different carrier sets and denominators. TranStats cause pages, the BTS airport profile, "Flight Delays at a Glance" (75.28 % for 2024 vs. 78.10 %) and Cirium (completed flights only) all disagree slightly. Jan–Aug 2026 BTS counts also suggest a 2026 change in reporting coverage. Always state the source series and keep it fixed within an analysis.

## 3. Stakeholder and use-case analysis

### 3.1 Who decides what, and when

| Stakeholder | Decisions the product could improve | When | What they use today | Unmet need |
|---|---|---|---|---|
| **People picking up arrivals** (family, friends, drivers) | When to leave home; when to leave the cell-phone lot; which terminal, level and door; how long customs will take | 0–6 h before arrival, then live | Flight trackers (gate ETA), shared flight cards, guesswork | **When will the passenger actually be at the curb?** Domestic vs. Terminal 5 international; bags vs. carry-on |
| **Departing ORD travelers** | Rebook proactively on bad-day forecasts; how early to leave; which flight to book | Booking time; 72 h → 0 h | Airline apps, Flighty, TripIt Go Now, weather apps | A calibrated, explained "how risky is my day?" signal, especially 1–3 days ahead of storms |
| **Connecting travelers** (esp. self-transfer / separate tickets, non-UA/AA) | Accept a tight connection at booking; prepare alternatives; whether to run | Booking → en route | United app (walk times, ConnectionSaver), Flighty Connection Assistant (qualitative rating) | Probabilities and historical pair reliability, especially where no airline protects the connection |
| **Ground transport** (limo/black-car dispatch, hotel shuttles) | Dispatch and staging time | 0–3 h | FlightStats ETA + fixed offset | Smarter, terminal-specific offsets (customs, bags) |
| **Journalists, researchers, civic groups** | Explaining performance: the FAA cap, construction, United–American competition | Days to months | BTS tables, FR24 index | Transparent ORD-specific analytics and explainers |
| **Airport operator (CDA) / airlines / FAA** | Staffing, curb management, schedule decisions | Hours to seasons | Internal systems with far better data (A-CDM, ASDE-X, crew and booking data) | Little; a public tool cannot out-predict their internal data, but could be a data or research partner |

### 3.2 Scoring the candidate use cases

Each criterion is scored 1–5; higher is better. "Feasibility" assumes public or low-cost data. "Validation" means ground truth exists to measure accuracy. "Licensing/cost risk" scores 5 when the risk is lowest.

| Use case | Impact | Reach | Feasibility | Validation | Differentiation | Licensing/cost risk | **Total** |
|---|---|---|---|---|---|---|---|
| **U1 ORD Outlook**: 1–3-day disruption forecast plus "why is ORD bad today" | 4 | 4 | 5 | 5 | 4 | 5 | **27** |
| **U2 Reliability Lab**: historical flight/route/airline/hour reliability, causes, cap analysis, connection-pair history | 3 | 3 | 5 | 5 | 3 | 5 | **24** |
| **U3 Pickup Planner**: curb-ready window plus "leave now" | 4 | 4 | 3 | 2 | 5 | 3 | **21** |
| U4 Flight-level pre-departure risk with explanations | 3 | 4 | 3 | 5 | 2 | 3 | 20 |
| U5 Delay-propagation explorer (aircraft rotations) | 2 | 2 | 4 | 4 | 3 | 5 | 20 |
| U6 Live connection-risk probability | 5 | 3 | 3 | 2 | 3 | 3 | 19 |
| U7 Ops analytics (taxi-out, surface congestion, runway config) | 3 | 1 | 3 | 4 | 3 | 4 | 18 |
| U8 Departure timing (when to leave; TSA waits) | 3 | 4 | 2 | 2 | 2 | 3 | 16 |

**Interpretation.**

- **U1 and U2 are the right *first* builds.** They are fully feasible with public data, rigorously verifiable, and they create the data platform every other use case needs. They also directly answer the research question "why does ORD have delays?".
- **U3 is the flagship traveler feature.** It is the clearest unserved problem (§8) and highly local. Its weakness is validation: the egress segment is unobserved, so it needs a deliberate measurement program (§3.3).
- **U4 is necessary but not differentiating.** It should appear on every flight page, but incumbents already do day-of prediction with better live data.
- **U6 is deferred.** The historical pair reliability goes into U2 now; the live probability comes later.
- **U8 is deferred** until better security-wait data exists.

### 3.3 What is observable along each journey

**Pickup timeline (arrival).**

| Segment | Observable historically? | Observable live? | Source / method |
|---|---|---|---|
| Origin departure (wheels-off) | Yes: BTS (domestic reporting carriers) | Yes: ADS-B; status APIs | Validated |
| Landing (wheels-on) | Yes: BTS (domestic); ADS-B (all, incl. international) | Yes: ADS-B | Validated |
| Taxi-in → gate (in-block) | Yes: BTS `TaxiIn` (domestic); partly ADS-B surface tracks | Partly: status APIs; ADS-B ground coverage | Validated (domestic). Model by airline/terminal/hour/runway flow |
| Door open → deplaned | **No** | No | Assumption by aircraft size and seat zone; calibrate with feedback |
| Walk to exit / baggage claim | **No** (geometry only) | No | Gate → exit distance model (OSM/CDA maps) at a walking-speed distribution |
| Bag delivery | **No** | No | Benchmarks and opt-in user reports |
| CBP processing (T5 international) | **Partly**: CBP Airport Wait Times, hourly by terminal (see §4.4) | No (published with a lag) | Climatology by hour/weekday/season, scaled by scheduled international arrivals |
| Curb meet | No | User location only | Drive time from cell-phone lot or home (routing API) |

**Connection (A arrives ORD → B departs ORD).**

| Component | Observable? | Note |
|---|---|---|
| A in-block, B departure (actual) | Yes (BTS, domestic) | Enables **historical pair reliability without itineraries** |
| Gate/terminal pair | Live only (status APIs / FIDS) | Historical gates are not in BTS |
| Walking/transfer time | Estimate (geometry; ATS people mover for terminal changes) | International → domestic requires customs at T5, bag recheck and re-screening (see §4.4) |
| Airline hold (United ConnectionSaver) | **No** | Explicit assumption plus sensitivity analysis |
| Rebooking outcome | **No** | Out of scope; show alternatives only |

**Departure timeline (home → gate).**

| Segment | Observable? | Note |
|---|---|---|
| Drive / transit time | Live via routing APIs; historical via Chicago TNC/taxi trip data, CTA | Good |
| Security wait | **Weak**: TSA throughput (weekly, lagged); no public live ORD waits | Estimate from scheduled departing seats by terminal and hour; flag uncertainty |
| Walk to gate | Estimate (geometry) | – |
| Boarding cutoff | Airline policy | Static |

**Design consequence.** The product should be explicit about which parts are measured and which are assumed, for example a stacked bar showing "validated" vs. "estimated" minutes. The project should also *create* ground truth for the unobserved segments: opt-in "I'm at the curb" taps, volunteer timing logs and, possibly, a CDA data partnership. That data asset is also the most defensible part of the product.

## 4. Data source inventory

**How to read this section.** Each source was checked against official pages in October 2026 during this research. Prices and terms change, so re-verify at build time. The central distinctions are:

1. **historical training** vs. **real-time inference**;
2. **public-domain/open** vs. **licensed** data. This determines what a public website may display, and how long raw data may be stored.

### 4.1 The short version

| Need | Best free source | Best paid option | Gap |
|---|---|---|---|
| Flight-level outcome labels (history) | **BTS On-Time** (reporting + marketing carrier files) | – | Domestic US carriers only; ≈ 2-month lag; no gates; no planned tails |
| Weather forecasts as they existed then | **IEM (TAF, MOS), MDL LAMP, NBM and HRRR on AWS** | – | Some products are real-time only |
| Traffic-management programs | **ATCSCC advisory archive (2001 →)** + FAA NAS Status (live) | – | NAS Status has no history: self-archive |
| Live airport state (programs, runway configuration, AAR) | **FAA NAS Status** (XML + undocumented JSON with `airportConfig`) | – | Undocumented JSON may change |
| Live positions, takeoffs and landings (all operators) | **adsb.lol (ODbL)**; OpenSky (non-profit research only) | ADS-B Exchange Enterprise; FR24 | Callsign ↔ flight-number mapping |
| Live airline status (ETAs, gates, cancellations) | FAA SWIM TFMS (free, approval, engineering-heavy) | **AeroDataBox** (cheapest board), AeroAPI, Cirium, OAG | Storage and mixing restrictions |
| Future schedules | – (BTS is historical) | AeroDataBox, AeroAPI, OAG, Cirium | No free source |
| Customs waits (T5) | **CBP AWT** (hourly, 2023-05 →) | – | Lagged ≈ 2 days; not real-time |
| Security | TSA FOIA throughput (hourly × checkpoint, weekly PDFs) | – | Counts, not waits; no ORD live feed |
| Ground access | Chicago TNC/taxi trips; CTA/Metra; routing APIs | Google/Mapbox/HERE/TomTom | Caching limits on Google |

### 4.2 Flight operations and ATC (historical and live)

**BTS Reporting Carrier On-Time Performance (1987 →)** ([profile](https://www.transtats.bts.gov/DatabaseInfo.asp?QO_VQ=EFD&Yv0x=D), [fields](https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=FGJ)): the project's ground truth.

- **Fields (111).** Scheduled and actual departure/arrival times, delays, `Tail_Number`, `TaxiOut`, `WheelsOff`, `WheelsOn`, `TaxiIn`, cancellation and code, diversion detail (from 10/2008), gate-return fields, and delay-cause minutes (from 6/2003).
- **Scope.** Domestic flights of US reporting carriers only. Transborder, international and foreign carriers are excluded.
- **2026 reporting carriers** ([Directive #40](https://www.bts.gov/explore-topics-and-geography/modes/aviation/number-40-technical-directive-reporting-time)): Alaska, Allegiant, American, Delta, Envoy, Frontier, Hawaiian (now reported with Alaska under a single certificate), JetBlue, PSA, Republic, SkyWest, Southwest, Spirit, United. The threshold is > 0.5 % of domestic scheduled passenger revenue. *Spirit ceased operations on 2 May 2026* ([NPR](https://www.npr.org/2026/05/02/nx-s1-5807933/spirit-airlines-ceases-operations-folds)).
- **Rules that matter for modeling** ([14 CFR 234.2](https://www.law.cornell.edu/cfr/text/14/234.2), [234.4](https://www.law.cornell.edu/cfr/text/14/234.4)):
  - Only flights still in reservation systems **within 7 days of departure** count. Earlier schedule cuts are invisible as cancellations, and that applies to the 2025 shutdown cuts and the 2026 cap trims.
  - Cause minutes are reported only for arrivals ≥ 15 min late and for cancellations.
  - `ArrDelay` is NULL for diverted flights.
- **Lag and quality.** Carriers file 15 days after month end, but the effective public lag is **6–8 weeks** (Aug 2026 was the latest month on 26 Oct 2026). The DOT Inspector General found BTS "lacks procedures to verify the data's completeness" and saw BTS staffing shrink from 12 + 12 contractors (2016) to 6 + 5 (2024) ([OIG](https://www.oig.dot.gov/library-item/46490)). Mirror the data; don't assume perpetual availability.
- **Cause-code break.** Section 511(b) adds a sixth delay category and cancellation code **E** for flights from **1 Jan 2027** ([final rule](https://www.govinfo.gov/content/pkg/FR-2026-09-03/pdf/2026-18040.pdf), [delay notice](https://public-inspection.federalregister.gov/2026-21058.pdf)). A further ATC-delay category under Section 511(a) is pending.
- **Licence:** US government work, public domain. **Verdict: core labels; training only.**

**Other BTS sources:**

| Source | Coverage | Use |
|---|---|---|
| **Marketing Carrier On-Time** (2018 →; [fields](https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=FGK)) | Adds marketing network, operating carrier, codeshare flags | **Use for ORD.** Branded regional flights are ~49 % of ORD arrivals, and flights by non-reporting operators appear only through the marketing carrier [U, inference from reporting rules] |
| T-100 Segment ([profile](https://www.transtats.bts.gov/DatabaseInfo.asp?QO_VQ=EEE&Yv0x=D)) | Seats, passengers, load factors by carrier × segment × aircraft, **including foreign carriers** | Capacity features; international context |
| **DB1B → DB1C** | DB1B (10 % ticket sample) **ended after Q2 2025**; DB1C (40 % monthly sample) starts **Jul 2025** ([DB1C](https://www.transtats.bts.gov/DatabaseInfo.asp?QO_VQ=KDD&Yv0x=D)) | Connecting-share and itinerary features (no timestamps) |
| Form 41 B-43 aircraft inventory ([fields](https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=GEH)) | Tail → seats, model, year (annual) | Aircraft size features |

**FAA:**

| Source | What / access | History | Live? | Verdict |
|---|---|---|---|---|
| ASPM / OPSNET / TFMSC portal ([home](https://www.aspm.faa.gov/), [help](https://www.aspm.faa.gov/aspmhelp/index/Aviation_System_Performance_Metrics_(ASPM).html)) | **Public without login:** Airport Analysis, City Pair Analysis, **Taxi Time**, OPSNET delay counts. **Restricted** (account + approval): flight-level data and the quarter-hour download containing **runway configuration, AAR/ADR, EDCT** | 2000 → (77 airports) | No (≤ 60-day release) | Public aggregates for EDA. **Request research access** for runway configuration and rates |
| **NAS Status** ([XML](https://nasstatus.faa.gov/api/airport-status-information)) | GDP (avg/max delay, reason), ground stops, arrival/departure delay trend, closures, deicing; updates every minute. An undocumented JSON (`/api/airport-events`) adds **`airportConfig`** (arrival/departure runways, **arrival rate**) for airports with active events | **None: self-archive** | Yes | **Real-time core.** Archive every minute from day one. Treat the JSON as fragile |
| **ATCSCC advisories** ([form](https://www.fly.faa.gov/adv/advAdvisoryForm)) | GDP/GS/AFP/CTOP/reroute advisory texts with timestamps. The form shows 15 days, but **direct URLs serve advisories back to Jun 2001** | 2001 → | Yes (≈ 5-min refresh) | **Historical program labels plus real-time feed.** Crawl politely |
| EDCT lookup | Per-flight lookup for operators only | – | Per flight | Not for bulk use |
| **SWIM via SWIFT Portal** ([access](https://www.faa.gov/air_traffic/technology/swim/products/get_connected)) | TFMS (flow and flight data), TBFM (metering), STDDS (ASDE-X/ASSC surface, TDLS), SFDPS, ITWS, NOTAMs; Solace JMS streaming. **Free, approval required.** "Not intended for NAS-impacting usage." Public display permitted with **LADD filtering** ([LADD](https://www.faa.gov/pilots/ladd)). The old `scds.faa.gov` host no longer resolves | **None: self-archive** | Yes (streaming) | **Best free flight-level live source;** heavy engineering. Phase 3 |
| NOTAMs (NMS, live since Sep 2025; API by request) | Closures, construction | 5-year search UI only | Yes | Closure features; manual curation |
| **Aircraft Registry** ([download](https://www.faa.gov/licenses_certificates/aircraft_certification/aircraft_registry/releasable_aircraft_download)) | N-number ↔ **Mode S hex** ↔ type; daily | Current + deregistered | – | Join ADS-B ↔ BTS tails |
| NASR (28-day) | Runways, fixes, procedures (format change from the 2026-09-03 cycle) | – | – | Reference geometry |
| FAA ORD orders (cap 2026–27; Nov 2025 cuts) | Regime definitions | – | – | Regime flags |

**NASA:**

- Sherlock requires a NASA badge, so it is not usable.
- The FUSER-derived DrivenData datasets include **KORD** (Run-way Functions, Nov 2020 – Nov 2021; Pushback to the Future, 2020–22), but their rules restrict use to the competition and forbid redistribution ([rules](https://www.drivendata.org/competitions/89/competition-nasa-airport-configuration/page/419/)).
- They are an **excellent schema reference** (configuration, ETD, LAMP, TBFM, TFM, stand times), not a reusable dataset.

### 4.3 Weather: observations and archived forecasts

**Key finding:** you can train leakage-safe models for free. Public archives keep the forecasts that actually existed at each horizon, with issuance times, for ORD. The real-time-only products, by contrast, must be archived by the project starting on day one.

| Source | What it gives | History (ORD) | Latency / limits | Licence | Use |
|---|---|---|---|---|---|
| **IEM ASOS/METAR** ([site](https://mesonet.agron.iastate.edu/sites/site.php?station=ORD&network=IL_ASOS), [API help](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?help)) | Wind/gust, visibility, sky layers, present weather, precipitation, ice accretion, raw METAR; 5-min HFMETAR | Archive from **1946-10-01**; 5-min rows from ≈ 2019 | Syncs every 10 min; **1 s per-IP throttle (Apr 2026)**; ≤ 1,000 station-years per request | Public domain ([disclaimer](https://mesonet.agron.iastate.edu/disclaimer.php)) | Training + real time |
| **IEM TAF archive** ([page](https://mesonet.agron.iastate.edu/request/taf.php)) | Every ORD TAF with issuance time, amendment flag, FM/TEMPO/PROB groups; "as-of" API (`/api/1/nws/taf.json?station=KORD&issued=…`) | **From 1996-01-01** | 4/day + amendments | Public domain | **Core 0–30 h feature** |
| **LAMP** station guidance ([MDL](https://vlab.noaa.gov/web/mdl/lamp), [archive](https://vlab.noaa.gov/web/mdl/lamp-archived-bulletins-year)) | Hourly ceiling, visibility, wind, lightning/convection, precipitation type; 15-min ceiling/visibility (v2.6+) | Hourly bulletins **from Aug 2006** (yearly tars); IEM parsed copy from 2020 (4 cycles/day) | Hourly; v2.7 (16 Sep 2025) changed visibility categories (regime break) | NWS | **Core 1–25 h** |
| **NBM** text and GRIB2 ([text archive](https://vlab.noaa.gov/web/mdl/nbm-text-archives), [versions](https://vlab.noaa.gov/web/mdl/nbm-versions)) | Probabilistic ceiling/visibility (MVFR/IFR/LIFR), thunder, precipitation type, snow, gusts | AWS bucket **from 2020-05-18**; IEM NBS from 2018-11 | Hourly; text ≈ +65 min. Versions v4.3 (May 2025), v5.0 (Apr/May 2026); RRFS inputs from 3 Nov 2026 | NODD open | **Core 6–72 h** |
| GFS MOS (IEM) ([MOS](https://mesonet.agron.iastate.edu/mos/)) | Classic station guidance (ceiling, visibility, thunder, precipitation type) | From 2003-12 | 4 cycles/day | Public domain | Long baseline. (**NAM MOS ends 3 Nov 2026**) |
| **HRRR** ([AWS registry](https://registry.opendata.aws/noaa-hrrr-pds/)) | 3-km gridded ceiling, visibility, reflectivity, echo tops, lightning, gust, precipitation type; 15-min sub-hourly | **From 2014-07-30** (v4 from 2020-12-02) | Hourly cycles; f00 ≈ +51 min | NODD open | Core gridded 0–18 h (48 h every 6 h) |
| NDFD official forecast ([NCEI](https://www.ncei.noaa.gov/products/weather-climate-models/national-digital-forecast-database), [AWS](https://registry.opendata.aws/noaa-ndfd/)) | Official NWS grids incl. aviation ceiling/visibility (operational 17 Mar 2025) | 2004 (by order); ceiling/visibility from 2022 | 30-min updates | NODD | Optional |
| **SPC convective outlooks** (IEM as-of point API) | Day-1/2/3 risk categories with issuance stamps | **From 1987** | ≈ 5 Day-1 issuances/day; SIGN hatching → CIG1–3 (Mar 2026) | Public domain | 6–72 h thunderstorm risk |
| **TCF** (traffic-management convective forecast) text (IEM) | 4/6/8-h convective areas used by FAA planners | **From 2004-05-26** | Every 2 h | Public domain | 3–8 h |
| Convective SIGMET / CWA / G-AIRMET (IEM) | Hazard polygons with issue/expire times | 2005 / 2014 / 2021 | Event-driven; Convective SIGMET validity drops to 1 h (≈ Dec 2026) | Public domain | 0–3 h, en route |
| **MRMS** radar mosaics ([AWS](https://registry.opendata.aws/noaa-mrms-pds/)) | 2-min composite reflectivity, echo tops, precipitation, lightning-derived grids | From 2020-10-14 (v12) | ≈ 1.5 min | NODD | Nowcast 0–2 h |
| **GOES GLM lightning** | 20-s total-lightning flashes | From 2018-02-13 (GOES-19 since 2025-04-07) | ≈ 10–20 s | NODD | **Ramp-closure proxy** (flashes within 3/5/10 mi) |
| NEXRAD L2/L3 + ORD TDWR ([AWS](https://registry.opendata.aws/noaa-nexrad/)) | Raw radar | L2 1991; L3/TDWR 2020 | ≈ 5 min | NODD | Research |
| AWC Data API ([docs](https://aviationweather.gov/data/api/)) | Live METAR/TAF/PIREP/SIGMET/TCF | **Rolling 30 days only** | "100 requests per minute", ≤ 400 rows, custom User-Agent | US government | Real time only |
| NWS API (api.weather.gov) | Gridpoint forecasts | No forecast history; 7 days of observations | User-Agent required | Free | Real time only |
| NCEI ISD / GHCNh / LCD v2 | Quality-controlled hourly observations | Full record | **ISD frozen after 2025-08-24** (successor GHCNh); LCD v1 deprecated | US government | QC backfill and labels, not live features |
| ERA5 | Reanalysis | 1940– | ≈ 5 days | CC-BY | Climatology only |
| Real-time only (no archive): WSSI/WSSI-P (winter severity), WPC probabilistic precipitation portal, eTCF/ECFP, GTG/IFI/CIP icing and turbulence, CIWS/ITWS (FAA SWIM), FICON runway-condition NOTAMs | – | – | – | – | **Archive yourself from day one, or skip** |

**Weather regime breaks to encode** (they matter for backtests):

- HRRR v4 (2020-12-02)
- MRMS v12 (2020-10-14)
- NBM v4.0 → v5.0 (2020–2026)
- LAMP v2.7 (2025-09-16)
- ISD frozen (2025-08-24)
- SPC outlook categories (2026-03-02)
- **NAM/NAM MOS/SREF/HREF retired and RRFS operational (2026-11-03)**
- Convective SIGMET 1-h validity (≈ 2026-12-01)

The practical window in which *all* core feeds coexist starts in **Dec 2020**. TAF, GFS MOS and LAMP support a longer 2006+ baseline.

**Minimal weather stack per horizon** (inputs must be the latest product available *before* the prediction time, after a measured dissemination lag):

| Horizon | Archived forecasts | Observations at prediction time |
|---|---|---|
| 24–72 h | NBM (probabilities at ORD's capacity thresholds; thunder; precipitation type/snow; wind components), SPC Day 1–3, latest TAF (≤ 30 h), GFS MOS (pre-2018 baseline) | Climatology and persistence |
| 6 h | + hourly LAMP, latest HRRR cycle at ORD and upstream, TCF 6/8 h | METAR; upstream MRMS convection |
| 3 h | + LAMP/HRRR sub-hourly, TCF 4 h, active SIGMET/CWA | 5-min METAR; MRMS rings at 20/50/100 nm; GLM |
| 1 h | latest LAMP 15-min, HRRR sub-hourly, Convective SIGMET | 5-min METAR, 2-min MRMS, GLM flash counts within 3/5/10 mi, ORD TDWR |
| En route | ORD forecast at the ETA (LAMP/HRRR/TAF); TCF/SIGMET polygons along the remaining route; HRRR/RAP winds aloft | MRMS echo tops along the route and at arrival fixes; PIREPs |

**ORD-specific translation.** The FAA's 2018 ORD capacity profile defines the capacity breakpoints as visual ≥ **5,500 ft ceiling and 7 mi visibility** and instrument < **1,000 ft or 3 mi** ([profile](https://www.faa.gov/sites/faa.gov/files/airports/planning_capacity/profiles/ORD-Airport-Capacity-Profile-2018.pdf)). Features should therefore be forecast probabilities at *those* thresholds, not standard VFR/IFR categories. Two more feature sets are needed:

- **Forecast runway wind components.** FAA accepts ≤ 5 kt tailwind. In a CDA analysis, wind forces west flow 29.9 % of the time and east flow 16.9 %, either flow works 51.9 %, and the diagonals are needed 1.3 %. A flow change "can take an hour or more" ([CDA 2016](https://oharenoise.org/resources/presentations/technical/403-east-west-flow-operations/file)).
- **Lightning-ring counts.** There is no FAA ramp-closure standard and practices vary by airline and airport ([Vaisala guidance](https://www.vaisala.com/sites/default/files/documents/Guidelines%20for%20Airport%20Ramp%20Closures%20Due%20to%20Lightning.pdf)).

**Operational constraints.** IEM asks that its API not be hit from high-traffic websites, so the public site must serve weather from the project's own cache. The AWC API's 30-day window and the NWS API's lack of forecast history make them real-time-only feeds.

### 4.4 Passenger-side, ground-side and terminal data

| Source | What it gives | Granularity and history | Latency | Access and terms | Use |
|---|---|---|---|---|---|
| **CBP Airport Wait Times** ([site](https://awt.cbp.gov/)) | Passport-control waits for passengers on flights arriving each hour: average and max, **US vs. non-US citizens**, 7 wait buckets (0–15 … 120+ min), passenger and flight counts, booths used, Global Entry count | **Hourly, ORD Terminal 5 only** (entry `A392`). Data window starts **2023-05-03** (≈ 3.5-year rolling window) | ≈ 1.5–2 days | JSON endpoints behind the React app (`/api/airport`, `/api/waitTime`). **Undocumented**, no key, no stated limits. Federal work (public domain likely [U]) | **Core prior for international pickups.** Archive it yourself, because the window rolls. Excludes baggage claim and exit time ("do not include time to retrieve baggage") |
| **TSA FOIA throughput** ([reading room](https://www.tsa.gov/foia/readingroom)) | Screened passengers (+ crew?) by **airport × checkpoint × hour**. ORD labels: 1, 2, 3A, 4B, 5, 6, 6A, 7, 7A, 8, 10, 11 | Weekly PDFs **since Feb 2017** (one week ≈ 1,400 pages, all US airports) | ≈ 2 days after week end | Public. PDF parsing required. The checkpoint-to-terminal mapping is partly an assumption | Security *demand*, not waits. Demand → queue models |
| TSA national daily volumes ([page](https://www.tsa.gov/travel/passenger-volumes)) | National screened totals | Daily | Next weekday | Public | Context |
| MyTSA / TSA wait API | Crowd and historical estimates | – | – | **Legacy API endpoints now return HTML: no TSA wait API exists.** App unreliable during the Feb 2026 DHS funding lapse | Not usable |
| flychicago.com (CDA) | No live security waits. **Undocumented JSON** for flight status (credits OAG; fields include estimated/actual runway and gate times, `ArrivalGate`, `ArrivalTerminal`, **`BaggageClaim`**, codeshares), parking occupancy, a taxi-wait bucket | Live only | Live | **No published API or terms**: ask CDA before any use | Potentially the best source for gates and bag carousels; legally unclear |
| CDA monthly statistics ([page](https://www.flychicago.com/business/CDA/factsfigures/Pages/ohare-midway-air-traffic-data.aspx)) | Operations, passengers, cargo, **customs counts** | Monthly PDFs since 2000 | ≈ 7 weeks | Public | Demand context |
| **Chicago Data Portal: rideshare (TNP) trips** ([2025– `6dvr-xwnh`](https://data.cityofchicago.org/d/6dvr-xwnh); 2023–24 `n26f-ihde`; 2018–22 `m6dm-c72p`) | Trip start/end (**rounded to 15 min**), seconds, miles, pickup/drop-off tract and community area, fare | Trip-level, Nov 2018 → **Aug 2026** | ≈ 2 months | SODA API; app token; City disclaimer and indemnity terms | Airport-tract `17031980000` pickups give **arrival-wave demand curves**. Airport ↔ neighborhood in-vehicle times give drive-time priors. ≈ 23 % of community-area-76 pickups lack a tract (privacy) |
| Chicago Data Portal: taxi trips (2024– `ajtu-isnz`; 2013–23 `wrvz-psew`) | Same plus masked taxi ID and company | 2013 → Sep 2026 | ≈ 1 month | Same | Same (≈ 41 % tract suppression) |
| CTA 'L' daily entries (`5neh-572f`) | O'Hare station (`40890`) entries | Daily, 2001 → Jul 2026 | ≈ 2 months | Same | Airport egress by rail (entries only) |
| Chicago Traffic Tracker | Arterial speeds | – | – | **Discontinued 30 Apr 2026**; never covered expressways | Not usable |
| CTA Train Tracker API ([docs](https://www.transitchicago.com/developers/ttdocs/)) | Train arrival predictions | Live | Live | API key; terms limit use to helping transit riders | Transit option in planners |
| Metra GTFS + GTFS-RT ([page](https://metra.com/metra-gtfs-api)) | Schedules, live positions and updates (30 s) | Live | Live | Token. **Must serve from your own host** | Weekday-only O'Hare Transfer (North Central Service) |
| IDOT Travel Midwest ([reuse policy](https://travelmidwest.com/About/InfoReusePolicy)) | Expressway travel times, incidents | Live | ≤ 5-min polling | Registration; credit IDOT; **"no critical use"** | Kennedy/I-190 travel times |
| Routing APIs | Traffic-aware drive times | Live | Live | Google Routes: 10 k free Essentials and 5 k Pro (traffic-aware) calls per month, then $5–10 per 1 k. **Caching mostly prohibited**; results shown on a map must be on a Google Map. Mapbox: 100 k free. TomTom: 20 k free ([Google](https://developers.google.com/maps/documentation/routes/usage-and-billing), [Mapbox](https://www.mapbox.com/pricing)) | "Leave now" times |
| **OpenStreetMap** ([copyright](https://www.openstreetmap.org/copyright)) | 219 `aeroway=gate` nodes, terminal footprints, stands, arrival-curb roads, the cell-phone lot | Snapshot | – | **ODbL** (attribution + share-alike) | Gate → exit walking-distance model (validate against CDA gate counts; Concourse F under-mapped) |
| **CDA noise-office runway use** (ANMS [monthly](https://www.flychicago.com/community/ORDnoise/ANMS/Pages/ANMSreports.aspx), Fly Quiet [quarterly](https://www.flychicago.com/community/ORDnoise/FlyQuiet/Pages/quarterlyreports.aspx)) | Runway utilization day/night; Fly Quiet mode logs | Monthly since 2008; quarterly since 2003 | ≈ 2 months | Public PDFs (some tables are images) | Validate ADS-B-inferred runway use; **no hourly configurations** |

**ORD process facts that shape the models** (CDA pages, 2026):

- **Check-in terminals.** T1: United, Lufthansa, ANA. T2: Air Canada, Alaska, JetBlue and others. T3: American, BA, Iberia, JAL. T5: Delta, Frontier, Sun Country, Avelo and ≈ 30 foreign carriers. United's 99 gates extend beyond T1, so gate-level data matters.
- **Carrier exits.** **Southwest left ORD on 3–4 Jun 2026** (consolidating at Midway). **Spirit ceased operations entirely on 2 May 2026.** Both are structural breaks in ORD carrier mix and in BTS reporting coverage.
- **International arrivals.** Non-precleared arrivals clear CBP at **T5**. Passengers collect *all* bags, pass agriculture screening, recheck at counters outside CBP, then take the ATS train and re-clear TSA. Alternatively they re-screen at T5 and ride the airside **Terminal Transfer Bus** (every 15 min, 11:30–21:30; T1↔T5 and T3↔T5). T1–T3 are connected airside; **T5 is not**.
- **CBP waits.** **Enhanced Passenger Processing (May 2025)** cut US-citizen processing from ≈ 60 s to ≈ 10 s, and CBP reports 74 % lower waits ([CBP](https://www.cbp.gov/newsroom/local-media-release/chicago-cbp-and-chicago-department-aviation-introduce-updated)). That is a structural break in the CBP series. Example day (Sat 24 Oct 2026): 91 international arrivals, 19.4 k passengers, hourly average waits 6–24 min (US 2–18, non-US 7–38), peak hourly maximum 89 min.
- **ATS people mover.** 24/7, every 3–5 min at peak, ≈ 10 min T1 → Multi-Modal Facility. Reliability is imperfect (dozens of outages after reopening; backup buses). There is no live status feed.
- **Pickup rules.** Curbside waiting is prohibited. Free cell-phone lot at 560 N Bessie Coleman Dr (≈ 0.8 km straight-line to T5, ≈ 1.4–1.7 km to T1–T3). Rideshare uses T2 upper-level zones 2A–2G and T3 zones; T5 rideshare moved to T2 in 2023. Pre-arranged livery takes 5–20 min to reach the curb.
- **Construction.** Concourse D (19 gates, due late 2028; bridge to Concourse C) has closed gates B1–B3 (Sep 2025 – Jul 2026) and C1/C3 (from Jul 2026). The new Concourse E starts in late 2026. The O'Hare Global Terminal replaces T2 in 2029–2033. ElevateT3 is consolidating two T3 checkpoints. **Walking paths will keep changing, so the geometry model must be versioned.**
- **Minimum connection times.** No official public table; OAG's MCT database is paid. Secondary figures [S]: ORD standard 30 / 60 / 90 min (domestic–domestic / domestic–international / international–domestic); United 35 / 40 / 85; American 35 / 35 / 80.

**Benchmarks for unobserved segments:**

| Segment | Benchmark | Source |
|---|---|---|
| Bag delivery | Bags at claim within **20 min of gate arrival** or compensation (Alaska, domestic). Delta runs a similar 20-min guarantee [S] | [Alaska](https://www.alaskaair.com/content/travel-info/baggage/baggage-claim/delayed-damaged-missing) |
| Bag delivery (planning) | Most domestic flights are unloaded and claimed within a ≈ 20-min window; + ≈ 10 min for bags missing the first carousel rotation; widebodies longer | [ACRP Report 25](https://onlinepubs.trb.org/onlinepubs/acrp/acrp_rpt_025v1.pdf) |
| Deplaning | ≈ 14–20 passengers/min per door [S]. Open literature lacks empirical deboarding distributions | [S] |
| Gate → curb (rules of thumb) | Domestic with bags 30–45 min after touchdown; international 60–90+ min [S] | – |
| Curb dwell | Illustrative 3-min dwell; acceptable curb delay ≤ 30–60 s | [ACRP Report 40](https://crp.trb.org/acrpwebresource2/wp-content/themes/acrp-child/documents/038/original/ACRP_40_Airport_Curbside_and_Terminal_Area_Roadway_Operations.pdf) |

### 4.5 ADS-B and commercial flight data

| Source | Access / price | History | Licence and display | Verdict |
|---|---|---|---|---|
| **adsb.lol** ([API](https://api.adsb.lol/api/openapi.json), [archive](https://github.com/adsblol/globe_history_2026)) | Free, anonymous (keys "in the future"; production users asked to contact) | Daily global archives on GitHub **2023 →** (≈ 1–2 TB/year; filter to the ORD region) | **ODbL**: attribution + share-alike for derived databases. Does *not* filter LADD (offers `/v2/ladd` lists) | **Primary open ADS-B source** for training and for the live product |
| OpenSky Network ([REST](https://openskynetwork.github.io/opensky-api/rest.html), [terms](https://opensky-network.org/about/terms-of-use)) | OAuth2 client credentials (basic auth retired). 400 / 4,000 / 8,000 credits/day (anonymous / registered / feeder). Arrivals/departures are previous-day batch only | Trino database: state vectors 2013 →, flights 2016 →. Free to **university-affiliated researchers** | **Non-profit research and education only.** "Operational use of the REST API in any live product … requires a written license, regardless of … non-profit status" | Research and training only (if eligible). **Not for the live site** without a licence |
| ADS-B Exchange (JETNET) ([data products](https://www.adsbexchange.com/data-products/)) | Community API $10/mo for 10 k requests (non-commercial); Enterprise on quote | Snapshots 2016/2020 →; free sample days (1st of each month, incl. runway-tagged operations) | No publishing without an Order Form | Licensed use only. Samples are useful for prototyping |
| airplanes.live / adsb.fi | 1 req/s; non-commercial. airplanes.live now **gated** (403, contact required) | – | Non-commercial; attribution | Not for the product |
| **AeroDataBox** ([pricing](https://aerodatabox.com/pricing/)) | Direct: Starter $19 (40 k units), Growth $99, Scale $499. API.Market/RapidAPI: free 400 units; Pro $7.50–8; Ultra $37.50–40; Mega $187.50–200. FIDS board = 2 units/call | 365 days | Commercial use on paid plans; B2B only on Mega/Scale. **Caching 7 days on lower tiers; "never make permanent copies"** | **Cheapest live board** (gates, status, estimates). Cannot double as a training archive |
| **FlightAware AeroAPI** ([pricing](https://www.flightaware.com/commercial/aeroapi/), [Standard licence](https://www.flightaware.com/commercial/aeroapi/AeroAPI_Standard_License.pdf)) | Personal: no minimum, $5/mo free, **personal or academic only**. Standard: $100/mo minimum, B2C allowed. Premium: $1,000/mo minimum, B2B and **Foresight**. Airport board endpoints $0.005 per 15 records; `/flights/{ident}` $0.005; Foresight $0.015; volume discounts above $1 k/mo | 2011 → (Standard and above) | **Raw data ≤ 30 days**; **no use "in conjunction with or as a backfill to" other real-time providers** without written permission; attribution required; Terms of Use bar betting/prediction-market products | High-quality but restrictive. Choose it *or* other live feeds, not both, without permission |
| Flightradar24 API ([plans](https://fr24api.flightradar24.com/subscriptions-and-credits)) | Explorer $9 / Essential $90 / Advanced $900 per month + credits | 30 days → all, by plan | **No schedule data**; ≤ 30-day storage; no backfill of other feeds; bars "competing services" | Poor fit (movement-only; competition clause) |
| AviationStack / Airlabs | $0–499/mo tiers; free 100 / 1,000 requests | AviationStack 3-month window | AviationStack display terms ambiguous; Airlabs silent on redistribution | Possible fallbacks; read the terms closely |
| Cirium (FlightStats → Cirium Sky), OAG | Trials (OAG: free key to explore); production by contract | Deep | Contract | Enterprise-grade; overkill for the MVP |
| Amadeus Self-Service (incl. Flight Delay Prediction API) | **Decommissioned 17 Jul 2026** | – | – | Gone |
| D-ATIS (`atis.info`, formerly `datis.clowd.io`) | Free JSON for ≈ 70 US airports incl. KORD (runways in use, approaches) | Self-archive | No published terms or operator | Valuable runway-configuration feature. Archive it, and prefer SWIM for public use |

### 4.6 Licensing: what a public website may show, and what it costs

**Displayable with public-domain or open data:**

- **Historical analytics** from BTS, ASPM public modules, OPSNET, CBP AWT and TSA throughput.
- **Live FAA status** (NAS Status, advisories, NOTAMs).
- **Weather** (NOAA/IEM, served from the project's own cache).
- **ADS-B-derived positions and landing times from adsb.lol**, under ODbL attribution and share-alike.
- **The project's own model outputs.**

That is enough for the whole Phase 1 product and most of the Pickup Planner.

**Requires a commercial licence:**

- Flight-number status with gates, terminals and airline estimates (AeroDataBox paid, AeroAPI Standard+, Cirium, OAG).
- Foresight ETAs (AeroAPI Premium).
- Any OpenSky-powered live feature.
- B2B resale.

The CDA's flight-status JSON (vendor data credited to OAG) has **no published terms**, so ask the CDA before using it.

**Architecture consequences:**

1. **Per-licence retention.** Public-domain and ODbL feeds go into the permanent bi-temporal archive. Licensed feeds are stored only within their terms (AeroAPI ≤ 30 days raw; AeroDataBox ≤ 7 days on lower tiers, no permanent copies). The project's own *archive of airline-posted status* therefore cannot be built from these feeds. The archivable public alternative is **FAA SWIM TFMS** (Phase 3).
2. **No silent mixing.** AeroAPI and FR24 forbid combining their data with other real-time feeds without permission. Pick one licensed provider per function, or obtain written permission.
3. **LADD compliance** applies if positions are displayed from FAA-derived feeds. Filtering LADD aircraft is good practice regardless; ORD airline traffic is rarely affected.

**Monthly cost scenarios** for a near-real-time ORD board (≈ 2,300 operations/day; rolling 4-h window; prices as verified in Oct 2026):

| Approach | Every 15 min | Every 5 min | Notes |
|---|---|---|---|
| **AeroDataBox airport board** (2 units/call) | **≈ $15** (≈ 5.8 k units; API.Market Pro 2) | **≈ $19–40** (≈ 17.5 k units; Direct Starter) | Gates and status included; 7-day cache |
| AeroAPI airport-board endpoints | ≈ $396 | ≈ $1,132 (after volume discount) | Standard tier minimum is $100 |
| AeroAPI per-flight checks | ≈ $3,238 | ≈ $6,133 | Board polling is far cheaper |
| AeroDataBox per-flight status | ≈ $499–895 | ≈ $2,486+ | – |
| Flightradar24 movement board (no schedules) | ≈ $450 | ≈ $1,110–1,170 | Not recommended |
| **Free path:** FAA NAS Status + ATCSCC + adsb.lol + D-ATIS | $0 | $0 | No gates or airline ETAs; callsign mapping required |

**Recommendation.** Use the **free path** for Phase 1 and the Pickup Planner beta. Add **AeroDataBox (≈ $15–40/mo)** only if gate and terminal data prove necessary, and only within its caching terms. Defer AeroAPI or Cirium until a value-of-information ablation (§6.5) shows that the extra fields pay for themselves.

## 5. Feature feasibility matrix

**Legend.**

- **Availability at prediction time:** ● available; ◐ partial, approximate or forecast-only; ○ not available.
- **Relevance:** H/M/L, from the literature (§6.1) and the ORD evidence (§2). Final rankings come from Phase 1 ablations.
- **Effort:** integration complexity, L/M/H.

### 5.1 The matrix

**Flight characteristics**

| Feature | Rel. | Source (history) | 24 h | 6 h | 3 h | 1 h | En route | Quality / leakage notes | Effort |
|---|---|---|---|---|---|---|---|---|---|
| Carrier (operating + marketing), flight number, route, distance, scheduled times, scheduled block | H | BTS (1987/2018 →); schedule feed for future dates | ● | ● | ● | ● | ● | Codeshare mapping; regional operators | L |
| Aircraft type / seats (planned) | M | BTS tail → Registry/B-43 (actual); live status (planned) | ◐ typical | ◐ | ● | ● | ● | **Actual tail is post-hoc at long horizons** | M |

**Historical performance**

| Feature | Rel. | Source (history) | 24 h | 6 h | 3 h | 1 h | En route | Quality / leakage notes | Effort |
|---|---|---|---|---|---|---|---|---|---|
| Rolling delay/cancellation rates by flight number, route, carrier, hour | H | BTS | ● | ● | ● | ● | ● | **Respect the 6–8-week BTS publication lag**, or use self-measured ADS-B outcomes for recent weeks | L |
| Climatology (month × weekday × hour); previous-day ORD disruption index | M | BTS; own archive | ● | ● | ● | ● | ● | – | L |

**Weather**

| Feature | Rel. | Source (history) | 24 h | 6 h | 3 h | 1 h | En route | Quality / leakage notes | Effort |
|---|---|---|---|---|---|---|---|---|---|
| ORD forecast P(ceiling < 1,000 ft or visibility < 3 mi), P(< 5,500 ft / 7 mi), P(thunder), precipitation type/snow, gusts | **H** | NBM (2020 →), LAMP (2006 →), TAF (1996 →), HRRR (2014 →) | ● | ● | ● | ● | ● | Version breaks; **never use observed weather for the future** | M |
| Forecast runway wind components (head/cross/tail per flow) → expected flow and flow-change risk | H | Same | ● | ● | ● | ● | ● | True vs. magnetic heading | M |
| Observed ORD weather (5-min METAR) | H (≤ 1 h) | IEM (1946 →) | ○ | ◐ | ◐ | ● | ● | Persistence only for future hours | L |
| Lightning within 3/5/10 mi; minutes since last flash (ramp-closure proxy) | M–H | GLM (2018 →), MRMS (2020 →) | ○ | ○ | ◐ | ● | ● | No ground truth for ramp closures | M |
| Convective outlooks (SPC Day 1–3, TCF 4–8 h) | M | IEM (1987 / 2004 →) | ● | ● | ● | ◐ | ◐ | Category changes in 2026 | L |
| Origin/destination and en-route weather (TAF/NBM at the other airport; SIGMET/TCF polygons along the route) | M–H | Same archives | ● | ● | ● | ● | ● | Route geometry approximations | M–H |
| Winter severity (NBM snow and precipitation-type probabilities) | H (winter) | NBM, LAMP | ● | ● | ● | ● | ● | WSSI is real-time only | M |

**Airport operations**

| Feature | Rel. | Source (history) | 24 h | 6 h | 3 h | 1 h | En route | Quality / leakage notes | Effort |
|---|---|---|---|---|---|---|---|---|---|
| **Scheduled demand per 30 min vs. expected capacity** (capacity profile × forecast weather category × flow) | **H** | Schedules (BTS history; feed for future dates; ADS-B for non-reporting operators) | ● | ● | ● | ● | ● | BTS omits foreign and non-reporting operators | M |
| Runway configuration (current / predicted) | M–H | NAS Status JSON + D-ATIS (live, self-archive); ADS-B-inferred (history); ASPM (restricted) | ◐ from wind | ◐ | ◐ | ● | ● | Configuration labels change with layout eras | M–H |
| Called arrival/departure rates (AAR/ADR) | H | NAS Status JSON (live, when events); ASPM (restricted) | ○ | ◐ | ◐ | ● | ● | Present only when programs are active | M |
| Recent taxi-out / taxi-in (as of now) | M–H | ADS-B (live); BTS (history) | ○ | ◐ | ● | ● | ● | Exclude flights not yet completed | M |
| Gate / terminal / baggage carousel | M (taxi-in, pickup, connections) | Licensed status APIs; CDA JSON (terms unknown) | ○ | ◐ | ● | ● | ● | **No history** in BTS | M |
| Construction / closures / cap regime flags | M | NOTAMs, CDA/ONCC notices, FAA orders | ● | ● | ● | ● | ● | Manual curation | M |

**Air traffic control**

| Feature | Rel. | Source (history) | 24 h | 6 h | 3 h | 1 h | En route | Quality / leakage notes | Effort |
|---|---|---|---|---|---|---|---|---|---|
| Active GDP / ground stop / AFP at ORD and destination (avg/max delay, scope, end time) | **H** | NAS Status (live); ATCSCC advisories (2001 →) | ◐ | ● | ● | ● | ● | Index by **issuance time** | M |
| Planning advisories (programs flagged as "probable" in ATCSCC operations plans) | M–H (2–8 h) | ATCSCC | ◐ | ● | ● | ● | – | Text parsing | M |
| Flight-specific EDCT | H (≤ 2 h) | SWIM TFMS (approval); ASPM (restricted) | ○ | ○ | ◐ | ● | – | Bulk access gated | H |
| National program count / NAS stress | M | NAS Status | ◐ | ● | ● | ● | ● | – | L |

**Aircraft and airline operations**

| Feature | Rel. | Source (history) | 24 h | 6 h | 3 h | 1 h | En route | Quality / leakage notes | Effort |
|---|---|---|---|---|---|---|---|---|---|
| **Inbound-aircraft readiness** (predicted in-block + minimum turn − scheduled departure) | **Very H** | Live tail link (status API, or ADS-B hex ↔ registry); BTS rotations (history) | ○ | ◐ | ● | ● | – | **Post-hoc tail swaps leak at long horizons** | H |
| Aircraft's cumulative delay so far today | H | BTS (history); ADS-B (live) | ○ | ◐ | ● | ● | – | As above | M |
| Scheduled turn buffer | H | Schedule (planned) | ◐ | ◐ | ● | ● | – | Planned rotations not public long-range | M |
| Carrier-wide disruption today (IT outage, carrier ground stop, % of carrier delayed) | M–H | NAS Status, ADS-B, BTS (history) | ○ | ○ | ◐ | ● | ● | – | M |
| Crew legality / duty limits | H (late-day cancellations) | Not observable | ○ | ○ | ○ | ○ | ○ | Unknown | – |

**Temporal**

| Feature | Rel. | Source (history) | 24 h | 6 h | 3 h | 1 h | En route | Quality / leakage notes | Effort |
|---|---|---|---|---|---|---|---|---|---|
| Hour, weekday, month, holidays, school breaks, DST, major Chicago events | M | Public calendars (curated) | ● | ● | ● | ● | ● | Event effects are mostly on ground access and TSA | L |

**Network**

| Feature | Rel. | Source (history) | 24 h | 6 h | 3 h | 1 h | En route | Quality / leakage notes | Effort |
|---|---|---|---|---|---|---|---|---|---|
| Delay/program state at the origin (for arrivals) and destination (for departures) | H | NAS Status, ATCSCC, ADS-B, BTS (history) | ◐ | ● | ● | ● | ● | Destination GDPs drive ORD departure EDCTs | M |

**Passenger experience**

| Feature | Rel. | Source (history) | 24 h | 6 h | 3 h | 1 h | En route | Quality / leakage notes | Effort |
|---|---|---|---|---|---|---|---|---|---|
| Gate → exit walking distance; terminal transfer (ATS, airside bus) | H (pickup / connection) | OSM (ODbL), CDA pages | ● | ● | ● | ● | ● | Construction changes; version the geometry | M |
| CBP wait (hour × weekday × citizenship climatology; scheduled international arrival load) | H (T5 pickups) | CBP AWT (2023-05 →) | ● | ● | ● | ● | ● | ≈ 2-day lag; EPP break (May 2025) | M |
| Deplaning and bag-delivery time | H (pickup) | Benchmarks + opt-in feedback | ◐ | ◐ | ◐ | ◐ | ◐ | **Unobserved**: needs measurement | M |
| Security demand (screened passengers per checkpoint-hour) | M (departures) | TSA FOIA (2017 →, weekly) | ◐ | ◐ | ◐ | ◐ | – | Counts, not waits; PDF parsing | M |
| Drive time to curb (cell-phone lot or home) | H (pickup) | Routing APIs (live); TNC trips (history) | ◐ | ◐ | ● | ● | ● | Google caching limits | L–M |

**Real-time signals**

| Feature | Rel. | Source (history) | 24 h | 6 h | 3 h | 1 h | En route | Quality / leakage notes | Effort |
|---|---|---|---|---|---|---|---|---|---|
| ADS-B kinematics (distance and time to go, ground speed, altitude, holding/vectoring, arrival sequence) | **Very H** (en route) | adsb.lol (2023 → archive; live) | ○ | ○ | ○ | ◐ | ● | Callsign ↔ flight-number mapping; coverage | M–H |
| Airline-posted ETA / status / cancellation | Very H (≤ 3 h) | Licensed APIs; SWIM TFMS | ○ | ◐ | ● | ● | ● | **Licence storage limits; no free history** | M |
| TBFM scheduled times of arrival (metering) | Very H (last 30–60 min) | SWIM TBFM | ○ | ○ | ○ | ◐ | ● | Approval + JMS | H |

### 5.2 Takeaways

1. **The highest-value features with free history are:** forecast weather at ORD's capacity thresholds, scheduled demand vs. weather-dependent capacity, traffic-management programs indexed by issuance time, rotation-based aircraft features, and ADS-B kinematics. This core supports the Outlook and the en-route ETA without paid data.
2. **The features that need live-only or licensed data are:** inbound-aircraft readiness at long horizons, airline-posted ETAs, gates and EDCTs. They explain most of the short-horizon skill gap between a public project and incumbents.
3. **Leakage hotspots:** observed weather; post-hoc tails; rolling statistics over unpublished BTS months; day-level aggregates; cause codes; actual departure delay in pre-departure arrival models. Each needs a dedicated test (§7.5).
4. **Two features are not observable at all:** crew legality, and the passenger-side segments (deplaning, bags, curb). The first stays a residual; the second must be measured by the project.

## 6. Data science and modeling strategy

### 6.1 Realism anchors from the literature

Most published "90 %+ accurate" flight-delay models would not survive deployment. They test on balanced or random splits, report accuracy on imbalanced labels, or use information that is not available at prediction time. The studies below give honest anchors.

| Study | Setting | Result | Lesson |
|---|---|---|---|
| Rebollo & Balakrishnan 2014, *TR-C* 44 ([doi](https://doi.org/10.1016/j.trc.2014.04.007)) | Link-level departure-delay state (>60 min), 100 most-delayed O-D links, 2007–08 ASPM; random forest | Classification error **19.1 % at 2 h → 21.4 % (4 h) → 22.6 % (6 h) → 27.2 % at 24 h**; time-of-day-only model: 30 %. Balanced, random test samples, so optimistic | Skill decays with horizon. At 24 h most residual skill comes from the previous day's delay state |
| Gopalakrishnan & Balakrishnan 2017, ATM Seminar ([hdl](http://hdl.handle.net/1721.1/114750)) | Train 2011 / test 2012 | Headline 93.7 % accuracy vs. **93.5 %** for "always on time"; 71 % on a balanced set | Accuracy is meaningless on imbalanced labels. Use proper scoring rules against climatology |
| Aeolus benchmark 2025 ([arXiv:2510.26616](https://arxiv.org/abs/2510.26616)) | BTS 2016–24, 54.7 M flights | Schedule + weather features only: chronological-split **AUC 0.56–0.62** for arrival delay >15 min. Random split inflates AUC by **≈ 0.057** | Without live operational state, pre-departure flight-level prediction is weak. Random splits flatter models |
| Beltman et al. 2025, *JATM* 126 ([doi](https://doi.org/10.1016/j.jairtraman.2025.102788)) | Hub-airline departures 2020–23, dynamic forecasts | 90-min horizon **MAE 8.46 min**; random forest beat CatBoost and a DNN on probabilistic performance; shadow-run validated | Short-horizon distributional forecasts are operationally viable |
| GE Flight Quest 2012–13 ([GE](https://www.ge.com/news/press-releases/ge-and-partners-alaska-airlines-and-ochsner-health-system-announce-winners)) | En-route runway- and gate-arrival prediction; last 14 days held out | Winners **≈ 40 % better than the 7-min industry benchmark** (reported ≈ 4.2 min gate / 3.2 min runway error [S]) | En-route ETA is the most mature, highest-skill target |
| NASA/DrivenData Run-way Functions 2022 ([results](https://drivendata.co/blog/airport-configuration-winners)) | Runway configuration 30 min–6 h ahead; 10 airports including **KORD** | CatBoost winner (log loss 0.074 vs. 0.106 logistic). At 2 h: 41 % of changes caught at 49 % precision. "No change" is a strong baseline | Gradient-boosted trees win; persistence baselines are hard to beat |
| NASA/DrivenData Pushback to the Future 2023 ([results](https://drivendata.co/blog/airport-pushback-finalists)) | Pushback time; 10 airports including **KORD**; LAMP forecasts + Fuser data | MAE ≈ **10 min** vs. > 19 min benchmark; all winners were GBDTs | Same |
| Wang 2011, NASA ([NTRS](https://ntrs.nasa.gov/api/citations/20140008304/downloads/20140008304.pdf)) | **ORD** arrival rate below the GDP threshold (AAR ≤ 95), 2/4/6 h, TAF/CCFP-derived forecast index | AUC 0.95 / 0.93 / 0.92 (10-fold CV, so optimistic; pre-OMP runway layout). ORD GDP causes 2007–09: wind 29 %, low ceilings 25 %, thunderstorms 15 %, snow/ice 14 % | **Airport-level capacity outcomes are far more predictable from forecasts than individual flights** |
| Barnhart, Fearing & Vaze 2014, *Oper. Res.* 62(3) ([doi](https://doi.org/10.1287/opre.2014.1268)) | Passenger-centric delay reconstruction, 2007 | Average passenger delay ≈ **1.97×** average flight delay; cancellations ≈ 30 % and missed connections ≈ 18 % of passenger delay; **ORD among the six worst transfer airports** (12.2 % of connecting passengers disrupted vs. 6.9 %) | Flight on-time statistics understate traveler pain. Connections matter at ORD |
| Grinsztajn et al. 2022 ([arXiv](https://arxiv.org/abs/2207.08815)); Shwartz-Ziv & Armon 2022 ([doi](https://doi.org/10.1016/j.inffus.2021.11.011)); TabArena 2025 ([arXiv](https://arxiv.org/abs/2506.16791)) | Tabular benchmarks | Tree ensembles remain state of the art or tied; tuned deep models catch up only with heavy compute | GBDT should be the workhorse and deep learning the challenger |

None of the deep-learning or graph-neural-network delay papers reviewed shows a verified, chronological-split, flight-level win over a tuned GBDT with lag and network features. The best-documented one, STPN ([arXiv:2207.06959](https://arxiv.org/abs/2207.06959)), improves MAE ≈ 6–11 % over vector autoregression on capped, airport-level aggregates and has no GBDT baseline. Several recent papers also leak information: random splits, or BTS `WeatherDelay` used as a feature.

**Implications for this project**

1. Flight-level prediction value is concentrated **at ≤ 3 h and en route**. At 24 h, value comes mostly from **airport-level disruption forecasts** such as "tomorrow is likely a bad day at ORD", not from flight-level precision.
2. Report probabilistic skill against **climatology** (Brier skill score, CRPS skill), never raw accuracy, and publish calibration.
3. Use GBDTs (LightGBM/CatBoost) plus calibration and conformal intervals as the default. Deep models are justified only for raw trajectory or sequence inputs, and only if they beat the GBDT in the same backtest.
4. Passenger-centric targets (missed connections, time to curb) have **no public ground truth**. Model them as compositions of validated components, and collect your own data for the rest.

### 6.2 Prediction targets and horizons

| # | Target | Definition | Horizons | Label source | Phase |
|---|---|---|---|---|---|
| T1 | ORD disruption outlook | Hourly/daily share of ORD departures and arrivals delayed ≥ 15/60 min, cancellation share, P(GDP or ground stop at ORD) | 72 h → 1 h | BTS aggregates; ATCSCC advisories | **1** |
| T2 | Departure-delay distribution | Gate departure delay (min) as an ordered-bucket distribution including *cancelled*; derived P(≥15/30/60/120/180) | T-24 h, 6 h, 3 h, 1 h, 15 min | BTS | 1 (pre-day) / 2 (day-of) |
| T3 | Arrival delay / ETA | In-block (gate) and wheels-on time distributions for ORD arrivals | Pre-departure horizons; en route every 10–15 min | BTS (domestic); ADS-B landings (all flights) | **2** |
| T4 | En-route recovery | P(arrival delay < departure delay − x); expected recovered minutes | at wheels-off | BTS | 2 |
| T5 | Cancellation / diversion | P(not operated); P(diverted) | 72 h → 1 h | BTS | 1–2 (diversion: research only) |
| T6 | Propagation | P(next departure of the same aircraft delayed ≥ 15 min \| inbound state); propagated minutes | 6 h → 15 min | BTS rotations | 2 |
| T7 | Connection reliability | Historical and live P(misconnect) for a given inbound/outbound pair at ORD | booking time → en route | Derived from BTS timing (no itinerary labels) | 1 (historical) / 3 (live) |
| T8 | Curb-ready time | Distribution of when the passenger is ready at the curb (or the cell-phone-lot "leave now" time) | pre-departure → on ground | In-block validated; egress needs self-collected data | **2** |
| T9 | Operations indicators | Taxi-out time, runway configuration, AAR | 0–6 h | ADS-B-derived; D-ATIS archive | 3 (stakeholder analytics) |

### 6.3 Feasibility and usefulness by horizon

Skill is relative to climatology. Skill estimates combine the literature above with the data constraints in §4–5.

| Target | 72–24 h | 6 h | 3 h | 1 h | En route | Usefulness |
|---|---|---|---|---|---|---|
| T1 ORD disruption outlook | **Medium** (forecast-driven) | Medium–high | High | High | – | High: planning, rebooking, "leave early" decisions |
| T2 Departure-delay probabilities | Low (useful on forecast storm days) | Low–medium | Medium | Medium–high *if* inbound-aircraft status is known | – | Medium (incumbents cover the day of travel) |
| T3 Arrival delay / ETA | Low | Low–medium | Medium | Medium–high | **High** | High for pickups |
| T4 En-route recovery | Medium (structural padding) | Medium | Medium | Medium | Medium–high | Medium |
| T5 Cancellation | Low–medium; high value on storm days | Medium | Medium | Medium–high | – | High on bad days |
| T5 Diversion | Very low | Very low | Low | Low | Low–medium | Low (rare: ~0.2–0.3 % of flights [U]) |
| T6 Propagation | Low (tail unknown) | Medium | Medium–high | High | High | Medium (input to T2/T7) |
| T7 Connection risk | Historical frequencies: **high reliability** | Low–medium | Medium | Medium–high | Medium–high | High stakes; partly served by United app and Flighty |
| T8 Curb-ready time | Low | Low | Low–medium | Medium | Medium (in-block validated; egress assumed) | **High, unserved** |

### 6.4 Model design by target

**Common core**

- *Point-in-time snapshots:* one training row per flight × issue time, using only inputs with `known_time ≤ issue time` (§7.5).
- *Coherent probabilities:* for T2/T3/T5, train one **multiclass ordered-bucket GBDT** over {cancelled, diverted, ≤ 0, 1–14, 15–29, 30–59, 60–119, 120–179, ≥ 180 min}. This yields every user-facing threshold (15/30/60/120 min, plus **≥ 3 h, the DOT automatic-refund threshold for domestic flights**) from a single distribution, so no probabilities can contradict each other. Recalibrate with temperature or Dirichlet scaling on a recent window.
- *Continuous quantities* (ETA, curb time, expected delay): quantile GBDT (or LightGBMLSS/NGBoost) wrapped in **conformalized quantile regression** with day-blocked calibration sets. Use **adaptive conformal inference** to maintain coverage under drift ([CQR](https://arxiv.org/abs/1905.03222), [ACI](https://arxiv.org/abs/2106.00170)).
- *Interpretability:* monotone constraints where the physics is unambiguous (e.g., more inbound delay never lowers predicted departure delay), SHAP-based reason codes, and per-horizon model cards.
- *Key structural feature, inbound readiness:* `R = predicted inbound in-block + minimum turn time(carrier, aircraft type, ORD)` and `slack deficit = max(0, R − scheduled departure)`. This feature carries most short-horizon skill. It requires a known tail assignment, which only exists live (§5).

| Target | Baseline(s) | Main model | Uncertainty / calibration | Main pitfalls |
|---|---|---|---|---|
| T1 Outlook | Climatology (month × weekday × hour); persistence | GBDT on archived forecasts (NBM/LAMP/TAF, SPC/WPC), scheduled demand vs. expected capacity, previous-day state, national program count | Isotonic per target; reliability by season | Using observed weather; ignoring the 2026–27 FAA cap regime |
| T2 Departure | Climatology per flight number/route × month × hour; slack rule at short horizons; airline-posted delay (live shadow comparison, licence permitting) | Ordered-bucket GBDT per horizon | Temperature/Dirichlet; segment reliability (carrier, weather regime) | Post-hoc tails at long horizons; ConnectionSaver holds shift small UA delays |
| T3 ETA | Scheduled arrival + predicted departure delay − median block deviation; wheels-off + route-median air time + median taxi-in | Quantile GBDT on ADS-B features (distance and time to go, ground speed, altitude, winds, holding, arrival-flow rate, runway configuration, taxi-in congestion) | CQR by distance-to-go bucket | Callsign ↔ flight-number mapping errors; actual departure delay leaking into pre-departure snapshots |
| T4 Recovery | Scheduled minus historical median block time ("padding") | Derived from the block-deviation distribution | Isotonic | Recovery is mostly padding plus ORD arrival congestion |
| T5 Cancellation | Carrier × month × hour base rate + forecast-storm uplift | GBDT classifier, or the "cancelled" class of T2 | Platt/beta on recent windows | BTS lacks the decision timestamp, so long-horizon labels mix flights already cancelled. Day-level cancellation counts are leakage |
| T6 Propagation | Slack rule | GBDT on slack deficit + inbound distribution + ORD ground state; analytical root-vs-propagated decomposition for explanations ([AhmadBeygi 2008](https://doi.org/10.1016/j.jairtraman.2008.04.010), [Kafle & Zou 2016](https://doi.org/10.1016/j.trb.2016.08.012)) | As T2 | `LateAircraftDelay` is a post-hoc label, never a feature |
| T7 Connection | Historical frequency for the flight pair: share of days on which *actual* in-block of A + transfer time > *actual* departure of B (computable from BTS without itineraries) | Joint Monte Carlo from the A and B predictive distributions with a **shared ORD-state factor** (copula), plus an explicit hold-policy adjustment for UA-operated departures | Components calibrated separately; sensitivity analysis on transfer time and hold assumptions | Assuming independence overstates risk, because ORD-wide delays hit both flights. No ground-truth labels |
| T8 Curb-ready | In-block + fixed allowances (the limo-dispatch "ETA + offset" convention) | In-block quantiles convolved with deplaning (aircraft size, seat), walk (concourse → exit), bags (yes/no), and CBP (T5, by hour, from the AWT climatology) distributions | Report quantiles; decision rule below; recalibrate with opt-in user feedback | Only the in-block component is validated initially. Present the other components as transparent assumptions |

**Decision rule for pickups.** If arriving early costs the driver *c_w* per minute and making the passenger wait costs *c_p* per minute, the cost-minimizing time to be at the curb is the **c_w / (c_w + c_p) quantile** of curb-ready time (the newsvendor result). ORD discourages curb waiting, so the practical advice is "leave the cell-phone lot when P(passenger ready by your arrival) ≥ *p*". The interface should expose *p* as a simple preference: "I hate waiting" ↔ "never make them wait".

### 6.5 Validation protocol

1. **As-of feature store** with explicit knowledge-time rules per source (§7.5). Weather uses only **forecast products issued before the cutoff**. Never use observed weather after the cutoff.
2. **Rolling-origin evaluation by month** (expanding window), with ≥ 12 test months so every season is covered. Use a validation month before each test month for early stopping and calibration, an **embargo of ≥ 1 day**, and keep all flights of a calendar day in the same fold. Never use random K-fold splits or oversampled test sets ([Bergmeir et al. 2018](https://doi.org/10.1016/j.csda.2017.11.003); [Kapoor & Narayanan](https://arxiv.org/abs/2207.07048)).
3. **Regimes and structural breaks.** Report pooled results and results by regime: GDP/ground-stop days, snow/ice days, convective days, holiday peaks, first and last banks.
   - Flag or exclude Mar 2020 – mid-2021 (COVID), the 2020–21 runway transitions, and the Nov 2025 shutdown flight cuts.
   - **Model the FAA ORD operations cap (2 Jun 2026 – 30 Oct 2027) as its own regime.**
   - For cause analyses, treat the **BTS Section 511(b) cause-code change (applies to flights from 1 Jan 2027)** as a hard break.
4. **Required baselines:** climatology, persistence or slack rule, schedule-only GBDT, and the airline-posted or FAA ETA via a live shadow comparison. Where licences limit raw retention, store only the derived error metrics. The airline ETA is the bar a consumer product must beat.
5. **Ablations as value of information:** forecast weather vs. none vs. "oracle" observed weather; with vs. without inbound/tail features; with vs. without FAA advisories. Each gap prices a data source, which directly informs whether to pay for commercial feeds.
6. **Leakage checklist:**
   - departure delay, taxi-out or wheels-off used in pre-departure arrival models;
   - delay-cause fields used as features;
   - day-level aggregates such as daily cancellations or "type of day";
   - delay states indexed by actual rather than scheduled time;
   - target encodings fitted on all data;
   - dropping cancelled or diverted flights (survivorship);
   - post-hoc tail rotations at long horizons;
   - rolling "recent performance" features that use BTS months not yet published at the cutoff.
7. **Uncertainty in the comparison itself:** block-bootstrap by day for confidence intervals on metric differences.

### 6.6 Metrics

- **Probabilities** (thresholds, cancellation, GDP): Brier score and **Brier skill score vs. climatology**, log loss, reliability diagrams with equal-mass bins, calibration slope and intercept, ECE. Use PR-AUC for rare events and ROC-AUC as secondary. Monotonicity violations across thresholds must be zero.
- **Distributions / continuous:** CRPS (primary), pinball loss at decision quantiles, MAE / median absolute error, and 80/90 % interval coverage and width, by horizon and regime ([Gneiting & Raftery 2007](https://doi.org/10.1198/016214506000001437)).
- **Alerts** ("P(≥ 60 min or cancelled) ≥ p"): precision and recall at fixed lead times, false alarms per 100 flights, and the distribution of lead time gained over the airline's first posted delay.
- **Decision metrics:**
  - Pickup: realized asymmetric cost vs. two baselines, "scheduled arrival + fixed offset" and "airline ETA + fixed offset".
  - Connections: alert precision and recall with an explicit false-alarm budget.
  - Outlook: rebooking-worthy days caught vs. false alarms.
- **Public track record.** Publish rolling reliability diagrams and skill scores on the website. This is itself a differentiator (§8).

### 6.7 Is deep learning worth it?

Not for the MVP. The evidence (§6.1) favors GBDTs for tabular, mixed-type, heavy-tailed operational data. Deep learning becomes worth testing in three places:

1. **trajectory-based ETA** from raw ADS-B sequences, where sequence models may extract holding and vectoring patterns better than hand-built features;
2. **network-wide nowcasting** of delay states across airports (a GNN or spatio-temporal model as a challenger to GBDT + lag features);
3. **text**, for parsing FAA advisories and NOTAMs into structured features (an LLM-based extractor, validated against hand labels).

In each case, adopt the model only if it beats the GBDT on the same rolling-origin backtest and stays calibrated.

## 7. Data engineering and platform architecture

### 7.1 Design principles

1. **Batch first; real time only where the product needs it.** Almost all training data arrives monthly (BTS) or hourly (weather, CBP), so it fits a batch pipeline. Only the live product needs streaming-like collection: flight status, FAA programs, METARs and ADS-B. Even those are polled HTTP feeds, not true streams, until FAA SWIM is adopted.
2. **Point-in-time correctness is the core invariant.** Every stored fact carries a `valid_time` (when it happened or applies) and a `known_time` (when it was published, issued or ingested). A feature for a prediction made at time *t* may only use rows with `known_time ≤ t`. This one rule prevents most of the leakage problems described in §6: observed weather in place of forecasts, final BTS outcomes, post-hoc tail swaps, and rolling statistics that use months BTS has not published yet.
3. **Raw data is immutable, and retention follows the licence.** Everything downstream must be reproducible from raw data plus versioned code.
   - *Public-domain and open feeds* (BTS, FAA NAS Status and advisories, NOAA/IEM, CBP, adsb.lol) are kept permanently, exactly as received. Live snapshots of them cannot be re-fetched later, so the archive becomes a training asset nobody can buy.
   - *Licensed feeds* are kept only as long as their terms allow: AeroAPI ≤ 30 days raw; AeroDataBox ≤ 7 days on lower tiers, with "no permanent copies" (§4.6).
4. **One feature code path.** The same Python/SQL functions compute features for backfills, where `as_of` is a historical timestamp, and for live scoring, where `as_of` is now. This prevents training/serving skew.
5. **Licence-aware data.** Every row carries a `source` and `licence_class`: public domain, open with attribution or share-alike, non-commercial only, or commercial with display/retention restrictions.
   - The website and the archiver both filter on this column, so moving to a paid or commercial tier is a configuration change, not a rewrite.
   - Providers whose terms forbid combining their data with other real-time feeds (AeroAPI, FR24) are isolated behind an adapter and never blended without written permission.
6. **Boring, cheap technology.** One small VM, object storage, PostgreSQL and DuckDB/Parquet. Kafka, Spark, Kubernetes or a feature-store product only come in after a measured need. The ORD-relevant data is small: national BTS on-time data is roughly 7 M rows a year, and ORD-touching rows are a few hundred thousand a year.

### 7.2 Logical architecture

```
SOURCES
 Batch / public ......  BTS On-Time, T-100, DB1B, B-43 · FAA registry & NASR · ATCSCC advisory archive ·
                        IEM METAR/TAF/MOS · NBM/LAMP/HRRR (AWS Open Data) · CBP AWT · TSA FOIA throughput ·
                        Chicago Data Portal (TNC, taxi, CTA) · ADS-B history (adsb.lol / OpenSky*)
 Live ................  FAA NAS Status (XML + JSON) · ATCSCC advisories · AWC METAR/TAF · ADS-B live (adsb.lol) ·
                        D-ATIS · optional licensed status API (one provider; retention per licence) · (later) FAA SWIM TFMS/TBFM/STDDS
                 │ scheduled batch jobs (orchestrator)            │ always-on pollers (async worker)
                 ▼                                                ▼
RAW ZONE  (object storage; immutable; partitioned source/yyyy/mm/dd; payloads stored verbatim + fetch metadata)
                 │
                 ▼
STAGING   (typed Parquet; UTC; de-duplicated; bi-temporal columns valid_time / known_time; licence_class)
                 │      └─► data-quality gates (schema, freshness, volume vs. schedule, null rates, key uniqueness)
                 ▼
CORE      (dbt-duckdb models): flight_leg · aircraft_rotation · flight_status_snapshot · weather_obs ·
          weather_fcst · atc_program · adsb_event · runway_config · cbp_wait · tsa_throughput · calendar
                 │
        ┌────────┴──────────────────────────────┐
        ▼                                       ▼
OFFLINE FEATURES (Parquet; as-of snapshots      ONLINE FEATURES (PostgreSQL; rolling 48 h window,
per horizon: T-24h, T-6h, T-3h, T-1h, en route)  refreshed by the scoring job)
        │                                       │
        ▼                                       ▼
TRAINING + BACKTESTS (LightGBM/CatBoost;        SCORING JOB every 5 min for all ORD flights in the next
calibration; conformal; MLflow tracking)        36 h → predictions table (quantiles, probabilities, reasons)
        └────────────► MODEL REGISTRY ──────────────┤
                                                    ▼
                               FastAPI read API (cache) ──► public web app  ·  static analytics site
                                                    │
                                                    ▼
MONITORING: feed freshness & gaps · data tests · live calibration/MAE vs. ADS-B actuals · monthly BTS truth-up · drift
   (* OpenSky = non-profit research use only; any live product needs a written licence; see §4.5)
```

### 7.3 Storage and data model

**Object storage layout:** `raw/<source>/<yyyy>/<mm>/<dd>/…` → `stage/<entity>/…parquet` → `core/…` → `features/<horizon>/…` → `models/<name>/<version>/…`. Cloudflare R2 is the default because egress is free and the first 10 GB-month is free. S3 or Backblaze B2 work just as well. A local disk mirror is enough for Phases 0–1.

**Core entities** (simplified):

| Entity | Grain | Key fields | Notes |
|---|---|---|---|
| `flight_leg` | one scheduled leg | operating carrier, flight no., origin, dest, sched. dep. date (local) | Canonical BTS record. Codeshare map to the marketing carrier. Local hhmm values (including "2400") converted to UTC with DST handling |
| `aircraft_rotation` | tail × day | tail, ordered legs, scheduled/actual ground times | Built from BTS `Tail_Number`. Source of slack and propagation features. *Actual* tails only (see leakage) |
| `flight_status_snapshot` | flight × observation | flight key, observed_at, status, est./act. times, gate, tail, source, licence_class | Bi-temporal live archive. Public-domain sources (NAS Status, SWIM) are kept permanently; licensed sources expire per their terms |
| `weather_obs` / `weather_fcst` | station × valid time (× issue time) | station, valid_time, issue_time, variables | Forecasts keyed by (issue, valid) so as-of selection is trivial |
| `atc_program` | program × revision | airport/element, type (GDP/GS/AFP/CTOP), issued_at, start/end, avg/max delay, scope | From the ATCSCC advisory archive plus the NAS Status live feed |
| `adsb_event` | flight × event | icao24, callsign, event (takeoff, landing, runway, holding, go-around, on-block proxy), time | Derived from trajectories. Raw tracks kept 30–90 days |
| `cbp_wait`, `tsa_throughput` | terminal/checkpoint × hour | waits, volumes | Mostly climatology features. CBP data is lagged |
| `calendar` | date | holidays, school breaks, DST, major Chicago events | Hand-curated plus scraped calendars |

**Online (PostgreSQL) tables:** `flight_live`, `prediction` (flight key, as_of, horizon, model_version, quantiles/probabilities as JSONB, top reasons), `feed_health`, and an opt-in `feedback_pickup` table holding user-reported curb times, needed to calibrate the unobservable part of the pickup model.

**Sizing (order of magnitude):** National BTS on-time data in column-pruned Parquet is roughly 0.5 GB a year, so ten years is about 5 GB. ORD METARs and station-extracted NBM/LAMP values are megabytes. HRRR and MRMS must never be stored as full grids; extract ORD-area statistics and route-corridor features at ingestion. Raw ADS-B for a 100 nm ORD box can reach several GB a day, so aggregate it to events daily and expire the raw data.

### 7.4 Pipelines and schedules

| Pipeline | Cadence | Output | Notes |
|---|---|---|---|
| BTS On-Time (+ marketing-carrier file) | check daily, lands ~monthly | `flight_leg`, `aircraft_rotation`, labels | Release lag of 1–2 months: rolling "recent performance" features must respect it |
| T-100 / DB1B→DB1C / B-43 | monthly / quarterly→monthly / annual | load factors, O&D connection flows, fleet | DB1B (10 % sample) ended Q2 2025; DB1C (40 %, monthly) from Jul 2025; no timestamps |
| FAA registry / NASR | daily / 28-day cycle | tail ↔ icao24 ↔ type; runways | Joins ADS-B to BTS tails |
| ATCSCC advisories | live 2–5 min + daily backfill | `atc_program` | Includes planning advisories (programs that are "possible") |
| FAA NAS Status | 1–2 min | `atc_program` (live), delay reasons | Archive every response; there is no official history of this feed |
| METAR / TAF | 5 min live, daily IEM backfill | `weather_obs`, `weather_fcst` | TAF valid periods → hourly expansion |
| NBM / LAMP (station guidance) | hourly | `weather_fcst` | Station extraction for ORD plus ~40 network airports |
| Licensed flight-status API (optional) | 5–15 min board polls | `flight_status_snapshot` (TTL per licence) | ≈ $15–40/mo for AeroDataBox board polling (§4.6); raw rows expire per terms |
| ADS-B | continuous live; daily archive ingest | `adsb_event`, runway configuration | Landing/takeoff truth for every operator, including international flights |
| CBP AWT / TSA FOIA / Chicago Data Portal | weekly–monthly | passenger-side climatologies | Climatology, not live, inputs |
| Training | monthly (after the BTS drop) | candidate model | Promoted only if it beats the incumbent on the rolling backtest |
| Calibration refresh | weekly | calibrators | Uses ADS-B-derived actuals so it does not wait for BTS |

### 7.5 Feature pipeline (point-in-time)

Each source gets an explicit *knowledge-time rule*, kept in a single registry that is tested in CI:

- METAR: known at observation time + ~5 min. TAF/NBM/LAMP: known at issuance time + dissemination delay.
- ATCSCC advisories: known at their advisory timestamp.
- BTS outcomes: as *labels*, available only after release. As *in-day state* during historical reconstruction (e.g., "how late were ORD departures in the last hour?"), assume a departure or arrival was known when it happened. This approximates what a live feed would have shown; document it and quantify its effect once the project's own live archive exists.
- Tail assignment: in historical training the tail is the *actual* aircraft. In live use it is the *currently assigned* aircraft. Train short-horizon models with that caveat, and for horizons beyond about 6 h, use flight-number-level aggregates instead of tail-specific features.

Backfills generate snapshots at fixed offsets before each scheduled departure or arrival (T-24h, T-6h, T-3h, T-1h, T-15m, plus en-route checkpoints). Live scoring calls the same function with `as_of = now`. A property-based test asserts that no feature row ever uses an input with `known_time > as_of`.

### 7.6 Training, inference and explanations

- **Offline:** monthly retraining over a rolling-origin backtest (§6.5). A model is promoted only if it improves proper scoring rules (Brier/log loss for events, CRPS/pinball for durations) *and* keeps calibration error under a threshold on the latest holdout.
- **Online:** a batch scoring job every five minutes covers all ORD departures and arrivals in the next 36 hours (about 2–3 k flights). That is cheap enough to precompute, so the website reads predictions instead of calling the model. On-demand computation is reserved for user-specific queries: pickup from *my* location, or *my* connection pair.
- **Explanations:** SHAP contributions are mapped to plain-language reason templates, for example "Thunderstorms forecast at ORD 4–7 pm (NBM thunder probability 60 %)", "Inbound aircraft from LGA is 48 min late", "FAA ground delay program in effect for flights to SFO". They are stored with each prediction so the site can show why a prediction changed.

### 7.7 API surface (illustrative)

`GET /flights/search?number=UA1234&date=…` · `GET /flights/{key}` · `GET /flights/{key}/prediction?horizon=…` · `GET /pickup?flight=…&from=lat,lon&bags=yes` · `GET /connection?inbound=…&outbound=…` · `GET /airport/ORD/today` · `GET /reliability?carrier=&route=&month=`.
FastAPI provides typed schemas and OpenAPI documentation. Responses go through a CDN with short TTLs (30–60 s live, long for historical data), plus per-IP rate limits.

### 7.8 Monitoring

- **Data:** a freshness SLA per feed, schema-drift detection, volume checks (observed ORD movements per hour vs. schedule), null-rate and duplicate checks. If a feed goes stale, a "degraded mode" banner appears and the system falls back to the baseline model.
- **Model:** rolling Brier/CRPS/MAE against ADS-B-derived actuals (live) and BTS (monthly true-up), weekly reliability diagrams, population-stability drift on key features, and segment dashboards (carrier, weather regime, hour of day, "bad days").
- **System:** uptime pings (e.g., Healthchecks.io), error tracking (e.g., Sentry), structured logs, monthly restore test of backups.

### 7.9 Technology choices

| Need | Recommendation | Why | Defer / alternative |
|---|---|---|---|
| Languages | Python 3.12 + SQL | ecosystem; named in the brief | – |
| Environment | Conda env (`environment.yml`) + lock file (conda-lock) | reproducible, as requested | Docker images for deployment |
| Analytical storage | Parquet on object storage | cheap, columnar, portable | Iceberg / DuckLake only if concurrent writers or time travel are needed |
| Analytical engine | DuckDB (+ Polars where convenient) | single-node speed; SQL over Parquet/S3 | MotherDuck for shared cloud queries. Spark is unnecessary at this scale |
| Transformations | dbt-core + dbt-duckdb | tests, lineage, docs, reviewable SQL | SQLMesh |
| Operational database | PostgreSQL (managed free tier → small paid) | concurrency, JSONB, serving | TimescaleDB extension if time-series queries grow |
| Orchestration | Dagster OSS (software-defined assets, partitions, backfills) | partitioned backfills of monthly/daily sources are the core workload | Prefect (simpler, Python-first). Plain cron + Make for the first weeks. Airflow is overkill for one developer |
| Live collection | asyncio worker (httpx) under systemd/Docker | a handful of HTTP polls does not need a broker | Redpanda/Kafka only with multiple consumers or SWIM streaming at volume |
| ML | LightGBM / CatBoost, scikit-learn, MAPIE (conformal), SHAP | state of the art for tabular data; calibration tooling | PyTorch later for trajectory/sequence ETA models |
| Experiment tracking | MLflow (local server) | runs and model registry | Weights & Biases |
| Data quality | dbt tests + Pandera | lightweight, code-reviewed | Great Expectations / Soda |
| API | FastAPI | typed, async, OpenAPI | – |
| Internal dashboards | Streamlit | fastest analyst iteration | Panel |
| Public analytics site | Observable Framework (or Quarto) | static, fast, cheap, publication quality | Evidence |
| Public app | Next.js (React) + MapLibre GL JS + deck.gl, Protomaps tiles | mobile-first UX; open-source maps; cheap tiles | SvelteKit |
| Hosting | one small VM + Cloudflare (Pages, R2, CDN) | lowest cost and operations | Cloud Run for an autoscaled API |
| CI/CD | GitHub Actions | free for public repositories | – |

Not recommended initially: Kubernetes, Spark, Kafka, a dedicated feature store (Feast), or a microservice split. Each adds operations burden without a measured need at ORD scale.

### 7.10 Cost model (monthly, USD, order of magnitude; verify prices at build time)

| Item | Phase 0–1 (historical research + static site) | Phase 2 (live private beta) | Phase 3 (public launch) |
|---|---|---|---|
| Compute | laptop · $0 | 1 small VM ≈ $6–25 (Hetzner raised prices in Apr/Jun 2026; DigitalOcean from $4; Fly.io from ≈ $2.19 per 256 MB machine) | 2 VMs or VM + Cloud Run ≈ $30–80 |
| PostgreSQL | none | free tier (Neon free: 1 GB/project; Supabase free: 500 MB, pauses when idle) → ≈ $0–25 | ≈ $25–75 |
| Object storage | R2 free tier (10 GB-month) · $0 | ≈ $0–5 ($0.015/GB-month, no egress fees) | ≈ $5–20 |
| Static site / CDN | Cloudflare Pages or GitHub Pages · $0 | $0 | $0–20 (Vercel Hobby is non-commercial only; Pro from $20) |
| Flight-status / schedule data | $0 (BTS) | **$0 on the free path** (FAA + adsb.lol + D-ATIS); ≈ $15–40 if an AeroDataBox board is added (§4.6) | **commercial licence: ≈ $100–2,000+** (AeroAPI Standard ≥ $100 minimum, ≈ $400/mo for 15-min board polling; Premium/Foresight ≥ $1,000; Cirium/OAG by contract) |
| Traffic / routing API | $0 | free tiers | usage-based |
| Monitoring | $0 | free tiers | ≈ $0–30 |
| **Total** | **≈ $0–15** | **≈ $10–100** | **≈ $250–2,500+** |

The engineering is cheap. **Live flight data licensing is the cost driver and the main business constraint.** That supports a public-data-first sequence (Phase 1) and a deliberately small live beta (Phase 2) before any spending commitment.

## 8. Competitive landscape and differentiation

### 8.1 What already exists (verified Oct 2026)

| Product | What it does well | Prediction / analytics | Price | Notes for ORD |
|---|---|---|---|---|
| **FlightAware** (Collins/RTX) | Free "Where is my plane?" inbound check; free alerts; airport delay flags; MiseryMap | Consumer ETAs from "proprietary algorithms". **Foresight** ML ETAs, taxi and runway predictions are enterprise-only. Its claim of "30–50 % more accurate" discloses no metric ([blog](https://blog.flightaware.com/flightawares-role-in-airspace-modernization), [Foresight](https://www.flightaware.com/commercial/foresight/)) | App free; ad-free $8.99/yr | 4.9★ from ≈ 391 K ratings ([App Store](https://apps.apple.com/us/app/flightaware-flight-tracker/id316793974)) |
| **Flighty** (Apple platforms only) | Polished alerts, 25-h inbound tracking, "Airport Intelligence" for ≈ 70 North American airports including ORD | **Delay predictions** (Aug 2025) from FAA data plus the inbound aircraft. Output is a delay *length*, not a probability; claims "over 95 % accurate" without methodology. Excludes maintenance and crew causes ([help](https://flighty.com/help/delay-predictions)). **Connection Assistant** (7 Jul 2026) rates connections relaxed/normal/tight/at risk from MCT plus live conditions ([help](http://flighty.com/help/connection-assistant)) | Pro $59.99/yr; lifetime $299 | No pickup or curb features; Friends only works between Flighty users ([help](https://flighty.com/help/flighty-friends)). Android: "no immediate plans" |
| **United app** | ORD connection countdown, turn-by-turn walking times, **ConnectionSaver** hold notifications (2025) ([PR](https://www.prnewswire.com/news-releases/united-mobile-app-now-gives-people-more-information-about-their-connecting-flight-302490849.html)); inbound aircraft and **TSA wait estimates at hubs**, standby for earlier flights (1 Sep 2026) ([PR](https://united.mediaroom.com/2026-09-01-Another-First-for-United-Mobile-App-Lets-Customers-Join-Standby-for-Earlier-Flights-and-Automatically-Finds-Open-Seats-During-Disruptions)) | Delay explanations via gen-AI-assisted texts and radar maps (2024) | Free | ConnectionSaver has "saved" 3.3 M connections since 2019. United carries ≈ 47 % of ORD passengers on a marketing-carrier basis [S] |
| **American app** | Disruption rebooking flow, bag tracking (Jan 2026) ([news](https://news.aa.com/news/news-details/2026/American-empowers-customers-with-new-app-enhancements-MKG-OTH-01/default.aspx)) | Gate-to-gate walk-time wayfinding "will appear" (not live as of Apr 2026) | Free | AA ≈ 33 % of ORD passengers [S] |
| **TripIt Pro** | "Go Now" leave-for-airport countdown from location, flight status and traffic ([help](https://help.tripit.com/en/support/solutions/articles/103000063349-go-now)); risk alerts; alternate flights | No probabilities | $49/yr | 2019 security-wait feature did not include ORD |
| **Flightradar24** | Live map; airport disruption index 0–5 ([support](https://support.fr24.com/support/solutions/articles/3000120425-how-does-the-airport-disruption-widget-work-)); airport runway-usage statistics | No predictions | $2.99–7.99/mo | – |
| **Google Flights / Search; Apple** | Google: ML delay flags since 2018 (≥ 80→85 % confidence; current status unverified) ([blog](https://blog.google/products/travel/get-help-cheaper-flights-and-potential-flight-delays-winter/)). Apple iOS 26: boarding-pass Live Activities, Share Flight Tracker (iPhone-to-iPhone) ([Apple](https://support.apple.com/en-us/123179)) | Binary flags, no calibration | Free | – |
| **Ground transport** | Uber Reserve / Lyft track flights; the rider signals "ready" ([Uber](https://help.uber.com/en/riders/article/using-uber-reserve?nodeId=71708d67-bbac-4dda-9d32-53c2509bdd1b), [Lyft](https://help.lyft.com/hc/en-us/all/articles/115013078668-Scheduled-rides-for-riders)); limo dispatch (Limo Anywhere) sets pickup = FlightStats ETA + **fixed offset** ([support](https://support.limoanywhere.com/support/solutions/articles/69000882671)) | None for the egress phase | – | **Nobody models gate-to-curb** |
| **Niche predictors** | DelayGuard (BTS-based risk bands; "significantly better than a coin flip"); KnowDelay (airport-level weather delays "up to three days"); Lumo (B2B, OAG-fed); FlightQueue (crowd waits; **no ORD reports**) | Mostly unvalidated claims | $0–5/mo | Show that the space is crowded at the generic level |
| **Airport / government** | flychicago.com: flight search, maps, parking, ground transport. **No live TSA waits** (checkpoint hours only). FAA NAS Status (current programs). BTS on-time statistics | Historical and current only | Free | The leading third-party ORD app has 196 ratings, a sign of thin local-app demand |
| **Failed or pivoted** | FlightCaster (acquired 2011 after pivoting), FlightPredictor (died when its upstream API vanished), **App in the Air (shut down 2024 despite ≈ 6 M users)**, **Amadeus Self-Service APIs incl. Flight Delay Prediction (decommissioned 17 Jul 2026)** | – | – | Accuracy alone does not sell. Free upstream APIs disappear. Episodic use hurts retention |

### 8.2 Feature gap matrix (condensed)

| Capability | FlightAware | Flighty | United app | TripIt Pro | Others | **Gap?** |
|---|---|---|---|---|---|---|
| Live status, alerts, inbound aircraft | ✔ | ✔ | ✔ | partial | many | No |
| Delay prediction with causes | partial | ✔ (length, not %) | explanations only | – | DelayGuard, Google | **Calibrated %, public track record** |
| Connection guidance | – | ✔ (4-level rating) | ✔ (walk times, holds) | partial | – | Probability for self-transfers and non-UA/AA itineraries; historical pair reliability |
| Gate-to-curb / pickup timing | – | – | – | – | fixed offsets | **Yes: unserved** |
| International-arrival (T5 customs) timing for greeters | – | for connections only | – | – | FlightQueue (empty at ORD) | **Yes** |
| TSA waits at ORD | – | – | hubs (UA) | – | MyTSA (historical) | Partial; data-limited |
| ORD "why today" plus history | flags | airport status | radar texts | – | FR24 index | **Yes: explanatory and historical context** |
| Airport-level outlook 1–3 days ahead | – | – | – | – | KnowDelay (claims) | **Yes, if validated publicly** |
| Delay ≥ 3 h framing (DOT refund threshold) | – | – | – | – | – | Yes (inform; not legal advice) |

### 8.3 Does a real product opportunity exist?

**As a general consumer flight app: no.** Live tracking, inbound-aircraft awareness, FAA-program-aware delay prediction, connection guidance and sharing are already provided free or cheaply by well-funded incumbents with licensed real-time feeds. They are iterating quickly: Flighty Connection Assistant in Jul 2026, United inbound aircraft and TSA waits in Sep 2026, American wayfinding in 2026. A single-airport scope shrinks the audience further. Most ORD travelers already carry the United or American app.

**As a transparent, ORD-specific decision tool: yes, three narrow gaps hold up:**

1. **Pickup timing ("curb-ready").** No product estimates when an arriving ORD passenger will actually be at the door, especially for international arrivals through Terminal 5 customs. Uber and Lyft avoid the question with a "ready" button; limo software uses a fixed offset. This is a frequent, local pain point: for every ORD arrival there is often someone driving, circling, or sitting in the cell-phone lot.
2. **Honest uncertainty with a public track record.** Incumbents make single-number accuracy claims without methodology. A site that shows calibrated probabilities *and publishes its own reliability diagrams and skill scores* is credible and portfolio-worthy.
3. **ORD-specific explanation and outlook.** This covers "why is ORD bad today?" in plain language, the 1–3-day disruption outlook, and historical analytics. The historical side spans the 2026–27 FAA cap, the United–American capacity contest, and the 2027 BTS cause-code change. It serves travelers, journalists and researchers, and needs only public data.

**Who would use it:**

- people picking up arriving passengers (the core segment);
- ORD travelers on storm-risk days, deciding whether to rebook early or leave early;
- self-transfer and multi-airline connectors;
- local media and researchers;
- possibly limo/black-car dispatchers wanting a smarter offset.

**Willingness to pay is low.** Treat the project as a public-interest data product and portfolio piece. Possible B2B upside is small: a curb-time offset API for dispatch software, media embeds, or calibrated ≥ 3 h delay probabilities for disruption-protection products. It is not a business plan.

### 8.4 Risks specific to competing

- **Fast-follower risk:** any visible feature (e.g., pickup ETA) can be copied by Flighty or the airlines. The defensible assets are the *ORD-specific data assets* (curb-time feedback, live-snapshot archive) and *transparency* (public calibration).
- **Data dependency risk:** upstream APIs change or vanish (FlightCaster, Amadeus). Design for provider swaps (§7.1, principle 5).
- **Licensing risk:** the low-cost tiers of commercial APIs forbid commercial or B2B use or limit storage (§4).
- **Liability and expectation risk:** users may time pickups or skip rebooking based on the numbers. Show uncertainty prominently, use "as-is" language, never advise arriving late for a departure, and do not present refund eligibility as legal advice.

## 9. Project directions compared

| Direction | What it is | Traveler value | Novelty vs. incumbents | Public-data feasibility | Ground truth | Running cost | Technical depth / portfolio value | Main risk |
|---|---|---|---|---|---|---|---|---|
| **A. Reliability Lab** | Historical analytics and explainers: flight/route/airline/hour reliability, causes, propagation, the 2026–27 cap, connection-pair history | Medium (booking choices, understanding) | Medium (data exists in pieces; nobody explains ORD) | **High** | **High** (BTS) | ≈ $0 | Medium-high (rigorous EDA and causal analysis) | Being "just a dashboard" without strong narratives |
| **B. ORD Outlook** | Calibrated 1–72 h airport-level disruption forecasts (bad-day probability, GDP/ground-stop risk, cancellation rate) plus live "why today" | **High** on storm days | **High** (no validated public product) | **High** (forecast archives + FAA advisories + BTS) | **High** | ≈ $0–10/mo | High (forecast-archive engineering, calibration, public track record) | Low-signal days (most days are normal) |
| **C. Pickup Planner** | Curb-ready time and "leave now" guidance for ORD arrivals (domestic + T5 international) | **High**, frequent, local | **Highest** (unserved) | Medium (ADS-B + BTS + CBP climatology + assumptions; status API optional) | **Low at first** (egress unobserved) | ≈ $10–100/mo | High (probabilistic composition, decision theory, data flywheel) | Credibility before feedback data exists |
| D. Flight Risk | Flight-level delay/cancellation probabilities at 24 h → 15 min | Medium | Low (Flighty, United, Google) | Medium (live inbound data needed for skill) | High | $10–300/mo | Medium | Hard to beat incumbents on the day of travel |
| E. Connection Risk | Live P(misconnect) for an ORD pair | High (stakes) | Low–medium (United app, Flighty) | Medium | **None** (no itineraries) | $10–300/mo | Medium-high | Unverifiable claims; airline holds |
| F. Ops Analytics | Taxi-out, surface congestion, runway configuration, cap and construction impacts | Low for travelers | Medium (public) | Medium (ADS-B, D-ATIS archive) | Medium | ≈ $0–20/mo | High (research) | Narrow audience |
| G. Propagation network | Network/graph models of how delays spread | Low directly | Medium (research) | High (BTS tails) | Medium | ≈ $0 | High (academic) | Little user value on its own |

**Recommendation: pursue A + B first, as one public "ORD Outlook & Reliability Lab". Then build C as the flagship of the live MVP, with D embedded only where it adds value.**

- **A + B first.** They need no paid data, have rigorous ground truth, and answer the core research question. They also force the project to build the hardest and most reusable infrastructure early: the point-in-time feature store over archived forecasts, rotation reconstruction, and calibration and backtesting harnesses. The free live archivers (NAS Status, ATCSCC, D-ATIS, adsb.lol, CBP AWT) must start on day one of this phase, because those snapshots cannot be recovered later.
- **C next.** It is where the product solves a problem nobody else solves, and it reuses B's infrastructure. Its validation gap is closed deliberately through feedback and measurement.
- **E and F later, G as research.** Connection risk (E) and ops analytics (F) follow once the live archive and feedback data exist. Propagation modeling (G) runs as a research thread that feeds features into B, C and D.

## 10. MVP proposal

### 10.1 Positioning

**"ORD, honestly: will today be a bad day at O'Hare, and when will my person actually be at the curb?"** A transparent, ORD-specific decision tool that publishes its own accuracy. It is *not* a flight tracker.

### 10.2 Scope: v0.1 (public), then v0.2 (live beta)

| | v0.1 "Outlook & Lab" (public, batch) | v0.2 "Pickup Planner" (live beta) |
|---|---|---|
| **Users** | ORD travelers planning 1–3 days ahead; media and researchers | People picking up ORD arrivals |
| **Features** | (1) **ORD Outlook**: hourly and daily probabilities that ≥ X % of ORD flights are delayed ≥ 60 min or cancelled, P(GDP/ground stop), today → +3 days, with drivers in plain language. (2) **ORD Today**: live FAA program and weather status explained. (3) **Reliability Explorer**: any flight number, route, airline or hour, with delay distribution, cancellation rate, P(≥ 3 h), trend, and cause mix (with 2027 code-break handling). (4) **Connection-pair history**: how often inbound A → outbound B timing failed historically. (5) **Research notes**: "Why ORD delays happen", "What the 2026–27 cap did". (6) **Track record page**: reliability diagrams and skill vs. climatology, updated monthly | (1) Enter a flight number → **curb-ready window** (e.g., 50 / 80 / 90 % times) for domestic or T5 international, bags yes/no. (2) **"Leave now" time** from home or the cell-phone lot, with a waiting-tolerance slider. (3) Stacked timeline showing *measured* vs. *estimated* segments. (4) One-tap feedback "we met at …" to collect ground truth. (5) Shareable link |
| **Data** | BTS On-Time + Marketing Carrier files (2015 →), FAA ATCSCC advisory archive (2001 →), FAA NAS Status (self-archived), IEM METAR/TAF/MOS, NBM/LAMP/HRRR station extracts, SPC outlooks, calendar. **All public domain** | v0.1 data + **adsb.lol ADS-B** (ODbL) for takeoff/landing/en-route ETA, NAS Status JSON + D-ATIS for runway configuration/AAR, CBP AWT climatology (self-archived), OSM terminal geometry, routing API (Mapbox free tier or Google). Optional AeroDataBox board (≈ $15–40/mo) for gates and carousels, within its caching terms |
| **Models** | Outlook GBDT per horizon (24/48/72 h, 6 h, 1 h) with calibration; climatology baselines; reliability statistics | En-route ETA quantile GBDT + taxi-in model + egress convolution; conformal intervals; newsvendor decision rule |
| **Out of scope** | Live maps, push alerts, accounts, mobile apps, flight-level day-of predictions, TSA waits | Live connection probabilities, departure planning, commercial redistribution |

### 10.3 Success criteria (pre-registered before launch)

| Area | v0.1 target | v0.2 target |
|---|---|---|
| Skill | Outlook Brier skill score > 0.10 vs. climatology at 24 h, > 0.25 at 6 h; ECE ≤ 0.03 on the 12-month rolling holdout | In-block ETA MAE ≤ 5 min at 30 min to landing [baseline TBD from data]; 80 % interval coverage within 75–85 % |
| Decision value | ≥ 60 % of "bad days" (top-decile disruption) flagged ≥ 24 h ahead, at ≤ 1 false alarm per 10 normal days | Lower realized asymmetric waiting cost than "scheduled/estimated arrival + fixed offset" heuristics on feedback-labelled pickups |
| Reliability | Daily pipeline success ≥ 99 %; site static and cached | Live feed freshness SLA met ≥ 99 % of hours; graceful degraded mode |
| Learning | Public write-up of ORD delay drivers with reproducible notebooks | ≥ 200 labelled pickups in the first 3 months (volunteers + users) |

These thresholds are hypotheses to validate in Phase 1. The 24 h Outlook skill target, in particular, should be set after seeing the climatology baseline.

### 10.4 Website feature map: MVP vs. long term

| Candidate feature (from the brief) | Verdict | When |
|---|---|---|
| Search by flight number, airline, route | **Yes.** Entry point for the Reliability Explorer and the Pickup Planner | v0.1 / v0.2 |
| Historical airline/route reliability comparisons | **Yes, core** | v0.1 |
| Airport congestion and weather views ("ORD Today") | **Yes.** FAA programs, weather and the Outlook, explained | v0.1 |
| Explanations of why delays happen | **Yes** at airport level (v0.1); flight level once live inbound data exists | v0.1 → v1 |
| Updated arrival and pickup-time estimates | **Yes, flagship** | v0.2 |
| Connecting-flight risk | Historical pair reliability (v0.1); live probability later | v0.1 → v1 |
| Live flight status and delay probabilities for departures | Later. Incumbents do this well; needs licensed data for skill | v1+ |
| Personalized recommendations, alerts and accounts | Later (privacy, notification costs) | v1+ |
| Interactive maps / operational dashboards | Low priority for travelers (commodity). A stakeholder dashboard (taxi times, runway configuration, cap impacts) is a research add-on | v1+ |

### 10.5 UX sketch: the Pickup Planner (v0.2)

```
┌────────────────────────────────────────────────────────────────────┐
│ UA 1234  DEN → ORD  ·  Sched. arr 17:45  ·  Terminal 1 (Conc. C)   │
│ Status: airborne, 212 mi out · Landing est. 17:31 (±4 min)          │
├────────────────────────────────────────────────────────────────────┤
│ Your passenger is likely at the Terminal 1 curb (lower level):     │
│   50 % by 17:58 · 80 % by 18:06 · 90 % by 18:12   [checked bags ✓] │
│ ▸ Leave the cell-phone lot at 17:55 (≈ 8 min drive)                │
│   Waiting tolerance:  [I hate waiting] ●───────○ [never make them wait] │
├────────────────────────────────────────────────────────────────────┤
│ Timeline   landing ▇▇ taxi-in ▇▇▇ deplane ░░ walk ░░ bags ░░░       │
│            ▇ measured (ADS-B / history)   ░ estimated (assumptions) │
│ Why: west flow, arrivals on 27C (longer taxi-in); no FAA programs  │
├────────────────────────────────────────────────────────────────────┤
│ [ We met at 18:03 ]  ← one tap helps calibrate these estimates     │
└────────────────────────────────────────────────────────────────────┘
```

## 11. Development roadmap

### 11.1 Phases (part-time solo pace; adjust after Phase 1)

| Phase | Weeks | Milestones | Exit criteria |
|---|---|---|---|
| **0. Setup and decisions** | 1–2 | Repo and Conda environment per §12; data-catalog cards with licence class; ADRs (storage, orchestrator, ADS-B/status provider); confirm the ToS questions in §13; apply for FAA SWIM access | Approved data contracts; licence matrix signed off |
| **1a. Historical foundation** | 3–6 | BTS 2015 → ingest (+ marketing-carrier file); UTC/2400 handling; rotation reconstruction; IEM METAR/TAF; ATCSCC advisory scraper; calendar; dbt core models + tests. **Start the free live archivers (NAS Status, ATCSCC, METAR/TAF, NBM/LAMP, adsb.lol landings, D-ATIS, CBP AWT) in week 3** | Reproducible core tables; first "Why ORD delays" EDA notebook |
| **1b. Outlook + Lab** | 7–12 | NBM/LAMP/HRRR station extracts with knowledge times; point-in-time feature store; baselines; Outlook GBDT + calibration; rolling-origin backtest harness; static site v0.1 (Observable Framework) | §10.3 v0.1 targets met or documented; **public v0.1** |
| **2. Pickup Planner beta** | 13–20 | ADS-B event extraction (takeoff/landing/runway/holding); en-route ETA model; taxi-in model by terminal and flow; CBP AWT climatology; terminal geometry; egress priors; FastAPI + Postgres; web app; feedback capture; monitoring | Private beta with ≥ 50 testers; first calibration report on feedback data |
| **3. Extend** | 21–32 | Day-of flight risk using ≥ 3 months of live archive; live connection probabilities; ops analytics (cap/construction, taxi-out, runway configuration); evaluate a commercial status feed (value-of-information ablation from §6.5) | Go / no-go on public v1 and on any paid data licence |

### 11.2 Dependencies and critical path

1. **Live archive start date → everything day-of.** Public live feeds cannot be backfilled: NAS Status (programs, runway configuration, AAR), D-ATIS, ADS-B landings, and CBP's rolling window. Any model using them must wait for months of archive. *Start archiving in Phase 1a.* Licensed airline-status snapshots cannot be accumulated beyond their retention terms. The archivable public substitute is FAA SWIM TFMS, so apply for SWIM access early.
2. **Point-in-time feature store → every model.** Build it once, test it heavily (property tests), and reuse it.
3. **ADS-B provider licence → public Pickup Planner.** Choose an openly licensed source, or keep the beta private.
4. **Feedback volume → Pickup Planner credibility.** Recruit volunteers early (e.g., university communities, local forums).

### 11.3 Technical risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Federal data disruption (shutdowns delayed BTS/ATCR in 2025; NOAA product retirements) | Medium | Medium | Mirror raw data; degrade gracefully; alternative sources (ADS-B for actuals) |
| Silent leakage inflating backtests | High if unchecked | High | Knowledge-time registry, property tests, oracle ablations, a pre-registered holdout |
| Regime shifts (FAA cap, construction, 511(b) code change, RRFS/NBM upgrades) | Certain | Medium | Regime flags; recency weighting; adaptive conformal; per-regime reporting |
| ADS-B gaps (coverage, callsign ↔ flight-number mapping, codeshares) | Medium | Medium | Multi-provider fallback; mapping tables from schedules; quality metrics |
| Egress assumptions wrong | High initially | Medium | Show as estimates; collect feedback; widen intervals until calibrated |
| API terms change or service shutdown (e.g., airplanes.live gated in 2026; Amadeus APIs decommissioned) | Medium | Medium–high | Provider adapters; licence tags; no hard dependency on one vendor |
| Licence violations (retention limits, no-mixing clauses, OpenSky live-use ban, ODbL share-alike) | Medium | High | Licence matrix in the data catalog; automated TTL deletion; legal review before public launch |
| Scope creep into a generic flight tracker | High | High | Non-goals list (§10.2); "does an incumbent already do this?" test before every feature |

### 11.4 Cost summary

See §7.10 and §4.6. Phase 0–1 costs about $0–15/month. Phase 2 costs about $10–100/month on the free data path, with an optional ≈ $15–40 AeroDataBox board. A public v1 with commercial live data could cost $250–2,500+/month, mostly licensing, which is why the go/no-go decision sits at the end of Phase 3.

## 12. GitHub organization and development environment (plan only; nothing created)

Per the brief, **no repository, Conda environment, code, or data collection has been created.** This section only records the intended setup so implementation can start cleanly.

### 12.1 Repository

- **Home:** `github.com/yzysnake/ord-flight-intelligence`, a public monorepo. A single repo keeps data contracts, pipelines, models and the web app versioned together. Split it only if the web front end gets its own release cadence.
- **Proposed layout:**

```
ord-flight-intelligence/
├── README.md · LICENSE (code: Apache-2.0 or MIT) · CITATION.cff · CONTRIBUTING.md · CHANGELOG.md
├── environment.yml · conda-lock.yml · pyproject.toml   # package "ordfi", optional dependency groups
├── Makefile (or justfile)                               # env, ingest-*, build, test, backtest, docs
├── .pre-commit-config.yaml                              # ruff (lint+format), mypy, sqlfluff, nbstripout, gitleaks
├── .github/ (workflows: ci.yml, data-tests.yml, docs.yml; ISSUE_TEMPLATE/; PULL_REQUEST_TEMPLATE.md; CODEOWNERS)
├── docs/
│   ├── research/        # this feasibility study and later research notes
│   ├── adr/             # architecture decision records (ADR-0001 storage, -0002 orchestrator, -0003 flight-data provider…)
│   ├── data-catalog/    # one card per source: URL, licence_class, cadence, knowledge-time rule, known issues
│   └── model-cards/     # target, horizon, data window, metrics, calibration, limitations
├── src/ordfi/
│   ├── ingest/          # one module per source; raw-zone writers; no transformations
│   ├── timeutil/        # local↔UTC, BTS hhmm/2400 handling, DST; heavily tested
│   ├── features/        # as-of feature functions shared by backfill and live scoring
│   ├── models/          # training, calibration, conformal, backtest harness
│   ├── serving/         # scoring job, FastAPI app
│   └── quality/         # Pandera schemas, freshness checks
├── dbt/                 # staging → core → marts; tests; docs
├── pipelines/           # Dagster (or Prefect) definitions, schedules, sensors
├── notebooks/           # numbered EDA notebooks; outputs stripped; promoted code moves to src/
├── apps/ (web/ public app · site/ static analytics site · dash/ internal Streamlit)
├── tests/ (unit/ · property/ (point-in-time invariants) · integration/ (sample fixtures))
├── infra/ (docker/, compose.yml, deployment notes)
└── data/                # git-ignored; README documents the local mirror layout
```

### 12.2 Practices

- **Environment:** `conda env create -f environment.yml` (Python 3.12), pinned through `conda-lock`. Install the package itself in editable mode. A Docker image built from the lock file is the deployment artifact.
- **Workflow:** trunk-based development with short-lived branches and pull requests, Conventional Commits, and semantic version tags for model and API releases. Roadmap milestones map to GitHub Milestones. A GitHub Projects board uses labels such as `data-source`, `pipeline`, `model`, `web`, `research`, `licence`.
- **Quality gates in CI:** lint, type-check, unit tests, the point-in-time property tests, dbt tests on a small committed fixture dataset, and a "backtest smoke test" that retrains on a tiny sample and checks that metrics stay within tolerance.
- **Reproducibility:** raw partitions are immutable and carry checksummed manifests. Every model artifact records its code commit, data window, feature list and metrics, and backtest reports are published as CI artifacts. DVC is optional; manifests plus object storage are probably enough.
- **Secrets and licences:** API keys live in `.env` (git-ignored) or GitHub Actions secrets and never appear in notebooks. Data is not committed. Every data-catalog card records the source licence and attribution text, for example ODbL attribution for OpenStreetMap or adsb.lol, OpenSky's citation requirement, and commercial API display terms.
- **Documentation:** a MkDocs-Material site built from `docs/`, plus the public analytics site. The research report is versioned like code.

## 13. Challenging the brief: unknowns, questionable assumptions and further research

### 13.1 Assumptions in the original brief that the evidence challenges

1. **"Predict delays 24 hours ahead for individual flights."** Pre-departure flight-level models built from schedule and weather alone reach only about AUC 0.56–0.62 under honest chronological splits (§6.1). The useful 24–72 h product is an **airport-level disruption outlook**; flight-level precision mostly arrives with inbound-aircraft information (≤ 3 h) and en route.
2. **"Delay predictions help departing passengers."** Only some decisions benefit: rebooking early before storms, choosing a more reliable flight at booking, and leaving early on bad-traffic days. A prediction of *delay* must never encourage arriving late. Airlines recover delays, swap aircraft and close doors on time. The product should frame departure risk as "plan for disruption", never as "you have more time".
3. **"Predict missed connections."** No public data records itineraries or misconnections. United holds flights for connecting passengers (ConnectionSaver at ORD since April 2019; 3.3 M connections "saved"). The independence assumption overstates risk, because ORD-wide delays hit both flights. The honest products are **historical pair reliability** and a clearly labelled *model estimate* with sensitivity ranges.
4. **"Use runway configuration, gate assignments, taxi data, security waits as features."** These are the hard-to-get variables:
   - Historical runway configuration is not publicly downloadable in bulk; it must be inferred from ADS-B or archived from D-ATIS.
   - Historical gate assignments are not in BTS.
   - Live ORD security waits are not published by the airport.
   - FAA surface data (ASDE-X) needs SWIM approval and has no archive.
5. **"Airlines and airport operators as users."** They have strictly better internal data (A-CDM, crew, bookings). A public tool can serve them only as an independent analysis or research partner.
6. **"Do not assume ORD performs poorly."** The brief was right to question this, and the answer depends on the period. In 2023 ORD *beat* the national on-time arrival rate (79.2 % vs. 78.3 %) and ranked 4th of 15 large peers. In 2025–26 it fell to the bottom fifth of major airports, as operations grew 10.5 % to 857 k (most in the world) during airfield construction and the United–American capacity race. The FAA responded with a daily operations cap (§2). Any "ORD is bad" narrative on the site should therefore be dated and decomposed, not asserted.
7. **"International arrivals."** BTS covers only domestic flights of US reporting carriers. International arrivals at T5, the hardest pickup case, need ADS-B or a commercial feed for ground truth.

### 13.2 Unavailable or restricted data (verified gaps)

| Needed | Status | Workaround |
|---|---|---|
| As-of (planned) tail assignments, historical | Not public | Live archive; flight-number-level features at long horizons |
| Historical airline-posted ETAs / delay announcements | Not public. Commercial feeds forbid long-term storage (AeroAPI ≤ 30 days raw; AeroDataBox no permanent copies) | Archive public-domain equivalents instead: NAS Status, ADS-B, and FAA SWIM TFMS (apply early). Keep only licence-compliant derived aggregates |
| Cancellation decision timestamps | Not in BTS | Accept label mixing at long horizons; measure it with the live archive |
| Historical runway configuration (bulk) | FAA ASPM access is restricted [see §4] | Infer from ADS-B; archive D-ATIS |
| Gate-level history | Not public | Live FIDS/status archive (licence permitting) |
| Passenger itineraries / misconnections | Not public (DB1B/DB1C are ticket samples without times) | Historical timing-based pair reliability |
| Baggage delivery, deplaning, curb times | Not public | Benchmarks + opt-in feedback + volunteer measurement |
| Live TSA waits at ORD | Not published by CDA | Throughput-based estimates (lagged) or skip |
| Lightning ramp-closure records | Not public | GLM/MRMS lightning-ring proxies |
| Real-time-only weather products (WSSI, eTCF/ECFP, GTG/IFI) | No archive | Archive from day one or skip |

### 13.3 Open questions to resolve before or early in implementation

1. **Licensing.** Confirm the current terms for the chosen ADS-B and status providers: public display, storage duration, caching, attribution, and mixing restrictions such as AeroAPI's ≤ 30-day storage and no-mixing clause. Also confirm flychicago.com terms for any FIDS use and LADD obligations if positions are displayed.
2. **ORD reporting coverage.** What share of ORD departures and arrivals is covered by BTS reporting carriers in 2025–26 (regional partners, foreign carriers)? Quantify it in Phase 1a, with ADS-B as the denominator.
3. **Cap regime.** How did delays respond to the cap (2 Jun 2026 →)? This needs BTS months for Jun–Oct 2026, released with a lag of about 2 months.
4. **ORD capacity today.** Current called arrival and departure rates by configuration after the 2020–21 runway changes, and during construction. The public 2018 capacity profile predates 9C/27C.
5. **Egress priors.** What deplaning, walking and bag-delivery distributions does ORD actually exhibit? Run a structured measurement study (stopwatch logs for ~50 arrivals across terminals) in Phase 2.
6. **Volunteer and partner data.** Is the Chicago Department of Aviation willing to share anonymized curb or wait-time sensor data for research? A university research affiliation may help.

### 13.4 Additional research directions the brief did not mention

1. **The 2026–27 FAA cap as a natural experiment.** Measure how ORD delays respond to a binding demand cap, using a difference-in-differences design against other hubs and against Summer 2025. This is a publishable, policy-relevant analysis.
2. **Construction and surface congestion.** The FAA says surface constraints, not runways, limit ORD capacity during construction. ADS-B taxi-time analysis (taxi-out by runway/flow/terminal) can quantify this.
3. **United–American competitive scheduling.** Quantify how schedule peaks (operations per half-hour vs. called rates) changed through the 2024–26 gate dispute, and how much delay they caused.
4. **Regional-jet exposure.** Partner-operated flights make up about half of ORD domestic arrivals. Literature suggests airlines cancel smaller and spoke flights first under ground delay programs. Test this at ORD: which travelers bear cancellations?
5. **Destination-driven delays.** ORD departures to New York or other capacity-limited airports inherit those airports' GDPs and EDCTs. Decompose ORD departure delay into ORD-caused and destination-caused shares.
6. **Passenger-weighted performance.** Weight delays by seats or load factor (T-100) instead of flights, and estimate passenger delay (a connection-aware metric following Barnhart et al.).
7. **MDW vs. ORD for Chicago travelers.** "Should I fly from Midway?" is a real decision. Compare reliability by route and weather regime.
8. **Communication research.** How should probabilities be shown (icons, ranges, words) so users act correctly? A small user study would improve the product more than another model feature.
9. **The 2027 BTS cause-code break.** Re-estimate cause shares across the break, and document how "air carrier" delay changes when the 511(b) events are moved out.

---

## Appendix A. Reproducing the headline BTS figures

The ORD comparisons in §2 come from BTS TranStats cause-of-delay pages. They are reproducible without downloading data:

- **Base URL:** `https://www.transtats.bts.gov/OT_Delay/ot_delaycause1.asp?20=E&fry=N&Nv42146=<AIRPORT>&Nv42146_anzr=<NAME>&2r4v1qs41z=<FROM>&2r4v1q61=<TO>`
  - Drop the three airport parameters for national figures.
  - Prefix `6B2r=I&` for FAA OPSNET "causes of NAS delay".
  - Prefix `6B2r=G&` for "weather's share of delayed flights".
  - Prefix `qv52ynB=qn6n&` for counts and minutes.
  - Append `&Pn44vr4=<CARRIER>` for one operating carrier.
- **Example (ORD, 2024):** [link](https://www.transtats.bts.gov/OT_Delay/ot_delaycause1.asp?20=E&fry=N&Nv42146=beQ&Nv42146_anzr=Puvpnt1%2C%20VY%3A%20Puvpnt1%20bUn4r%20V06r40n6v10ny&2r4v1qs41z=FHFLM&2r4v1q61=FHGDD).
- **Period codes** encode year × 12 + month with digits 0–9 written as D–M:

  | Period | FROM | TO |
  |---|---|---|
  | 2019 | FHFFM | FHFHD |
  | 2023 | FHFKK | FHFLL |
  | 2024 | FHFLM | FHGDD |
  | 2025 | FHGDE | FHGEF |
  | Jan–Aug 2026 | FHGEG | FHGFD |

- **Airport codes:** ORD `beQ`, MDW `ZQj`, ATL `NgY`, DFW `QSj`, DEN `QRa`, JFK `WSX`, EWR `Rje`, LGA `YTN`, SFO `fSb`, LAX `YNk`, CLT `PYg`, IAH `VNU`, MCO `ZPb`, LAS `YNf`, MSP `Zfc`.
- **Carrier codes:** UA `hN`, AA `NN`, SkyWest `bb`, Envoy `Zd`, Republic `lk`.
- **Airport profile page** (ranks among major airports): [ORD profile](https://www.transtats.bts.gov/airports.asp?20=E&Nv42146=beQ&Nv42146_anzr=Puvpnt1%2C+VY%3A+Puvpnt1+bUn4r+V06r40n6v10ny&pn44vr4=SNPgf).

**Caution.** TranStats cause pages, airport profiles, "Flight Delays at a Glance", the ATCR and Cirium use different carrier sets and denominators. Fix one series per analysis. Phase 1 should recompute everything from raw BTS files.

## Appendix B. Selected primary sources

**Regulation and policy**

- [FAA ORD scheduling-limit order, 91 FR 21071](https://www.govinfo.gov/content/pkg/FR-2026-04-20/pdf/2026-07665.pdf)
- [ORD order amendment](https://www.govinfo.gov/content/pkg/FR-2026-04-27/pdf/2026-08163.pdf)
- [ORD order extension to 30 Oct 2027](https://www.govinfo.gov/content/pkg/FR-2026-07-14/pdf/2026-14147.pdf)
- [Section 511(b) delay-cause final rule](https://www.govinfo.gov/content/pkg/FR-2026-09-03/pdf/2026-18040.pdf)
- [511(b) delay of effective date](https://public-inspection.federalregister.gov/2026-21058.pdf)
- [14 CFR 234.2](https://www.law.cornell.edu/cfr/text/14/234.2), [234.4](https://www.law.cornell.edu/cfr/text/14/234.4), [234.11](https://www.ecfr.gov/current/title-14/chapter-II/subchapter-A/part-234/section-234.11)
- [DOT automatic refund rule](https://www.govinfo.gov/content/pkg/FR-2024-04-26/html/2024-07177.htm)
- [Withdrawal of the delay-compensation proposal](https://www.govinfo.gov/content/pkg/FR-2025-11-17/html/2025-20042.htm)
- [DOT OIG AV2025003 on delay data](https://www.oig.dot.gov/library-item/46490)
- [FAA LADD program](https://www.faa.gov/pilots/ladd)

**ORD operations**

- [BTS ORD airport profile](https://www.transtats.bts.gov/airports.asp?20=E&Nv42146=beQ&Nv42146_anzr=Puvpnt1%2C+VY%3A+Puvpnt1+bUn4r+V06r40n6v10ny&pn44vr4=SNPgf)
- [DOT Air Travel Consumer Report, Dec 2024 (ROSA P)](https://rosap.ntl.bts.gov/view/dot/82026)
- [CDA facility data](https://www.flychicago.com/business/CDA/factsfigures/Pages/facility.aspx)
- [CDA 2025 traffic summary](https://www.flychicago.com/SiteCollectionDocuments/Business/AccessiblePDFs/FactsandFigures/AirTraffic/1225%20ORD%20SUMMARY%20REVISED.pdf)
- [ORD annual operations 2006–2025](https://www.flychicago.com/SiteCollectionDocuments/Community/AccessiblePDFs/Noise/O%27Hare/AR/ORD_Annual_Operations_%282006-2025%29.pdf)
- [ACI world rankings 2025](https://aci.aero/2026/07/15/worlds-busiest-airports-atlanta-holds-asia-climbs-strong-demand-while-asia-pacific-growth-reshape-the-rankings/)
- [FAA ORD capacity profile 2018](https://www.faa.gov/sites/faa.gov/files/airports/planning_capacity/profiles/ORD-Airport-Capacity-Profile-2018.pdf)
- [CDA east/west flow analysis](https://oharenoise.org/resources/presentations/technical/403-east-west-flow-operations/file)
- [ONCC 2025 construction briefing](https://oharenoise.org/sitemedia/documents/2024/ORD-ONCC-2025-Airfield-Construction-110725.pdf)
- [FAA–EUROCONTROL operational comparison (2024 edition)](https://www.eurocontrol.int/sites/default/files/2024-01/eurocontrol-comparison-atm-related-performance-us-europe.pdf)
- [GAO on delay sources](https://www.gao.gov/assets/a304866.html)
- [NWS ORD normals](https://www.weather.gov/lot/ord_rfd_monthly_yearly_normals)

**Flight, ATC and ADS-B data**

- BTS On-Time [profile](https://www.transtats.bts.gov/DatabaseInfo.asp?QO_VQ=EFD&Yv0x=D) and fields ([reporting carrier](https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=FGJ), [marketing carrier](https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=FGK))
- [BTS Technical Directive #40](https://www.bts.gov/explore-topics-and-geography/modes/aviation/number-40-technical-directive-reporting-time)
- [FAA ASPM portal](https://www.aspm.faa.gov/)
- [FAA NAS Status XML](https://nasstatus.faa.gov/api/airport-status-information)
- [ATCSCC advisories](https://www.fly.faa.gov/adv/advAdvisoryForm)
- [FAA SWIM access](https://www.faa.gov/air_traffic/technology/swim/products/get_connected)
- [FAA aircraft registry download](https://www.faa.gov/licenses_certificates/aircraft_certification/aircraft_registry/releasable_aircraft_download)
- OpenSky [REST](https://openskynetwork.github.io/opensky-api/rest.html) and [terms](https://opensky-network.org/about/terms-of-use)
- adsb.lol [API](https://api.adsb.lol/api/openapi.json) and [archive](https://github.com/adsblol/globe_history_2026)
- [ADS-B Exchange data products](https://www.adsbexchange.com/data-products/)
- FlightAware AeroAPI [pricing](https://www.flightaware.com/commercial/aeroapi/) and [Standard licence](https://www.flightaware.com/commercial/aeroapi/AeroAPI_Standard_License.pdf)
- [Flightradar24 API plans](https://fr24api.flightradar24.com/subscriptions-and-credits)
- [AeroDataBox pricing](https://aerodatabox.com/pricing/)
- [DrivenData Run-way Functions rules](https://www.drivendata.org/competitions/89/competition-nasa-airport-configuration/page/419/)

**Weather**

- IEM [ASOS](https://mesonet.agron.iastate.edu/request/download.phtml), [TAF](https://mesonet.agron.iastate.edu/request/taf.php) and [MOS](https://mesonet.agron.iastate.edu/mos/)
- [MDL LAMP archive](https://vlab.noaa.gov/web/mdl/lamp-archived-bulletins-year)
- [NBM text archive](https://vlab.noaa.gov/web/mdl/nbm-text-archives)
- [HRRR on AWS](https://registry.opendata.aws/noaa-hrrr-pds/)
- [MRMS on AWS](https://registry.opendata.aws/noaa-mrms-pds/)
- [AWC Data API](https://aviationweather.gov/data/api/)
- [NWS API](https://www.weather.gov/documentation/services-web-api)
- [NAM/NAM MOS retirement notice](https://www.weather.gov/media/notification/pdf_2026/scn26-47_Updated_Retirement_of_NAM_SREF_HREF_HiresW_NAM_MOS_aac.pdf)

**Passenger side**

- [CBP Airport Wait Times](https://awt.cbp.gov/)
- [CBP Enhanced Passenger Processing at ORD](https://www.cbp.gov/newsroom/local-media-release/chicago-cbp-and-chicago-department-aviation-introduce-updated)
- [TSA FOIA reading room](https://www.tsa.gov/foia/readingroom)
- [Chicago TNC trips 2025–](https://data.cityofchicago.org/d/6dvr-xwnh)
- CTA [Train Tracker](https://www.transitchicago.com/developers/ttdocs/) and [terms](https://www.transitchicago.com/developers/terms/)
- [Metra GTFS](https://metra.com/metra-gtfs-api)
- [Travel Midwest reuse policy](https://travelmidwest.com/About/InfoReusePolicy)
- [Google Routes billing](https://developers.google.com/maps/documentation/routes/usage-and-billing)
- [CDA international arrivals](https://www.flychicago.com/ohare/myflight/international/pages/default.aspx)
- [CDA Terminal Transfer Bus](https://www.flychicago.com/ohare/ServicesAmenities/services/Pages/tbt.aspx)
- [CDA pickup rules](https://www.flychicago.com/ohare/tofrom/dropoff/Pages/default.aspx)
- [ACRP Report 25](https://onlinepubs.trb.org/onlinepubs/acrp/acrp_rpt_025v1.pdf)
- [Alaska bag guarantee](https://www.alaskaair.com/content/travel-info/baggage/baggage-claim/delayed-damaged-missing)

**Competition**

- Flighty [delay predictions](https://flighty.com/help/delay-predictions) and [Connection Assistant](http://flighty.com/help/connection-assistant)
- United app releases ([Jun 2025](https://www.prnewswire.com/news-releases/united-mobile-app-now-gives-people-more-information-about-their-connecting-flight-302490849.html), [Sep 2026](https://united.mediaroom.com/2026-09-01-Another-First-for-United-Mobile-App-Lets-Customers-Join-Standby-for-Earlier-Flights-and-Automatically-Finds-Open-Seats-During-Disruptions))
- [FlightAware Foresight](https://www.flightaware.com/commercial/foresight/)
- [TripIt Go Now](https://help.tripit.com/en/support/solutions/articles/103000063349-go-now)
- [Limo Anywhere flight tracking](https://support.limoanywhere.com/support/solutions/articles/69000882671)
- [Google Flights delay predictions (2018)](https://blog.google/products/travel/get-help-cheaper-flights-and-potential-flight-delays-winter/)

**Modeling literature**

See §6.1 and §6.4–6.6 for DOIs. Core references:

- Rebollo & Balakrishnan 2014
- Gopalakrishnan & Balakrishnan 2017
- Aeolus benchmark 2025
- Beltman et al. 2025
- Barnhart, Fearing & Vaze 2014
- Fleurquin et al. 2013
- AhmadBeygi et al. 2008
- Kafle & Zou 2016
- Wang 2011 (NASA, ORD)
- Mukherjee et al. 2014
- NASA/DrivenData challenge results
- Grinsztajn et al. 2022
- Romano et al. 2019 (CQR)
- Gibbs & Candès 2021 (ACI)
- Gneiting & Raftery 2007
- Niculescu-Mizil & Caruana 2005
- Bergmeir et al. 2018
- Kapoor & Narayanan (leakage)

## Appendix C. Glossary

| Term | Meaning |
|---|---|
| AAR / ADR | Airport arrival / departure rate: aircraft per hour the FAA plans to accept |
| ADS-B | Automatic Dependent Surveillance–Broadcast: aircraft-broadcast positions received by ground (and space) receivers |
| AFP / CTOP | Airspace Flow Program / Collaborative Trajectory Options Program: en-route traffic-management initiatives |
| ASPM / OPSNET / TFMSC | FAA performance databases: flight-level metrics / ATC-reported delays and counts / traffic counts |
| ATCSCC | FAA Air Traffic Control System Command Center, which issues national advisories |
| BSS / CRPS / ECE | Brier skill score / continuous ranked probability score / expected calibration error |
| CQR / ACI | Conformalized quantile regression / adaptive conformal inference: methods that give prediction intervals coverage guarantees |
| EDCT | Expect Departure Clearance Time, assigned to flights under a ground delay program |
| EPP | CBP Enhanced Passenger Processing (biometric US-citizen processing; at ORD since May 2025) |
| FIDS | Flight information display system (airport arrival/departure boards) |
| GDP / GS | Ground delay program / ground stop |
| LADD / PIA | FAA programs letting aircraft owners limit public display of their flights, or use privacy ICAO addresses |
| Level 2 / Level 3 | IATA scheduling levels: schedule-facilitated / slot-coordinated |
| MCT | Minimum connection time published by airlines/airports for legal connections |
| NAS delay | BTS cause category for delays attributable to the National Airspace System (ATC, volume, airport operations, non-extreme weather) |
| NBM / LAMP / HRRR / TAF / METAR | NWS blended model guidance / hourly aviation station guidance / 3-km rapid-refresh model / terminal aerodrome forecast / routine weather observation |
| SWIM (TFMS, TBFM, STDDS) | FAA System Wide Information Management feeds: traffic flow management, time-based metering, surface and terminal data |
| VMC / IMC | Visual / instrument meteorological conditions |

## Appendix D. How this research was done

The study ran eight parallel research tracks:

- ORD operations (with sub-tracks for hub structure/volumes and capacity/weather/taxi)
- flight/ATC/ADS-B data
- weather data
- passenger-side data
- competition
- modeling literature

Each track was instructed to cite primary sources and to label verification status. Key claims were then spot-checked by reading the primary documents directly: the FAA ORD orders and the Section 511(b) delay notice (from the Federal Register PDFs), the Spirit and Southwest exits, and cloud prices.

**Limitations:**

- Several federal sites block automated access.
- A shared web-search quota was exhausted mid-study, so some items rely on fetching known official URLs.
- A few figures remain secondary-source only and are tagged [S].

No bulk data was downloaded and no code, environment or repository was created.
