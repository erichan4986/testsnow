import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "previews"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from periodic_report_narrative_cards_acceptance import (  # noqa: E402
    analyze_cards_pack,
    build_acceptance_markdown,
)


SAMPLE_REPORT = """
2025年年度报告

报告期内公司从事的主要业务
公司主要从事高性能碳纤维及相关产品的研发、生产、销售和技术服务。
产品主要应用于航空航天、轨道交通、新能源等领域。

行业情况
高端航空航天用碳纤维需求保持增长，低端通用级碳纤维产能过剩，价格承压。

主营业务分产品情况
公司高端产品出货占比提升，产品结构优化带动毛利率同比提升，规模效应和成本控制持续强化公司竞争力。
"""


def _card(card_type, excerpt, *, card_id=None, source_hash=None):
    suffix = card_id or f"{card_type}:0"
    return {
        "card_id": f"periodic:000001:2025:annual:narrative:{suffix}",
        "card_type": card_type,
        "source_excerpt": excerpt,
        "source_excerpt_hash": source_hash or f"{abs(hash(excerpt)):064x}"[-64:],
        "report_year": 2025,
        "report_type": "annual",
    }


def test_analyze_cards_pack_counts_distribution_and_quality_flags():
    duplicate_hash = "a" * 64
    cards_pack = {
        "cards": [
            _card("business_model", "公司主要从事高性能碳纤维及相关产品的研发、生产、销售和技术服务。", source_hash=duplicate_hash),
            _card("business_model", "公司主要从事高性能碳纤维及相关产品的研发、生产、销售和技术服务。", card_id="business_model:1", source_hash=duplicate_hash),
            _card("management_market_view", "力、众多的产品线，仍占据较大的市场份额，公司主要产品在相关领域与其展开竞争。"),
            _card("operation_update", "产品名称 接入网类型 传输速率 □适用 不适用 光模块 光纤接入 详见下文 不适用。"),
            _card("financial_note", "存货减值。"),
        ],
        "candidate_cards": [
            _card("business_model", "候选卡片保留，用于维护摘要。"),
            _card("financial_note", "另一个候选卡片保留，用于维护摘要。"),
        ],
    }

    summary = analyze_cards_pack(
        stock_code="000001",
        stock_name="测试股",
        cards_pack=cards_pack,
        maintenance_summary={
            "existing_notes": 3,
            "refreshable_notes": 2,
            "moved_or_reindexed_notes": 1,
            "dangling_notes": 0,
            "new_candidate_notes": 2,
        },
    )

    assert summary["selected_cards"] == 5
    assert summary["candidate_cards"] == 2
    assert summary["card_type_counts"]["business_model"] == 2
    assert summary["quality_flags"]["duplicate_excerpt_hashes"] == 1
    assert summary["quality_flags"]["short_excerpts"] == 1
    assert summary["quality_flags"]["dangling_start_excerpts"] == 1
    assert summary["quality_flags"]["table_fragment_excerpts"] == 1
    assert summary["maintenance"]["moved_or_reindexed_notes"] == 1


def test_analyze_cards_pack_does_not_flag_valid_temporal_sentence_starters():
    cards_pack = {
        "cards": [
            _card("market_outlook", "未来，先进封装占比将逐步超越传统封装，国产替代从单点突破迈向全产业链系统性突破。"),
            _card("management_market_view", "当前，地缘博弈深化、全球经济复苏乏力，公司保持战略定力并推进技术创新。"),
        ]
    }

    summary = analyze_cards_pack(
        stock_code="688035",
        stock_name="德邦科技",
        cards_pack=cards_pack,
    )

    assert summary["quality_flags"]["dangling_start_excerpts"] == 0


def test_build_acceptance_markdown_from_local_cache(tmp_path):
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    (cache_dir / "测试股_2025_annual_jina.txt").write_text(SAMPLE_REPORT, encoding="utf-8")

    markdown = build_acceptance_markdown(
        stocks=[("000001", "测试股")],
        cache_dir=cache_dir,
        report_type="annual",
        report_year=2025,
    )

    assert "# 定期报告 Narrative Cards Acceptance" in markdown
    assert "测试股" in markdown
    assert "card_type distribution" in markdown
    assert "quality flags" in markdown
    assert "business_model" in markdown


def test_cli_writes_acceptance_markdown_without_touching_knowledge(tmp_path):
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    (cache_dir / "测试股_2025_annual_jina.txt").write_text(SAMPLE_REPORT, encoding="utf-8")
    output = tmp_path / "acceptance.md"
    knowledge_dir = tmp_path / "knowledge"
    script = (
        Path(__file__).parent.parent.parent
        / "scripts"
        / "previews"
        / "periodic_report_narrative_cards_acceptance.py"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--stock",
            "000001:测试股",
            "--cache-dir",
            str(cache_dir),
            "--knowledge-base-dir",
            str(knowledge_dir),
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
    assert output.exists()
    assert "dry_run_only：true" in output.read_text(encoding="utf-8")
    assert not list(knowledge_dir.rglob("*.md"))
