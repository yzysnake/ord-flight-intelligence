"""Live collector: change-only snapshots, poll log, restart de-duplication and HTTP outcomes."""

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from ordfi.collector import __main__ as cli
from ordfi.collector.feeds import (
    FEEDS,
    Feed,
    cbp_trailing_week,
    drop_json_keys,
    strip_nas_update_time,
)
from ordfi.collector.service import poll_once, run_feed
from ordfi.collector.store import FeedStore

FEED = Feed(
    source_id="src",
    name="feed",
    url="https://example.test/status",
    interval_s=60,
    licence_class="public-domain",
)
WHEN = datetime(2026, 10, 27, 6, 15, tzinfo=UTC)
CATALOG = Path(__file__).resolve().parents[2] / "docs" / "data-catalog"


def read_lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def record(store: FeedStore, body: bytes | None, status: int | None = 200) -> bool:
    error = (
        None if status == 200 else ("ConnectError: down" if status is None else f"HTTP {status}")
    )
    return store.record(
        fetched_at=WHEN, status=status, body=body, latency_ms=12.3, error=error, content_type=None
    )


def test_only_changed_payloads_are_stored(tmp_path: Path) -> None:
    store = FeedStore(tmp_path, FEED)
    assert record(store, b"<a/>")
    assert not record(store, b"<a/>")
    assert record(store, b"<b/>")
    day = store.day_dir(WHEN)
    assert day == tmp_path / "raw" / "src" / "feed" / "2026" / "10" / "27"
    assert [s["body"] for s in read_lines(day / "snapshots.jsonl")] == ["<a/>", "<b/>"]
    assert [p["changed"] for p in read_lines(day / "polls.jsonl")] == [True, False, True]


def test_failures_are_logged_but_not_stored(tmp_path: Path) -> None:
    store = FeedStore(tmp_path, FEED)
    assert not record(store, None, status=None)
    assert not record(store, b"busy", status=503)
    day = store.day_dir(WHEN)
    assert not (day / "snapshots.jsonl").exists()
    errors = [p["error"] for p in read_lines(day / "polls.jsonl")]
    assert errors == ["ConnectError: down", "HTTP 503"]


def test_restart_does_not_duplicate_last_snapshot(tmp_path: Path) -> None:
    record(FeedStore(tmp_path, FEED), b"same")
    restarted = FeedStore(tmp_path, FEED)
    assert not record(restarted, b"same")
    assert len(read_lines(restarted.day_dir(WHEN) / "snapshots.jsonl")) == 1


def test_binary_payloads_are_base64(tmp_path: Path) -> None:
    store = FeedStore(tmp_path, FEED)
    record(store, b"\xff\xfe")
    (snapshot,) = read_lines(store.day_dir(WHEN) / "snapshots.jsonl")
    assert snapshot["encoding"] == "base64" and snapshot["body"] == "//4="


def test_poll_once_sends_cbp_post(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"Items": []})

    cbp = next(feed for feed in FEEDS if feed.source_id == "cbp_awt")

    async def go() -> bool:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await poll_once(cbp, client, FeedStore(tmp_path, cbp))

    assert asyncio.run(go())
    assert seen[0].method == "POST"
    assert json.loads(seen[0].content)["Id"] == "A392"


def test_poll_once_records_transport_errors(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    store = FeedStore(tmp_path, FEED)

    async def go() -> bool:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await poll_once(FEED, client, store)

    assert not asyncio.run(go())
    (polls,) = list(store.base.glob("*/*/*/polls.jsonl"))
    (poll,) = read_lines(polls)
    assert poll["status"] is None and poll["error"].startswith("ConnectError")


def test_cbp_window_is_trailing_week() -> None:
    assert cbp_trailing_week(WHEN) == {
        "Id": "A392",
        "FromDate": "2026-10-20",
        "ToDate": "2026-10-27",
    }


def test_every_feed_is_unique_and_has_a_catalog_card() -> None:
    ids = [feed.feed_id for feed in FEEDS]
    assert len(ids) == len(set(ids))
    for feed in FEEDS:
        assert (CATALOG / f"{feed.source_id}.md").exists(), f"missing card for {feed.source_id}"


def test_run_feed_polls_until_stopped(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=f"v{calls}".encode())

    fast = Feed(
        "src", "loop", "https://example.test/x", interval_s=0.01, licence_class="public-domain"
    )
    store = FeedStore(tmp_path, fast)

    async def go() -> None:
        stop = asyncio.Event()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            task = asyncio.create_task(run_feed(fast, client, store, stop))
            while calls < 2:
                await asyncio.sleep(0.01)
            stop.set()
            await asyncio.wait_for(task, timeout=5)

    asyncio.run(go())
    (snapshots,) = list(store.base.glob("*/*/*/snapshots.jsonl"))
    assert len(read_lines(snapshots)) >= 2


def test_pid_tracking_and_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.running_pid(tmp_path) is None
    pid_path = cli.pid_file(tmp_path)
    pid_path.parent.mkdir(parents=True)
    pid_path.write_text(str(os.getpid()))
    assert cli.running_pid(tmp_path) == os.getpid()
    pid_path.write_text("999999999")  # stale PID file
    assert cli.running_pid(tmp_path) is None

    nas = FEEDS[0]
    FeedStore(tmp_path, nas).record(
        fetched_at=datetime.now(UTC), status=200, body=b"<x/>", latency_ms=1.0, error=None,
        content_type=None,
    )  # fmt: skip
    cli.status(tmp_path)
    out = capsys.readouterr().out
    assert "not running" in out
    assert f"{nas.feed_id}" in out and "snapshots=1" in out


def test_volatile_fields_do_not_create_snapshots(tmp_path: Path) -> None:
    feed = Feed("src", "atis", "https://example.test/a", 300, "non-commercial",
                normalize=drop_json_keys("updatedAt"))  # fmt: skip
    store = FeedStore(tmp_path, feed)
    assert record(store, b'[{"code":"O","updatedAt":"06:17"}]')
    assert not record(store, b'[{"code":"O","updatedAt":"06:18"}]')
    assert record(store, b'[{"code":"P","updatedAt":"06:19"}]')
    snaps = read_lines(store.day_dir(WHEN) / "snapshots.jsonl")
    assert [s["body"] for s in snaps] == [
        '[{"code":"O","updatedAt":"06:17"}]',
        '[{"code":"P","updatedAt":"06:19"}]',
    ]
    assert snaps[0]["sha256"] != snaps[0]["content_sha256"]


def test_nas_update_time_is_ignored() -> None:
    a = b"<A><Update_Time>Tue 06:15</Update_Time><X>1</X></A>"
    b = b"<A><Update_Time>Tue 06:16</Update_Time><X>1</X></A>"
    assert strip_nas_update_time(a) == strip_nas_update_time(b) == b"<A><X>1</X></A>"
