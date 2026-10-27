"""Async polling loop (ADR-0003): one task per feed, independent of the orchestrator."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx

from ordfi.collector.feeds import Feed
from ordfi.collector.store import FeedStore
from ordfi.settings import USER_AGENT

log = logging.getLogger("ordfi.collector")
TIMEOUT = httpx.Timeout(30.0)


async def poll_once(feed: Feed, client: httpx.AsyncClient, store: FeedStore) -> bool:
    """Poll a feed once and record the outcome; returns whether a new snapshot was stored."""
    fetched_at = datetime.now(UTC)
    started = time.perf_counter()
    payload = feed.body(fetched_at) if feed.body else None
    try:
        response = await client.request(feed.method, feed.url, json=payload)
    except httpx.HTTPError as exc:
        store.record(
            fetched_at=fetched_at,
            status=None,
            body=None,
            latency_ms=(time.perf_counter() - started) * 1000,
            error=f"{type(exc).__name__}: {exc}",
            content_type=None,
        )
        log.warning("%s: %s", feed.feed_id, exc)
        return False
    changed = store.record(
        fetched_at=fetched_at,
        status=response.status_code,
        body=response.content,
        latency_ms=(time.perf_counter() - started) * 1000,
        error=None if response.is_success else f"HTTP {response.status_code}",
        content_type=response.headers.get("content-type"),
    )
    if changed:
        log.info("%s: new snapshot (%d bytes)", feed.feed_id, len(response.content))
    return changed


async def run_feed(
    feed: Feed, client: httpx.AsyncClient, store: FeedStore, stop: asyncio.Event
) -> None:
    """Poll ``feed`` every ``interval_s`` seconds until ``stop`` is set."""
    while not stop.is_set():
        started = time.monotonic()
        try:
            await poll_once(feed, client, store)
        except Exception:  # one feed's failure must never stop the others
            log.exception("%s: unexpected error", feed.feed_id)
        remaining = feed.interval_s - (time.monotonic() - started)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=max(remaining, 1.0))


async def run(feeds: Sequence[Feed], data_root: Path, *, once: bool = False) -> None:
    """Run all feeds until SIGINT/SIGTERM (or a single round with ``once=True``)."""
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(headers=headers, timeout=TIMEOUT, follow_redirects=True) as client:
        stores = [FeedStore(data_root, feed) for feed in feeds]
        if once:
            await asyncio.gather(*(poll_once(s.feed, client, s) for s in stores))
            return
        log.info("collector started: %s", ", ".join(feed.feed_id for feed in feeds))
        await asyncio.gather(*(run_feed(s.feed, client, s, stop) for s in stores))
        log.info("collector stopped")
