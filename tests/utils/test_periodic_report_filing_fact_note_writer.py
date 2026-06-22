from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_filing_fact_note_writer import (
    FilingFactWritePlan,
    write_periodic_report_filing_fact_notes,
)


def _normalized_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _filing_fact(**overrides):
    fact = {
        "schema_version": "periodic_report_structured_fact.v1",
        "source_type": "periodic_report_filing_fact",
        "fact_id": "periodic:300777:2025:annual:revenue",
        "stock_code": "300777",
        "stock_name": "中简科技",
        "report_year": 2025,
        "report_type": "annual",
        "metric_key": "revenue",
        "label": "营业收入",
        "value": "84601.52万元",
        "normalized_value": "84601.52万元",
        "unit": "万元",
        "currency": "CNY",
        "period": "2025",
        "value_basis": "as_reported",
        "source_block_id": "financial_summary_table-0",
        "evidence_refs": ["financial_summary_table-0"],
        "source_excerpt": "2025年公司实现营业收入 846,015,199.43 元",
        "confidence": "high",
        "source_credit": 75,
        "knowledge_eligible": False,
    }
    fact.update(overrides)
    return fact


def _pack(filing_facts, **extra):
    pack = {
        "schema_version": "periodic_report_structured_fact.v1",
        "stock_code": "300777",
        "stock_name": "中简科技",
        "report_year": 2025,
        "report_type": "annual",
        "filing_facts": filing_facts,
        "derived_facts": [],
        "filing_risk_signals": [],
        "diagnostics": [],
    }
    pack.update(extra)
    return pack


def _facts_dir(base: Path, stock_name: str = "中简科技") -> Path:
    return base / "10-Stocks" / stock_name / "filing_facts"


def test_writes_only_valid_filing_facts_to_tmp_knowledge(tmp_path) -> None:
    plan = write_periodic_report_filing_fact_notes(
        stock_name="中简科技",
        stock_code="300777",
        fact_pack=_pack([_filing_fact()]),
        base_dir=tmp_path,
        collected_at="2026-06-20",
    )

    assert isinstance(plan, FilingFactWritePlan)
    assert len(plan.written) == 1
    path = Path(plan.written[0]["planned_path"])
    assert path.exists()
    assert path.parent == _facts_dir(tmp_path)
    assert path.name == "2025-annual-revenue.md"

    text = path.read_text(encoding="utf-8")
    assert "营业收入" in text
    assert "846,015,199.43" in text
    assert "periodic:300777:2025:annual:revenue" in text


def test_filters_fulltext_derived_and_risk_entries_from_mixed_pack(tmp_path) -> None:
    mixed = [
        _filing_fact(),
        _filing_fact(
            source_type="periodic_report_fulltext_analysis",
            metric_key="fulltext_summary",
            fact_id="periodic:300777:2025:annual:fulltext",
        ),
        _filing_fact(
            source_type="periodic_report_derived_fact",
            metric_key="operating_cash_flow_to_net_profit",
            fact_id="periodic:300777:2025:annual:ratio",
        ),
        _filing_fact(
            source_type="periodic_report_risk_signal",
            metric_key="cashflow_quality_weak",
            fact_id="periodic:300777:2025:annual:signal",
        ),
    ]
    pack = _pack(
        mixed,
        derived_facts=[{"source_type": "periodic_report_derived_fact"}],
        filing_risk_signals=[{"source_type": "periodic_report_risk_signal"}],
    )

    plan = write_periodic_report_filing_fact_notes(
        stock_name="中简科技",
        stock_code="300777",
        fact_pack=pack,
        base_dir=tmp_path,
    )

    assert len(plan.written) == 1
    files = sorted(p.name for p in _facts_dir(tmp_path).glob("*.md"))
    assert files == ["2025-annual-revenue.md"]
    # The three non-filing-fact entries are recorded as filtered, not written.
    assert len(plan.filtered) == 3
    assert all("periodic_report_filing_fact" in entry["reason"] for entry in plan.filtered)


def test_skips_fact_missing_evidence_fields(tmp_path) -> None:
    missing_block = _filing_fact(
        metric_key="net_profit",
        fact_id="periodic:300777:2025:annual:net_profit",
    )
    del missing_block["source_block_id"]

    missing_excerpt = _filing_fact(
        metric_key="operating_cash_flow",
        fact_id="periodic:300777:2025:annual:operating_cash_flow",
    )
    missing_excerpt["source_excerpt"] = ""

    plan = write_periodic_report_filing_fact_notes(
        stock_name="中简科技",
        stock_code="300777",
        fact_pack=_pack([_filing_fact(), missing_block, missing_excerpt]),
        base_dir=tmp_path,
    )

    assert len(plan.written) == 1
    reasons = [entry["reason"] for entry in plan.filtered]
    assert any("source_block_id" in reason for reason in reasons)
    assert any("source_excerpt" in reason for reason in reasons)


def test_frontmatter_keeps_knowledge_eligible_false_and_status_filing_fact(tmp_path) -> None:
    # Even a hostile fact claiming knowledge_eligible=True must be persisted as false.
    plan = write_periodic_report_filing_fact_notes(
        stock_name="中简科技",
        stock_code="300777",
        fact_pack=_pack([_filing_fact(knowledge_eligible=True)]),
        base_dir=tmp_path,
    )

    text = Path(plan.written[0]["planned_path"]).read_text(encoding="utf-8")
    assert "source_type: periodic_report_filing_fact" in text
    assert "knowledge_fact_status: filing_fact" in text
    assert "knowledge_eligible: false" in text
    assert "knowledge_persisted: true" in text
    assert "knowledge_eligible: true" not in text
    assert "source_credit: 75" in text
    assert "verified_by: []" in text
    assert "conflicts_with: []" in text


def test_note_frontmatter_persists_source_hashes_and_computes_excerpt_hash(tmp_path) -> None:
    fact = _filing_fact(source_block_hash="b" * 64)
    plan = write_periodic_report_filing_fact_notes(
        stock_name="中简科技",
        stock_code="300777",
        fact_pack=_pack([fact]),
        base_dir=tmp_path,
    )

    text = Path(plan.written[0]["planned_path"]).read_text(encoding="utf-8")
    assert f"source_excerpt_hash: {_normalized_hash(fact['source_excerpt'])}" in text
    assert f"source_block_hash: {'b' * 64}" in text


def test_dry_run_returns_plan_without_writing_file(tmp_path) -> None:
    plan = write_periodic_report_filing_fact_notes(
        stock_name="中简科技",
        stock_code="300777",
        fact_pack=_pack([_filing_fact()]),
        base_dir=tmp_path,
        dry_run=True,
    )

    assert len(plan.written) == 1
    planned = Path(plan.written[0]["planned_path"])
    assert not planned.exists()
    assert planned.name == "2025-annual-revenue.md"
    assert not _facts_dir(tmp_path).exists()


def test_duplicate_existing_file_is_skipped_by_default(tmp_path) -> None:
    pack = _pack([_filing_fact()])
    first = write_periodic_report_filing_fact_notes(
        stock_name="中简科技",
        stock_code="300777",
        fact_pack=pack,
        base_dir=tmp_path,
    )
    assert len(first.written) == 1

    second = write_periodic_report_filing_fact_notes(
        stock_name="中简科技",
        stock_code="300777",
        fact_pack=pack,
        base_dir=tmp_path,
    )
    assert second.written == []
    assert len(second.skipped_existing) == 1
    assert second.skipped_existing[0]["fact_id"] == "periodic:300777:2025:annual:revenue"


def test_refresh_existing_overwrites_deterministically(tmp_path) -> None:
    pack = _pack([_filing_fact()])
    write_periodic_report_filing_fact_notes(
        stock_name="中简科技",
        stock_code="300777",
        fact_pack=pack,
        base_dir=tmp_path,
        collected_at="2026-06-20",
    )
    path = _facts_dir(tmp_path) / "2025-annual-revenue.md"
    original = path.read_text(encoding="utf-8")

    plan = write_periodic_report_filing_fact_notes(
        stock_name="中简科技",
        stock_code="300777",
        fact_pack=pack,
        base_dir=tmp_path,
        collected_at="2026-06-20",
        refresh_existing=True,
    )
    assert len(plan.refreshed) == 1
    assert plan.written == []
    # Same inputs -> byte-identical note.
    assert path.read_text(encoding="utf-8") == original


def test_refresh_existing_frontmatter_only_adds_hashes_without_touching_body(tmp_path) -> None:
    pack = _pack([_filing_fact(source_block_hash="d" * 64)])
    write_periodic_report_filing_fact_notes(
        stock_name="中简科技",
        stock_code="300777",
        fact_pack=_pack([_filing_fact()]),
        base_dir=tmp_path,
        collected_at="2026-06-20",
    )
    path = _facts_dir(tmp_path) / "2025-annual-revenue.md"
    original = path.read_text(encoding="utf-8")
    manual_body = original + "\n## Manual Note\n\n保留人工补充。\n"
    path.write_text(manual_body, encoding="utf-8")

    plan = write_periodic_report_filing_fact_notes(
        stock_name="中简科技",
        stock_code="300777",
        fact_pack=pack,
        base_dir=tmp_path,
        collected_at="2026-06-22",
        refresh_existing=True,
        refresh_frontmatter_only=True,
    )

    refreshed = path.read_text(encoding="utf-8")
    assert len(plan.refreshed) == 1
    assert plan.refreshed[0]["reason"] == "refreshed_frontmatter_hashes"
    assert "## Manual Note\n\n保留人工补充。\n" in refreshed
    assert f"source_excerpt_hash: {_normalized_hash(_filing_fact()['source_excerpt'])}" in refreshed
    assert f"source_block_hash: {'d' * 64}" in refreshed
    assert refreshed.split("---", 2)[2] == manual_body.split("---", 2)[2]


def test_hostile_stock_name_and_metric_key_cannot_escape_filing_facts_dir(tmp_path) -> None:
    fact = _filing_fact(
        metric_key="../../../../etc/passwd",
        fact_id="periodic:300777:2025:annual:evil",
    )

    plan = write_periodic_report_filing_fact_notes(
        stock_name="../../evil",
        stock_code="300777",
        fact_pack=_pack([fact]),
        base_dir=tmp_path,
    )

    base = tmp_path.resolve()
    for entry in plan.written:
        resolved = Path(entry["planned_path"]).resolve()
        assert str(resolved).startswith(str(base) + "/")
        assert resolved.parent.name == "filing_facts"

    # No traversal artifacts created outside the sandbox.
    assert not (tmp_path.parent / "etc").exists()
    for created in tmp_path.rglob("*.md"):
        assert str(created.resolve()).startswith(str(base) + "/")


def test_stock_code_mismatch_is_filtered_and_note_uses_api_stock_identity(tmp_path) -> None:
    mismatched = _filing_fact(
        stock_code="000000",
        stock_name="错误公司",
        metric_key="net_profit",
        fact_id="periodic:000000:2025:annual:net_profit",
    )

    plan = write_periodic_report_filing_fact_notes(
        stock_name="中简科技",
        stock_code="300777",
        fact_pack=_pack([_filing_fact(), mismatched]),
        base_dir=tmp_path,
    )

    assert len(plan.written) == 1
    assert len(plan.filtered) == 1
    assert "stock_code mismatch" in plan.filtered[0]["reason"]

    text = Path(plan.written[0]["planned_path"]).read_text(encoding="utf-8")
    assert 'stock: "中简科技"' in text
    assert 'code: "300777"' in text
    assert "错误公司" not in text
