"""Polite HTTP access: identifying User-Agent, timeouts, and retries on transient failures."""

from __future__ import annotations

import hashlib
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from ordfi.settings import USER_AGENT

RETRY_STATUS = {429, 500, 502, 503, 504}
TIMEOUT = httpx.Timeout(connect=15.0, read=300.0, write=60.0, pool=15.0)


class NotPublishedError(Exception):
    """The requested resource does not exist (yet); for example, a BTS month not released."""


class NotModifiedError(Exception):
    """The server confirmed (HTTP 304) that the resource is unchanged since the last fetch."""


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in RETRY_STATUS


def make_client() -> httpx.Client:
    """Return an HTTP client that identifies the project and follows redirects."""
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True)


@dataclass(frozen=True)
class Download:
    """A completed download held in a temporary file until it is committed to the raw zone."""

    url: str
    tmp_path: Path
    fetched_at: datetime
    status: int
    sha256: str
    size_bytes: int
    content_type: str | None
    last_modified: str | None
    etag: str | None


@retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    reraise=True,
)
def download(
    client: httpx.Client, url: str, tmp_dir: Path, headers: dict[str, str] | None = None
) -> Download:
    """Stream ``url`` to a temporary file in ``tmp_dir``, hashing as it goes.

    Pass conditional ``headers`` (``If-None-Match`` / ``If-Modified-Since``) to skip unchanged
    resources. Raises ``NotModifiedError`` on HTTP 304, ``NotPublishedError`` on HTTP 404 and
    ``httpx.HTTPStatusError`` on other errors.
    """
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(UTC)
    with client.stream("GET", url, headers=headers or {}) as response:
        if response.status_code == 304:
            raise NotModifiedError(url)
        if response.status_code == 404:
            raise NotPublishedError(url)
        response.raise_for_status()
        digest = hashlib.sha256()
        size = 0
        with tempfile.NamedTemporaryFile(dir=tmp_dir, prefix=".dl-", delete=False) as handle:
            try:
                for chunk in response.iter_bytes(chunk_size=1 << 20):
                    handle.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            except BaseException:
                Path(handle.name).unlink(missing_ok=True)  # never leave a partial file behind
                raise
        return Download(
            url=str(response.url),
            tmp_path=Path(handle.name),
            fetched_at=fetched_at,
            status=response.status_code,
            sha256=digest.hexdigest(),
            size_bytes=size,
            content_type=response.headers.get("content-type"),
            last_modified=response.headers.get("last-modified"),
            etag=response.headers.get("etag"),
        )


def sweep_partial_downloads(tmp_dir: Path, older_than_s: float = 900) -> int:
    """Delete partial downloads (``.dl-*``) left by interrupted runs; returns the count removed.

    Only files older than ``older_than_s`` are touched, so concurrent downloads are safe.
    """
    if not tmp_dir.exists():
        return 0
    cutoff = time.time() - older_than_s
    removed = 0
    for path in tmp_dir.glob(".dl-*"):
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1
    return removed
