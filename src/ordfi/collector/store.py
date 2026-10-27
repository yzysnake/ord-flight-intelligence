"""Append-only daily JSONL archive for polled feeds.

Layout: ``<data>/raw/<source_id>/<feed>/<yyyy>/<mm>/<dd>/`` (UTC dates) containing

- ``snapshots.jsonl``: one line per *changed* payload, body included;
- ``polls.jsonl``: one line per poll (status, checksum, latency, error). This makes collector
  gaps and "unchanged since" recoverable when reconstructing what was known at a given time.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ordfi.collector.feeds import Feed


class FeedStore:
    """Writes polls and changed snapshots for one feed; remembers the last stored checksum."""

    def __init__(self, data_root: Path, feed: Feed) -> None:
        self.feed = feed
        self.base = data_root / "raw" / feed.source_id / feed.name
        self.last_sha = self._restore_last_sha()

    def day_dir(self, when: datetime) -> Path:
        return self.base / f"{when:%Y}" / f"{when:%m}" / f"{when:%d}"

    def _restore_last_sha(self) -> str | None:
        files = sorted(self.base.glob("*/*/*/snapshots.jsonl"))
        for path in reversed(files):
            lines = path.read_text(encoding="utf-8").splitlines()
            if lines:
                last = json.loads(lines[-1])
                return str(last.get("content_sha256", last["sha256"]))
        return None

    @staticmethod
    def _append(path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def record(
        self,
        *,
        fetched_at: datetime,
        status: int | None,
        body: bytes | None,
        latency_ms: float,
        error: str | None,
        content_type: str | None,
    ) -> bool:
        """Log one poll; store the payload if it is a successful response whose content changed.

        Change detection uses the feed's normaliser (if any), so volatile fields such as fetch
        timestamps do not create duplicate snapshots; the stored body is always verbatim.
        """
        sha = hashlib.sha256(body).hexdigest() if body is not None else None
        content_sha = sha
        if body is not None and self.feed.normalize is not None:
            content_sha = hashlib.sha256(self.feed.normalize(body)).hexdigest()
        changed = status == 200 and content_sha is not None and content_sha != self.last_sha
        day = self.day_dir(fetched_at)
        if changed and body is not None:
            try:
                text, encoding = body.decode("utf-8"), "utf-8"
            except UnicodeDecodeError:
                text, encoding = base64.b64encode(body).decode("ascii"), "base64"
            self._append(
                day / "snapshots.jsonl",
                {
                    "fetched_at": fetched_at.isoformat(),
                    "url": self.feed.url,
                    "status": status,
                    "sha256": sha,
                    "content_sha256": content_sha,
                    "content_type": content_type,
                    "licence_class": self.feed.licence_class,
                    "encoding": encoding,
                    "body": text,
                },
            )
            self.last_sha = content_sha
        self._append(
            day / "polls.jsonl",
            {
                "fetched_at": fetched_at.isoformat(),
                "status": status,
                "sha256": sha,
                "content_sha256": content_sha,
                "changed": changed,
                "latency_ms": round(latency_ms, 1),
                "error": error,
            },
        )
        return changed
