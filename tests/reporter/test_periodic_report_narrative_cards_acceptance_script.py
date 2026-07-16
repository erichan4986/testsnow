import subprocess
import sys
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "previews"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import periodic_report_narrative_cards_acceptance as acceptance_module  # noqa: E402
from periodic_report_narrative_cards_acceptance import (  # noqa: E402
    analyze_cards_pack,
    analyze_pack_projection,
    build_acceptance_markdown,
)
from periodic_report_narrative_pack_store import write_periodic_report_narrative_pack


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
    )

    assert summary["selected_cards"] == 5
    assert summary["candidate_cards"] == 2
    assert summary["card_type_counts"]["business_model"] == 2
    assert summary["quality_flags"]["duplicate_excerpt_hashes"] == 1
    assert summary["quality_flags"]["short_excerpts"] == 1
    assert summary["quality_flags"]["dangling_start_excerpts"] == 1
    assert summary["quality_flags"]["table_fragment_excerpts"] == 1


def test_analyze_cards_pack_uses_v2_argument_family_for_distribution():
    summary = analyze_cards_pack(
        stock_code="000001",
        stock_name="测试股",
        cards_pack={
            "cards": [{
                "schema_version": "periodic_report_narrative_evidence_card.v2",
                "argument_family": "business_structure",
                "source_excerpt": "公司主营业务覆盖航空航天和新能源客户。",
            }],
        },
    )

    assert summary["card_type_counts"] == {"business_structure": 1}


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
    assert "business_structure" in markdown


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
    assert "pack shadow" not in output.read_text(encoding="utf-8")
    assert not list(knowledge_dir.rglob("*.md"))


def _build_and_store_cards_pack(tmp_path):
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    (cache_dir / "测试股_2025_annual_jina.txt").write_text(SAMPLE_REPORT, encoding="utf-8")
    from periodic_report_evidence_pack import build_periodic_report_evidence_pack
    from periodic_report_narrative_evidence_cards import build_periodic_report_narrative_evidence_cards

    evidence = build_periodic_report_evidence_pack(SAMPLE_REPORT, report_type="annual")
    cards_pack = build_periodic_report_narrative_evidence_cards(
        stock_code="000001",
        stock_name="测试股",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence,
        raw_text=SAMPLE_REPORT,
    )
    stored = write_periodic_report_narrative_pack(
        stock_name="测试股", stock_code="000001", card_pack=cards_pack, base_dir=tmp_path,
    )
    return cache_dir, cards_pack, stored


def test_analyze_pack_projection_is_deterministic_and_read_only(tmp_path):
    _, cards_pack, stored = _build_and_store_cards_pack(tmp_path)
    before_pack = stored.pack_path.read_bytes()
    before_manifest = stored.manifest_path.read_bytes()

    result = analyze_pack_projection(
        stock_code="000001",
        stock_name="测试股",
        cards_pack=cards_pack,
        knowledge_base_dir=tmp_path,
    )

    assert result["producer_pack_parity"] is True
    assert result["projection_deterministic"] is True
    assert result["pack_bytes_unchanged"] is True
    assert result["manifest_bytes_unchanged"] is True
    assert result["projection_cards_sha256_matches"] is True
    assert result["projection_total_cards"] == len(cards_pack["cards"])
    assert 0 <= result["projection_displayed_cards"] <= len(cards_pack["cards"])
    assert result["v1_actionable_needs_recovery_count"] == 0
    assert result["v1_adapter_use_count"] == 0
    assert stored.pack_path.read_bytes() == before_pack
    assert stored.manifest_path.read_bytes() == before_manifest
    assert not list(tmp_path.rglob("periodic_narrative_views/*.md"))

    drifted = dict(cards_pack, selection_version="future-selection")
    assert analyze_pack_projection(
        stock_code="000001", stock_name="测试股", cards_pack=drifted,
        knowledge_base_dir=tmp_path,
    )["producer_pack_parity"] is False


def test_pack_shadow_alias_and_pack_projection_render_new_read_only_audit(tmp_path):
    cache_dir, _, _ = _build_and_store_cards_pack(tmp_path)

    for kwargs in ({"pack_shadow": True}, {"pack_projection": True}, {
        "pack_shadow": True, "pack_projection": True,
    }):
        markdown = build_acceptance_markdown(
            stocks=[("000001", "测试股")], cache_dir=cache_dir,
            report_type="annual", report_year=2025,
            knowledge_base_dir=tmp_path, **kwargs,
        )
        assert "### pack projection" in markdown
        assert "- producer_pack_parity: True" in markdown
        assert "- projection_deterministic: True" in markdown
        assert "active_v2_parity" not in markdown
        assert "selected_material_parity" not in markdown
        assert "knowledge maintenance" not in markdown
    assert not list(tmp_path.rglob("periodic_narrative_views/*.md"))


def test_cli_pack_projection_is_read_only(tmp_path):
    cache_dir, _, stored = _build_and_store_cards_pack(tmp_path)
    output = tmp_path / "acceptance.md"
    script = Path(acceptance_module.__file__)
    before = (stored.pack_path.read_bytes(), stored.manifest_path.read_bytes())

    result = subprocess.run(
        [sys.executable, str(script), "--stock", "000001:测试股", "--cache-dir",
         str(cache_dir), "--knowledge-base-dir", str(tmp_path), "--pack-projection",
         "--output", str(output)],
        cwd=Path(__file__).parent.parent.parent, text=True, capture_output=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "### pack projection" in output.read_text(encoding="utf-8")
    assert (stored.pack_path.read_bytes(), stored.manifest_path.read_bytes()) == before
    assert not list(tmp_path.rglob("periodic_narrative_views/*.md"))


def _projection_gate(*, recovery: int = 0, adapters: int = 0) -> dict:
    return {
        "producer_pack_parity": True,
        "projection_deterministic": True,
        "pack_bytes_unchanged": True,
        "manifest_bytes_unchanged": True,
        "projection_cards_sha256_matches": True,
        "v1_actionable_needs_recovery_count": recovery,
        "v1_adapter_use_count": adapters,
    }


def _legacy_note(base: Path, stock: str, name: str, schema: str) -> Path:
    path = base / "10-Stocks" / stock / "periodic_narrative_cards" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nsource_type: periodic_report_narrative_evidence\n"
        f"schema_version: {schema}\n---\n",
        encoding="utf-8",
    )
    return path


def test_archive_manifest_is_deterministic_and_lists_notes_only_after_global_gate(
    tmp_path: Path,
) -> None:
    v1 = _legacy_note(
        tmp_path, "甲公司", "2025-annual-business-model-0.md",
        "periodic_report_narrative_evidence_card.v1",
    )
    v2 = _legacy_note(
        tmp_path, "乙公司", "2025-annual-business-structure-0.md",
        "periodic_report_narrative_evidence_card.v2",
    )
    stocks = [("000001", "甲公司"), ("000002", "乙公司")]
    projections = {name: _projection_gate() for _code, name in stocks}

    first = acceptance_module.build_archive_manifest(
        stocks=stocks, knowledge_base_dir=tmp_path, projections=projections
    )
    second = acceptance_module.build_archive_manifest(
        stocks=stocks, knowledge_base_dir=tmp_path, projections=projections
    )

    assert first == second
    assert first["dry_run_only"] is True
    assert first["requires_explicit_confirmation"] is True
    assert first["all_stock_gates_passed"] is True
    assert [item["path"] for item in first["archive_eligible"]] == sorted([
        str(v1.relative_to(tmp_path)),
        str(v2.relative_to(tmp_path)),
    ])
    hashes = {item["path"]: item["sha256"] for item in first["archive_eligible"]}
    assert hashes[str(v1.relative_to(tmp_path))] == hashlib.sha256(v1.read_bytes()).hexdigest()
    assert first["stocks"][0]["v1_note_count"] == 1
    assert first["stocks"][1]["v2_note_count"] == 1

    blocked = acceptance_module.build_archive_manifest(
        stocks=stocks,
        knowledge_base_dir=tmp_path,
        projections={"甲公司": _projection_gate(recovery=1), "乙公司": _projection_gate()},
    )
    assert blocked["all_stock_gates_passed"] is False
    assert blocked["archive_eligible"] == []
