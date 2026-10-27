"""Smoke tests for the package skeleton."""

import importlib
import re

import pytest

import ordfi

SUBPACKAGES = ["ingest", "timeutil", "features", "models", "serving", "quality"]


def test_version_is_pep440() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+((a|b|rc)\d+)?(\.dev\d+)?", ordfi.__version__)


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name: str) -> None:
    module = importlib.import_module(f"ordfi.{name}")
    assert module.__doc__, f"ordfi.{name} should document its purpose"
