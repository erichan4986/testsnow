from __future__ import annotations

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from broker_research_digest_note_writer import write_broker_research_digest_card_notes


def _card(**overrides):
    card = {
        "schema_version": "broker_research_digest_card.v1",
        "card_id": "broker:abc123",
        "source_type": "broker_research",
        "card_type": "broker_core_view",
        "title": "券商核心观点",
        "source_excerpt": "公司一季度收入增长，产品结构改善，客户需求保持强劲。",
        "source_excerpt_hash": "a" * 64,
        "report_title": "收入创季度新高",
        "institution": "国信证券",
        "publish_time": "2026-05-12",
        "source_url": "https://pdf.dfcfw.com/pdf/H3_TEST_1.pdf",
        "source_pdf_path": "data/raw/broker_research_reports/圣邦股份_300661/_downloads/test.pdf",
        "stock_name": "圣邦股份",
        "stock_code": "300661",
        "source_credit": 72,
        "claim_status": "professional_analysis",
        "verification_status": "professional_observation",
        "display_only": False,
        "knowledge_eligible": True,
        "confirmed_fact": False,
        "scoring_eligible": False,
        "risk_score_eligible": False,
        "viewpoint_cluster": "business_driver_product_mix_profitability",
        "report_length_class": "short",
    }
    card.update(overrides)
    return card


def _notes_dir(base: Path, stock_name: str = "圣邦股份") -> Path:
    return base / "10-Stocks" / stock_name / "broker_research_digest"


def test_writes_only_knowledge_eligible_broker_digest_cards(tmp_path: Path) -> None:
    cards = [
        _card(),
        _card(
            card_id="broker:display-only",
            card_type="broker_earnings_forecast",
            display_only=True,
            knowledge_eligible=False,
            source_excerpt="预计未来三年利润增长，维持买入评级。",
        ),
        _card(card_id="not-broker", source_type="periodic_report_narrative_evidence"),
    ]

    plan = write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=cards,
        base_dir=tmp_path,
        collected_at="2026-06-24",
    )

    assert len(plan.written) == 1
    assert len(plan.filtered) == 2
    path = Path(plan.written[0]["planned_path"])
    assert path.parent == _notes_dir(tmp_path)
    assert path.name == "2026-05-12-国信证券-broker-core-view-abc123.md"

    text = path.read_text(encoding="utf-8")
    assert "source_type: broker_research" in text
    assert "claim_status: professional_analysis" in text
    assert "verification_status: professional_observation" in text
    assert "source_credit: 72" in text
    assert "knowledge_fact_status: professional_analysis" in text
    assert "knowledge_eligible: true" in text
    assert "confirmed_fact: false" in text
    assert "scoring_eligible: false" in text
    assert "risk_score_eligible: false" in text
    assert "公司一季度收入增长" in text


def test_broker_digest_writer_dry_run_does_not_write(tmp_path: Path) -> None:
    plan = write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[_card()],
        base_dir=tmp_path,
        dry_run=True,
    )

    assert len(plan.written) == 1
    assert not Path(plan.written[0]["planned_path"]).exists()
    assert not _notes_dir(tmp_path).exists()


def test_broker_digest_writer_skips_existing_by_default(tmp_path: Path) -> None:
    write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[_card()],
        base_dir=tmp_path,
    )

    second = write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[_card()],
        base_dir=tmp_path,
    )

    assert second.written == []
    assert len(second.skipped_existing) == 1


def test_broker_digest_writer_refreshes_existing_note_without_selection_diagnostics(
    tmp_path: Path,
) -> None:
    notes_dir = _notes_dir(tmp_path)
    notes_dir.mkdir(parents=True)
    path = notes_dir / "2026-05-12-国信证券-broker-core-view-abc123.md"
    path.write_text(
        "---\n"
        "source_type: broker_research\n"
        "card_id: broker:abc123\n"
        "---\n\n"
        "## Broker Research Excerpt\n\n"
        "> 旧摘录。\n",
        encoding="utf-8",
    )

    plan = write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[
            _card(
                source_excerpt="新摘录保留券商论点、论据和差异。",
                selection_reason="selected_best_heading_candidate",
                selection_diagnostics=[
                    {
                        "heading": "投资要点",
                        "score": 82,
                        "status": "selected",
                        "reason": "selected",
                    },
                    {
                        "heading": "核心观点",
                        "score": 41,
                        "status": "skipped",
                        "reason": "skipped_lower_score",
                    },
                ],
            )
        ],
        base_dir=tmp_path,
    )

    assert len(plan.written) == 1
    assert plan.skipped_existing == []

    text = path.read_text(encoding="utf-8")
    assert "新摘录保留券商论点、论据和差异" in text
    assert "selection_reason: selected_best_heading_candidate" in text
    assert "## Selection Diagnostics" in text
    assert "heading=`投资要点` | score=`82` | parts=`" in text
    assert "status=`selected` | reason=`selected`" in text
    assert "heading=`核心观点` | score=`41` | parts=`" in text
    assert "status=`skipped` | reason=`skipped_lower_score`" in text


def test_broker_digest_writer_repairs_ocr_artifacts_in_persisted_excerpt(
    tmp_path: Path,
) -> None:
    noisy = (
        "营收、利润实 现双增，高速光模 块出货比例提升。现 方面，公司经营活动现金流净额改善，"
        "高速光 过持续向更高端速率升级，收入稳增长与盈 展。"
        "核心增 链能力作为关键支撑，结构升级驱 的业务格局，"
        "公司实现营收195. 环比分别增长，归母净利润57.3亿元，同环比 262.3%。"
        "全年营业收 382.40亿元，面向超大 互联场景。"
    )

    plan = write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[_card(source_excerpt=noisy)],
        base_dir=tmp_path,
    )

    text = Path(plan.written[0]["planned_path"]).read_text(encoding="utf-8")
    assert "实现双增" in text
    assert "高速光模块" in text
    assert "现金流方面" in text
    assert "收入稳增长与盈利扩展" in text
    assert "核心增长与供应链能力" in text
    assert "结构升级驱动的业务格局" in text
    assert "营收195亿元，环比" in text
    assert "同环比增长262.3%" in text
    assert "营业收入382.40亿元" in text
    assert "超大互联场景" in text
    for artifact in ("实 现", "光模 块", "现 方面", "高速光 过", "盈 展", "核心增 链", "结构升级驱 的", "营收195. 环比", "同环比 262.3%", "营业收 382.40", "超大 互联"):
        assert artifact not in text


def test_broker_digest_writer_archives_legacy_broker_notes(
    tmp_path: Path,
) -> None:
    notes_dir = _notes_dir(tmp_path)
    notes_dir.mkdir(parents=True)
    legacy = notes_dir / "2026-05-12-国信证券-broker-core-view-old.md"
    legacy.write_text(
        "---\n"
        "source_type: broker_research\n"
        "card_id: broker:old\n"
        "claim_status: professional_analysis\n"
        "source_credit: 72\n"
        "confirmed_fact: false\n"
        "scoring_eligible: false\n"
        "risk_score_eligible: false\n"
        "display_only: false\n"
        "---\n\n"
        "## Broker Research Excerpt\n\n"
        "> 旧格式摘录。\n",
        encoding="utf-8",
    )

    plan = write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[_card()],
        base_dir=tmp_path,
    )

    archived = notes_dir / "_legacy_archive" / legacy.name
    assert len(plan.archived_legacy) == 1
    assert not legacy.exists()
    assert archived.exists()
    assert "旧格式摘录" in archived.read_text(encoding="utf-8")


def test_broker_digest_writer_refreshes_current_note_missing_cleaner_version(
    tmp_path: Path,
) -> None:
    write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[_card(source_excerpt="高速光模 块出货比例提升。")],
        base_dir=tmp_path,
    )
    path = _notes_dir(tmp_path) / "2026-05-12-国信证券-broker-core-view-abc123.md"

    stale = path.read_text(encoding="utf-8").replace("excerpt_cleaner_version: broker_ocr_v2\n", "")
    path.write_text(stale, encoding="utf-8")

    plan = write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[_card(source_excerpt="高速光模 块出货比例提升。")],
        base_dir=tmp_path,
    )

    refreshed = path.read_text(encoding="utf-8")
    assert len(plan.written) == 1
    assert plan.skipped_existing == []
    assert "excerpt_cleaner_version: broker_ocr_v2" in refreshed
    assert "高速光模块出货比例提升" in refreshed
    assert "高速光模 块" not in refreshed


def test_broker_digest_writer_refreshes_current_note_missing_selection_version(
    tmp_path: Path,
) -> None:
    write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[_card(source_excerpt="高速光模 块出货比例提升。")],
        base_dir=tmp_path,
    )
    path = _notes_dir(tmp_path) / "2026-05-12-国信证券-broker-core-view-abc123.md"

    stale = path.read_text(encoding="utf-8").replace(
        "selection_version: broker_digest_v3_2\n", ""
    )
    path.write_text(stale, encoding="utf-8")

    plan = write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[_card(source_excerpt="高速光模 块出货比例提升。")],
        base_dir=tmp_path,
    )

    refreshed = path.read_text(encoding="utf-8")
    assert len(plan.written) == 1
    assert plan.skipped_existing == []
    assert "selection_version: broker_digest_v3_2" in refreshed


def test_broker_digest_writer_skips_existing_note_with_selection_version(
    tmp_path: Path,
) -> None:
    write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[_card(source_excerpt="高速光模 块出货比例提升。")],
        base_dir=tmp_path,
    )
    path = _notes_dir(tmp_path) / "2026-05-12-国信证券-broker-core-view-abc123.md"
    assert "selection_version: broker_digest_v3_2" in path.read_text(encoding="utf-8")

    plan = write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[_card(source_excerpt="高速光模 块出货比例提升。")],
        base_dir=tmp_path,
    )

    assert plan.written == []
    assert len(plan.skipped_existing) == 1


def test_broker_digest_writer_refreshes_v3_1_note_after_selector_damage_gate_revision(
    tmp_path: Path,
) -> None:
    write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[_card(source_excerpt="产品需求和订单增长支撑收入改善。")],
        base_dir=tmp_path,
    )
    path = _notes_dir(tmp_path) / "2026-05-12-国信证券-broker-core-view-abc123.md"
    stale = path.read_text(encoding="utf-8").replace(
        "selection_version: broker_digest_v3_2\n",
        "selection_version: broker_digest_v3_1\n",
    )
    path.write_text(stale, encoding="utf-8")

    plan = write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[_card(source_excerpt="产品需求和订单增长支撑收入改善。")],
        base_dir=tmp_path,
    )

    refreshed = path.read_text(encoding="utf-8")
    assert len(plan.written) == 1
    assert plan.skipped_existing == []
    assert "selection_version: broker_digest_v3_2" in refreshed


def test_broker_digest_writer_keeps_existing_note_with_selection_diagnostics(
    tmp_path: Path,
) -> None:
    notes_dir = _notes_dir(tmp_path)
    notes_dir.mkdir(parents=True)
    path = notes_dir / "2026-05-12-国信证券-broker-core-view-abc123.md"
    existing = (
        "---\n"
        "source_type: broker_research\n"
        "schema_version: broker_research_digest_card.v1\n"
        "card_id: broker:abc123\n"
        "selection_reason: selected_best_heading_candidate\n"
        "excerpt_cleaner_version: broker_ocr_v2\n"
        "selection_version: broker_digest_v3_2\n"
        "---\n\n"
        "## Broker Research Excerpt\n\n"
        "> 人工保留摘录。\n\n"
        "## Selection Diagnostics\n\n"
        "- heading=`投资要点` | score=`80` | status=`selected` | reason=`selected`\n"
    )
    path.write_text(existing, encoding="utf-8")

    plan = write_broker_research_digest_card_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=[
            _card(
                source_excerpt="不应覆盖的新摘录。",
                selection_reason="selected_best_heading_candidate",
                selection_diagnostics=[
                    {
                        "heading": "投资要点",
                        "score": 82,
                        "status": "selected",
                        "reason": "selected",
                    }
                ],
            )
        ],
        base_dir=tmp_path,
    )

    assert plan.written == []
    assert len(plan.skipped_existing) == 1
    assert path.read_text(encoding="utf-8") == existing
