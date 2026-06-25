import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "curated_external_analysis_preview.py"


def test_curated_external_analysis_preview_cli_writes_markdown_from_local_materials(tmp_path: Path) -> None:
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()
    (materials_dir / "article.md").write_text("精选长文：模拟芯片和车规产品。", encoding="utf-8")
    output = tmp_path / "preview.md"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--materials-dir",
            str(materials_dir),
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert str(output) in result.stdout
    content = output.read_text(encoding="utf-8")
    assert "# Curated External Analysis Preview" in content
    assert "精选长文：模拟芯片和车规产品" in content
    assert "knowledge_eligible: `false`" in content


def test_curated_external_analysis_preview_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--url-list" in result.stdout
    assert "--materials-dir" in result.stdout
