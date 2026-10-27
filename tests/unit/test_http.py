"""HTTP download behaviour with a mock transport: success, 304, 404 and transient retries."""

import hashlib
from pathlib import Path

import httpx
import pytest
from tenacity import stop_after_attempt, wait_none

from ordfi.ingest.http import NotModifiedError, NotPublishedError, download
from ordfi.settings import USER_AGENT

URL = "https://example.test/data.zip"


def client_for(*responses: httpx.Response) -> tuple[httpx.Client, list[httpx.Request]]:
    seen: list[httpx.Request] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return queue.pop(0)

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, headers={"User-Agent": USER_AGENT}), seen


def test_download_streams_and_hashes(tmp_path: Path) -> None:
    body = b"x" * 3_000_000
    client, seen = client_for(
        httpx.Response(200, content=body, headers={"ETag": '"v1"', "Last-Modified": "today"})
    )
    dl = download(client, URL, tmp_path)
    assert dl.tmp_path.read_bytes() == body
    assert dl.sha256 == hashlib.sha256(body).hexdigest() and dl.size_bytes == len(body)
    assert (dl.etag, dl.last_modified, dl.status) == ('"v1"', "today", 200)
    assert seen[0].headers["User-Agent"].startswith("ord-flight-intelligence/")


def test_conditional_request_and_not_modified(tmp_path: Path) -> None:
    client, seen = client_for(httpx.Response(304))
    with pytest.raises(NotModifiedError):
        download(client, URL, tmp_path, headers={"If-None-Match": '"v1"'})
    assert seen[0].headers["If-None-Match"] == '"v1"'


def test_missing_resource_is_not_published(tmp_path: Path) -> None:
    client, _ = client_for(httpx.Response(404))
    with pytest.raises(NotPublishedError):
        download(client, URL, tmp_path)


def test_transient_errors_are_retried(tmp_path: Path) -> None:
    client, seen = client_for(httpx.Response(503), httpx.Response(200, content=b"ok"))
    fast = download.retry_with(wait=wait_none(), stop=stop_after_attempt(3))
    dl = fast(client, URL, tmp_path)
    assert dl.tmp_path.read_bytes() == b"ok" and len(seen) == 2


def test_client_errors_are_not_retried(tmp_path: Path) -> None:
    client, seen = client_for(httpx.Response(403), httpx.Response(200))
    fast = download.retry_with(wait=wait_none(), stop=stop_after_attempt(3))
    with pytest.raises(httpx.HTTPStatusError):
        fast(client, URL, tmp_path)
    assert len(seen) == 1
