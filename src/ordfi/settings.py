"""Project paths and runtime settings."""

from __future__ import annotations

import os
from pathlib import Path

from ordfi import __version__

USER_AGENT = (
    f"ord-flight-intelligence/{__version__} (+https://github.com/yzysnake/ord-flight-intelligence)"
)


def project_root(start: Path | None = None) -> Path:
    """Return the nearest ancestor of ``start`` (default: cwd) that contains ``pyproject.toml``."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return here


def data_dir() -> Path:
    """Root of the local data lake: ``$ORDFI_DATA_DIR`` if set, else ``<project root>/data``."""
    override = os.environ.get("ORDFI_DATA_DIR")
    return Path(override).expanduser().resolve() if override else project_root() / "data"
