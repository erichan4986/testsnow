from __future__ import annotations

import sys
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "utils"))

from broker_research_digest_preview import (  # noqa: E402
    build_broker_research_digest_preview,
    write_broker_research_digest_preview,
)


def test_build_preview_aggregates_local_broker_pdfs_without_knowledge_write(tmp_path: Path) -> None:
    pdf_a = tmp_path / "2026-05-12_国信证券_收入创季度新高.pdf"
    pdf_b = tmp_path / "2026-04-28_华西证券_AI算力驱动增长.pdf"
    pdf_a.write_bytes(b"%PDF fake a")
    pdf_b.write_bytes(b"%PDF fake b")

    texts = {
        str(pdf_a): """
        核心观点
        公司2026年一季度实现收入10.98亿元，同比增长39.08%，毛利率为51.63%。
        投资建议
        预计2026-2028年归母净利润为8.48/12.53/17.67亿元，维持买入评级。
        风险提示
        产品研发不及预期，客户导入不及预期。
        """,
        str(pdf_b): """
        产业趋势
        AI算力基础设施投资持续增长，800G与1.6T光模块需求快速提升。
        \f\f\f\f\f\f\f\f\f\f\f\f\f\f\f
        竞争格局
        公司在重点客户联合开发和产能交付方面形成优势。
        """,
    }

    result = build_broker_research_digest_preview(
        pdf_paths=[pdf_a, pdf_b],
        stock_name="圣邦股份",
        stock_code="300661",
        extractor=lambda path: texts[path],
    )

    assert result["pdf_count"] == 2
    assert result["processed_pdf_count"] == 2
    assert result["errors"] == []
    assert result["cards_count"] >= 3
    assert "国信证券" in result["markdown"]
    assert "华西证券" in result["markdown"]
    assert "professional_analysis" in result["markdown"]
    assert "confirmed_fact：`false`" in result["markdown"]
    assert "scoring_eligible：`false`" in result["markdown"]
    assert "risk_score_eligible：`false`" in result["markdown"]


def test_write_preview_discovers_pdfs_and_returns_output_path(tmp_path: Path) -> None:
    pdf = tmp_path / "2026-05-12_国信证券_收入创季度新高.pdf"
    pdf.write_bytes(b"%PDF fake")
    output = tmp_path / "preview.md"

    summary = write_broker_research_digest_preview(
        pdf_dir=tmp_path,
        stock_name="圣邦股份",
        stock_code="300661",
        output=output,
        extractor=lambda path: """
        核心观点
        公司2026年一季度实现收入10.98亿元，同比增长39.08%，毛利率为51.63%。
        风险提示
        产品研发不及预期，客户导入不及预期。
        """,
    )

    assert summary["preview_path"] == str(output)
    assert summary["pdf_count"] == 1
    assert summary["cards_count"] == 1
    assert output.exists()
    assert "圣邦股份" in output.read_text(encoding="utf-8")


def test_write_preview_discovers_standard_stock_cache_dir(tmp_path: Path) -> None:
    cache_root = tmp_path / "broker_research_reports"
    pdf_dir = cache_root / "圣邦股份_300661" / "_downloads"
    pdf_dir.mkdir(parents=True)
    pdf = pdf_dir / "2026-05-12_国信证券_收入创季度新高.pdf"
    pdf.write_bytes(b"%PDF fake")
    output = tmp_path / "preview.md"

    summary = write_broker_research_digest_preview(
        cache_root=cache_root,
        stock_name="圣邦股份",
        stock_code="300661",
        output=output,
        extractor=lambda path: """
        核心观点
        公司2026年一季度实现收入10.98亿元，同比增长39.08%，毛利率为51.63%。
        投资建议
        产品矩阵持续扩张，工业和汽车电子客户导入继续推进。
        """,
    )

    assert summary["pdf_dir"] == str(pdf_dir)
    assert summary["pdf_count"] == 1
    assert summary["processed_pdfs"] == [str(pdf)]
    assert summary["cards_count"] >= 1
    assert output.exists()


def test_preview_passes_page_count_to_length_classifier(tmp_path: Path) -> None:
    pdf = tmp_path / "2026-05-08_西南证券_深度报告.pdf"
    pdf.write_bytes(b"%PDF fake")
    pages = [
        "核心观点\n公司2026年一季度实现收入194.96亿元，同比增长192.12%，归母净利润57.35亿元，同比增长262.28%。",
        "产业趋势\nAI算力基础设施投资持续增长，800G与1.6T高速光模块需求快速提升。",
        "竞争格局\n公司在硅光芯片、自研能力和重点客户联合开发方面形成交付优势。",
        "盈利预测\n预计2026-2028年EPS分别为22.36元、35.37元、65.71元。",
        "风险提示\nAI算力需求不及预期，客户集中度较高。",
    ]
    pages.extend([f"附录第{i}页" for i in range(6, 18)])
    long_text = "\f".join(pages)

    result = build_broker_research_digest_preview(
        pdf_paths=[pdf],
        stock_name="中际旭创",
        stock_code="300308",
        extractor=lambda path: long_text,
    )

    assert "report_length_class：`long`" in result["markdown"]
    assert "`broker_product_driver`" in result["markdown"]


def test_preview_does_not_dedupe_same_viewpoint_across_different_inferred_stocks(tmp_path: Path) -> None:
    pdf_a = tmp_path / "2026-04-01_中邮证券_乐鑫科技S31推动平台从AI_MCU走向AIoT智能节点.pdf"
    pdf_b = tmp_path / "2026-04-08_国元证券_圣邦股份25年年报点评：产品结构优化.pdf"
    pdf_a.write_bytes(b"%PDF fake a")
    pdf_b.write_bytes(b"%PDF fake b")

    result = build_broker_research_digest_preview(
        pdf_paths=[pdf_a, pdf_b],
        stock_name="研报样本",
        stock_code="smoke",
        extractor=lambda path: """
        核心观点
        公司2026年一季度实现收入10.98亿元，同比增长39.08%，毛利率为51.63%，产品结构持续改善。
        """,
    )

    assert result["cards_count"] == 2
    assert "乐鑫科技" in result["markdown"]
    assert "圣邦股份" in result["markdown"]


def test_cli_can_start_as_script() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "broker_research_digest_preview.py"), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--pdf-dir" in result.stdout
