"""Append-only raw zone: verbatim payloads plus a metadata manifest per source.

Layout: ``<data>/raw/<source_id>/<yyyy>/<mm>/<dd>/<filename>`` (partitioned by fetch date), with
one JSON line per stored payload in ``<data>/raw/<source_id>/_manifest.jsonl``. A payload whose
checksum matches the latest stored version of the same logical key is not stored again, so a
changed checksum marks a publisher revision.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from ordfi.ingest.http import Download

LicenceClass = Literal[
    "public-domain", "open-share-alike", "non-commercial", "commercial-restricted"
]


@dataclass(frozen=True)
class RawRecord:
    """Manifest entry describing one stored payload."""

    source_id: str
    key: str
    url: str
    path: str
    fetched_at: str
    sha256: str
    size_bytes: int
    licence_class: str
    http_status: int
    content_type: str | None
    last_modified: str | None
    etag: str | None
    revision: int

    @property
    def fetched_at_dt(self) -> datetime:
        return datetime.fromisoformat(self.fetched_at)


def source_root(data_root: Path, source_id: str) -> Path:
    return data_root / "raw" / source_id


def manifest_path(data_root: Path, source_id: str) -> Path:
    return source_root(data_root, source_id) / "_manifest.jsonl"


def read_manifest(data_root: Path, source_id: str) -> list[RawRecord]:
    path = manifest_path(data_root, source_id)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [RawRecord(**json.loads(line)) for line in handle if line.strip()]


def latest(data_root: Path, source_id: str, key: str) -> RawRecord | None:
    """Most recently stored payload for a logical key, or ``None``."""
    matches = [r for r in read_manifest(data_root, source_id) if r.key == key]
    return matches[-1] if matches else None


def conditional_headers(record: RawRecord | None) -> dict[str, str]:
    """HTTP validators from a stored record, for a conditional re-fetch."""
    if record is None:
        return {}
    headers = {"If-None-Match": record.etag} if record.etag else {}
    if record.last_modified:
        headers["If-Modified-Since"] = record.last_modified
    return headers


def commit_download(
    data_root: Path,
    source_id: str,
    key: str,
    filename: str,
    dl: Download,
    licence_class: LicenceClass,
) -> tuple[RawRecord, bool]:
    """Move a finished download into the raw zone; return the record and whether it is new.

    If the latest stored payload for ``key`` has the same checksum, the temporary file is
    discarded and the existing record is returned with ``False``.
    """
    previous = latest(data_root, source_id, key)
    if previous is not None and previous.sha256 == dl.sha256:
        dl.tmp_path.unlink(missing_ok=True)
        return previous, False

    when = dl.fetched_at
    target_dir = source_root(data_root, source_id) / f"{when:%Y}" / f"{when:%m}" / f"{when:%d}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    if target.exists():  # same file name fetched twice in one day with different content
        target = target_dir / f"{when:%H%M%S}-{filename}"
    os.replace(dl.tmp_path, target)

    record = RawRecord(
        source_id=source_id,
        key=key,
        url=dl.url,
        path=str(target.relative_to(data_root)),
        fetched_at=dl.fetched_at.isoformat(),
        sha256=dl.sha256,
        size_bytes=dl.size_bytes,
        licence_class=licence_class,
        http_status=dl.status,
        content_type=dl.content_type,
        last_modified=dl.last_modified,
        etag=dl.etag,
        revision=(previous.revision + 1) if previous else 1,
    )
    with manifest_path(data_root, source_id).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")
    return record, True
