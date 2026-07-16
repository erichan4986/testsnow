"""Tests for the shared direct-script path bootstrap."""

import sys

import pytest

from scripts._path_bootstrap import prepend_sys_path


@pytest.fixture(autouse=True)
def restore_sys_path():
    original = list(sys.path)
    yield
    sys.path[:] = original


def test_prepend_sys_path_collapses_relative_and_absolute_aliases(
    monkeypatch, tmp_path
):
    target = tmp_path / "utils"
    target.mkdir()
    monkeypatch.chdir(tmp_path)
    sys.path[:] = ["", "before", str(target), "utils", "after"]

    canonical = prepend_sys_path(target)

    assert canonical == str(target.resolve())
    assert sys.path == [canonical, "", "before", "after"]


def test_prepend_sys_path_is_idempotent_and_preserves_unrelated_order(tmp_path):
    target = tmp_path / "utils"
    target.mkdir()
    sys.path[:] = ["", "alpha", str(target), "omega"]

    prepend_sys_path(target)
    prepend_sys_path(target)

    assert sys.path == [str(target.resolve()), "", "alpha", "omega"]
