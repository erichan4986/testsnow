"""Browser-free CLI tests for extract_detail.py and extract_detail_via_cdp.py."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_script(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_extract_detail_help_does_not_start_browser():
    result = run_script("scripts/extract_detail.py", "--help")

    assert result.returncode == 0
    assert "雪球帖子详情页批量提取" in result.stdout


def test_deprecated_cdp_script_help_works():
    result = run_script("scripts/extract_detail_via_cdp.py", "--help")

    assert result.returncode == 0
    assert "Deprecated" in result.stdout or "deprecated" in result.stdout
    assert "extract_detail.py" in result.stdout


def test_deprecated_cdp_script_exits_nonzero_with_guidance():
    result = run_script("scripts/extract_detail_via_cdp.py")

    assert result.returncode == 1
    assert "extract_detail.py" in result.stdout
    assert "--cdp-port 9222" in result.stdout
