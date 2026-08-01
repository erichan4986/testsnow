"""Named stock entries are compatibility wrappers around the generic owner."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_named_entry(script_name: str):
    path = REPO_ROOT / "scripts" / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{script_name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("script_name", "stock_name"),
    [
        ("run_中际旭创", "中际旭创"),
        ("run_圣邦股份", "圣邦股份"),
        ("run_黑芝麻智能", "黑芝麻智能"),
        ("run_中简科技", "中简科技"),
    ],
)
def test_named_entry_forwards_to_generic_owner(script_name, stock_name, monkeypatch):
    module = _load_named_entry(script_name)
    calls = []
    monkeypatch.setattr(module, "_run_generic_report", lambda argv: calls.append(argv) or 17)

    result = module.main(["--fast-test", "--no-pdf"])

    assert result == 17
    assert calls == [["--stock", stock_name, "--fast-test", "--no-pdf"]]
