"""Project-root detection and the data-directory override."""

from pathlib import Path

import pytest

from ordfi.settings import data_dir, project_root


def test_project_root_walks_up_to_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert project_root(nested) == tmp_path.resolve()


def test_project_root_falls_back_to_start(tmp_path: Path) -> None:
    assert project_root(tmp_path) == tmp_path.resolve()


def test_data_dir_defaults_to_project_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "pyproject.toml").write_text("")
    monkeypatch.delenv("ORDFI_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert data_dir() == tmp_path.resolve() / "data"


def test_data_dir_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORDFI_DATA_DIR", str(tmp_path / "lake"))
    assert data_dir() == (tmp_path / "lake").resolve()
