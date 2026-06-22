import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from periodic_report_narrative_cards_preview import build_preview_markdown, default_output_path


SAMPLE_REPORT = """
2025年年度报告

报告期内公司从事的主要业务
公司主要从事高性能碳纤维及相关产品的研发、生产、销售和技术服务。
产品主要应用于航空航天、轨道交通、新能源等领域。

行业情况
我国碳纤维产业已进入高端转型的关键窗口期，高端航空航天用碳纤维需求保持增长。

存货跌价风险 公司存货主要由原材料、库存商品构成。报告期末，公司存货账面价值较高。
"""


def test_build_preview_markdown_from_local_cache(tmp_path):
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    (cache_dir / "测试股_2025_annual_jina.txt").write_text(SAMPLE_REPORT, encoding="utf-8")

    markdown = build_preview_markdown(
        stock_code="000001",
        stock_name="测试股",
        cache_dir=cache_dir,
        report_type="annual",
    )

    assert "# 定期报告 Narrative Evidence Cards Preview" in markdown
    assert "测试股" in markdown
    assert "periodic_report_narrative_evidence" in markdown
    assert "## 1." in markdown
    assert "confirmed_fact" not in markdown
    assert "fact_candidate" not in markdown


def test_build_preview_markdown_can_include_json_block(tmp_path):
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    (cache_dir / "000001_2025_annual_jina.txt").write_text(SAMPLE_REPORT, encoding="utf-8")

    markdown = build_preview_markdown(
        stock_code="000001",
        stock_name="测试股",
        cache_dir=cache_dir,
        report_type="annual",
        include_json=True,
    )

    assert "```json" in markdown
    payload = markdown.split("```json", 1)[1].split("```", 1)[0]
    data = json.loads(payload)
    assert data["schema_version"] == "periodic_report_narrative_evidence_cards.v1"
    assert data["cards"]


def test_build_preview_markdown_reports_missing_cache(tmp_path):
    markdown = build_preview_markdown(
        stock_code="000001",
        stock_name="测试股",
        cache_dir=tmp_path / "missing",
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
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    (cache_dir / "测试股_2025_annual_jina.txt").write_text(SAMPLE_REPORT, encoding="utf-8")
    output = tmp_path / "cards.md"
    script = Path(__file__).parent.parent.parent / "scripts" / "periodic_report_narrative_cards_preview.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--stock-code",
            "000001",
            "--stock-name",
            "测试股",
            "--cache-dir",
            str(cache_dir),
            "--output",
            str(output),
        ],
        cwd=Path(__file__).parent.parent.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert str(output) in result.stdout
    content = output.read_text(encoding="utf-8")
    assert "Narrative Evidence Cards Preview" in content
    assert "periodic_report_narrative_evidence" in content


def test_cli_knowledge_base_dir_defaults_to_dry_run(tmp_path):
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    (cache_dir / "测试股_2025_annual_jina.txt").write_text(SAMPLE_REPORT, encoding="utf-8")
    output = tmp_path / "cards.md"
    knowledge_dir = tmp_path / "knowledge"
    script = Path(__file__).parent.parent.parent / "scripts" / "periodic_report_narrative_cards_preview.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--stock-code",
            "000001",
            "--stock-name",
            "测试股",
            "--cache-dir",
            str(cache_dir),
            "--output",
            str(output),
            "--knowledge-base-dir",
            str(knowledge_dir),
        ],
        cwd=Path(__file__).parent.parent.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    content = output.read_text(encoding="utf-8")
    assert "Knowledge note plan" in content
    assert "dry_run：`true`" in content
    assert not list(knowledge_dir.rglob("*.md"))


def test_build_preview_markdown_existing_only_refresh_plan(tmp_path):
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    (cache_dir / "测试股_2025_annual_jina.txt").write_text(SAMPLE_REPORT, encoding="utf-8")
    knowledge_dir = tmp_path / "knowledge"
    existing_dir = knowledge_dir / "10-Stocks" / "测试股" / "periodic_narrative_cards"
    existing_dir.mkdir(parents=True)
    existing_note = existing_dir / "2025-annual-management-market-view-0.md"
    existing_note.write_text(
        "---\n"
        "source_type: periodic_report_narrative_evidence\n"
        "card_id: \"periodic:000001:2025:annual:narrative:management_market_view:0\"\n"
        "knowledge_fact_status: narrative_evidence\n"
        "---\n"
        "\n"
        "## Manual Note\n"
        "\n"
        "保留人工补充。\n",
        encoding="utf-8",
    )

    markdown = build_preview_markdown(
        stock_code="000001",
        stock_name="测试股",
        cache_dir=cache_dir,
        report_type="annual",
        knowledge_base_dir=knowledge_dir,
        refresh_existing=True,
        refresh_frontmatter_only=True,
        existing_only=True,
    )

    assert "Knowledge note plan" in markdown
    assert "dry_run：`true`" in markdown
    assert "written：0" in markdown
    assert "refreshed：1" in markdown
    assert "skipped_existing：0" in markdown
    assert "filtered：0" in markdown
    assert "保留人工补充" in existing_note.read_text(encoding="utf-8")
    assert len(list(existing_dir.glob("*.md"))) == 1


def test_build_preview_markdown_renders_knowledge_maintenance_summary(tmp_path):
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    (cache_dir / "测试股_2025_annual_jina.txt").write_text(SAMPLE_REPORT, encoding="utf-8")
    knowledge_dir = tmp_path / "knowledge"
    existing_dir = knowledge_dir / "10-Stocks" / "测试股" / "periodic_narrative_cards"
    existing_dir.mkdir(parents=True)
    matching_note = existing_dir / "2025-annual-management-market-view-0.md"
    matching_note.write_text("---\nsource_type: periodic_report_narrative_evidence\n---\n", encoding="utf-8")
    dangling_note = existing_dir / "2025-annual-rd-product-progress-99.md"
    dangling_note.write_text("---\nsource_type: periodic_report_narrative_evidence\n---\n", encoding="utf-8")

    markdown = build_preview_markdown(
        stock_code="000001",
        stock_name="测试股",
        cache_dir=cache_dir,
        report_type="annual",
        knowledge_base_dir=knowledge_dir,
    )

    assert "## Knowledge maintenance summary" in markdown
    assert "- generated_cards：" in markdown
    assert "- generated_note_candidates：" in markdown
    assert "- existing_notes：2" in markdown
    assert "- refreshable_notes：1" in markdown
    assert "- dangling_notes：1" in markdown
    assert "`2025-annual-rd-product-progress-99.md`" in markdown


def test_cli_write_knowledge_writes_tmp_notes(tmp_path):
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    (cache_dir / "测试股_2025_annual_jina.txt").write_text(SAMPLE_REPORT, encoding="utf-8")
    output = tmp_path / "cards.md"
    knowledge_dir = tmp_path / "knowledge"
    script = Path(__file__).parent.parent.parent / "scripts" / "periodic_report_narrative_cards_preview.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--stock-code",
            "000001",
            "--stock-name",
            "测试股",
            "--cache-dir",
            str(cache_dir),
            "--output",
            str(output),
            "--knowledge-base-dir",
            str(knowledge_dir),
            "--write-knowledge",
        ],
        cwd=Path(__file__).parent.parent.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    notes = list(knowledge_dir.rglob("*.md"))
    assert notes
    note = notes[0].read_text(encoding="utf-8")
    assert "source_type: periodic_report_narrative_evidence" in note
    assert "knowledge_eligible: false" in note
    assert "knowledge_fact_status: narrative_evidence" in note
