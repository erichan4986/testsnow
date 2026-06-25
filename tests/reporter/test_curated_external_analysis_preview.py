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
    assert "--wechat-export-dir" in result.stdout
    assert "--wechat-max-items" in result.stdout


def test_curated_external_analysis_preview_cli_wechat_export_dir(tmp_path: Path) -> None:
    wechat_dir = tmp_path / "wechat"
    wechat_dir.mkdir()
    (wechat_dir / "sgm.md").write_text(
        "---\n"
        "title: 圣邦微电子推出SGM3810\n"
        "url: https://mp.weixin.qq.com/s/abc123\n"
        "---\n\n"
        "SGM3810 适用于 TFT LCD 偏置。\n",
        encoding="utf-8",
    )
    output = tmp_path / "preview.md"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--wechat-export-dir",
            str(wechat_dir),
            "--wechat-max-items",
            "5",
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    assert "# Curated External Analysis Preview" in content
    assert "## WeChat Product Signals" in content
    assert "SGM3810" in content
    assert "source_kind: `wechat_product_signal`" in content
    assert "knowledge_eligible: `false`" in content
