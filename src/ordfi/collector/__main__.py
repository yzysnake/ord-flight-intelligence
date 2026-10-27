"""``python -m ordfi.collector``: run, stop, or inspect the live collector."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from ordfi.collector.feeds import FEEDS
from ordfi.collector.service import run
from ordfi.collector.store import FeedStore
from ordfi.settings import data_dir


def pid_file(root: Path) -> Path:
    return root / "run" / "collector.pid"


def running_pid(root: Path) -> int | None:
    """PID of a live collector process, or ``None`` (stale PID files are ignored)."""
    path = pid_file(root)
    if not path.exists():
        return None
    pid = int(path.read_text().strip())
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    return pid


def status(root: Path) -> None:
    pid = running_pid(root)
    print(f"collector: {'running (pid ' + str(pid) + ')' if pid else 'not running'}")
    now = datetime.now(UTC)
    for feed in FEEDS:
        polls = FeedStore(root, feed).day_dir(now) / "polls.jsonl"
        lines = polls.read_text(encoding="utf-8").splitlines() if polls.exists() else []
        if not lines:
            print(f"  {feed.feed_id:30s} no polls today (UTC)")
            continue
        last = json.loads(lines[-1])
        changed = sum(json.loads(line)["changed"] for line in lines)
        errors = sum(1 for line in lines if json.loads(line)["error"])
        print(
            f"  {feed.feed_id:30s} last poll {last['fetched_at'][11:19]}Z status={last['status']}"
            f"  today: polls={len(lines)} snapshots={changed} errors={errors}"
        )


def stop(root: Path) -> None:
    pid = running_pid(root)
    if pid is None:
        print("collector is not running")
        return
    os.kill(pid, signal.SIGTERM)
    for _ in range(50):
        if running_pid(root) is None:
            print(f"collector (pid {pid}) stopped")
            return
        time.sleep(0.2)
    print(f"collector (pid {pid}) did not stop within 10 s", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Live collector for feeds without history.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--once", action="store_true", help="poll every feed once and exit")
    group.add_argument("--status", action="store_true", help="show collector status")
    group.add_argument("--stop", action="store_true", help="stop a running collector")
    args = parser.parse_args(argv)
    root = data_dir()
    if args.status:
        status(root)
        return
    if args.stop:
        stop(root)
        return

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if args.once:
        asyncio.run(run(FEEDS, root, once=True))
        return
    if (pid := running_pid(root)) is not None:
        raise SystemExit(f"collector already running (pid {pid})")
    path = pid_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()))
    try:
        asyncio.run(run(FEEDS, root))
    finally:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
