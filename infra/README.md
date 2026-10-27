# Infra

Deployment configuration (Docker images, compose files, hosting notes). Hosting beyond the developer's Mac is planned for Phase 2; see §7 of the research study.

## Live collector (running on the developer's Mac since 2026-10-27)

`ordfi.collector` polls public feeds that have **no public history** and archives every change. It is a separate always-on process (ADR-0003); feeds are chosen in ADR-0004.

| Feed | Interval | Raw path (`data/raw/…`) |
|---|---|---|
| FAA NAS Status XML | 60 s | `faa_nas_status/airport_status/` |
| FAA NAS Status airport events (runway configuration, arrival rate) | 60 s | `faa_nas_status/airport_events/` |
| ORD D-ATIS (atis.info) | 5 min | `atis_info_datis/kord/` |
| CBP wait times, ORD T5, trailing 7 days | 6 h | `cbp_awt/ord_t5/` |

Each feed writes two files per UTC day:

- `snapshots.jsonl`: payloads whose *content* changed, stored verbatim. Volatile fields are ignored for change detection: atis.info `updatedAt` and the NAS XML `Update_Time`.
- `polls.jsonl`: every poll (status, checksums, latency, error). Use it to find gaps and to establish "unchanged since".

```bash
make collector-start    # background process; log in data/logs/collector.log, PID in data/run/
make collector-status   # liveness plus today's polls, snapshots and errors per feed
make collector-stop     # graceful stop (SIGTERM)
```

**Limitations of running on a laptop:**

- Nothing is collected while the Mac sleeps or is shut down. The gaps are visible in `polls.jsonl`.
- The collector does not restart automatically after a reboot or logout. Run `make collector-start` again, or install it as a macOS LaunchAgent (not done yet; available on request).
- Move it to an always-on VM before relying on continuous coverage (Phase 2, or earlier on request).
