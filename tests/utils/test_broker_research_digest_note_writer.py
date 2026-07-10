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
    assert "heading=`投资要点` | score=`82` | status=`selected` | reason=`selected`" in text
    assert "heading=`核心观点` | score=`41` | status=`skipped` | reason=`skipped_lower_score`" in text


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
