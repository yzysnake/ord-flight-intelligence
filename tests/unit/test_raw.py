"""Raw-zone behaviour: idempotent commits, revisions, manifest and conditional headers."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from ordfi.ingest.http import Download
from ordfi.ingest.raw import (
    RawRecord,
    commit_download,
    conditional_headers,
    latest,
    load_latest,
    read_manifest,
)


def make_download(tmp_path: Path, payload: bytes, when: datetime) -> Download:
    tmp = tmp_path / f".dl-{hashlib.sha256(payload).hexdigest()[:8]}"
    tmp.write_bytes(payload)
    return Download(
        url="https://example.test/file.zip",
        tmp_path=tmp,
        fetched_at=when,
        status=200,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        content_type="application/zip",
        last_modified="Mon, 26 Oct 2026 20:49:33 GMT",
        etag='"abc"',
    )


def test_first_commit_creates_file_and_manifest(tmp_path: Path) -> None:
    root = tmp_path / "data"
    when = datetime(2026, 10, 27, 5, 0, tzinfo=UTC)
    record, new = commit_download(
        root, "src", "2026-08", "file.zip", make_download(tmp_path, b"v1", when), "public-domain"
    )
    assert new and record.revision == 1
    assert (root / record.path).read_bytes() == b"v1"
    assert record.path == "raw/src/2026/10/27/file.zip"
    assert [r.sha256 for r in read_manifest(root, "src")] == [record.sha256]


def test_identical_payload_is_not_stored_twice(tmp_path: Path) -> None:
    root = tmp_path / "data"
    when = datetime(2026, 10, 27, 5, 0, tzinfo=UTC)
    first, _ = commit_download(
        root, "src", "k", "f.zip", make_download(tmp_path, b"same", when), "public-domain"
    )
    dl = make_download(tmp_path, b"same", when)
    second, new = commit_download(root, "src", "k", "f.zip", dl, "public-domain")
    assert not new and second == first
    assert not dl.tmp_path.exists()
    assert len(read_manifest(root, "src")) == 1


def test_changed_payload_is_a_new_revision(tmp_path: Path) -> None:
    root = tmp_path / "data"
    when = datetime(2026, 10, 27, 5, 0, tzinfo=UTC)
    commit_download(
        root, "src", "k", "f.zip", make_download(tmp_path, b"v1", when), "public-domain"
    )
    record, new = commit_download(
        root, "src", "k", "f.zip", make_download(tmp_path, b"v2", when), "public-domain"
    )
    assert new and record.revision == 2
    assert (root / record.path).read_bytes() == b"v2"
    assert latest(root, "src", "k") == record


def test_conditional_headers() -> None:
    assert conditional_headers(None) == {}
    record = RawRecord(
        source_id="s", key="k", url="u", path="p", fetched_at="2026-10-27T05:00:00+00:00",
        sha256="x", size_bytes=1, licence_class="public-domain", http_status=200,
        content_type=None, last_modified="Mon, 26 Oct 2026 20:49:33 GMT", etag='"abc"', revision=1,
    )  # fmt: skip
    assert conditional_headers(record) == {
        "If-None-Match": '"abc"',
        "If-Modified-Since": "Mon, 26 Oct 2026 20:49:33 GMT",
    }


def test_partition_and_index(tmp_path: Path) -> None:
    root = tmp_path / "data"
    when = datetime(2026, 10, 27, 5, 0, tzinfo=UTC)
    index: dict[str, RawRecord] = {}
    record, new = commit_download(
        root, "src", "listing/2019-07-15", "l.html", make_download(tmp_path, b"v1", when),
        "public-domain", partition="listings/2019/07", index=index,
    )  # fmt: skip
    assert new and record.path == "raw/src/listings/2019/07/l.html"
    assert index["listing/2019-07-15"] == record
    again, new_again = commit_download(
        root, "src", "listing/2019-07-15", "l.html", make_download(tmp_path, b"v1", when),
        "public-domain", partition="listings/2019/07", index=index,
    )  # fmt: skip
    assert not new_again and again == record
    assert load_latest(root, "src") == {"listing/2019-07-15": record}
