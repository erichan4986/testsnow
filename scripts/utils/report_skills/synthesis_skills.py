"""LLM synthesis skill."""

import json
from pathlib import Path
from typing import Any, Dict, List

if __name__.startswith("utils."):
    from ..skill_pipeline import BaseSkill, SkillContext
    from ..knowledge_synthesizer import KnowledgeSynthesizer
    from ..source_adapter import adapt_all
    from ..synthesis_credit import (
        credit_usage_rules_text,
        derive_synthesis_usage,
        format_synthesis_source_line,
        is_core_fact_supporting_source,
        format_claim_verification_appendix,
    )
    from ..periodic_report_narrative_card_synthesis_items import (
        load_periodic_narrative_card_synthesis_items,
    )
    from ..broker_research_digest_synthesis_items import (
        load_broker_research_digest_synthesis_items,
    )
    from ..synthesis_display_deduper import dedupe_synthesis_display_items
    from ..curated_external_evidence_card_synthesis_items import (
        load_curated_external_evidence_card_synthesis_items,
    )
    from ..curated_external_display_lint import lint_curated_external_display_text
else:
    from skill_pipeline import BaseSkill, SkillContext
    from knowledge_synthesizer import KnowledgeSynthesizer
    from source_adapter import adapt_all
    from synthesis_credit import (
        credit_usage_rules_text,
        derive_synthesis_usage,
        format_synthesis_source_line,
        is_core_fact_supporting_source,
        format_claim_verification_appendix,
    )
    from periodic_report_narrative_card_synthesis_items import (
        load_periodic_narrative_card_synthesis_items,
    )
    from broker_research_digest_synthesis_items import (
        load_broker_research_digest_synthesis_items,
    )
    from synthesis_display_deduper import dedupe_synthesis_display_items
    from curated_external_evidence_card_synthesis_items import (
        load_curated_external_evidence_card_synthesis_items,
    )
    from curated_external_display_lint import lint_curated_external_display_text


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

        baseline = self._synthesize(stock_name, stock_raw, keep_posts, ctx)
        ctx.set("synthesis", baseline)
        core_facts = self._select_core_facts(
            baseline.get("core_facts", []),
            ctx.get("periodic_report_filing_core_facts", []),
        )
        ctx.set("core_facts", core_facts)
        ctx.set("synthesis_text", self._flatten_synthesis_text(baseline))
        ctx.set("synthesis_items_count", baseline.get("_items_count", 0))
        ctx.set("synthesis_sources", baseline.get("_sources", []))

        # Optional experimental paths: annual-report materials and broker-research
        # digest notes may enter the DISPLAY synthesis only.  Canonical synthesis,
        # core_facts, synthesis_text, and synthesis_sources stay baseline so risk
        # scoring and Knowledge persistence never see display-only material.
        display_items = []
        fulltext_items = []
        narrative_card_items = []
        broker_digest_items = []
        if ctx.get("include_periodic_report_fulltext_in_synthesis"):
            fulltext_items = self._eligible_periodic_report_fulltext_items(ctx)
            display_items.extend(fulltext_items)
        if ctx.get("include_periodic_narrative_cards_in_synthesis_display"):
            narrative_card_items = self._eligible_periodic_narrative_card_items(ctx)
            display_items.extend(narrative_card_items)
        if ctx.get("include_broker_research_digest_in_synthesis_display"):
            broker_digest_items = self._eligible_broker_research_digest_items(ctx)
            display_items.extend(broker_digest_items)
        if display_items:
            display = self._synthesize(
                stock_name,
                stock_raw,
                keep_posts,
                ctx,
                extra_items=display_items,
            )
            display_text = self._flatten_synthesis_text(display)
            ctx.set("synthesis_display", display)
            ctx.set("synthesis_display_sources", display.get("_sources", []))
            ctx.set("synthesis_text_with_periodic_display_materials", display_text)
            if fulltext_items:
                ctx.set("synthesis_text_with_periodic_report_fulltext", display_text)
            if narrative_card_items:
                ctx.set("synthesis_text_with_periodic_narrative_cards", display_text)
            if broker_digest_items:
                ctx.set("synthesis_text_with_broker_research_digest", display_text)

        # Curated external materials: separate deep-analysis-only display paths.
        # These branches intentionally do not reuse ctx["synthesis_display"].
        self._build_viewpoint_narrative_deep_analysis_display(ctx)
        if not ctx.get("deep_analysis_display"):
            self._build_viewpoint_digest_deep_analysis_display(ctx)
        if not ctx.get("deep_analysis_display"):
            self._build_deep_analysis_display(ctx)

        return ctx

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
        stock_name = ctx.get("stock_name")
        if not stock_name:
            return []
        base_dir = ctx.get("knowledge_base_dir")
        if not base_dir:
            base_dir = Path(__file__).resolve().parents[3] / "knowledge"
        max_cards = ctx.get("periodic_narrative_cards_max_display_items", 12)
        try:
            max_cards = int(max_cards)
        except (TypeError, ValueError):
            max_cards = 12
        try:
            return load_periodic_narrative_card_synthesis_items(
                stock_name=stock_name,
                base_dir=base_dir,
                max_cards=max_cards,
                use_pack=True,
                per_type_limit=3,
            )
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
        max_items = ctx.get("broker_research_digest_max_display_items", 5)
        try:
            max_items = int(max_items)
        except (TypeError, ValueError):
            max_items = 5
        try:
            return load_broker_research_digest_synthesis_items(
                stock_name=stock_name,
                base_dir=base_dir,
                max_items=max_items,
            )
        except Exception:
            return []

    def _build_deep_analysis_display(self, ctx: SkillContext) -> None:
        """Build a deep-analysis-only display synthesis from curated external cards.

        On success this writes ctx["deep_analysis_display"] (and related keys).
        On failure or insufficient material it writes status/stats explaining why
        and leaves canonical synthesis keys unchanged.
        """
        enabled = bool(
            ctx.get("include_curated_external_evidence_cards_in_synthesis_display")
            or getattr(self, "include_curated_external_evidence_cards_in_synthesis_display", False)
        )
        if not enabled:
            return

        cards_json = ctx.get("curated_external_evidence_cards_json") or getattr(
            self, "curated_external_evidence_cards_json", ""
        )
        if not cards_json:
            ctx.set("curated_external_evidence_cards_status", "missing_config")
            ctx.set("curated_external_evidence_cards_stats", {"rejection_reasons": ["curated_external_evidence_cards_json not set"]})
            return

        max_items = ctx.get("curated_external_evidence_cards_max_display_items")
        if max_items is None:
            max_items = getattr(self, "curated_external_evidence_cards_max_display_items", 8)
        min_cards = ctx.get("curated_external_evidence_cards_min_cards")
        if min_cards is None:
            min_cards = getattr(self, "curated_external_evidence_cards_min_cards", 3)
        min_total = ctx.get("curated_external_evidence_cards_min_total_excerpt_chars")
        if min_total is None:
            min_total = getattr(self, "curated_external_evidence_cards_min_total_excerpt_chars", 1200)

        try:
            curated_items, stats = load_curated_external_evidence_card_synthesis_items(
                cards_json,
                max_items=int(max_items),
                min_cards=int(min_cards),
                min_total_excerpt_chars=int(min_total),
            )
        except Exception as exc:
            ctx.set("curated_external_evidence_cards_status", "reader_error")
            ctx.set("curated_external_evidence_cards_stats", {"rejection_reasons": [str(exc)]})
            return

        ctx.set("curated_external_evidence_cards_status", stats.get("status"))
        ctx.set("curated_external_evidence_cards_stats", stats)

        if not curated_items:
            return

        stock_name = ctx.get("stock_name")
        stock_raw = ctx.get("stock_raw", {})
        keep_posts = ctx.get("keep_posts", [])

        # Curated external display is intentionally display-only.  When no custom
        # synthesizer or LLM client is supplied, skip the LLM entirely and render
        # a deterministic, citation-aware observation block.  This avoids curated
        # external materials being rewritten into strong claims that would fail
        # the display lint.
        if self.llm_client is None and self.synthesizer is None:
            display = self._deterministic_curated_external_display(stock_name, curated_items)
        else:
            display = self._synthesize(
                stock_name,
                stock_raw,
                keep_posts,
                ctx,
                extra_items=curated_items,
                deduped_sources_key="deep_analysis_display_deduped_sources",
            )
            if self._is_template_fallback_synthesis(display):
                display = self._deterministic_curated_external_display(stock_name, curated_items)
        lint = lint_curated_external_display_text(display)
        ctx.set("curated_external_evidence_cards_lint", lint)
        if not lint.get("ok"):
            ctx.set("curated_external_evidence_cards_status", "lint_failed")
            return

        display_text = self._flatten_synthesis_text(display)
        ctx.set("deep_analysis_display", display)
        ctx.set("deep_analysis_display_sources", display.get("_sources", []))
        ctx.set("synthesis_text_with_curated_external_evidence_cards", display_text)
        ctx.set("curated_external_evidence_cards_status", "ok")

    def _build_viewpoint_narrative_deep_analysis_display(self, ctx: SkillContext) -> None:
        """Build deep-analysis-only display from cached full-body narrative JSON."""
        enabled = bool(
            ctx.get("include_curated_external_viewpoint_narrative_in_deep_analysis_display")
            or getattr(self, "include_curated_external_viewpoint_narrative_in_deep_analysis_display", False)
        )
        if not enabled:
            return

        narrative_json = ctx.get("curated_external_viewpoint_narrative_json") or getattr(
            self, "curated_external_viewpoint_narrative_json", ""
        )
        if not narrative_json:
            ctx.set("curated_external_viewpoint_narrative_status", "missing_config")
            ctx.set(
                "curated_external_viewpoint_narrative_stats",
                {"rejection_reasons": ["curated_external_viewpoint_narrative_json not set"]},
            )
            return

        try:
            narrative = json.loads(Path(narrative_json).read_text(encoding="utf-8"))
        except Exception as exc:
            ctx.set("curated_external_viewpoint_narrative_status", "reader_error")
            ctx.set("curated_external_viewpoint_narrative_stats", {"rejection_reasons": [str(exc)]})
            return

        status = str(narrative.get("status") or "")
        ctx.set("curated_external_viewpoint_narrative_status", status)
        ctx.set("curated_external_viewpoint_narrative_stats", narrative.get("stats") or {})
        if status != "ok":
            return

        paragraphs = [p for p in narrative.get("paragraphs") or [] if isinstance(p, dict)]
        citations = self._normalize_viewpoint_narrative_citations(narrative.get("citations") or {})
        if not paragraphs or not citations:
            ctx.set("curated_external_viewpoint_narrative_status", "empty")
            return

        display = {
            "industry_logic": self._flatten_viewpoint_narrative_paragraphs(paragraphs),
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "core_facts": [],
            "citations": citations,
            "_curated_external_narrative": True,
            "_curated_external_narrative_paragraphs": paragraphs,
            "_items_count": len(paragraphs),
            "_sources": list(citations.values()),
        }
        lint = lint_curated_external_display_text(display)
        ctx.set("curated_external_viewpoint_narrative_lint", lint)
        if not lint.get("ok"):
            ctx.set("curated_external_viewpoint_narrative_status", "lint_failed")
            return

        ctx.set("deep_analysis_display", display)
        ctx.set("deep_analysis_display_sources", display.get("_sources", []))
        ctx.set("synthesis_text_with_curated_external_viewpoint_narrative", self._flatten_synthesis_text(display))
        ctx.set("curated_external_viewpoint_narrative_status", "ok")

    @staticmethod
    def _normalize_viewpoint_narrative_citations(citations: Dict[Any, Any]) -> Dict[int, dict]:
        normalized = {}
        for key, value in (citations or {}).items():
            try:
                ref_id = int(key)
            except (TypeError, ValueError):
                continue
            if not isinstance(value, dict):
                continue
            if (
                value.get("source_type") == "curated_external_analysis_evidence"
                and value.get("verification_status") == "professional_observation"
            ):
                normalized[ref_id] = value
        return normalized

    @classmethod
    def _flatten_viewpoint_narrative_paragraphs(cls, paragraphs: list) -> str:
        parts = []
        for paragraph in paragraphs:
            heading = str(paragraph.get("heading") or "").strip()
            text = str(paragraph.get("text") or "").strip()
            refs = paragraph.get("citation_refs") or []
            rendered = cls._attach_refs_to_sentence(text, refs)
            if heading:
                parts.append(f"{heading}：{rendered}")
            elif rendered:
                parts.append(rendered)
        return "\n\n".join(parts)

    @staticmethod
    def _attach_refs_to_sentence(text: str, refs: list) -> str:
        ref_text = "".join(f"[^{int(ref)}]" for ref in refs if str(ref).isdigit())
        stripped = str(text or "").strip()
        if not ref_text:
            return stripped
        if stripped.endswith(("。", "；", ";", "！", "？")):
            return f"{stripped[:-1]}{ref_text}{stripped[-1]}"
        return f"{stripped}{ref_text}"

    def _build_viewpoint_digest_deep_analysis_display(self, ctx: SkillContext) -> None:
        """Build deep-analysis-only display from cached full-body viewpoint digest."""
        enabled = bool(
            ctx.get("include_curated_external_viewpoint_digest_in_deep_analysis_display")
            or getattr(self, "include_curated_external_viewpoint_digest_in_deep_analysis_display", False)
        )
        if not enabled:
            return

        digest_json = ctx.get("curated_external_viewpoint_digest_json") or getattr(
            self, "curated_external_viewpoint_digest_json", ""
        )
        if not digest_json:
            ctx.set("curated_external_viewpoint_digest_status", "missing_config")
            ctx.set("curated_external_viewpoint_digest_stats", {"rejection_reasons": ["curated_external_viewpoint_digest_json not set"]})
            return

        try:
            digest = json.loads(Path(digest_json).read_text(encoding="utf-8"))
        except Exception as exc:
            ctx.set("curated_external_viewpoint_digest_status", "reader_error")
            ctx.set("curated_external_viewpoint_digest_stats", {"rejection_reasons": [str(exc)]})
            return

        status = str(digest.get("status") or "")
        ctx.set("curated_external_viewpoint_digest_status", status)
        ctx.set("curated_external_viewpoint_digest_stats", digest.get("stats") or {})
        if status != "ok":
            return

        claims = [
            claim for claim in (digest.get("claims") or [])
            if self._is_safe_curated_external_viewpoint_claim(claim)
        ]
        if not claims:
            ctx.set("curated_external_viewpoint_digest_status", "empty")
            return

        claims = self._dedupe_viewpoint_digest_claims_for_display(claims)
        display = self._deterministic_viewpoint_digest_display(ctx.get("stock_name"), claims)
        lint = lint_curated_external_display_text(display)
        ctx.set("curated_external_viewpoint_digest_lint", lint)
        if not lint.get("ok"):
            ctx.set("curated_external_viewpoint_digest_status", "lint_failed")
            return

        ctx.set("deep_analysis_display", display)
        ctx.set("deep_analysis_display_sources", display.get("_sources", []))
        ctx.set("synthesis_text_with_curated_external_viewpoint_digest", self._flatten_synthesis_text(display))
        ctx.set("curated_external_viewpoint_digest_status", "ok")

    @staticmethod
    def _is_safe_curated_external_viewpoint_claim(claim: Dict[str, Any]) -> bool:
        if not isinstance(claim, dict):
            return False
        return (
            claim.get("schema_version") == "curated_external_viewpoint_claim.v1"
            and claim.get("quality_action") == "preview_only"
            and claim.get("knowledge_eligible") is False
            and claim.get("synthesis_display_only") is True
            and claim.get("scoring_eligible") is False
            and claim.get("risk_score_eligible") is False
            and claim.get("verification_status") == "professional_observation"
            and str(claim.get("source_quote") or "").strip()
            and str(claim.get("source_quote_hash") or "").strip()
        )

    def _deterministic_viewpoint_digest_display(self, stock_name: str, claims: list) -> dict:
        grouped = {
            "industry_logic": [],
            "fundamentals": [],
            "valuation_debate": [],
            "funding_sentiment": [],
            "events_catalysts": [],
        }
        citations = {}

        for ref_id, claim in enumerate(claims, start=1):
            line = self._format_viewpoint_digest_observation(claim, ref_id)
            bucket = self._viewpoint_digest_bucket(claim)
            grouped[bucket].append(line)
            citations[ref_id] = self._viewpoint_digest_citation(claim)

        return {
            "industry_logic": self._join_curated_external_observations(
                stock_name,
                "产业链、竞争格局或技术路径增量观点",
                grouped["industry_logic"],
            ),
            "fundamentals": self._join_curated_external_observations(
                stock_name,
                "业绩质量、周期或供需变量",
                grouped["fundamentals"],
            ),
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": self._join_curated_external_observations(
                stock_name,
                "事件、政策或待验证变量",
                grouped["events_catalysts"],
            ),
            "core_facts": [],
            "citations": citations,
            "_items_count": len(claims),
            "_sources": list(citations.values()),
        }

    @classmethod
    def _dedupe_viewpoint_digest_claims_for_display(cls, claims: list) -> list:
        """Collapse obvious same-theme repeats while keeping the full digest auditable."""
        deduped = []
        seen = set()
        for claim in claims:
            key = cls._viewpoint_digest_semantic_key(claim)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(claim)
        return deduped

    @staticmethod
    def _viewpoint_digest_semantic_key(claim: Dict[str, Any]) -> str:
        text = " ".join(
            str(claim.get(field) or "")
            for field in ("topic", "claim", "source_quote", "why_incremental")
        )
        lower_text = text.lower()

        if "800g" in lower_text and any(token in text for token in ("1500万", "1200万", "交付计划", "交付下调", "传言")):
            return "800g_delivery_rumor"
        if any(token in text for token in ("预付款", "物料", "原材料", "磷化铟", "光芯片", "供应链")):
            return "material_supply_tightness"
        if "cpo" in lower_text and any(token in text for token in ("可插拔", "Scale Out", "scale out", "替代")):
            return "cpo_vs_pluggable"
        if any(token in text for token in ("NPO", "XPO", "Scale Up", "scale up", "光进铜退")):
            return "npo_xpo_timeline"
        if any(token in text for token in ("2026", "2027", "2028")) and any(
            token in text for token in ("需求指引", "客户需求", "资本开支", "capex", "CapEx")
        ):
            return "customer_demand_capex_guide"

        fingerprint_source = str(claim.get("source_quote_hash") or claim.get("claim_id") or claim.get("claim") or "")
        return f"claim:{fingerprint_source[:32]}"

    @staticmethod
    def _viewpoint_digest_bucket(claim: Dict[str, Any]) -> str:
        topic = str(claim.get("topic") or "")
        claim_type = str(claim.get("claim_type") or "")
        if any(token in topic for token in ("earnings", "fundamentals", "supply", "capacity", "prepayment")):
            return "fundamentals"
        if claim_type in ("dissent", "watch_variable"):
            return "events_catalysts"
        return "industry_logic"

    @staticmethod
    def _format_viewpoint_digest_observation(claim: Dict[str, Any], ref_id: int) -> str:
        title = " ".join(str(claim.get("source_title") or claim.get("title") or "外部观点").split())[:80]
        claim_text = str(claim.get("claim") or "").strip().rstrip("。")
        why = str(claim.get("why_incremental") or "").strip().rstrip("。")
        suffix = f"（{why}）" if why else ""
        return f"《{title}》观察到：{claim_text}{suffix}[^{ref_id}]"

    @staticmethod
    def _viewpoint_digest_citation(claim: Dict[str, Any]) -> dict:
        return {
            "source": "微信公众号精选观察",
            "author": claim.get("source_account") or claim.get("account") or "",
            "title": claim.get("source_title") or claim.get("title") or "外部观点",
            "url": claim.get("source_ref") or claim.get("url") or "",
            "source_type": "curated_external_analysis_evidence",
            "source_credit": claim.get("source_credit", 55),
            "verification_status": claim.get("verification_status", "professional_observation"),
            "claim_id": claim.get("claim_id", ""),
            "source_quote_hash": claim.get("source_quote_hash", ""),
        }

    @staticmethod
    def _is_template_fallback_synthesis(synthesis: dict) -> bool:
        """Detect the generic non-LLM template so curated cards can still render."""
        if not isinstance(synthesis, dict):
            return True
        if synthesis.get("citations"):
            return False
        text = "\n".join(str(synthesis.get(key, "")) for key in SYNTHESIS_KEYS)
        return "LLM 合成未启用或未产生有效输出" in text

    def _deterministic_curated_external_display(self, stock_name: str, items: list) -> dict:
        """Build a cited, display-only deep-analysis fallback without calling an LLM."""
        grouped = {
            "industry_logic": [],
            "fundamentals": [],
            "valuation_debate": [],
            "funding_sentiment": [],
            "events_catalysts": [],
        }
        citations = {}

        for ref_id, item in enumerate(items, start=1):
            topic = (item.extra or {}).get("topic") or ""
            line = self._format_curated_external_observation(item, ref_id)
            if topic == "industry_logic":
                grouped["industry_logic"].append(line)
            elif topic in ("earnings_context", "cycle_price", "capital_market_context"):
                grouped["fundamentals"].append(line)
            elif topic in ("commercialization", "certification_policy"):
                grouped["events_catalysts"].append(line)
            else:
                grouped["events_catalysts"].append(line)
            citations[ref_id] = {"_placeholder": True}

        fallback = {
            "industry_logic": self._join_curated_external_observations(
                stock_name,
                "产业逻辑相关线索",
                grouped["industry_logic"],
            ),
            "fundamentals": self._join_curated_external_observations(
                stock_name,
                "业绩、周期或资本市场相关线索",
                grouped["fundamentals"],
            ),
            "valuation_debate": "精选外部材料仅作为专业观察，不直接形成估值结论；估值仍应回到官方财务、市场价格和评分模型。",
            "funding_sentiment": "精选外部材料不直接生成资金面判断，资金面仍以交易数据、资金流和市场指标为准。",
            "events_catalysts": self._join_curated_external_observations(
                stock_name,
                "商业化、认证、政策或事件跟踪线索",
                grouped["events_catalysts"],
            ),
            "core_facts": [],
            "citations": citations,
            "_items_count": len(items),
            "_sources": self._source_list(items),
        }
        return self._fill_citation_metadata(fallback, items)

    @staticmethod
    def _format_curated_external_observation(item, ref_id: int) -> str:
        title = " ".join(str(item.title or "未命名材料").split())[:80]
        content = str(item.content or "")
        excerpt = content.split("\n\n", 1)[-1] if "\n\n" in content else content
        excerpt = SynthesisSkill._truncate_observation_excerpt(" ".join(excerpt.split()), 220)
        if excerpt:
            return f"《{title}》观察到：{excerpt}[^{ref_id}]"
        return f"《{title}》提供了一条外部观察线索[^{ref_id}]"

    @staticmethod
    def _truncate_observation_excerpt(text: str, max_chars: int) -> str:
        text = str(text or "").strip()
        if len(text) <= max_chars:
            return text
        window = text[:max_chars]
        for marker in ("。", "；", ";", "，", ","):
            pos = window.rfind(marker)
            if pos >= 80:
                return window[: pos + 1].rstrip()
        return window.rstrip() + "..."

    @staticmethod
    def _join_curated_external_observations(stock_name: str, label: str, lines: list) -> str:
        if not lines:
            return ""
        return f"精选外部材料仅作为专业观察，提示 {stock_name} 的{label}包括：" + "；".join(lines)

    def _synthesize(
        self,
        stock_name: str,
        stock_raw: dict,
        keep_posts: list,
        ctx: SkillContext = None,
        extra_items: list = None,
        deduped_sources_key: str = "synthesis_display_deduped_sources",
    ) -> dict:
        """调用 KnowledgeSynthesizer 或降级模板生成综合叙事。"""
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

        if self.llm_client and hasattr(self.llm_client, "chat"):
            return self._legacy_llm_synthesize(stock_name, stock_raw, keep_posts, cv_context)

        items = self._build_synthesis_items(stock_raw, keep_posts, extra_items=extra_items)
        if extra_items:
            items, deduped_sources = dedupe_synthesis_display_items(items)
            if ctx is not None:
                ctx.set(deduped_sources_key, deduped_sources)
        if not items:
            return self._template_synthesize(stock_raw, items_count=0, sources=[])

        synthesizer = self.synthesizer or KnowledgeSynthesizer(client=self.llm_client)
        all_data = {"items": items}
        if cv_context:
            all_data["claim_verification_context"] = cv_context
        result = synthesizer.synthesize(stock_name, all_data)
        result = self._fill_citation_metadata(result, items)
        result = self._enrich_core_fact_provenance(result)

        if not any(result.get(k) for k in SYNTHESIS_KEYS):
            return self._template_synthesize(
                stock_raw,
                items_count=len(items),
                sources=self._source_list(items),
            )

        result["_items_count"] = len(items)
        result["_sources"] = self._source_list(items)
        return result

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

    def _build_synthesis_items(self, stock_raw: dict, keep_posts: list, extra_items: list = None):
        zhihu = stock_raw.get("zhihu", {})
        items = adapt_all(
            xueqiu_items=keep_posts,
            zhihu_items=zhihu.get("report_items", []),
            reports=stock_raw.get("reports", []),
            announcements=stock_raw.get("announcements", []),
            fundflow=stock_raw.get("fundflow", []),
            news=stock_raw.get("news", []),
        )
        # Extra material-layer items (e.g. periodic-report full text) are
        # appended LAST so ordinary source numbering stays stable.
        if extra_items:
            items = list(items) + list(extra_items)
        return items

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

    def _source_list(self, items: list) -> List[str]:
        return sorted({item.source_platform for item in items if item.source_platform})

    def _flatten_synthesis_text(self, synthesis: dict) -> str:
        return "\n".join(str(synthesis.get(k, "")) for k in SYNTHESIS_KEYS if synthesis.get(k))

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

    def _template_synthesize(self, stock_raw: dict, items_count: int = 0, sources: List[str] = None) -> dict:
        """无 LLM 时的降级模板，只描述可验证状态，不生成伪基本面结论。"""
        tech = stock_raw.get("technical", {})
        indicators = tech.get("indicators", {})
        resonance = indicators.get("_resonance", {})
        score = resonance.get("composite_score", 5)
        sources = sources or []
        source_text = "、".join(sources) if sources else "无可用多源内容"

        if score >= 7:
            trend = "整体偏多"
        elif score <= 3:
            trend = "整体偏空"
        else:
            trend = "震荡整理"

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
        }
