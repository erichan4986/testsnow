"""LLM synthesis skill."""

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

if __name__.startswith("utils."):
    from ..skill_pipeline import BaseSkill, SkillContext
    from ..knowledge_synthesizer import KnowledgeSynthesizer
    from ..source_adapter import adapt_all
    from ..synthesis_credit import (
        citation_identity,
        credit_usage_rules_text,
        derive_synthesis_usage,
        format_synthesis_source_line,
        is_core_fact_supporting_source,
        format_claim_verification_appendix,
    )
    from ..synthesis_source_policy import (
        is_canonical_synthesis_source,
        is_formal_display_source,
    )
    from ..periodic_report_narrative_card_synthesis_items import (
        load_periodic_narrative_card_synthesis_items,
    )
    from ..broker_research_digest_synthesis_items import (
        load_broker_research_digest_synthesis_items,
    )
    from ..broker_research_digest_note_writer import (
        refresh_broker_research_digest_card_notes_from_manifest,
    )
    from ..synthesis_display_deduper import dedupe_synthesis_display_items
    from ..curated_external_display import build_curated_external_argument_display, flatten_synthesis_text
    from ..periodic_external_evidence_map import build_periodic_external_evidence_map
    from ..industry_news_relevance import build_industry_relevance_manifest
    from ..peer_comparison_material import build_peer_comparison_material
    from ..fundflow_material import build_fundflow_material_pack
    from ..annual_report_material_pack import (
        build_annual_report_material_pack,
        selected_cards_to_synthesis_items,
    )
    from ..periodic_report_narrative_pack_store import PeriodicNarrativePackStorageError
    from ..evidence_freshness import build_freshness_overlay, parse_explicit_date
    from ..deep_analysis_material_snapshot import build_chapter4_formal_material_diagnostics
else:
    from skill_pipeline import BaseSkill, SkillContext
    from knowledge_synthesizer import KnowledgeSynthesizer
    from source_adapter import adapt_all
    from synthesis_credit import (
        citation_identity,
        credit_usage_rules_text,
        derive_synthesis_usage,
        format_synthesis_source_line,
        is_core_fact_supporting_source,
        format_claim_verification_appendix,
    )
    from synthesis_source_policy import (
        is_canonical_synthesis_source,
        is_formal_display_source,
    )
    from periodic_report_narrative_card_synthesis_items import (
        load_periodic_narrative_card_synthesis_items,
    )
    from broker_research_digest_synthesis_items import (
        load_broker_research_digest_synthesis_items,
    )
    from broker_research_digest_note_writer import (
        refresh_broker_research_digest_card_notes_from_manifest,
    )
    from synthesis_display_deduper import dedupe_synthesis_display_items
    from curated_external_display import build_curated_external_argument_display, flatten_synthesis_text
    from periodic_external_evidence_map import build_periodic_external_evidence_map
    from industry_news_relevance import build_industry_relevance_manifest
    from peer_comparison_material import build_peer_comparison_material
    from fundflow_material import build_fundflow_material_pack
    from annual_report_material_pack import (
        build_annual_report_material_pack,
        selected_cards_to_synthesis_items,
    )
    from periodic_report_narrative_pack_store import PeriodicNarrativePackStorageError
    from evidence_freshness import build_freshness_overlay, parse_explicit_date
    from deep_analysis_material_snapshot import build_chapter4_formal_material_diagnostics


SYNTHESIS_KEYS = [
    "industry_logic",
    "fundamentals",
    "valuation_debate",
    "funding_sentiment",
    "events_catalysts",
]

class SynthesisSkill(BaseSkill):
    """LLM 综合叙事生成。"""
    name = "synthesis"

    def __init__(self, llm_client=None, synthesizer=None, **kwargs):
        super().__init__(**kwargs)
        self.llm_client = llm_client
        self.synthesizer = synthesizer

    def run(self, ctx: SkillContext) -> SkillContext:
        stock_name = ctx.get("stock_name")
        stock_raw = ctx.get("stock_raw", {})
        keep_posts = ctx.get("keep_posts", [])

        # Build peer comparison material from deterministic metrics.
        # Must be done BEFORE baseline synthesis so _build_prompt can
        # add peer appendix to 4.1/4.2 theme prompts.
        peer_material = build_peer_comparison_material(
            stock_name=stock_name,
            competitor_metrics=ctx.get("competitor_metrics"),
            stock_config=ctx.get("stock_config"),
        )
        ctx.set("peer_comparison_material", peer_material)

        # Build formal material packs early so evidence profile can read them.
        financial_fact_pack = self._build_formal_financial_fact_pack(
            ctx.get("periodic_report_filing_core_facts", [])
        )
        if financial_fact_pack.get("facts"):
            ctx.set("formal_financial_fact_pack", financial_fact_pack)
        financial_explanation_pack = ctx.get("periodic_report_explanation_pack") or {}
        if isinstance(financial_explanation_pack, dict) and financial_explanation_pack.get("rows"):
            ctx.set("formal_financial_explanation_pack", financial_explanation_pack)
        fundflow_material_pack = build_fundflow_material_pack(stock_raw.get("fundflow", []))
        if fundflow_material_pack.get("rows"):
            ctx.set("fundflow_material_pack", fundflow_material_pack)

        # Build annual-report material pack and load broker display material once.
        annual_material_pack: Dict[str, Any] = {}
        stock_name_for_annual = ctx.get("stock_name")
        if stock_name_for_annual:
            base_dir = ctx.get("knowledge_base_dir") or Path(__file__).resolve().parents[3] / "knowledge"
            stock_code_for_annual = str((ctx.get("stock_codes") or {}).get(stock_name_for_annual) or "").strip()
            try:
                annual_material_pack = build_annual_report_material_pack(
                    stock_name=stock_name_for_annual,
                    stock_code=stock_code_for_annual,
                    base_dir=base_dir,
                )
            except PeriodicNarrativePackStorageError:
                raise
            except Exception:
                pass
        if annual_material_pack:
            ctx.set("annual_report_material_pack", annual_material_pack)
        self._refresh_broker_research_digest_notes(ctx)
        if ctx.get("broker_research_digest_items") is None:
            ctx.set("broker_research_digest_items", self._eligible_broker_research_digest_items(ctx))
        ctx.set(
            "chapter4_formal_material_diagnostics",
            build_chapter4_formal_material_diagnostics(ctx),
        )

        # Build canonical synthesis items once.
        items = self._build_synthesis_items(stock_raw, keep_posts, ctx=ctx)

        # Curated external display is independent of baseline synthesis; build it first.
        self._build_curated_external_deep_analysis_display(ctx)

        # Evidence-adaptive routing: profile decides which deep-analysis prompts run.
        profile = self._build_evidence_profile(ctx, items)
        ctx.set("deep_analysis_evidence_profile", profile)
        ctx.set("deep_analysis_material_coverage", self._build_material_coverage_diagnostics(ctx))

        if profile["profile"] in {"formal_rich", "formal_medium"}:
            baseline = self._synthesize(stock_name, stock_raw, keep_posts, ctx, items=items)
        else:
            source_policy = self._canonical_synthesis_source_policy(ctx)
            formal_first_insufficient = source_policy == "formal_first"
            if ctx is not None and formal_first_insufficient:
                ctx.set("formal_first_sources_insufficient", True)
            baseline = self._empty_baseline_synthesis(stock_raw, items, source_policy=source_policy, formal_first_insufficient=formal_first_insufficient)
        external_display = ctx.get("deep_analysis_display") or {}
        freshness = self._build_evidence_freshness_overlay(ctx, profile, external_display)
        self._reserve_freshness_citations(baseline, freshness, external_display)
        ctx.set("evidence_freshness", freshness)
        ctx.set("synthesis", baseline)
        core_facts = self._select_core_facts(
            baseline.get("core_facts", []),
            ctx.get("periodic_report_filing_core_facts", []),
        )
        ctx.set("core_facts", core_facts)
        ctx.set("synthesis_text", flatten_synthesis_text(baseline))
        ctx.set("synthesis_items_count", baseline.get("_items_count", 0))
        ctx.set("synthesis_sources", baseline.get("_sources", []))
        ctx.set("industry_relevance_manifest", baseline.get("_industry_relevance_manifest", {}))

        # Optional experimental paths: annual-report materials and broker-research
        # digest notes may enter the DISPLAY synthesis only.  Canonical synthesis,
        # core_facts, synthesis_text, and synthesis_sources stay baseline so risk
        # scoring and Knowledge persistence never see display-only material.
        # Formal-rich and formal-medium reports keep the legacy deep-analysis
        # sections, so they may use display-only formal materials to improve
        # readability. Thin layouts use the external viewpoint map / formal
        # summary instead.
        display_items = []
        fulltext_items = []
        narrative_card_items = []
        broker_digest_items = []
        if profile["profile"] in {"formal_rich", "formal_medium"}:
            if ctx.get("include_periodic_report_fulltext_in_synthesis"):
                fulltext_items = self._eligible_periodic_report_fulltext_items(ctx)
                display_items.extend(fulltext_items)
            if ctx.get("include_periodic_narrative_cards_in_synthesis_display"):
                narrative_card_items = self._eligible_periodic_narrative_card_items(ctx)
                display_items.extend(narrative_card_items)
            if ctx.get("include_broker_research_digest_in_synthesis_display"):
                broker_digest_items = ctx.get("broker_research_digest_items") or []
                display_items.extend(broker_digest_items)
        if display_items:
            display = self._synthesize(
                stock_name,
                stock_raw,
                keep_posts,
                ctx,
                extra_items=display_items,
            )
            display_text = flatten_synthesis_text(display)
            ctx.set("synthesis_display", display)
            ctx.set("synthesis_display_sources", display.get("_sources", []))
            ctx.set("synthesis_text_with_periodic_display_materials", display_text)
            if fulltext_items:
                ctx.set("synthesis_text_with_periodic_report_fulltext", display_text)
            if narrative_card_items:
                ctx.set("synthesis_text_with_periodic_narrative_cards", display_text)
            if broker_digest_items:
                ctx.set("synthesis_text_with_broker_research_digest", display_text)

        return ctx

    def _build_evidence_freshness_overlay(self, ctx: SkillContext, profile: dict, external_display: dict) -> dict:
        as_of = parse_explicit_date(ctx.get("report_as_of_date")) or date.today()
        official_types = {"exchange_announcement", "company_ir", "company_official", "announcement", "official", "confirmed_fact", "periodic_report_excerpt"}
        official = list(self._eligible_periodic_report_fulltext_items(ctx))
        official.extend(item for item in (ctx.get("source_intake_items") or []) if (getattr(item, "extra", {}) or {}).get("source_type") in official_types)
        broker = ctx.get("broker_research_digest_items") or []
        broker = [item for item in (broker or []) if (getattr(item, "extra", {}) or {}).get("card_type") != "broker_risk_note"]
        return build_freshness_overlay(
            profile=str(profile.get("profile") or ""), as_of_date=as_of,
            official_items=official, broker_items=broker, external_display=external_display or {},
        )

    @staticmethod
    def _reserve_freshness_citations(baseline: dict, overlay: dict, external_display: dict) -> None:
        candidate = (overlay or {}).get("summary_candidate")
        if not candidate:
            return
        source_citations = (external_display or {}).get("citations") or {}
        citations = baseline.setdefault("citations", {})
        normalized = {}
        for key, meta in citations.items():
            try:
                normalized[citation_identity(meta, fallback_ref=int(key))] = int(key)
            except (TypeError, ValueError):
                continue
        refs = []
        for raw_ref in candidate.get("citation_refs") or []:
            meta = source_citations.get(raw_ref) or source_citations.get(str(raw_ref))
            if not isinstance(meta, dict):
                continue
            identity = citation_identity(meta, fallback_ref=raw_ref)
            ref_id = normalized.get(identity)
            if ref_id is None:
                ref_id = max((int(key) for key in citations if str(key).isdigit()), default=0) + 1
                citations[ref_id] = dict(meta)
                normalized[identity] = ref_id
            refs.append(ref_id)
        candidate["citation_refs"] = list(dict.fromkeys(refs))
        candidate["citation_identities"] = [citation_identity(citations[ref], fallback_ref=ref) for ref in candidate["citation_refs"]]
        if not candidate["citation_refs"]:
            overlay["summary_candidate"] = None
            overlay["preface"] = False

    @staticmethod
    def _select_core_facts(baseline_core_facts: list, filing_core_facts: list) -> list:
        """Prefer baseline core facts only when at least one is renderable."""
        baseline_core_facts = baseline_core_facts or []
        filing_core_facts = filing_core_facts or []
        supportable_statuses = {"supported", "partially_supported"}
        has_supportable_baseline = any(
            isinstance(fact, dict)
            and fact.get("provenance_status", "missing_ref") in supportable_statuses
            for fact in baseline_core_facts
        )
        if has_supportable_baseline or not filing_core_facts:
            return baseline_core_facts
        return filing_core_facts

    @staticmethod
    def _eligible_periodic_report_fulltext_items(ctx: SkillContext) -> list:
        """Return only legitimate periodic-report full-text material items."""
        items = ctx.get("periodic_report_fulltext_items", []) or []
        eligible = []
        for item in items:
            extra = getattr(item, "extra", {}) or {}
            if (
                extra.get("source_type") == "periodic_report_fulltext_analysis"
                and extra.get("source_credit") == 75
                and extra.get("verification_status") == "professional_analysis"
                and extra.get("claim_status") == "professional_analysis"
                and extra.get("experimental") is True
            ):
                eligible.append(item)
        return eligible

    @staticmethod
    def _eligible_periodic_narrative_card_items(ctx: SkillContext) -> list:
        """Load persisted periodic-report narrative cards as display-only items."""
        try:
            max_cards = max(
                0,
                int(ctx.get("periodic_narrative_cards_max_display_items", 12)),
            )
        except (TypeError, ValueError):
            max_cards = 12
        material_pack = ctx.get("annual_report_material_pack") or {}
        selected_cards = material_pack.get("selected_narrative_cards")
        if isinstance(selected_cards, list):
            return selected_cards_to_synthesis_items(selected_cards)[:max_cards]
        stock_name = ctx.get("stock_name")
        if not stock_name:
            return []
        base_dir = ctx.get("knowledge_base_dir")
        if not base_dir:
            base_dir = Path(__file__).resolve().parents[3] / "knowledge"
        try:
            return load_periodic_narrative_card_synthesis_items(
                stock_name=stock_name,
                stock_code=str((ctx.get("stock_codes") or {}).get(stock_name) or "").strip(),
                base_dir=base_dir,
                max_cards=max_cards,
                use_pack=True,
            )
        except PeriodicNarrativePackStorageError:
            raise
        except Exception:
            return []

    @staticmethod
    def _eligible_broker_research_digest_items(ctx: SkillContext) -> list:
        """Load persisted broker-research digest notes as display-only items."""
        stock_name = ctx.get("stock_name")
        if not stock_name:
            return []
        base_dir = ctx.get("knowledge_base_dir")
        if not base_dir:
            base_dir = Path(__file__).resolve().parents[3] / "knowledge"
        max_items = ctx.get("broker_research_digest_max_display_items", 8)
        try:
            max_items = int(max_items)
        except (TypeError, ValueError):
            max_items = 8
        try:
            return load_broker_research_digest_synthesis_items(
                stock_name=stock_name,
                base_dir=base_dir,
                max_items=max_items,
            )
        except Exception:
            return []

    @staticmethod
    def _refresh_broker_research_digest_notes(ctx: SkillContext) -> None:
        """Generate/update broker digest notes from local PDF cache before reading them."""
        if not ctx.get("include_broker_research_digest_in_synthesis_display"):
            return
        stock_name = str(ctx.get("stock_name") or "").strip()
        if not stock_name:
            return
        manifest_path = SynthesisSkill._broker_research_manifest_path(ctx)
        if manifest_path is None:
            ctx.set("broker_research_digest_note_refresh", {"status": "missing_manifest"})
            return
        stock_code = str((ctx.get("stock_codes") or {}).get(stock_name) or "").strip()
        base_dir = ctx.get("knowledge_base_dir") or Path(__file__).resolve().parents[3] / "knowledge"
        status = refresh_broker_research_digest_card_notes_from_manifest(
            stock_name=stock_name,
            stock_code=stock_code,
            manifest_path=manifest_path,
            base_dir=base_dir,
            max_pdfs=SynthesisSkill._int_ctx(ctx, "broker_research_digest_max_source_pdfs", 8),
            max_cards_per_pdf=SynthesisSkill._int_ctx(ctx, "broker_research_digest_max_cards_per_pdf", 5),
            collected_at=str(ctx.get("collected_at") or ""),
        )
        ctx.set("broker_research_digest_note_refresh", status)

    @staticmethod
    def _broker_research_manifest_path(ctx: SkillContext) -> Path | None:
        stock_name = str(ctx.get("stock_name") or "").strip()
        stock_code = str((ctx.get("stock_codes") or {}).get(stock_name) or "").strip()
        root = ctx.get("broker_research_cache_root")
        cache_root = Path(root) if root else Path(__file__).resolve().parents[3] / "data" / "raw" / "broker_research_reports"
        candidates: List[Path] = []
        if stock_name and stock_code:
            candidates.append(cache_root / f"{stock_name}_{stock_code}" / "manifest.json")
        if stock_name:
            candidates.append(cache_root / stock_name / "manifest.json")
            candidates.extend(sorted(cache_root.glob(f"{stock_name}_*/manifest.json")))
        return next((path for path in candidates if path.exists()), None)

    @staticmethod
    def _int_ctx(ctx: SkillContext, key: str, default: int) -> int:
        try:
            return int(ctx.get(key, default))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _build_material_coverage_diagnostics(ctx: SkillContext) -> Dict[str, Any]:
        """Return lightweight source-layer coverage diagnostics for chapter 4.

        This is audit-only metadata. It is not used for routing, scoring,
        target price, risk score, or recommendation wording.
        """
        annual_pack = ctx.get("annual_report_material_pack") or {}
        annual_diag = annual_pack.get("diagnostics") or {}
        formal = ctx.get("chapter4_formal_material_diagnostics") or {}
        raw_broker = SynthesisSkill._broker_raw_report_coverage(ctx)
        digest_notes = SynthesisSkill._broker_digest_note_coverage(ctx)
        loader_max_items = SynthesisSkill._broker_digest_loader_max_items(ctx)
        memo_institutions = formal.get("broker_institutions") or []
        uncovered_raw_institutions = [
            name for name in raw_broker["institutions"]
            if name not in memo_institutions
        ]
        raw_without_digest_note_institutions = [
            name for name in raw_broker["institutions"]
            if name not in digest_notes["institutions"]
        ]

        deep_display = ctx.get("deep_analysis_display") or {}
        argument_cards = deep_display.get("_curated_external_argument_cards") or []
        return {
            "schema": "deep_analysis_material_coverage.v1",
            "annual": {
                "memo_status": formal.get("annual_status", "absent"),
                "narrative_cards_seen": int(annual_diag.get("cards_seen") or 0),
                "narrative_cards_selected": int(annual_diag.get("cards_selected") or 0),
                "by_type_seen": annual_diag.get("by_type_seen") or {},
                "by_type_selected": annual_diag.get("by_type_selected") or {},
                "confirmed_row_count": int(formal.get("annual_confirmed_row_count") or 0),
                "explanation_row_count": int(formal.get("annual_explanation_row_count") or 0),
                "memo_row_count": int(formal.get("annual_confirmed_row_count") or 0) + int(formal.get("annual_explanation_row_count") or 0),
                "validation_warning_count": int(formal.get("annual_warning_count") or 0),
            },
            "broker": {
                "memo_status": formal.get("broker_status", "absent"),
                "raw_manifest_status": raw_broker["status"],
                "raw_report_count": raw_broker["report_count"],
                "raw_institution_count": len(raw_broker["institutions"]),
                "raw_institutions": raw_broker["institutions"],
                "digest_note_count": digest_notes["note_count"],
                "digest_note_institution_count": len(digest_notes["institutions"]),
                "digest_note_institutions": digest_notes["institutions"],
                "raw_without_digest_note_institutions": raw_without_digest_note_institutions,
                "note_to_raw_gap_count": len(raw_without_digest_note_institutions),
                "loader_max_items": loader_max_items,
                "loader_budget_limited": digest_notes["note_count"] > loader_max_items,
                "uncovered_raw_institutions": uncovered_raw_institutions,
                "digest_item_count": int(formal.get("broker_input_item_count") or formal.get("broker_usable_card_count") or 0),
                "memo_usable_card_count": int(formal.get("broker_usable_card_count") or 0),
                "memo_row_count": int(formal.get("broker_usable_card_count") or 0) if formal.get("broker_status") in {"ready", "single_institution"} else 0,
                "memo_institution_count": len(memo_institutions),
                "memo_institutions": memo_institutions,
                "content_families": formal.get("broker_content_families") or [],
            },
            "external": {
                "citation_source_count": len(deep_display.get("citations") or {}),
                "argument_card_count": len(argument_cards),
                "argument_coverage_families": sorted({
                    str(family) for card in argument_cards
                    for family in card.get("coverage_families") or []
                }),
                "status": ctx.get("curated_external_argument_pack_status") or "absent",
            },
        }

    @staticmethod
    def _broker_digest_loader_max_items(ctx: SkillContext) -> int:
        try:
            return int(ctx.get("broker_research_digest_max_display_items", 8))
        except (TypeError, ValueError):
            return 8

    @staticmethod
    def _broker_digest_note_coverage(ctx: SkillContext) -> Dict[str, Any]:
        stock_name = str(ctx.get("stock_name") or "").strip()
        if not stock_name:
            return {"status": "missing_stock", "note_count": 0, "institutions": []}
        base_dir = ctx.get("knowledge_base_dir") or Path(__file__).resolve().parents[3] / "knowledge"
        notes_dir = (
            Path(base_dir)
            / "10-Stocks"
            / SynthesisSkill._safe_dir_segment(stock_name)
            / "broker_research_digest"
        )
        if not notes_dir.exists():
            return {"status": "missing", "note_count": 0, "institutions": []}

        institutions: List[str] = []
        note_count = 0
        for path in sorted(notes_dir.glob("*.md")):
            note_count += 1
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            match = re.search(r"(?m)^institution:\s*[\"']?([^\"'\n]+)", text)
            institution = match.group(1).strip() if match else ""
            if institution and institution not in institutions:
                institutions.append(institution)
        return {"status": "ok", "note_count": note_count, "institutions": sorted(institutions)}

    @staticmethod
    def _safe_dir_segment(value: str) -> str:
        cleaned = re.sub(r"[\\/:\*\?\"<>\|\r\n\t]+", "_", str(value or "")).strip(" ._")
        return cleaned or "unknown"

    @staticmethod
    def _broker_raw_report_coverage(ctx: SkillContext) -> Dict[str, Any]:
        manifest_path = SynthesisSkill._broker_research_manifest_path(ctx)
        if manifest_path is None:
            return {"status": "missing", "report_count": 0, "institutions": []}
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {"status": "unreadable", "report_count": 0, "institutions": []}
        reports = payload.get("reports") if isinstance(payload, dict) else []
        if not isinstance(reports, list):
            reports = []
        institutions: List[str] = []
        for report in reports:
            if not isinstance(report, dict):
                continue
            institution = str(report.get("institution") or report.get("orgName") or "").strip()
            if institution and institution not in institutions:
                institutions.append(institution)
        return {"status": "ok", "report_count": len(reports), "institutions": institutions}

    def _build_curated_external_deep_analysis_display(self, ctx: SkillContext) -> None:
        """Project the persisted canonical argument pack into the external display."""
        pack_enabled = bool(
            ctx.get("include_curated_external_argument_pack_in_deep_analysis_display")
            or getattr(self, "include_curated_external_argument_pack_in_deep_analysis_display", False)
        )
        if not pack_enabled:
            return
        pack_json = ctx.get("curated_external_argument_pack_json") or getattr(
            self, "curated_external_argument_pack_json", ""
        )
        result = build_curated_external_argument_display(
            pack_json, expected_stock_name=str(ctx.get("stock_name") or "").strip(),
        )
        for suffix in ("status", "stats", "lint"):
            value = result.get(suffix)
            if value is not None:
                ctx.set(f"curated_external_argument_pack_{suffix}", value)
        if result.get("status") == "ok":
            display = result.get("display") or {}
            ctx.set("deep_analysis_display", display)
            ctx.set("deep_analysis_display_sources", display.get("_sources", []))
            ctx.set("synthesis_text_with_curated_external_argument_pack", result.get("synthesis_text") or "")
            metric_pack = ctx.get("periodic_report_metric_series_pack")
            scan_pack = ctx.get("periodic_report_financial_scan_pack")
            if metric_pack and scan_pack:
                stock_name = str(ctx.get("stock_name") or "").strip()
                ctx.set("periodic_external_evidence_map", build_periodic_external_evidence_map(
                    stock_code=str((ctx.get("stock_codes") or {}).get(stock_name) or "").strip(),
                    stock_name=stock_name,
                    metric_series_pack=metric_pack,
                    financial_scan_pack=scan_pack,
                    validated_external_display=display,
                ))

    @staticmethod
    def _build_evidence_profile(ctx: SkillContext, items: list) -> dict:
        """Deterministic evidence profile used to route Chapter 4 layout."""
        stock_name = ctx.get("stock_name", "")
        stock_config = ctx.get("stock_config") or {}
        fact_pack = ctx.get("formal_financial_fact_pack") or {}
        explanation_pack = ctx.get("periodic_report_explanation_pack") or {}
        fundflow_pack = ctx.get("fundflow_material_pack") or {}
        deep_display = ctx.get("deep_analysis_display") or {}
        peer_material = ctx.get("peer_comparison_material") or {}

        canonical_items = [it for it in items if is_canonical_synthesis_source(it)]

        def _dedupe_items(seq: list) -> list:
            seen: set = set()
            result: list = []
            for it in seq:
                extra = getattr(it, "extra", {}) or {}
                key = (it.source_platform, it.title, it.url)
                if key in seen:
                    continue
                seen.add(key)
                result.append(it)
            return result

        industry_items = _dedupe_items(
            KnowledgeSynthesizer._filter_items_for_theme("industry_logic", canonical_items, stock_name, stock_config)
        )
        fundamentals_items = _dedupe_items(
            KnowledgeSynthesizer._filter_items_for_theme("fundamentals", canonical_items, stock_name, stock_config)
        )
        funding_items = _dedupe_items(
            [it for it in canonical_items if KnowledgeSynthesizer._is_funding_sentiment_item(it)]
        )
        events_items = _dedupe_items(
            KnowledgeSynthesizer._filter_items_for_theme("events_catalysts", canonical_items, stock_name, stock_config)
        )

        has_fundflow_pack = bool(fundflow_pack.get("rows"))
        section_support = {
            "industry": len(industry_items),
            "fundamentals": len(fundamentals_items),
            "funding_support": len(funding_items) if (funding_items or has_fundflow_pack) else 0,
            "catalyst_support": len(events_items),
        }

        useful_fact_metrics = {
            "营业收入", "归母净利润", "净利润", "毛利率", "经营现金流", "经营现金流量净额",
            "订单", "客户", "产能", "产量", "价格", "交付", "交期", "库存", "存货",
            "供需", "采购", "备货", "供应商", "指引", "费用率", "研发费用", "销售费用",
            "管理费用", "产品", "产品线", "收入", "成本", "毛利", "营收", "净利",
        }
        useless_fact_metrics = {"年报发布", "年度报告发布", "业绩预告披露", "预告披露", "分红实施", "权益分派"}

        formal_insight_facts = 0
        for fact in (fact_pack.get("facts") or []):
            if not isinstance(fact, dict):
                continue
            metric = str(fact.get("metric") or "")
            if any(m in metric for m in useless_fact_metrics):
                continue
            if any(m in metric for m in useful_fact_metrics):
                formal_insight_facts += 1

        argument_cards = deep_display.get("_curated_external_argument_cards") or []
        citations = deep_display.get("citations", {}) or {}
        pack_active = ctx.get("curated_external_argument_pack_status") == "ok"
        external_topics = external_claims = 0
        if pack_active:
            target_cards = [
                card for card in argument_cards
                if str(card.get("entity_scope") or "").startswith("target")
            ]
            external_topics = len({
                family for card in target_cards
                for family in card.get("coverage_families") or []
                if family != "other"
            })
            external_claims = len({str(card.get("argument_key") or i) for i, card in enumerate(argument_cards)})
        external_sources = len(citations)
        distinct_authors = len({
            (str(m.get("source") or ""), str(m.get("author") or ""))
            for m in citations.values() if isinstance(m, dict)
        })
        single_source = external_sources == 1 and external_topics >= 3 if pack_active else False

        has_any_formal = any(section_support.values())
        has_any_item = bool(items)
        external_rich = pack_active and external_topics >= 3
        formal = ctx.get("chapter4_formal_material_diagnostics") or {}
        annual_ready = formal.get("annual_status") == "ready"
        broker_usable = int(formal.get("broker_usable_card_count") or 0)
        reasons: List[str] = []
        if formal_insight_facts >= 5 and section_support["industry"] >= 2 and section_support["fundamentals"] >= 2:
            profile = "formal_rich"
            reasons.append("formal_support_sufficient")
        elif pack_active and annual_ready and broker_usable > 0:
            profile = "formal_medium"
            reasons.append("annual_and_broker_material_ready")
        elif pack_active and annual_ready and external_rich and formal_insight_facts < 5:
            profile = "formal_thin_external_rich"
            reasons.append("formal_thin_external_rich")
            if single_source:
                reasons.append("single_source_external_rich")
        elif pack_active:
            profile = "formal_medium" if (has_any_formal or annual_ready or broker_usable) else "thin_all"
            reasons.append("formal_support_partial" if profile == "formal_medium" else "material_insufficient")
        elif has_any_formal or has_any_item:
            profile = "formal_medium"
            reasons.append("formal_support_partial")
        else:
            profile = "thin_all"
            reasons.append("material_insufficient")

        legacy_profile = profile in {"formal_rich", "formal_medium"}
        section_decisions = {
            "industry": "legacy" if (legacy_profile and section_support["industry"] >= 2) else ("formal_summary" if profile == "formal_thin_external_rich" else "skipped"),
            "fundamentals": "legacy" if (legacy_profile and section_support["fundamentals"] >= 2) else ("formal_summary" if profile == "formal_thin_external_rich" else "skipped"),
            "funding": "legacy" if (legacy_profile and section_support["funding_support"] >= 1) else ("fallback" if section_support["catalyst_support"] >= 1 else "skipped"),
            "catalysts": "timeline" if section_support["catalyst_support"] >= 1 else ("fallback" if legacy_profile else "skipped"),
        }

        return {
            "profile": profile,
            "formal_insight_facts": formal_insight_facts,
            "formal_section_support": section_support,
            "external_viewpoint_topics": external_topics,
            "external_usable_claims": external_claims,
            "external_source_count": external_sources,
            "external_distinct_author_count": distinct_authors,
            "single_source_external_rich": single_source,
            "external_signal_count": 0,
            "section_decisions": section_decisions,
            "reasons": reasons,
            "annual_memo_status": formal.get("annual_status", "absent"),
            "broker_memo_status": formal.get("broker_status", "absent"),
            "broker_single_institution": formal.get("broker_status") == "single_institution",
            "broker_usable_card_count": broker_usable,
            "broker_content_families": formal.get("broker_content_families", []),
            "broker_institution_count": len(formal.get("broker_institutions") or []),
            "memo_refs_resolved": bool(formal.get("formal_citation_candidate_count")),
            "formal_thin_layout_variant": (
                "annual_broker_external_checklist" if profile == "formal_thin_external_rich" else None
            ),
        }

    def _synthesize(
        self,
        stock_name: str,
        stock_raw: dict,
        keep_posts: list,
        ctx: SkillContext = None,
        extra_items: list = None,
        items: list = None,
        deduped_sources_key: str = "synthesis_display_deduped_sources",
    ) -> dict:
        """调用 KnowledgeSynthesizer 或降级模板生成综合叙事。"""
        llm_enabled = bool(ctx.get("report_llm_enabled", True)) if ctx is not None else True
        source_policy = self._canonical_synthesis_source_policy(ctx)
        enable_cv = bool(ctx.get("enable_claim_verification_context")) if ctx else False
        cv_context = None
        cv_status = None
        cv_error = ""

        if enable_cv:
            try:
                cv_status, cv_context, cv_error = self._build_claim_verification_context(stock_name, ctx)
            except Exception as exc:
                cv_status = "error"
                cv_context = None
                cv_error = f"claim verification build failed: {exc}"

        if ctx is not None:
            ctx.set("claim_verification_status", cv_status)
            ctx.set("claim_verification_error", cv_error)
            if cv_context:
                ctx.set("claim_verification_summary", cv_context)

        if llm_enabled and self.llm_client and hasattr(self.llm_client, "chat"):
            return self._legacy_llm_synthesize(stock_name, stock_raw, keep_posts, cv_context)

        fundflow_material_pack = build_fundflow_material_pack(stock_raw.get("fundflow", []))
        if fundflow_material_pack.get("rows") and ctx is not None:
            ctx.set("fundflow_material_pack", fundflow_material_pack)

        if items is None:
            items = self._build_synthesis_items(stock_raw, keep_posts, ctx=ctx, extra_items=extra_items)
            if extra_items:
                items, deduped_sources = dedupe_synthesis_display_items(items)
                if ctx is not None:
                    ctx.set(deduped_sources_key, deduped_sources)
        if not items:
            if ctx is not None and source_policy == "formal_first":
                ctx.set("formal_first_sources_insufficient", True)
            return self._template_synthesize(
                stock_raw,
                items_count=0,
                sources=[],
                source_policy=source_policy,
            )

        if not llm_enabled:
            return self._template_synthesize(
                stock_raw,
                items_count=len(items),
                sources=self._source_list(items),
                source_policy=source_policy,
            )

        synthesizer = self.synthesizer or KnowledgeSynthesizer(client=self.llm_client)
        all_data = {"items": items}
        if ctx and ctx.get("stock_config"):
            all_data["stock_config"] = ctx.get("stock_config")
        if ctx:
            financial_fact_pack = self._build_formal_financial_fact_pack(
                ctx.get("periodic_report_filing_core_facts", [])
            )
            if financial_fact_pack.get("facts"):
                ctx.set("formal_financial_fact_pack", financial_fact_pack)
                all_data["formal_financial_fact_pack"] = financial_fact_pack
            financial_explanation_pack = ctx.get("periodic_report_explanation_pack") or {}
            if isinstance(financial_explanation_pack, dict) and financial_explanation_pack.get("rows"):
                all_data["formal_financial_explanation_pack"] = financial_explanation_pack
        if cv_context:
            all_data["claim_verification_context"] = cv_context
        if ctx and ctx.get("peer_comparison_material"):
            all_data["peer_comparison_material"] = ctx.get("peer_comparison_material")
        if fundflow_material_pack.get("rows"):
            all_data["fundflow_material_pack"] = fundflow_material_pack
        result = synthesizer.synthesize(stock_name, all_data)
        result = self._fill_citation_metadata(result, items)
        result = self._enrich_core_fact_provenance(result)
        if ctx:
            result = self._enrich_peer_comparison_fact_provenance(
                result,
                ctx.get("peer_comparison_material"),
            )
        if ctx:
            fact_pack = ctx.get("formal_financial_fact_pack") or all_data.get("formal_financial_fact_pack") or {}
            result = self._sanitize_financial_missing_contradictions(result, fact_pack)
            result = self._sanitize_financial_direction_contradictions(result, fact_pack)
        result = self._sanitize_indirect_industry_citations_from_43(result, stock_name)

        if not any(result.get(k) for k in SYNTHESIS_KEYS):
            return self._template_synthesize(
                stock_raw,
                items_count=len(items),
                sources=self._source_list(items),
                source_policy=source_policy,
            )

        result["_items_count"] = len(items)
        result["_sources"] = self._source_list(items)
        result["_industry_relevance_manifest"] = build_industry_relevance_manifest(items)
        return result

    @staticmethod
    def _build_formal_financial_fact_pack(filing_core_facts: list) -> dict:
        """Build a compact formal financial pack for 4.2 prompts only."""
        facts = []
        for fact in filing_core_facts or []:
            if not isinstance(fact, dict):
                continue
            metric = str(fact.get("fact") or "")
            value = str(fact.get("data") or "")
            if not metric or not value:
                continue
            if metric not in {"营业收入", "归母净利润", "经营现金流量净额"}:
                continue
            if not SynthesisSkill._is_reliable_financial_value(value):
                continue
            source_labels = fact.get("source_labels") or []
            source = "、".join(str(label) for label in source_labels if label)
            facts.append({
                "metric": metric,
                "value": value,
                "period": source,
                "source": fact.get("evidence_type") or "periodic_report_filing_fact",
            })
        return {
            "schema": "formal_financial_fact_pack.v1",
            "facts": facts,
        }

    @staticmethod
    def _sanitize_financial_missing_contradictions(result: dict, fact_pack: dict) -> dict:
        """Remove LLM claims that revenue/profit are missing when formal facts exist."""
        available_parts = SynthesisSkill._available_financial_parts(fact_pack, result)
        if not available_parts:
            return result

        text = str(result.get("fundamentals") or "")
        if not text:
            return result

        missing_pattern = re.compile(
            r"[^。；\n]*(?:未提供[^。；\n]*(?:营收|营业收入|利润|净利润)|"
            r"(?:营收|营业收入|利润|净利润)[^。；\n]*未提供)[^。；\n]*[。；]?"
        )
        if not missing_pattern.search(text):
            return result

        replacement = (
            "正式财务事实包显示，"
            + "，".join(available_parts)
            + "；订单、客户、费用率或指引等未在正式事实包中出现的指标仍需等待后续公告。"
        )
        result = dict(result)
        result["fundamentals"] = missing_pattern.sub(replacement, text, count=1).strip()
        return result

    @staticmethod
    def _sanitize_financial_direction_contradictions(result: dict, fact_pack: dict) -> dict:
        """Align annual net-profit wording with deterministic formal financial facts."""
        replacement = SynthesisSkill._annual_net_profit_decline_replacement(fact_pack)
        if not replacement:
            return result

        sanitized = dict(result)
        for key in ("industry_logic", "fundamentals", "valuation_debate"):
            text = str(sanitized.get(key) or "")
            if text:
                sanitized[key] = SynthesisSkill._replace_false_annual_profit_growth(text, replacement)

        core_facts = []
        changed = False
        for fact in sanitized.get("core_facts") or []:
            if not isinstance(fact, dict):
                core_facts.append(fact)
                continue
            fact_blob = f"{fact.get('fact', '')} {fact.get('data', '')}"
            if SynthesisSkill._has_false_annual_profit_growth(fact_blob):
                changed = True
                continue
            core_facts.append(fact)
        if changed:
            sanitized["core_facts"] = core_facts
        return sanitized

    @staticmethod
    def _annual_net_profit_decline_replacement(fact_pack: dict) -> str:
        for fact in ((fact_pack or {}).get("facts") or []):
            if not isinstance(fact, dict):
                continue
            metric = str(fact.get("metric") or "")
            value = str(fact.get("value") or "").strip()
            if "净利润" not in metric or not value:
                continue
            if SynthesisSkill._is_net_profit_decline_value(value):
                return f"正式财务口径显示归母净利润{value}"
        return ""

    @staticmethod
    def _is_net_profit_decline_value(value: Any) -> bool:
        text = str(value or "").replace("－", "-").replace("—", "-")
        return bool(re.search(r"(?:同比)?(?:下降|下滑|减少)|-\d+(?:\.\d+)?%", text))

    @staticmethod
    def _replace_false_annual_profit_growth(text: str, replacement: str) -> str:
        cleaned = str(text or "")
        table_title_replacement = "估值溢价需等待盈利修复验证"
        for pattern in (
            r"(?:2025年)?年报显示利润随营收增长[，,、]?\s*营收扩张是利润增长主因",
            r"(?:2025年)?年报显示利润随营收增长",
            r"营收扩张是利润增长主因",
        ):
            cleaned = re.sub(pattern, replacement, cleaned)
        for pattern in (
            r"(?:公司)?2025年(?:归母净利润|归母净利|净利润|净利|利润)[^。；\n|]{0,16}同比增速显著",
            r"(?:公司)?2025年(?:归母净利润|归母净利|净利润|净利|利润)同比大幅增长",
            r"(?:公司)?2025年(?:归母净利润|归母净利|净利润|净利|利润)同比增长",
            r"2025年[^。；\n|]{0,16}利润高增",
        ):
            cleaned = re.sub(pattern, replacement, cleaned)
        for pattern in (
            r"高成长性应享有高估值溢价",
            r"高成长性支撑估值溢价",
        ):
            cleaned = re.sub(pattern, table_title_replacement, cleaned)
        return cleaned

    @staticmethod
    def _has_false_annual_profit_growth(text: str) -> bool:
        return bool(
            re.search(
                r"(?:公司)?2025年(?:归母净利润|归母净利|净利润|净利|利润)[^。；\n|]{0,16}同比增速显著|"
                r"(?:公司)?2025年(?:归母净利润|归母净利|净利润|净利|利润)同比(?:大幅)?增长|"
                r"2025年[^。；\n|]{0,16}利润高增|"
                r"(?:2025年)?年报显示利润随营收增长|"
                r"营收扩张是利润增长主因",
                str(text or ""),
            )
        )

    @staticmethod
    def _available_financial_parts(fact_pack: dict, result: dict) -> list:
        """Return reliable revenue/profit snippets for missing-data sanitization."""
        facts = {
            str(fact.get("metric") or ""): str(fact.get("value") or "")
            for fact in ((fact_pack or {}).get("facts") or [])
            if isinstance(fact, dict) and SynthesisSkill._is_reliable_financial_value(fact.get("value"))
        }
        available_parts = []
        if facts.get("营业收入"):
            available_parts.append(f"营业收入{facts['营业收入']}")
        if facts.get("归母净利润"):
            available_parts.append(f"归母净利润{facts['归母净利润']}")
        if available_parts:
            return available_parts

        fallback_parts = []
        seen_metrics = set()
        for fact in (result.get("core_facts") or []):
            if not isinstance(fact, dict):
                continue
            status = str(fact.get("provenance_status") or "supported")
            confidence = str(fact.get("confidence") or "")
            if status in {"invalid_ref", "unsupported"}:
                continue
            if status == "missing_ref" and confidence not in {"高", "high", "High"}:
                continue
            label = str(fact.get("fact") or "").strip()
            value = SynthesisSkill._brief_financial_value(fact.get("data"))
            if not label or not value or not SynthesisSkill._is_reliable_financial_value(value):
                continue
            if ("营收" in label or "营业收入" in label) and "revenue" not in seen_metrics:
                fallback_parts.append(f"{label}{value}")
                seen_metrics.add("revenue")
            elif "归母净利润" in label and "profit" not in seen_metrics:
                fallback_parts.append(f"{label}{value}")
                seen_metrics.add("profit")
        return fallback_parts

    @staticmethod
    def _brief_financial_value(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return re.split(r"[，,；;。]", text, maxsplit=1)[0].strip()

    @staticmethod
    def _is_reliable_financial_value(value: Any) -> bool:
        text = str(value or "").strip().replace(",", "")
        if not text:
            return False
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return False
        try:
            return abs(float(match.group(0))) > 1e-9
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _sanitize_indirect_industry_citations_from_43(result: dict, stock_name: str) -> dict:
        """Remove indirect industry/news citations from 4.3 synthesis text."""
        bad_refs = SynthesisSkill._indirect_industry_ref_ids(result.get("citations") or {}, stock_name)
        if not bad_refs:
            return result

        changed = False
        sanitized = dict(result)
        for key in ("funding_sentiment", "events_catalysts"):
            text = str(result.get(key) or "")
            if not text:
                continue
            cleaned = SynthesisSkill._drop_lines_with_refs(text, bad_refs)
            if cleaned != text:
                sanitized[key] = cleaned
                changed = True
        return sanitized if changed else result

    @staticmethod
    def _indirect_industry_ref_ids(citations: dict, stock_name: str) -> set:
        stock_text = str(stock_name or "").strip()
        bad_refs = set()
        for raw_ref, meta in (citations or {}).items():
            if not isinstance(meta, dict):
                continue
            source = str(meta.get("source") or "").strip()
            source_type = str(meta.get("source_type") or "").strip()
            title = str(meta.get("title") or "").strip()
            direct_company = bool(stock_text and stock_text in title)
            is_industry_or_news = (
                source in {"行业资讯", "新闻", "行业研报"}
                or source_type in {"mainstream_media", "industry_research"}
            )
            if is_industry_or_news and not direct_company:
                try:
                    bad_refs.add(int(raw_ref))
                except (TypeError, ValueError):
                    continue
        return bad_refs

    @staticmethod
    def _drop_lines_with_refs(text: str, bad_refs: set) -> str:
        bad_markers = {f"[^{ref}]" for ref in bad_refs}
        kept = []
        for line in str(text or "").splitlines():
            if any(marker in line for marker in bad_markers):
                continue
            kept.append(line)
        return "\n".join(kept).strip()

    def _build_claim_verification_context(
        self, stock_name: str, ctx: SkillContext
    ):
        """Build sanitized claim verification context. Returns (status, context, error)."""
        try:
            from claim_verification import (
                build_claim_verification_plan,
                summarize_claim_verification_plan,
            )
        except Exception as exc:
            return "error", None, f"failed to import claim verification: {exc}"

        base_dir = ctx.get("claim_verification_base_dir")
        if not base_dir:
            base_dir = Path(__file__).resolve().parents[3] / "knowledge"
        max_verified = ctx.get("claim_verification_max_verified", 6)
        max_supported = ctx.get("claim_verification_max_supported", 4)
        max_unverified = ctx.get("claim_verification_max_unverified", 4)

        try:
            plan = build_claim_verification_plan(stock_name, str(base_dir), dry_run=True)
            summary = summarize_claim_verification_plan(
                plan,
                max_verified=int(max_verified),
                max_supported=int(max_supported),
                max_unverified=int(max_unverified),
            )
        except Exception as exc:
            return "error", None, f"claim verification build failed: {exc}"

        counts = summary.get("counts", {})
        total_usable = (
            counts.get("verified", 0)
            + counts.get("supported", 0)
            + counts.get("unverified", 0)
            + counts.get("needs_review", 0)
        )
        if total_usable == 0 and counts.get("high_credit_claims", 0) == 0:
            return "empty", None, ""

        return "ok", summary, ""

    def _legacy_llm_synthesize(self, stock_name: str, stock_raw: dict, keep_posts: list, cv_context: Dict = None) -> dict:
        """兼容旧测试/调用方：使用 chat(prompt) 的简化 LLM 客户端。"""
        prompt = self._build_prompt(stock_name, stock_raw, keep_posts, cv_context)
        try:
            response = self.llm_client.chat(prompt)
            if isinstance(response, dict):
                response.setdefault("core_facts", [])
                response.setdefault("citations", {})
                response["_legacy_prompt"] = prompt
                return response
            return self._template_synthesize(stock_raw)
        except Exception:
            return self._template_synthesize(stock_raw)

    @staticmethod
    def _eligible_external_baseline_items(ctx: SkillContext = None) -> list:
        """Return canonical external evidence items allowed into baseline synthesis."""
        if ctx is None:
            return []
        eligible = []
        for item in ctx.get("external_evidence_keep_items", []) or []:
            extra = getattr(item, "extra", {}) or {}
            if extra.get("synthesis_display_only") is True:
                continue
            if not is_canonical_synthesis_source(item):
                continue
            if not (extra.get("knowledge_eligible") or extra.get("report_eligible")):
                continue
            eligible.append(item)
        return eligible

    def _build_synthesis_items(self, stock_raw: dict, keep_posts: list, ctx: SkillContext = None, extra_items: list = None):
        zhihu = stock_raw.get("zhihu", {})
        source_policy = self._canonical_synthesis_source_policy(ctx)
        fundflow_material_pack = ctx.get("fundflow_material_pack") if ctx else None
        fundflow = (
            stock_raw.get("fundflow", [])
            if (fundflow_material_pack and fundflow_material_pack.get("rows"))
            else []
        )
        items = adapt_all(
            xueqiu_items=keep_posts,
            zhihu_items=zhihu.get("report_items", []),
            reports=stock_raw.get("reports", []),
            announcements=stock_raw.get("announcements", []),
            fundflow=fundflow,
            news=stock_raw.get("news", []),
        )
        if source_policy == "formal_first":
            items = [item for item in items if is_canonical_synthesis_source(item)]
        baseline_external_items = self._eligible_external_baseline_items(ctx)
        if baseline_external_items:
            items = list(items) + baseline_external_items
        # Extra material-layer items (e.g. periodic-report full text) are
        # appended LAST so ordinary source numbering stays stable.
        if extra_items:
            extras = list(extra_items)
            if source_policy == "formal_first":
                extras = [item for item in extras if is_formal_display_source(item)]
            items = list(items) + extras
        return items

    def _canonical_synthesis_source_policy(self, ctx: SkillContext = None) -> str:
        raw_policy = None
        if ctx is not None:
            raw_policy = ctx.get("canonical_synthesis_source_policy")
        if not raw_policy:
            raw_policy = getattr(self, "canonical_synthesis_source_policy", "legacy_mixed")
        policy = str(raw_policy or "legacy_mixed").strip()
        if policy == "formal_first":
            return "formal_first"
        return "legacy_mixed"

    def _fill_citation_metadata(self, synthesis: dict, items: list) -> dict:
        citations = synthesis.get("citations", {}) or {}
        filled = {}
        for raw_ref_id, meta in citations.items():
            try:
                ref_id = int(raw_ref_id)
            except (TypeError, ValueError):
                ref_id = raw_ref_id

            item = items[ref_id - 1] if isinstance(ref_id, int) and 1 <= ref_id <= len(items) else None
            if item is None:
                filled[ref_id] = meta
                continue

            extra = item.extra or {}
            filled[ref_id] = {
                "source": item.source_platform,
                "author": item.author,
                "title": item.title,
                "url": item.url,
                "date": item.publish_time,
                "interaction_score": item.interaction_score,
                "source_credit": extra.get("source_credit"),
                "source_type": extra.get("source_type"),
                "verification_status": extra.get("verification_status"),
            }
            # Forward curated external traceability fields when present.
            for trace_key in (
                "card_id",
                "source_ref",
                "source_excerpt_hash",
                "source_block_hash",
                "topic",
                "synthesis_display_only",
                "quality_action",
                "scoring_eligible",
                "risk_score_eligible",
            ):
                if trace_key in extra:
                    filled[ref_id][trace_key] = extra[trace_key]
        synthesis["citations"] = filled
        return synthesis

    def _enrich_core_fact_provenance(self, synthesis: dict) -> dict:
        """Deterministically enrich core_facts with source labels, evidence type, and provenance status.

        Uses existing citation metadata; does not call LLM or add new data sources.
        Only high-credit official/announcement/exchange sources can support core facts;
        news/research/community/AgentReach/fundflow sources are rejected by the hard filter.
        """
        core_facts = synthesis.get("core_facts", []) or []
        if not core_facts:
            return synthesis

        citations = synthesis.get("citations", {}) or {}
        # Build an int-keyed lookup from possibly string-keyed citations
        citation_lookup = {}
        for raw_key, meta in citations.items():
            try:
                int_key = int(raw_key)
            except (TypeError, ValueError):
                int_key = raw_key
            citation_lookup[int_key] = meta

        for fact in core_facts:
            raw_refs = fact.get("source_refs", []) or []
            refs = []
            for r in raw_refs:
                if isinstance(r, bool):
                    continue
                if isinstance(r, int):
                    r_int = r
                elif isinstance(r, str) and r.strip().isdigit():
                    r_int = int(r.strip())
                else:
                    continue
                if r_int > 0:
                    refs.append(r_int)

            accepted_labels = []
            invalid_or_excluded = False
            seen_labels = set()

            for ref in refs:
                meta = citation_lookup.get(ref)
                if not meta or not isinstance(meta, dict):
                    invalid_or_excluded = True
                    continue

                source = str(meta.get("source", "")).strip()
                if not source:
                    invalid_or_excluded = True
                    continue

                # Deterministic hard filter: only allowed sources support core facts.
                if not is_core_fact_supporting_source(source, meta):
                    invalid_or_excluded = True
                    continue

                family = self._normalize_source_family(source)
                if family not in seen_labels:
                    seen_labels.add(family)
                    if len(accepted_labels) < 2:
                        accepted_labels.append(family)

            fact["source_labels"] = accepted_labels
            fact["evidence_type"] = self._derive_evidence_type(accepted_labels)
            fact["provenance_status"] = self._derive_provenance_status(refs, accepted_labels, invalid_or_excluded)

        return synthesis

    @staticmethod
    def _normalize_source_family(source: str) -> str:
        """Map fine-grained source_platform values to stable source families."""
        s = source.strip()
        lower = s.lower()

        if "知乎" in s:
            return "知乎"
        if lower in ("xueqiu", "雪球"):
            return "雪球"
        if "研报" in s or lower == "research_report":
            return "研报"
        if "公告" in s or lower == "announcement":
            return "公告"
        if "资金流向" in s or lower == "fundflow":
            return "资金流向"
        if "新闻" in s or lower == "news":
            return "新闻"
        return s

    @staticmethod
    def _derive_evidence_type(labels: list) -> str:
        if not labels:
            return "unknown"

        families = set(labels)
        if len(families) > 1:
            return "mixed"

        label = labels[0]
        if label == "公告":
            return "announcement"
        if label == "研报":
            return "research_report"
        if label in ("雪球", "知乎"):
            return "community"
        if label == "新闻":
            return "news"
        if label == "资金流向":
            return "fundflow"
        return "unknown"

    @staticmethod
    def _derive_provenance_status(refs: list, accepted_labels: list, invalid_or_excluded: bool) -> str:
        if not refs:
            return "missing_ref"
        if accepted_labels:
            if invalid_or_excluded:
                return "partially_supported"
            return "supported"
        return "invalid_ref"

    @staticmethod
    def _enrich_peer_comparison_fact_provenance(synthesis: dict, peer_material: dict | None) -> dict:
        """Mark peer-comparison core facts as structured metric evidence.

        These facts are generated from deterministic ``peer_comparison_material``
        rather than numbered citation refs.  They should not render as unknown,
        but they also should not be mislabeled as official announcements.
        """
        if not peer_material or not isinstance(peer_material, dict):
            return synthesis
        rows = peer_material.get("rows") or []
        if not rows:
            return synthesis

        for fact in synthesis.get("core_facts", []) or []:
            if not isinstance(fact, dict):
                continue
            status = str(fact.get("provenance_status") or "")
            if status not in {"missing_ref", "invalid_ref"}:
                continue
            if not SynthesisSkill._matches_peer_comparison_row(fact, rows):
                continue
            fact["source_labels"] = ["结构化同行估值数据"]
            fact["evidence_type"] = "peer_comparison_metric"
            fact["provenance_status"] = "supported"
        return synthesis

    @staticmethod
    def _matches_peer_comparison_row(fact: dict, rows: list) -> bool:
        blob = f"{fact.get('fact', '')} {fact.get('data', '')}"
        blob = re.sub(r"\s+", "", str(blob))
        if not blob:
            return False

        metric_labels = {
            "gross_margin": ("毛利率",),
            "pe_ttm": ("PE(TTM)", "PETTM"),
            "forward_pe": ("ForwardPE",),
            "ps": ("PS(市销率)", "PS", "市销率"),
            "mcap": ("总市值", "市值"),
        }
        for row in rows:
            if not isinstance(row, dict):
                continue
            peer = re.sub(r"\s+", "", str(row.get("peer") or ""))
            metric = str(row.get("metric") or "")
            labels = metric_labels.get(metric, ())
            if not peer or not labels:
                continue
            if peer in blob and any(label in blob for label in labels):
                return True
        return False

    @staticmethod
    def _source_list(items: list) -> List[str]:
        return sorted({item.source_platform for item in items if item.source_platform})

    @staticmethod
    def _empty_baseline_synthesis(stock_raw: dict, items: list, source_policy: str = "legacy_mixed", formal_first_insufficient: bool = False) -> dict:
        if formal_first_insufficient:
            return SynthesisSkill._template_synthesize(
                stock_raw,
                items_count=len(items),
                sources=SynthesisSkill._source_list(items),
                source_policy=source_policy,
            )
        return {
            "industry_logic": "",
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "core_facts": [],
            "citations": {},
            "_items_count": len(items),
            "_sources": SynthesisSkill._source_list(items),
            "_source_policy": source_policy,
        }

    def _build_prompt(self, stock_name: str, stock_raw: dict, keep_posts: list, cv_context: Dict = None) -> str:
        """构建 LLM prompt（legacy chat 路径，复用现代路径的信用规则）。"""
        tech = stock_raw.get("technical", {})
        reports = stock_raw.get("reports", [])
        anns = stock_raw.get("announcements", [])
        zhihu = stock_raw.get("zhihu", {}).get("report_items", [])

        prompt = f"""请基于以下数据，为股票「{stock_name}」生成综合分析：

技术面指标：{tech.get("indicators", {})}
最新研报数量：{len(reports)}
最新公告数量：{len(anns)}
知乎相关文章数量：{len(zhihu)}
高质量社区帖子数量：{len(keep_posts)}

{credit_usage_rules_text()}

请按以下 JSON 格式返回：
{{
  "industry_logic": "行业逻辑分析（100字以内）",
  "fundamentals": "基本面分析（100字以内）",
  "valuation_debate": "估值多空辩论（100字以内）",
  "funding_sentiment": "资金情绪分析（100字以内）",
  "events_catalysts": "事件催化分析（100字以内）"
}}
"""
        if cv_context:
            appendix = self._format_claim_verification_appendix(cv_context)
            if appendix:
                prompt += "\n\n---\n\n" + appendix
        return prompt

    def _format_claim_verification_appendix(self, context: Dict) -> str:
        """Render guarded non-citable appendix for legacy prompt."""
        return format_claim_verification_appendix(context, is_legacy=True)

    @staticmethod
    def _template_synthesize(
        stock_raw: dict,
        items_count: int = 0,
        sources: List[str] = None,
        source_policy: str = "legacy_mixed",
    ) -> dict:
        """无 LLM 时的降级模板，只描述可验证状态，不生成伪基本面结论。"""
        tech = stock_raw.get("technical", {})
        indicators = tech.get("indicators", {})
        resonance = indicators.get("_resonance", {})
        score = resonance.get("composite_score", 5)
        sources = sources or []
        source_text = "、".join(sources) if sources else "无可用多源内容"
        formal_sources_insufficient = source_policy == "formal_first" and items_count == 0

        if score >= 7:
            trend = "整体偏多"
        elif score <= 3:
            trend = "整体偏空"
        else:
            trend = "震荡整理"

        if formal_sources_insufficient:
            return {
                "industry_logic": (
                    f"formal_first 模式下正式材料不足：当前可用于 4.1-4.3 的公告、研报、年报或"
                    f"主流新闻不足；仅保留技术面降级摘要，技术面综合评分 {score}，{trend}。"
                ),
                "fundamentals": (
                    "formal_first 已排除非正式材料；在正式来源补足前，"
                    "不生成完整基本面叙事。"
                ),
                "valuation_debate": "估值多空分歧需等待可引用的正式材料补足后再展开。",
                "funding_sentiment": "资金面与情绪仅保留原始数据，未生成推断性叙事。",
                "events_catalysts": "事件催化仅保留原始公告/新闻线索，未生成推断性叙事。",
                "core_facts": [],
                "citations": {},
                "_items_count": items_count,
                "_sources": sources,
                "_source_policy": source_policy,
                "_formal_first_sources_insufficient": True,
            }

        return {
            "industry_logic": f"当前仅完成技术面降级摘要：技术面综合评分 {score}，{trend}。",
            "fundamentals": f"基本面 LLM 合成未启用或未产生有效输出；已收集 {items_count} 条候选内容，来源：{source_text}。",
            "valuation_debate": "估值多空分歧需等待可引用的研报、公告、新闻或高质量社区内容完成合成后再展开。",
            "funding_sentiment": "资金面与情绪仅保留原始数据，未生成推断性叙事。",
            "events_catalysts": "事件催化仅保留原始公告/新闻线索，未生成推断性叙事。",
            "core_facts": [],
            "citations": {},
            "_items_count": items_count,
            "_sources": sources,
            "_source_policy": source_policy,
        }
