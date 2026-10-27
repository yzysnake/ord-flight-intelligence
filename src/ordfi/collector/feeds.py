"""Feeds archived by the live collector (ADR-0004): public sources without a public history."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from ordfi.ingest.raw import LicenceClass


@dataclass(frozen=True)
class Feed:
    """One polled endpoint. ``source_id`` matches its data-catalog card."""

    source_id: str
    name: str
    url: str
    interval_s: float
    licence_class: LicenceClass
    method: str = "GET"
    body: Callable[[datetime], dict[str, Any]] | None = None
    # Change detection only: strips volatile fields. Stored payloads stay verbatim.
    normalize: Callable[[bytes], bytes] | None = None

    @property
    def feed_id(self) -> str:
        return f"{self.source_id}.{self.name}"


def drop_json_keys(*keys: str) -> Callable[[bytes], bytes]:
    """Normaliser that removes ``keys`` at any depth of a JSON payload (non-JSON passes through)."""

    def strip(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: strip(v) for k, v in value.items() if k not in keys}
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value

    def normalize(body: bytes) -> bytes:
        try:
            return json.dumps(strip(json.loads(body)), sort_keys=True).encode()
        except ValueError:
            return body

    return normalize


_NAS_UPDATE_TIME = re.compile(rb"<Update_Time>.*?</Update_Time>")


def strip_nas_update_time(body: bytes) -> bytes:
    """NAS Status XML carries a feed timestamp that can change without content changing."""
    return _NAS_UPDATE_TIME.sub(b"", body)


def cbp_trailing_week(now: datetime) -> dict[str, Any]:
    """CBP request for ORD Terminal 5 (``A392``) covering the trailing 7 days.

    CBP data lands about two days late and can be revised, so a rolling window plus checksum
    de-duplication captures both new days and revisions.
    """
    return {
        "Id": "A392",
        "FromDate": (now - timedelta(days=7)).date().isoformat(),
        "ToDate": now.date().isoformat(),
    }


FEEDS: tuple[Feed, ...] = (
    Feed(
        source_id="faa_nas_status",
        name="airport_status",
        url="https://nasstatus.faa.gov/api/airport-status-information",
        interval_s=60,
        licence_class="public-domain",
        normalize=strip_nas_update_time,
    ),
    Feed(
        source_id="faa_nas_status",
        name="airport_events",
        url="https://nasstatus.faa.gov/api/airport-events",
        interval_s=60,
        licence_class="public-domain",
    ),
    Feed(
        source_id="atis_info_datis",
        name="kord",
        url="https://atis.info/api/KORD",
        interval_s=300,
        licence_class="non-commercial",
        normalize=drop_json_keys("updatedAt"),  # refreshed on every fetch
    ),
    Feed(
        source_id="cbp_awt",
        name="ord_t5",
        url="https://awt.cbp.gov/api/waitTime",
        interval_s=6 * 3600,
        licence_class="public-domain",
        method="POST",
        body=cbp_trailing_week,
    ),
)
