import json
import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "previews"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from periodic_report_narrative_cards_preview import (  # noqa: E402
    build_preview_markdown,
    default_output_path,
)


SAMPLE_REPORT = """
2025年年度报告

报告期内公司从事的主要业务
公司主要从事高性能碳纤维及相关产品的研发、生产、销售和技术服务。
产品主要应用于航空航天、轨道交通、新能源等领域。

行业情况
我国碳纤维产业已进入高端转型的关键窗口期，高端航空航天用碳纤维需求保持增长。

存货跌价风险 公司存货主要由原材料、库存商品构成。报告期末，公司存货账面价值较高。
"""


def _cache(tmp_path: Path) -> Path:
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    (cache_dir / "测试股_2025_annual_jina.txt").write_text(SAMPLE_REPORT, encoding="utf-8")
    return cache_dir


def test_build_preview_markdown_from_local_cache(tmp_path):
    markdown = build_preview_markdown(
        stock_code="000001", stock_name="测试股", cache_dir=_cache(tmp_path),
        report_type="annual",
    )

    assert "# 定期报告 Narrative Evidence Cards Preview" in markdown
    assert "测试股" in markdown
    assert "periodic_report_narrative_evidence" in markdown
    assert "## 1." in markdown
    assert "confirmed_fact" not in markdown
    assert "fact_candidate" not in markdown


def test_build_preview_markdown_can_include_json_block(tmp_path):
    markdown = build_preview_markdown(
        stock_code="000001", stock_name="测试股", cache_dir=_cache(tmp_path),
        report_type="annual", include_json=True,
    )

    payload = markdown.split("```json", 1)[1].split("```", 1)[0]
    data = json.loads(payload)
    assert data["schema_version"] == "periodic_report_narrative_evidence_cards.v2"
    assert data["cards"]


def test_build_preview_markdown_reports_missing_cache(tmp_path):
    markdown = build_preview_markdown(
        stock_code="000001", stock_name="测试股", cache_dir=tmp_path / "missing",
        report_type="annual",
    )

    assert "未找到本地年报缓存" in markdown
    assert "000001" in markdown
    assert "测试股" in markdown


def test_default_output_path_uses_tmp_and_stock_name():
    path = default_output_path("测试股", "000001", "annual")

    assert str(path).startswith("/tmp/")
    assert path.name == "测试股_000001_annual_narrative_cards_preview.md"


def test_cli_runs_from_repo_root(tmp_path):
    output = tmp_path / "cards.md"
    script = Path(__file__).parent.parent.parent / "scripts" / "previews" / "periodic_report_narrative_cards_preview.py"
    result = subprocess.run(
        [
            sys.executable, str(script), "--stock-code", "000001", "--stock-name", "测试股",
            "--cache-dir", str(_cache(tmp_path)), "--output", str(output),
        ],
        cwd=Path(__file__).parent.parent.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert str(output) in result.stdout
    assert "Narrative Evidence Cards Preview" in output.read_text(encoding="utf-8")


def test_knowledge_base_without_write_is_read_only(tmp_path):
    knowledge_dir = tmp_path / "knowledge"
    markdown = build_preview_markdown(
        stock_code="000001", stock_name="测试股", cache_dir=_cache(tmp_path),
        report_type="annual", knowledge_base_dir=knowledge_dir,
    )

    assert "knowledge_write_mode：`disabled`" in markdown
    assert "Knowledge note plan" not in markdown
    assert not knowledge_dir.exists()


def test_preview_write_knowledge_writes_pack_and_one_view(tmp_path):
    knowledge_dir = tmp_path / "knowledge"
    markdown = build_preview_markdown(
        stock_code="000001", stock_name="测试股", cache_dir=_cache(tmp_path),
        report_type="annual", knowledge_base_dir=knowledge_dir, write_knowledge=True,
    )

    stock_root = knowledge_dir / "10-Stocks" / "测试股"
    assert not (stock_root / "periodic_narrative_cards").exists()
    assert (stock_root / "periodic_narrative_packs" / "2025-annual.json").exists()
    assert (stock_root / "periodic_narrative_pack_manifest.json").exists()
    views = list((stock_root / "periodic_narrative_views").glob("*.md"))
    assert len(views) == 1
    assert "periodic_narrative_view" in markdown
    assert "Knowledge note plan" not in markdown


def test_write_knowledge_requires_base_dir(tmp_path):
    with pytest.raises(ValueError, match="knowledge_base_dir_required"):
        build_preview_markdown(
            stock_code="000001", stock_name="测试股", cache_dir=_cache(tmp_path),
            report_type="annual", write_knowledge=True,
        )


@pytest.mark.parametrize("option", [
    {"refresh_existing": True},
    {"refresh_frontmatter_only": True},
    {"existing_only": True},
])
def test_legacy_note_options_fail_explicitly(tmp_path, option):
    with pytest.raises(ValueError, match="legacy_note_options_removed"):
        build_preview_markdown(
            stock_code="000001", stock_name="测试股", cache_dir=_cache(tmp_path),
            report_type="annual", **option,
        )


def test_cli_legacy_note_option_exits_two_without_traceback(tmp_path):
    output = tmp_path / "cards.md"
    script = Path(__file__).parent.parent.parent / "scripts" / "previews" / "periodic_report_narrative_cards_preview.py"
    result = subprocess.run(
        [
            sys.executable, str(script), "--stock-code", "000001", "--stock-name", "测试股",
            "--cache-dir", str(_cache(tmp_path)), "--output", str(output), "--refresh-existing",
        ],
        cwd=Path(__file__).parent.parent.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "legacy_note_options_removed" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_write_knowledge_writes_only_human_view_markdown(tmp_path):
    output = tmp_path / "cards.md"
    knowledge_dir = tmp_path / "knowledge"
    script = Path(__file__).parent.parent.parent / "scripts" / "previews" / "periodic_report_narrative_cards_preview.py"
    result = subprocess.run(
        [
            sys.executable, str(script), "--stock-code", "000001", "--stock-name", "测试股",
            "--cache-dir", str(_cache(tmp_path)), "--output", str(output),
            "--knowledge-base-dir", str(knowledge_dir), "--write-knowledge",
        ],
        cwd=Path(__file__).parent.parent.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    knowledge_markdown = list(knowledge_dir.rglob("*.md"))
    assert len(knowledge_markdown) == 1
    assert "generated_projection: true" in knowledge_markdown[0].read_text(encoding="utf-8")
