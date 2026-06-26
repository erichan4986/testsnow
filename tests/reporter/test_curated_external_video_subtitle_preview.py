import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "curated_external_video_subtitle_preview.py"


def test_curated_external_video_subtitle_preview_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--url-list" in result.stdout
    assert "--output" in result.stdout
    assert "--json-output" in result.stdout
    assert "--max-item-chars" in result.stdout
    assert "--timeout" in result.stdout
