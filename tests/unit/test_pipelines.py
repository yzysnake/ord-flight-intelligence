"""The Dagster code location loads, and a stage asset materializes with passing checks."""

import hashlib
import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import dagster as dg
import pytest

from ordfi.ingest import bts
from ordfi.ingest.http import Download
from ordfi.ingest.raw import commit_download
from tests.bts_sample import ZONES, write_zip

DEFINITIONS = Path(__file__).resolve().parents[2] / "pipelines" / "definitions.py"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ordfi_pipeline_definitions", DEFINITIONS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_definitions_are_loadable() -> None:
    defs = load_module().defs
    dg.Definitions.validate_loadable(defs)
    keys = {key.to_user_string() for key in defs.resolve_all_asset_keys()}
    assert keys == {
        "bts_ontime_reporting_raw",
        "bts_ontime_reporting_stage",
        "bts_ontime_marketing_raw",
        "bts_ontime_marketing_stage",
    }
    checks = {
        (check.asset_key.to_user_string(), check.name)
        for check in defs.resolve_asset_graph().asset_check_keys
    }
    assert ("bts_ontime_marketing_stage", "utc_derivation") in checks
    assert ("bts_ontime_reporting_stage", "timezones_resolved") in checks


def test_stage_asset_materializes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "data"
    archive = write_zip(tmp_path / "upload.zip")
    payload = archive.read_bytes()
    dl = Download(
        url="https://example.test/m.zip", tmp_path=archive,
        fetched_at=datetime(2026, 10, 27, 5, 0, tzinfo=UTC), status=200,
        sha256=hashlib.sha256(payload).hexdigest(), size_bytes=len(payload),
        content_type="application/zip", last_modified=None, etag=None,
    )  # fmt: skip
    commit_download(root, "bts_ontime_marketing", "2026-08", "m.zip", dl, "public-domain")
    monkeypatch.setenv("ORDFI_DATA_DIR", str(root))
    monkeypatch.setattr(bts, "airport_timezones", lambda: ZONES)

    defs = load_module().defs
    stage = defs.resolve_assets_def("bts_ontime_marketing_stage")
    result = dg.materialize([stage], partition_key="2026-08-01")

    assert result.success
    evaluations = result.get_asset_check_evaluations()
    assert {e.check_name for e in evaluations} == {"utc_derivation", "timezones_resolved"}
    assert all(e.passed for e in evaluations)
