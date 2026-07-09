"""深度分析板块渲染器。"""

import json
import re
from typing import Any, Dict, List

try:
    from ...curated_external_display import attach_refs_to_sentence, truncate_curated_source_excerpt
    from ...deep_analysis_material_snapshot import build_deep_analysis_material_snapshot
    from ...synthesis_credit import sanitize_citation_markers
    from ...synthesis_source_policy import is_external_viewpoint_source, is_formal_display_source
    from .executive_summary_renderer import _build_pe_spread_facts, _sanitize_pe_spread_in_text
except ImportError:
    try:
        from scripts.utils.curated_external_display import attach_refs_to_sentence, truncate_curated_source_excerpt
        from scripts.utils.deep_analysis_material_snapshot import build_deep_analysis_material_snapshot
        from scripts.utils.synthesis_credit import sanitize_citation_markers
        from scripts.utils.synthesis_source_policy import is_external_viewpoint_source, is_formal_display_source
        from scripts.utils.reporter.sections.executive_summary_renderer import _build_pe_spread_facts, _sanitize_pe_spread_in_text
    except ImportError:
        from utils.curated_external_display import attach_refs_to_sentence, truncate_curated_source_excerpt
        from utils.deep_analysis_material_snapshot import build_deep_analysis_material_snapshot
        from utils.synthesis_credit import sanitize_citation_markers
        from utils.synthesis_source_policy import is_external_viewpoint_source, is_formal_display_source
        from reporter.sections.executive_summary_renderer import _build_pe_spread_facts, _sanitize_pe_spread_in_text


MAX_VERIFIED_CLAIM_SUMMARY_ROWS = 6
CURATED_EXTERNAL_ADDENDUM_KEYS = [
    "industry_logic",
    "fundamentals",
    "events_catalysts",
]
CURATED_EXTERNAL_TOPIC_LABELS = [
    ("order_capacity_delivery", "订单、产能与交付节奏"),
    ("technology_route", "产业链与技术路线分歧"),
    ("financial_quality", "业绩质量与财务可持续性争议"),
    ("competition_commercialization", "竞争格局与商业化窗口"),
    ("market_expectation", "资本市场预期与情绪温度"),
    ("risk_rumor_rebuttal", "风险传言与反证线索"),
    ("other", "其他待验证观察"),
]
_CNINFO_PDF_TITLE_MAP: Dict[str, str] = {
    "1225145344": "2026年第一季度报告",
    "1225106812": "2026年第一季度业绩预告",
    "1225102392": "补缴税款及滞纳金事项公告",
    "1225362219": "2025年年度权益分派实施公告",
}


class DeepAnalysisRenderer:
    """深度分析板块 — 核心事实基座 + 产业逻辑/业绩路径/资金面 + 引用来源。"""

    @staticmethod
    def required_keys() -> List[str]:
        return ["stock_name", "synthesis"]

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        if not stock_name:
            return ""

        profile = ctx.get("deep_analysis_evidence_profile") or {"profile": "formal_rich"}
        profile_name = profile.get("profile", "formal_rich")

        deep_analysis_display = ctx.get("deep_analysis_display") or {}
        uses_curated_external_display = self._has_curated_external_citation(deep_analysis_display)

        # For formal-rich, preserve existing display-priority logic.
        # For thin layouts, use the baseline synthesis (often empty) and external map.
        if profile_name == "formal_rich":
            if (
                deep_analysis_display
                and not uses_curated_external_display
                and self._is_main_analysis_display_allowed(deep_analysis_display)
            ):
                synthesis = deep_analysis_display
                curated_display = {}
            else:
                synthesis_display = ctx.get("synthesis_display") or {}
                if synthesis_display and self._is_main_analysis_display_allowed(synthesis_display):
                    synthesis = synthesis_display
                else:
                    synthesis = ctx.get("synthesis") or {}
                curated_display = deep_analysis_display
        else:
            synthesis = ctx.get("synthesis") or {}
            curated_display = deep_analysis_display if uses_curated_external_display else {}

        if not synthesis:
            return ""

        core_facts = ctx.get("core_facts", [])
        lines = []

        # 核心事实基座
        core_facts_md = self._core_facts_table(core_facts, profile=profile)
        if core_facts_md:
            lines.append(core_facts_md)

        # 深度分析
        uses_annual_memo_display = (
            profile_name == "formal_medium"
            or (
                profile_name == "formal_thin_external_rich"
                and profile.get("formal_thin_layout_variant") == "annual_broker_external_checklist"
            )
        )
        annual_memo = (ctx.get("annual_report_memo") or {}) if uses_annual_memo_display else {}
        baseline_citations = synthesis.get("citations", {}) or {}
        annual_citation_offset = self._max_citation_id(baseline_citations)
        broker_memo = (ctx.get("broker_research_memo") or {}) if uses_annual_memo_display else {}
        material_snapshot = self._material_snapshot(ctx, uses_annual_memo_display)
        if material_snapshot is not None:
            broker_citation_offset = annual_citation_offset + self._max_snapshot_ref(material_snapshot, {"annual"})
            external_citation_offset = annual_citation_offset + self._max_snapshot_ref(
                material_snapshot,
                {"annual", "broker"},
            )
        else:
            annual_memo_citations = annual_memo.get("citations", {}) or {}
            broker_citation_offset = annual_citation_offset + self._max_citation_id(annual_memo_citations)
            broker_memo_citations = broker_memo.get("citations", {}) or {}
            external_citation_offset = broker_citation_offset + self._max_citation_id(broker_memo_citations)
        deep_md = self._deep_analysis(
            synthesis,
            ctx,
            profile=profile,
            curated_external_display=curated_display if profile_name == "formal_rich" else deep_analysis_display,
            curated_citation_offset=external_citation_offset,
            annual_citation_offset=annual_citation_offset,
            broker_citation_offset=broker_citation_offset,
            external_citation_offset=external_citation_offset,
        )
        pe_facts = _build_pe_spread_facts(ctx.get("peer_comparison_material"), ctx.get("stock_name", ""))
        deep_md = _sanitize_pe_spread_in_text(deep_md, pe_facts, ctx.get("stock_name", ""))
        if deep_md:
            lines.append(deep_md)

        # 全局引用：baseline → deep-analysis material snapshot.
        # Snapshot citations contain only rows that are admitted into the
        # chapter-4 material read model, avoiding stale memo citation entries.
        if material_snapshot is not None:
            citations = {self._citation_key(k): v for k, v in (baseline_citations or {}).items()}
            citations.update(self._offset_citations(material_snapshot.citations, self._max_citation_id(citations)))
        else:
            annual_memo_citations = annual_memo.get("citations", {}) or {}
            broker_memo_citations = broker_memo.get("citations", {}) or {}
            citations = self._merged_citations(
                baseline_citations,
                annual_memo_citations,
            )
            citations = self._merged_citations(
                citations,
                broker_memo_citations,
            )
            external_citations = (
                (curated_display or {}).get("citations", {}) if profile_name in {"formal_rich", "formal_medium"}
                else self._used_formal_thin_external_citations(deep_analysis_display)
            )
            citations = self._merged_citations(
                citations,
                external_citations,
            )
        citations = self._visible_citations_only(citations, "\n".join(lines))
        if citations:
            lines.append(self._citations_section("引用来源", citations))

        return "\n".join(lines)

    def _core_facts_table(self, core_facts: List[Dict], profile: Dict[str, Any] = None) -> str:
        """渲染核心事实基座表格。"""
        if not core_facts:
            return ""

        profile_name = (profile or {}).get("profile", "formal_rich")
        display_facts = self._prune_display_core_facts(core_facts, keep_all=profile_name == "formal_rich")

        # Phase 1: only facts with at least one accepted citation are shown as a
        # supportable base.  Rows that are entirely invalid_ref / missing_ref are
        # not presented as a "core facts base".
        supportable_statuses = {"supported", "partially_supported"}
        supportable_facts = [
            f for f in display_facts
            if f.get("provenance_status", "missing_ref") in supportable_statuses
        ]

        if not supportable_facts:
            return (
                "## 三、核心事实基座\n\n"
                "当前未形成可由高信用来源支撑的核心事实基座；以下深度分析仅作为多源观察，不作为确认事实。\n"
            )

        lines = [
            "## 三、核心事实基座",
            "",
            "| # | 事实 | 数据/来源 | 证据 | 置信度 |",
            "|---|---|-----------|------|--------|",
        ]
        for f in display_facts:
            fid = f.get("fact_id", "")
            fact = f.get("fact", "").replace("|", "\\|")
            data = f.get("data", "").replace("|", "\\|")
            conf = f.get("confidence", "中")
            evidence = self._render_evidence_cell(f)
            lines.append(f"| {fid} | {fact} | {data} | {evidence} | {conf} |")

        lines.extend([
            "",
            "> **说明**：后续深度分析模块不再重复展开这些数据，仅在需要支撑论点时引用编号（如“见事实#1”）。",
            "",
        ])
        return "\n".join(lines)

    @staticmethod
    def _prune_display_core_facts(core_facts: List[Dict], keep_all: bool = False) -> List[Dict]:
        """Drop document-existence / duplicate / useless facts from the visible table."""
        useless_patterns = (
            r"年报发布",
            r"年度报告",
            r"业绩预告",
            r"预告披露",
            r"分红实施",
            r"权益分派",
        )
        kept = []
        seen = set()
        for f in core_facts:
            if not isinstance(f, dict):
                continue
            fact_text = str(f.get("fact", "")).strip()
            data_text = str(f.get("data", "")).strip()
            if DeepAnalysisRenderer._is_suspicious_zero_financial_fact(f):
                continue
            if keep_all:
                kept.append(f)
                continue
            if any(re.search(p, fact_text) for p in useless_patterns):
                continue
            key = (fact_text, data_text)
            if key in seen:
                continue
            seen.add(key)
            kept.append(f)
        return kept

    @staticmethod
    def _is_suspicious_zero_financial_fact(fact: Dict[str, Any]) -> bool:
        fact_text = str(fact.get("fact") or "")
        data_text = str(fact.get("data") or "")
        if "0.00亿元" not in data_text:
            return False
        return any(term in fact_text for term in ("营收", "营业收入", "收入", "利润", "净利润", "现金流"))

    def _render_evidence_cell(self, fact: Dict) -> str:
        """Render the provenance evidence cell for a core fact row."""
        status = fact.get("provenance_status", "missing_ref")
        labels = fact.get("source_labels", []) or []
        evidence_type = fact.get("evidence_type", "unknown")

        if status == "supported":
            label_text = "、".join(labels) if labels else "未绑定引用"
            return f"{label_text} ({evidence_type})"

        if status == "partially_supported":
            label_text = "、".join(labels) if labels else "未绑定引用"
            return f"{label_text} ({evidence_type}, 部分引用无效)"

        if status == "invalid_ref":
            return "引用无效 (unknown)"

        # missing_ref or default
        return "未绑定引用 (unknown)"

    def _deep_analysis(
        self,
        synthesis: Dict[str, str],
        ctx: Dict[str, Any],
        profile: Dict[str, Any] = None,
        curated_external_display: Dict[str, Any] | None = None,
        curated_citation_offset: int = 0,
        annual_citation_offset: int = 0,
        broker_citation_offset: int = 0,
        external_citation_offset: int = 0,
    ) -> str:
        """
        深度分析板块：根据 evidence profile 渲染不同布局。
        """
        profile = profile or {"profile": "formal_rich"}
        profile_name = profile.get("profile", "formal_rich")
        badge = self._profile_badge(profile_name)
        profile_json = json.dumps(profile, ensure_ascii=False)
        lines = ["## 四、深度分析", "", f"<!-- deep_analysis_profile: {profile_json} -->", "", f"> {badge}", ""]

        if profile_name == "formal_rich":
            lines.extend(self._legacy_deep_analysis_body(
                synthesis, ctx.get("claim_verification_summary"),
                curated_external_display=curated_external_display,
                curated_citation_offset=curated_citation_offset,
            ))
        elif profile_name == "formal_medium":
            lines.extend(self._formal_medium_source_layer_body(
                ctx,
                curated_external_display,
                annual_citation_offset=annual_citation_offset,
                broker_citation_offset=broker_citation_offset,
                external_citation_offset=external_citation_offset,
            ))
        elif profile_name == "formal_thin_external_rich":
            lines.extend(self._formal_thin_external_rich_body(
                ctx, curated_external_display,
                annual_citation_offset=annual_citation_offset,
                broker_citation_offset=broker_citation_offset,
                external_citation_offset=external_citation_offset,
            ))
        else:
            lines.extend(self._thin_all_body(ctx))

        return "\n".join(lines)

    @staticmethod
    def _profile_badge(profile_name: str) -> str:
        if profile_name == "formal_rich":
            return "深度分析形态：正式材料丰富"
        if profile_name == "formal_medium":
            return "深度分析形态：正式材料中等"
        if profile_name == "formal_thin_external_rich":
            return "深度分析形态：正式材料薄但外部观点丰富"
        return "深度分析形态：材料不足"

    def _legacy_deep_analysis_body(
        self,
        synthesis: Dict[str, str],
        claim_verification_summary: Any = None,
        curated_external_display: Dict[str, Any] | None = None,
        curated_citation_offset: int = 0,
    ) -> List[str]:
        """
        原有深度分析板块：合并原5个合成板块为3个子板块。
        4.1 产业逻辑与竞争格局
        4.2 业绩路径与多空分歧
        4.3 资金面与催化剂时间线
        """
        citations = synthesis.get("citations", {})
        lines: List[str] = []

        verified_summary = self._verified_claim_summary_section(claim_verification_summary)
        if verified_summary:
            lines.append(verified_summary)
            lines.append("")

        # 4.1 产业逻辑与竞争格局
        industry_logic = synthesis.get("industry_logic", "")
        lines.extend([
            "### 4.1 产业逻辑与竞争格局",
            "",
            industry_logic
            or "当前正式材料不足以形成可验证的产业逻辑与竞争格局判断；本节不使用泛行业材料补链条。",
            "",
        ])
        used_refs = set(int(m) for m in re.findall(r"\[\^(\d+)\]", industry_logic))
        self._append_section_citations(lines, used_refs, citations)

        # 4.2 业绩路径与多空分歧
        fundamentals = synthesis.get("fundamentals", "")
        valuation_debate = synthesis.get("valuation_debate", "")
        lines.extend([
            "### 4.2 业绩路径与多空分歧",
            "",
        ])
        if fundamentals:
            lines.append(fundamentals)
            lines.append("")
        if valuation_debate:
            lines.append(valuation_debate)
            lines.append("")
        if not fundamentals and not valuation_debate:
            lines.append("当前正式材料不足以形成可验证的业绩路径或估值分歧判断；本节不使用外部观点补充财务结论。")
            lines.append("")

        used_refs = set()
        used_refs.update(int(m) for m in re.findall(r"\[\^(\d+)\]", fundamentals))
        used_refs.update(int(m) for m in re.findall(r"\[\^(\d+)\]", valuation_debate))
        self._append_section_citations(lines, used_refs, citations)

        # 4.3 资金面与催化剂时间线
        funding = synthesis.get("funding_sentiment", "")
        events = synthesis.get("events_catalysts", "")
        lines.extend([
            "### 4.3 资金面与催化剂时间线",
            "",
        ])
        if funding:
            lines.append(funding)
            lines.append("")
        if events:
            lines.append(events)
            lines.append("")
        if funding and not events:
            lines.append("当前正式材料未形成可验证的催化剂时间线。")
            lines.append("")
        elif events and not funding:
            lines.append("当前正式材料未提供足够资金面数据。")
            lines.append("")
        elif not funding and not events:
            lines.append("当前正式材料未形成可验证的资金面或催化剂时间线；本节不使用泛行业新闻补链条。")
            lines.append("")

        used_refs = set()
        used_refs.update(int(m) for m in re.findall(r"\[\^(\d+)\]", funding))
        used_refs.update(int(m) for m in re.findall(r"\[\^(\d+)\]", events))
        self._append_section_citations(lines, used_refs, citations)

        curated_md = self._curated_external_addendum(curated_external_display, curated_citation_offset)
        if curated_md:
            lines.append(curated_md)
            lines.append("")

        return lines

    def _formal_medium_source_layer_body(
        self,
        ctx: Dict[str, Any],
        curated_display: Dict[str, Any] | None,
        annual_citation_offset: int = 0,
        broker_citation_offset: int = 0,
        external_citation_offset: int = 0,
    ) -> List[str]:
        """Render formal-medium reports as source-layer-first analysis."""
        annual_memo = ctx.get("annual_report_memo") or {}
        broker_memo = ctx.get("broker_research_memo") or {}
        lines: List[str] = []

        lines.extend(["### 4.1 官方材料确认：业务与财务基座", ""])
        lines.extend(self._formal_medium_official_material_section(annual_memo, annual_citation_offset))

        lines.extend(["### 4.2 机构观点与盈利假设", ""])
        lines.extend(self._formal_medium_broker_assumption_section(broker_memo, broker_citation_offset))

        external_map = self._formal_medium_external_variable_map(curated_display, external_citation_offset)
        lines.extend(external_map or [
            "### 4.3 外部观察与待验证变量（Preview，不参与评分）",
            "",
            "> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或目标价。",
            "",
            "当前未取得足够外部观点材料。",
            "",
        ])

        lines.extend(["### 4.4 上行 / 下行条件与股价推演", ""])
        lines.extend(self._formal_medium_price_path_section(
            annual_memo,
            broker_memo,
            curated_display,
            annual_citation_offset=annual_citation_offset,
            broker_citation_offset=broker_citation_offset,
            external_citation_offset=external_citation_offset,
        ))
        return lines

    def _formal_medium_official_material_section(self, memo: Dict[str, Any], citation_offset: int = 0) -> List[str]:
        """Render official materials without dumping raw excerpts verbatim."""
        return self._annual_report_business_profile_section(
            memo,
            citation_offset,
            fallback="当前未取得足够官方材料，无法形成业务与财务基座。",
            include_confirmed_financial_rows=True,
            financial_label="财务基座",
        )

    def _formal_medium_broker_assumption_section(self, memo: Dict[str, Any], citation_offset: int = 0) -> List[str]:
        """Render broker research as attributed assumptions, not official facts."""
        if (memo or {}).get("status") not in {"ready", "single_institution"}:
            return ["当前未取得足够可用研报 digest，不展开机构观点与盈利假设。", ""]

        rows: List[Dict[str, Any]] = []
        for row in (memo.get("sections") or []):
            if not isinstance(row, dict) or not str(row.get("body") or "").strip():
                continue
            view = self._normalize_broker_attribution(
                str(row.get("body") or "").strip(),
                default_prefix="研报认为",
                author=self._broker_row_author(row, memo),
            )
            view = self._project_broker_assumption_view(view)
            rows.append({
                "assumption": str(row.get("title") or "机构核心观点").strip(),
                "view": view,
                "refs": self._display_refs(row, citation_offset),
            })
        for row in (memo.get("forecast_ranges") or []):
            if not isinstance(row, dict):
                continue
            metric = str(row.get("metric") or "盈利预测").strip()
            period = str(row.get("period") or "").strip()
            value_range = str(row.get("range") or "").strip()
            if not value_range:
                continue
            rows.append({
                "assumption": f"{metric}{period}",
                "view": self._normalize_broker_attribution(value_range, default_prefix="研报预计"),
                "refs": self._display_refs(row, citation_offset),
            })
        for row in (memo.get("risks") or []):
            if not isinstance(row, dict) or not str(row.get("body") or "").strip():
                continue
            rows.append({
                "assumption": "反方约束",
                "view": self._normalize_broker_attribution(
                    str(row.get("body") or "").strip(),
                    default_prefix="研报提示",
                    author=self._broker_row_author(row, memo),
                ),
                "refs": self._display_refs(row, citation_offset),
            })

        lines: List[str] = []
        consensus = self._broker_consensus_sentence(rows)
        if consensus:
            lines.extend(["**机构共识**", f"- {consensus}", ""])

        lines.extend([
            "**关键盈利假设**",
        ])
        used: set[int] = set()
        assumption_rows = [row for row in rows if row["assumption"] != "反方约束"]
        for row in assumption_rows[:6]:
            refs = row["refs"]
            used.update(refs)
            view = attach_refs_to_sentence(self._compact_annual_text(row["view"], 220), refs)
            lines.append(f"- **{row['assumption']}**：{view}。")
        if not assumption_rows:
            lines.append("- 当前研报 digest 可用信息不足，不形成业绩假设，也不写成官方确认事实。")
        lines.append("")
        risk_rows = [row for row in rows if row["assumption"] == "反方约束"]
        if risk_rows:
            lines.extend(["**主要分歧 / 反方风险**"])
            for row in risk_rows[:2]:
                refs = row["refs"]
                used.update(refs)
                lines.append(f"- {attach_refs_to_sentence(self._compact_annual_text(row['view'], 180), refs)}")
            lines.append("")
        if used:
            self._append_section_citations(lines, used, self._offset_citations(memo.get("citations", {}) or {}, citation_offset))
        return lines

    def _formal_medium_external_variable_map(self, curated_display: Dict[str, Any] | None, citation_offset: int = 0) -> List[str]:
        """Render curated external material as a compact variable map."""
        if not curated_display or not self._has_curated_external_citation(curated_display):
            return []

        citations = curated_display.get("citations", {}) or {}
        cards = [c for c in (curated_display.get("_curated_external_reasoning_cards") or []) if isinstance(c, dict)]
        lines = [
            "### 4.3 外部观察与待验证变量（Preview，不参与评分）",
            "",
            "> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或目标价。",
            "",
        ]
        used: set[int] = set()
        if cards:
            for card in cards[:6]:
                claim = str(card.get("claim") or "").strip()
                refs = self._display_refs(card, citation_offset)
                used.update(refs)
                variable = self._short_heading(claim) or "外部变量"
                framed = self._external_claim_sentence(claim, refs)
                self._append_external_variable_paragraph(
                    lines,
                    variable,
                    framed,
                )
        elif curated_display.get("_curated_external_narrative_paragraphs"):
            for paragraph in (curated_display.get("_curated_external_narrative_paragraphs") or [])[:6]:
                if not isinstance(paragraph, dict):
                    continue
                text = str(paragraph.get("text") or "").strip()
                if not text:
                    continue
                refs = self._display_refs(paragraph, citation_offset)
                used.update(refs)
                variable = str(paragraph.get("heading") or self._short_heading(text) or "外部变量")
                framed = self._external_claim_sentence(text, refs)
                self._append_external_variable_paragraph(
                    lines,
                    variable,
                    framed,
                )
        else:
            for topic_key, label in CURATED_EXTERNAL_TOPIC_LABELS:
                topic_rows = [
                    row for row in (curated_display.get("_curated_external_topic_groups") or {}).get(topic_key, [])
                    if isinstance(row, dict) and str(row.get("text") or "").strip()
                ]
                if not topic_rows:
                    continue
                row = topic_rows[0]
                refs = self._display_refs(row, citation_offset)
                used.update(refs)
                framed = self._external_claim_sentence(str(row.get("text") or ""), refs)
                self._append_external_variable_paragraph(
                    lines,
                    label,
                    framed,
                )
        lines.append("")
        if used:
            self._append_section_citations(lines, used, self._offset_citations(citations, citation_offset))
        return lines

    def _formal_medium_price_path_section(
        self,
        annual_memo: Dict[str, Any],
        broker_memo: Dict[str, Any],
        curated_display: Dict[str, Any] | None,
        annual_citation_offset: int = 0,
        broker_citation_offset: int = 0,
        external_citation_offset: int = 0,
    ) -> List[str]:
        """Render deterministic upgrade/downgrade conditions without changing scoring."""
        lines = [
            "> 本节只做股价方向的条件推演，不直接修改目标价、评分、风险评分或最终推荐。",
            "",
        ]
        used: set[int] = set()
        entry_count = 0

        raw_annual_rows = [
            row for row in ((annual_memo.get("sections") or {}).get("annual_report_explanation") or [])
            if isinstance(row, dict)
        ]
        annual_rows = [
            row for row in (self._clean_formal_medium_official_row(row) for row in raw_annual_rows)
            if row
        ]
        preferred_annual_rows: List[Dict[str, Any]] = []
        for group in ("product_business", "operation_update", "management_view", "competitiveness_rd", "financial_explanation", "other"):
            preferred_annual_rows.extend(self._annual_rows_by_group(annual_rows, group))
        annual_rows = preferred_annual_rows or annual_rows
        annual_pick = self._first_row_with_refs(annual_rows, annual_citation_offset)
        if annual_pick:
            text, refs = annual_pick
            used.update(refs)
            variable = self._infer_key_variable(text, "业务覆盖 / 产品线")
            evidence = attach_refs_to_sentence(self._compact_annual_text(text, 150), refs)
            lines.extend([
                f"**官方确认：{variable}**",
                f"- {evidence}。若年报/公告确认的产品线、经营变化和财务解释继续兑现，当前股价更容易获得基本面支撑；若增长线索不能延续，或毛利率、现金流、费用率恶化，则估值支撑减弱。",
                "",
            ])
            entry_count += 1

        broker_rows = [row for row in (broker_memo.get("sections") or []) if isinstance(row, dict)]
        broker_pick = self._first_row_with_refs(broker_rows, broker_citation_offset)
        if broker_pick:
            text, refs = broker_pick
            used.update(refs)
            text = self._normalize_broker_attribution(
                text,
                default_prefix="研报认为",
                author=self._broker_author_from_display_refs(refs, broker_memo, broker_citation_offset),
            )
            text = self._project_broker_assumption_view(text)
            variable = self._infer_key_variable(text, "产品放量 / 盈利弹性")
            evidence = attach_refs_to_sentence(self._compact_annual_text(text, 170), refs)
            lines.extend([
                f"**机构假设：{variable}**",
                f"- {evidence}。若券商关于需求、产品放量或盈利弹性的假设兑现，当前估值可由业绩增长消化；若机构假设落空，盈利预测或估值溢价面临下修。",
                "",
            ])
            entry_count += 1

        external_pick = self._first_curated_external_row_with_refs(curated_display, external_citation_offset)
        if external_pick:
            text, refs = external_pick
            used.update(refs)
            variable = self._infer_key_variable(text, "供应链 / 技术路线")
            evidence = self._external_claim_sentence(text, refs, limit=280)
            lines.extend([
                f"**外部待验证：{variable}**",
                f"- {evidence}。若该变量被公告、订单或行业数据验证，可提升市场置信度；若被证伪或长期无正式证据，则只作为情绪噪音处理。",
                "",
            ])
            entry_count += 1

        if entry_count == 0:
            lines.extend(["- 当前可验证变量不足，暂不形成上行/下行推演。", ""])
        if used:
            citations = {}
            citations.update(self._offset_citations(annual_memo.get("citations", {}) or {}, annual_citation_offset))
            citations.update(self._offset_citations(broker_memo.get("citations", {}) or {}, broker_citation_offset))
            citations.update(self._offset_citations((curated_display or {}).get("citations", {}) or {}, external_citation_offset))
            self._append_section_citations(lines, used, citations)
        return lines

    def _append_section_citations(
        self,
        lines: List[str],
        used_refs: set[int],
        citations: Dict[int, Any],
        include_url: bool = False,
    ) -> None:
        if not used_refs:
            return
        lines.append("**本节引用来源：**")
        for ref_id in sorted(used_refs):
            meta = citations.get(ref_id, {})
            source = meta.get("source", "未知")
            author = meta.get("author", "")
            title_text = meta.get("title", "")
            line = f"- [^{ref_id}] {source}"
            if author:
                line += f" | 作者: {author}"
            if title_text:
                line += f" | 《{self._truncate_title(title_text, 40)}》"
            if include_url and meta.get("url"):
                line += f" | {meta.get('url')}"
            lines.append(line)
        lines.append("")

    def _formal_thin_external_rich_body(
        self,
        ctx: Dict[str, Any],
        curated_display: Dict[str, Any] | None,
        annual_citation_offset: int = 0,
        broker_citation_offset: int = 0,
        external_citation_offset: int | None = None,
    ) -> List[str]:
        """Render formal-thin layout: annual memo + broker placeholder + external map + checklist."""
        lines: List[str] = []
        profile = ctx.get("deep_analysis_evidence_profile") or {}

        if profile.get("formal_thin_layout_variant") == "annual_broker_external_checklist":
            memo = ctx.get("annual_report_memo") or {}
            lines.extend(["### 4.1 年报经营摘要", ""])
            lines.extend(self._annual_report_memo_section(memo, annual_citation_offset))
            lines.extend(["### 4.2 研报观点与假设", ""])
            broker_memo = ctx.get("broker_research_memo") or {}
            lines.extend(self._broker_research_memo_section(broker_memo, broker_citation_offset))
            external_offset = (
                external_citation_offset
                if external_citation_offset is not None
                else broker_citation_offset + self._max_citation_id((broker_memo or {}).get("citations", {}))
            )
            map_md = self._external_viewpoint_map_section(
                curated_display,
                citation_offset=external_offset,
                heading="### 4.3 外部观点与待验证变量（Preview，不参与评分）",
            )
            lines.extend(map_md or ["### 4.3 外部观点与待验证变量（Preview，不参与评分）", "", "当前未取得足够外部观点材料。", ""])
        else:
            # 4.1 正式材料要点
            lines.extend(["### 4.1 正式材料要点", ""])
            lines.extend(self._formal_summary_section(ctx))

            # 4.2 外部观点地图
            map_md = self._external_viewpoint_map_section(curated_display)
            if map_md:
                lines.extend(map_md)

            # 4.3 待验证清单
            checklist_md = self._verification_checklist_section(curated_display)
            if checklist_md:
                lines.extend(checklist_md)

        return lines

    @staticmethod
    def _material_snapshot(ctx: Dict[str, Any], enabled: bool) -> Any:
        if not enabled:
            return None
        return ctx.get("deep_analysis_material_snapshot") or build_deep_analysis_material_snapshot(ctx)

    @staticmethod
    def _max_snapshot_ref(snapshot: Any, layers: set[str]) -> int:
        refs: List[int] = []
        for row in getattr(snapshot, "rows", ()) or ():
            if getattr(row, "source_layer", "") not in layers:
                continue
            refs.extend(int(ref) for ref in getattr(row, "citation_refs", ()) or ())
        return max(refs) if refs else 0

    def _broker_research_memo_section(self, memo: Dict[str, Any], citation_offset: int = 0) -> List[str]:
        """Render broker memo as attributed professional assumptions."""
        if (memo or {}).get("status") not in {"ready", "single_institution"}:
            return ["当前未取得足够可用研报 digest，不展开研报观点与假设。", ""]

        lines: List[str] = []
        used: set[int] = set()
        if memo.get("status") == "single_institution":
            lines.extend(["**单篇研报观点 / 单机构观点**", ""])
        for row in (memo.get("sections") or []):
            if not isinstance(row, dict):
                continue
            text = str(row.get("body") or "").strip()
            title = str(row.get("title") or "").strip()
            refs = [int(x) + citation_offset for x in row.get("citation_refs", []) if isinstance(x, (int, str))]
            if text:
                text = self._normalize_broker_attribution(
                    text,
                    default_prefix="研报认为",
                    author=self._broker_row_author(row, memo),
                )
                lines.append(f"- {attach_refs_to_sentence(f'**{title}**：{text}' if title else text, refs)}")
                used.update(refs)
        for row in (memo.get("forecast_ranges") or []):
            if not isinstance(row, dict):
                continue
            text = " ".join(str(row.get(k) or "").strip() for k in ("metric", "period", "range") if row.get(k))
            refs = [int(x) + citation_offset for x in row.get("citation_refs", []) if isinstance(x, (int, str))]
            if text:
                lines.append(f"- {attach_refs_to_sentence(text, refs)}")
                used.update(refs)
        for row in (memo.get("risks") or []):
            if not isinstance(row, dict):
                continue
            text = str(row.get("body") or "").strip()
            refs = [int(x) + citation_offset for x in row.get("citation_refs", []) if isinstance(x, (int, str))]
            if text:
                text = self._normalize_broker_attribution(
                    text,
                    default_prefix="研报提示",
                    author=self._broker_row_author(row, memo),
                )
                lines.append(f"- {attach_refs_to_sentence(text, refs)}")
                used.update(refs)
        lines.append("")
        if used:
            self._append_section_citations(lines, used, self._offset_citations(memo.get("citations", {}), citation_offset))
        return lines

    def _thin_all_body(self, ctx: Dict[str, Any]) -> List[str]:
        """Render material-insufficient layout."""
        lines: List[str] = [
            "### 4.1 正式材料要点",
            "",
        ]
        lines.extend(self._formal_summary_section(ctx))
        lines.extend([
            "",
            "当前可用于深度基本面分析的正式材料不足，未强制生成 4.2/4.3 推断性内容。",
            "",
        ])
        return lines

    def _annual_report_memo_section(self, memo: Dict[str, Any], citation_offset: int = 0) -> List[str]:
        """Render annual memo subsections: confirmed, explanation, not_disclosed, inconclusive."""
        return self._annual_report_business_profile_section(
            memo,
            citation_offset,
            fallback="当前未取得足够年报材料，无法形成年报经营摘要。",
        )

    def _annual_report_business_profile_section(
        self,
        memo: Dict[str, Any],
        citation_offset: int = 0,
        fallback: str = "当前未取得足够年报材料，无法形成业务画像。",
        include_confirmed_financial_rows: bool = True,
        financial_label: str = "财务变化原因",
    ) -> List[str]:
        """Project annual memo rows into a compact business profile."""
        lines: List[str] = []
        secs = memo.get("sections") or {}
        cits = memo.get("citations", {}) or {}
        used: set[int] = set()

        if (memo or {}).get("status") not in {"ready", "deterministic_fallback"}:
            return [fallback, ""]

        explanation_rows = [
            row for row in (
                self._clean_formal_medium_official_row(r)
                for r in (secs.get("annual_report_explanation") or [])
                if isinstance(r, dict)
            )
            if row
        ]
        confirmed_rows = [
            r for r in (secs.get("confirmed") or [])
            if isinstance(r, dict) and not self._is_suspicious_zero_annual_row(r)
        ]

        product_rows = self._annual_rows_by_group(explanation_rows, "product_business")
        portrait_row = self._select_annual_portrait_row(product_rows) if product_rows else (confirmed_rows[0] if confirmed_rows else None)
        if portrait_row:
            refs = self._display_refs(portrait_row, citation_offset)
            used.update(refs)
            portrait = self._compact_annual_text(str(portrait_row.get("body") or ""), 140)
            lines.extend(["**一句话画像**", f"- {attach_refs_to_sentence(portrait, refs)}", ""])

        seen_business_keys = {self._annual_row_text_key(portrait_row)} if portrait_row else set()
        business_rows: List[Dict[str, Any]] = []
        for row in product_rows:
            key = self._annual_row_text_key(row)
            if key in seen_business_keys:
                continue
            seen_business_keys.add(key)
            business_rows.append(row)
        financial_rows = [
            row for row in self._annual_rows_by_group(explanation_rows, "financial_explanation")
            if self._is_financial_explanation_row(row)
        ]
        if include_confirmed_financial_rows:
            financial_rows.extend(confirmed_rows)
        groups = (
            ("业务结构", business_rows),
            ("经营变化", self._annual_rows_by_group(explanation_rows, "operation_update") + self._annual_rows_by_group(explanation_rows, "management_view")),
            ("研发与产品进展", self._annual_rows_by_group(explanation_rows, "competitiveness_rd")),
            (financial_label, financial_rows),
        )
        for label, rows in groups:
            rows = [row for row in rows if str(row.get("body") or "").strip()]
            if not rows:
                continue
            lines.append(f"**{label}**")
            row_limit = 4 if label == financial_label else 2
            for row in rows[:row_limit]:
                refs = self._display_refs(row, citation_offset)
                used.update(refs)
                body = self._annual_row_visible_body(row, include_title=(label == financial_label))
                lines.append(f"- {attach_refs_to_sentence(body, refs)}")
            lines.append("")
        if not lines and not (confirmed_rows or explanation_rows):
            lines.extend([fallback, ""])
        if used:
            self._append_section_citations(lines, used, self._offset_citations(cits, citation_offset))
        return lines

    @staticmethod
    def _is_suspicious_zero_annual_row(row: Dict[str, Any]) -> bool:
        return DeepAnalysisRenderer._is_suspicious_zero_financial_fact({
            "fact": row.get("title"),
            "data": row.get("body"),
        })

    @staticmethod
    def _broker_row_author(row: Dict[str, Any], memo: Dict[str, Any]) -> str:
        for ref in row.get("citation_refs") or []:
            try:
                meta = (memo.get("citations") or {}).get(int(ref), {})
            except (TypeError, ValueError):
                continue
            author = str(meta.get("author") or "").strip()
            if author:
                return author
        return ""

    @staticmethod
    def _broker_author_from_display_refs(refs: List[int], memo: Dict[str, Any], citation_offset: int = 0) -> str:
        citations = memo.get("citations") or {}
        for ref in refs:
            try:
                meta = citations.get(int(ref) - int(citation_offset), {})
            except (TypeError, ValueError):
                continue
            author = str(meta.get("author") or "").strip()
            if author:
                return author
        return ""

    @staticmethod
    def _normalize_broker_attribution(text: str, default_prefix: str = "研报认为", author: str = "") -> str:
        value = re.sub(r"\s+", " ", str(text or "")).strip(" ：:")
        if not value:
            return ""
        author = str(author or "").strip()
        broker_prefix = f"{author}研报" if author else "研报"
        generic_assumption = re.match(r"^(?:券商认为|研报认为|机构认为)(?:[：:，,]\s*|\s+)(.+)$", value)
        if generic_assumption:
            return f"{broker_prefix}认为：{generic_assumption.group(1).strip()}"
        generic_risk = re.match(r"^(?:券商提示|研报提示|机构提示|风险提示)(?:[：:，,]\s*|\s+)(.+)$", value)
        if generic_risk:
            body = re.sub(r"^(?:风险提示|提示)[：:]\s*", "", generic_risk.group(1).strip())
            return f"{broker_prefix}提示：{body}"
        if author and value.startswith(f"{author}认为"):
            return value.replace(f"{author}认为", f"{author}研报认为", 1)
        if author and value.startswith(f"{author}提示"):
            return value.replace(f"{author}提示", f"{author}研报提示", 1)
        if re.match(r"^[^：:]{2,12}认为[：:]", value):
            return re.sub(r"^([^：:]{2,12})认为[：:]\s*", r"\1研报认为：", value, count=1)
        if re.match(r"^[^：:]{2,12}提示[：:]", value):
            return re.sub(r"^([^：:]{2,12})提示[：:]\s*", r"\1研报提示：", value, count=1)
        value = re.sub(r"^(?:券商认为|研报认为|机构认为)[：:]\s*([^：:]{2,12})认为[：:]\s*", r"\1研报认为：", value)
        value = re.sub(r"^(?:券商认为|研报认为|机构认为)[：:]\s*([^：:]{2,12})提示[：:]\s*", r"\1研报提示：", value)
        if any(term in value for term in ("券商认为", "研报认为", "研报预计", "机构认为", "机构假设", "研报提示", "券商预测")):
            return value
        if author and default_prefix.startswith("研报"):
            return f"{broker_prefix}{default_prefix.removeprefix('研报')}：{value}"
        return f"{default_prefix}：{value}"

    @staticmethod
    def _broker_consensus_sentence(rows: List[Dict[str, Any]]) -> str:
        texts = "；".join(str(row.get("view") or "") for row in rows)
        themes: List[str] = []
        for term in ("800G", "1.6T", "AI 数据中心", "毛利率", "产品结构升级", "客户资本开支"):
            if term in texts and term not in themes:
                themes.append(term)
        if themes:
            return "研报共识集中在" + "、".join(themes[:4]) + "等变量。"
        if rows:
            return "研报观点主要围绕需求、产品放量、盈利弹性与反方风险。"
        return ""

    @staticmethod
    def _project_broker_assumption_view(text: str) -> str:
        value = re.sub(r"\s+", " ", str(text or "")).strip()
        if not value:
            return ""
        match = re.match(r"^(.{0,18}?研报(?:认为|预计|提示)|研报(?:认为|预计|提示))[：:]\s*(.+)$", value)
        if not match:
            return value
        prefix, body = match.group(1), match.group(2)
        noisy_recap = any(term in body for term in ("业绩简评", "一季报", "Q1", "实现收入", "归母净利润", "同比", "环比"))
        if not noisy_recap:
            return value
        themes: List[str] = []
        if re.search(r"800G|1\.6T", body):
            themes.append("800G/1.6T 放量")
        if re.search(r"NPO|CPO|XPO|Scale[- ]?up|Scaleup", body, re.IGNORECASE):
            themes.append("NPO/Scale-up 等新技术路线")
        if any(term in body for term in ("毛利率", "产品结构", "规模效应")):
            themes.append("产品结构升级和毛利率弹性")
        if any(term in body for term in ("客户资本开支", "CSP", "AI 数据中心", "AI算力")):
            themes.append("AI 客户资本开支")
        if not themes:
            return value
        return f"{prefix}：研报关注{'、'.join(themes[:3])}。"

    @staticmethod
    def _annual_row_group(row: Dict[str, Any]) -> str:
        title = str(row.get("title") or "")
        if any(term in title for term in ("收入", "利润", "费用", "现金流", "存货", "减值", "毛利率")):
            return "financial_explanation"
        if any(term in title for term in ("研发", "技术", "竞争")):
            return "competitiveness_rd"
        if any(term in title for term in ("主营", "产品", "业务")):
            return "product_business"
        if any(term in title for term in ("经营", "进展", "更新")):
            return "operation_update"
        if any(term in title for term in ("管理层", "市场", "行业", "前景")):
            return "management_view"
        return "other"

    def _annual_rows_by_group(self, rows: List[Dict[str, Any]], group: str) -> List[Dict[str, Any]]:
        return [
            row for row in rows
            if str(row.get("display_group") or self._annual_row_group(row)) == group
        ]

    @staticmethod
    def _annual_row_text_key(row: Dict[str, Any] | None) -> str:
        if not isinstance(row, dict):
            return ""
        return re.sub(r"\s+", "", str(row.get("body") or ""))[:80]

    @staticmethod
    def _is_financial_explanation_row(row: Dict[str, Any]) -> bool:
        body = str(row.get("body") or "")
        title = str(row.get("title") or "")
        if not body.strip():
            return False
        if any(term in body for term in ("变化原因", "主要系", "所致")):
            return True
        if any(term in title for term in ("营业收入", "归母净利润", "净利润", "毛利率", "现金流", "存货", "费用")):
                return any(term in body for term in ("增长", "下降", "增加", "减少", "提升", "改善", "承压", "同比", "环比"))
        return False

    def _annual_row_visible_body(self, row: Dict[str, Any], include_title: bool = False) -> str:
        body = self._compact_annual_text(str(row.get("body") or ""), 140)
        title = str(row.get("title") or "").strip()
        if include_title and title and title not in body and "原因" not in body:
            return f"{title}：{body}"
        return body

    @staticmethod
    def _select_annual_portrait_row(rows: List[Dict[str, Any]]) -> Dict[str, Any] | None:
        if not rows:
            return None

        def score(row: Dict[str, Any]) -> int:
            body = str(row.get("body") or "")
            value = 0
            if "从事" in body and any(term in body for term in ("设计", "开发", "测试", "系统解决方案")):
                value += 8
            if "产品线" in body:
                value += 5
            for term in ("FPGA", "安全与识别", "非挥发", "智能电表", "集成电路测试", "光模块"):
                if term in body:
                    value += 2
            if "存储芯片产品线" in body and "FPGA" not in body:
                value -= 4
            return value

        return max(rows, key=score)

    @staticmethod
    def _display_refs(row: Dict[str, Any], offset: int = 0) -> List[int]:
        refs: List[int] = []
        for ref in row.get("citation_refs") or []:
            try:
                refs.append(int(ref) + offset)
            except (TypeError, ValueError):
                continue
        return refs

    @staticmethod
    def _compact_text(text: str, limit: int = 120) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip(" ；;。")
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[:limit].rstrip(" ，,；;。") + "..."

    @staticmethod
    def _compact_annual_text(text: str, limit: int = 140) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip(" ；;。")
        if len(cleaned) <= limit:
            return cleaned
        chunks = re.split(r"(?<=[。！？；;])", cleaned)
        kept = ""
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            next_text = (kept + chunk).strip()
            if len(next_text) <= limit:
                kept = next_text
                continue
            break
        if kept:
            return kept.strip(" ；;。")
        return cleaned[:limit].rstrip(" ，,；;。")

    @staticmethod
    def _compact_external_text(text: str, limit: int = 380) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip(" ；;。")
        if len(cleaned) <= limit:
            return cleaned
        chunks = re.split(r"(?<=[。！？；;])", cleaned)
        kept = ""
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            next_text = (kept + chunk).strip()
            if len(next_text) <= limit:
                kept = next_text
                continue
            break
        if kept:
            return kept.strip(" ；;。")
        return cleaned[:limit].rstrip(" ，,；;。")

    def _external_claim_sentence(self, text: str, refs: List[int], limit: int = 380) -> str:
        return attach_refs_to_sentence(
            self._frame_external_claim(self._compact_external_text(text, limit)),
            refs,
        )

    @staticmethod
    def _clean_formal_medium_official_row(row: Dict[str, Any]) -> Dict[str, Any] | None:
        body = str(row.get("body") or "").strip()
        if not body:
            return None
        body = re.sub(r"公司需遵守《[^》]+》[^。；，,]*披露要求[，,。；]*", "", body)
        body = re.sub(r"需遵守《[^》]+》[^。；，,]*披露要求[，,。；]*", "", body)
        body = re.sub(r"公司需遵守[^。；，,]*披露要求[，,。；]*", "", body)
        body = body.replace("报告期内公司从事的主要业务公司主营业务", "公司主营业务")
        body = body.replace("报告期内公司从事的主要业务", "")
        body = re.sub(r"^\d+[、.]\s*(?:主要业务|主要产品及服务情况)\s*", "", body)
        body = re.sub(r"^\d+(?:\.\d+)+\s*(?:FPGA芯片|[^，。；;]{1,20})\s*", "", body)
        body = re.sub(r"^（?[^）]{1,20}）?芯片\s*\d+[、.]\s*", "", body)
        body = body.replace("报告期内获得的研发成果截至", "截至")
        body = re.sub(r"\s+", " ", body).strip(" ，,；;。")
        if not body:
            return None
        if any(term in body for term in ("采购模式", "经营模式", "直接销售模式", "代理销售")):
            prefix = re.split(r"采购模式|经营模式|直接销售模式|代理销售", body, maxsplit=1)[0]
            prefix = prefix.strip(" ，,；;。")
            if len(prefix) >= 20 and any(term in prefix for term in ("主营业务", "产品服务", "云数据中心", "光模块", "产品线")):
                body = prefix
            else:
                return None
        cleaned = dict(row)
        cleaned["body"] = body
        return cleaned

    def _first_row_with_refs(self, rows: List[Dict[str, Any]], offset: int = 0) -> tuple[str, List[int]] | None:
        for row in rows:
            if not isinstance(row, dict):
                continue
            refs = self._display_refs(row, offset)
            body = str(row.get("body") or row.get("range") or "").strip()
            if body and refs:
                return body, refs
        return None

    def _first_curated_external_row_with_refs(
        self,
        curated_display: Dict[str, Any] | None,
        offset: int = 0,
    ) -> tuple[str, List[int]] | None:
        if not curated_display:
            return None
        rows: List[Dict[str, Any]] = []
        rows.extend(
            row for row in (curated_display.get("_curated_external_reasoning_cards") or [])
            if isinstance(row, dict)
        )
        rows.extend(
            row for row in (curated_display.get("_curated_external_narrative_paragraphs") or [])
            if isinstance(row, dict)
        )
        topic_groups = curated_display.get("_curated_external_topic_groups") or {}
        for topic_key, _label in CURATED_EXTERNAL_TOPIC_LABELS:
            rows.extend(row for row in (topic_groups.get(topic_key) or []) if isinstance(row, dict))
        for row in rows:
            refs = self._display_refs(row, offset)
            text = str(row.get("claim") or row.get("text") or row.get("body") or "").strip()
            if text and refs:
                return text, refs
        return None

    def _formal_summary_section(self, ctx: Dict[str, Any]) -> List[str]:
        """Build 4.1 formal-only summary blocks."""
        lines: List[str] = []
        fact_pack = ctx.get("formal_financial_fact_pack") or {}
        explanation_pack = ctx.get("formal_financial_explanation_pack") or {}

        confirmed: List[str] = []
        for fact in (fact_pack.get("facts") or []):
            if isinstance(fact, dict) and fact.get("metric") and fact.get("value"):
                confirmed.append(f"- {fact['metric']}：{fact['value']}")
        if confirmed:
            lines.append("**已确认**")
            lines.extend(confirmed)
            lines.append("")

        explanations: List[str] = []
        for row in (explanation_pack.get("rows") or []):
            if isinstance(row, dict) and row.get("metric") and row.get("excerpt"):
                explanations.append(f"- {row['metric']}：{row['excerpt']}")
        if explanations:
            lines.append("**经营解释**")
            lines.extend(explanations)
            lines.append("")

        lines.append("**未披露 / 不能下结论**")
        lines.append("- 重要客户、订单、产能、供应链、管理层指引或细分拆分未在正式材料中充分披露。")
        lines.append("- 不得用营收/利润推断主力资金或市场行为。")
        return lines

    def _external_viewpoint_map_section(
        self,
        curated_display: Dict[str, Any] | None,
        citation_offset: int = 0,
        heading: str | None = None,
    ) -> List[str]:
        """Build 4.2/4.3 external viewpoint map from curated external display."""
        if not curated_display or not self._has_curated_external_citation(curated_display):
            return []

        narrative_paragraphs = [
            paragraph for paragraph in (curated_display.get("_curated_external_narrative_paragraphs") or [])
            if isinstance(paragraph, dict)
        ]
        reasoning_cards = curated_display.get("_curated_external_reasoning_cards") or []
        topic_groups = curated_display.get("_curated_external_topic_groups") or {}

        lines: List[str] = [
            heading or ("### 4.3 外部观点地图（Preview，不参与评分）" if citation_offset else "### 4.2 外部观点地图（Preview，不参与评分）"),
            "",
            "> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。",
            "",
        ]

        if narrative_paragraphs:
            for paragraph in narrative_paragraphs[:6]:
                text = str(paragraph.get("text") or "").strip()
                display_refs = self._display_refs(paragraph, citation_offset)
                if not text or not display_refs:
                    continue
                rendered = self._external_claim_sentence(text, display_refs)
                self._append_external_variable_paragraph(
                    lines,
                    str(paragraph.get("heading") or self._short_heading(text) or "外部变量"),
                    rendered,
                )
        elif reasoning_cards:
            for card in reasoning_cards[:6]:
                if not isinstance(card, dict):
                    continue
                claim = str(card.get("claim") or "").strip()
                display_refs = self._display_refs(card, citation_offset)
                if not claim or not display_refs:
                    continue
                rendered_claim = self._external_claim_sentence(claim, display_refs)
                self._append_external_variable_paragraph(
                    lines,
                    self._short_heading(claim) or "外部变量",
                    rendered_claim,
                )
        elif topic_groups:
            for topic_key, label in CURATED_EXTERNAL_TOPIC_LABELS:
                rows = topic_groups.get(topic_key) or []
                rows = [r for r in rows if isinstance(r, dict)]
                if not rows:
                    continue
                for row in rows[:3]:
                    text = str(row.get("text") or "").strip()
                    display_refs = self._display_refs(row, citation_offset)
                    if not text or not display_refs:
                        continue
                    rendered = self._external_claim_sentence(text, display_refs)
                    if rendered:
                        self._append_external_variable_paragraph(
                            lines,
                            label,
                            rendered,
                        )

        if len(lines) == 4:
            lines.append("- 当前外部材料不足以形成可展示变量。")
        lines.append("")
        return lines

    def _verification_checklist_section(self, curated_display: Dict[str, Any] | None, citation_offset: int = 0) -> List[str]:
        """Build 4.4/4.3 verification checklist table from reasoning cards."""
        if not curated_display:
            return []
        reasoning_cards = curated_display.get("_curated_external_reasoning_cards") or []
        if not reasoning_cards:
            return []

        citations = curated_display.get("citations", {}) or {}
        lines: List[str] = [
            "### 4.4 待验证清单" if citation_offset else "### 4.3 待验证清单",
            "",
            "| 变量 | 为什么重要 | 需要什么证据 | 来源层级 |",
            "|---|---|---|---|",
        ]
        for card in reasoning_cards[:8]:
            if not isinstance(card, dict):
                continue
            variable = self._short_heading(str(card.get("claim") or "")) or "未命名变量"
            assumptions = [str(a).strip() for a in (card.get("assumptions") or []) if str(a).strip()]
            why = "；".join(assumptions[:2]) if assumptions else "外部观点的增量变量"
            verification = str(card.get("verification_need") or "").strip() or "后续公告、订单或行业数据"
            refs = card.get("citation_refs") or []
            credit_label = self._source_credit_label(citations, refs)
            lines.append(f"| {variable} | {why} | {verification} | {credit_label} |")
        lines.append("")
        return lines

    @staticmethod
    def _used_formal_thin_external_citations(curated_display: Dict[str, Any] | None) -> Dict[int, Any]:
        """Return only external citations referenced by formal-thin map/checklist rows."""
        if not curated_display:
            return {}
        used: set[int] = set()
        for card in (curated_display.get("_curated_external_reasoning_cards") or [])[:8]:
            if isinstance(card, dict):
                for ref in card.get("citation_refs") or []:
                    try:
                        used.add(int(ref))
                    except (TypeError, ValueError):
                        continue
        if not used:
            for rows in (curated_display.get("_curated_external_topic_groups") or {}).values():
                if not isinstance(rows, list):
                    continue
                for row in rows[:3]:
                    if isinstance(row, dict):
                        for ref in row.get("citation_refs") or []:
                            try:
                                used.add(int(ref))
                            except (TypeError, ValueError):
                                continue
        citations = curated_display.get("citations", {}) or {}
        return {ref: citations[ref] for ref in sorted(used) if ref in citations}

    @staticmethod
    def _short_heading(text: str) -> str:
        heading = str(text or "").split("。", 1)[0].split("；", 1)[0].strip()
        return heading[:40] + "..." if len(heading) > 40 else heading

    @staticmethod
    def _frame_external_claim(text: str) -> str:
        claim = re.sub(r"\s+", " ", str(text or "")).strip(" ，,；;。")
        if not claim:
            return ""
        claim = re.sub(
            r"^(?:外部材料|外部观点|外部文章|外部信息)(?:称|认为|提示|讨论|指出|显示)[，,：:\s]*",
            "",
            claim,
        ).strip(" ，,；;。")
        claim = re.sub(r"^据外部材料[，,：:\s]*", "", claim).strip(" ，,；;。")
        claim = DeepAnalysisRenderer._soften_external_unverified_terms(claim)
        if not claim:
            return ""
        return f"外部材料称：{claim}"

    @staticmethod
    def _append_external_variable_paragraph(lines: List[str], variable: str, claim_text: str) -> None:
        variable = re.sub(r"\s+", " ", str(variable or "")).strip(" ：:，,；;。") or "外部变量"
        variable = re.sub(
            r"^(?:外部材料|外部观点|外部文章|外部信息)(?:称|认为|提示|讨论|指出|显示)[，,：:\s]*",
            "",
            variable,
        ).strip(" ：:，,；;。") or "外部变量"
        variable = DeepAnalysisRenderer._soften_external_unverified_terms(variable)
        claim_text = re.sub(r"\s+", " ", str(claim_text or "")).strip()
        if not claim_text:
            return
        lines.append(f"**{variable}**")
        lines.append(f"- {claim_text}")
        lines.append("")

    @staticmethod
    def _soften_external_unverified_terms(text: str) -> str:
        softened = str(text or "")
        softened = softened.replace("后续订单落地情况", "后续订单进展")
        softened = softened.replace("订单落地情况", "订单进展")
        softened = softened.replace("订单落地", "订单进展")
        return softened

    @staticmethod
    def _infer_key_variable(text: str, fallback: str) -> str:
        value = str(text or "")
        if any(term in value for term in ("供应链", "预付款", "交付")):
            return "供应链与交付"
        if any(term in value for term in ("主营业务", "产品服务", "业务覆盖")):
            return fallback
        if any(term in value for term in ("1.6T", "800G", "3.2T")):
            return "高速光模块放量"
        if any(term in value for term in ("毛利率", "盈利", "利润")):
            return "盈利弹性 / 毛利率"
        if any(term in value for term in ("产品", "业务", "收入", "客户")):
            return fallback
        return fallback

    @staticmethod
    def _source_credit_label(citations: Dict[int, Any], refs: List[Any]) -> str:
        sources = set()
        for ref in refs:
            try:
                ref_id = int(ref)
            except (TypeError, ValueError):
                continue
            meta = citations.get(ref_id, {})
            if isinstance(meta, dict):
                sources.add(str(meta.get("source") or "外部来源"))
        if len(sources) > 1:
            return "来源层级：多源一致 / 需正式验证"
        if "微信公众号精选观察" in sources or "雪球" in sources:
            return "来源层级：低信用论坛 / 单源长文 / 需正式验证"
        return "来源层级：需正式验证"

    def _curated_external_addendum(
        self,
        curated_display: Dict[str, Any] | None,
        citation_offset: int = 0,
    ) -> str:
        if not curated_display or not self._has_curated_external_citation(curated_display):
            return ""

        citations = curated_display.get("citations", {}) or {}
        is_narrative = bool(curated_display.get("_curated_external_narrative"))
        lines = [
            (
                "### 4.4 精选外部观察（Preview）"
                if is_narrative
                else "### 4.4 外部观点与待验证变量（Preview）"
            ),
            "",
            "> 精选外部材料仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。",
            "",
        ]
        if is_narrative:
            return self._curated_external_narrative_addendum(
                curated_display,
                citation_offset,
                lines,
            )

        topic_groups = curated_display.get("_curated_external_topic_groups") or {}
        if topic_groups:
            return self._curated_external_grouped_addendum(
                topic_groups,
                curated_display.get("citations", {}) or {},
                citation_offset,
                lines,
            )

        bullets: List[str] = []
        for key in CURATED_EXTERNAL_ADDENDUM_KEYS:
            text = str(curated_display.get(key) or "").strip()
            if not text:
                continue
            text = self._offset_citation_markers(text, citation_offset)
            for piece in self._split_curated_observations(text):
                if piece:
                    bullets.append(piece)

        for bullet in bullets:
            lines.append(f"- {bullet}")
        lines.append("")

        used_refs = set()
        for bullet in bullets:
            used_refs.update(int(m) for m in re.findall(r"\[\^(\d+)\]", bullet))
        if used_refs:
            shifted_citations = self._offset_citations(citations, citation_offset)
            self._append_section_citations(lines, used_refs, shifted_citations, include_url=True)
        return "\n".join(lines)

    def _curated_external_narrative_addendum(
        self,
        curated_display: Dict[str, Any],
        citation_offset: int,
        lines: List[str],
    ) -> str:
        paragraphs = curated_display.get("_curated_external_narrative_paragraphs") or []
        reasoning_cards = curated_display.get("_curated_external_reasoning_cards") or []
        used_refs = self._curated_external_used_refs_from_rows(
            list(paragraphs) + [card for card in reasoning_cards if isinstance(card, dict)],
            citation_offset,
        )
        shifted_citations = self._offset_citations(curated_display.get("citations", {}) or {}, citation_offset)
        ref_map, display_refs = self._curated_external_display_ref_map(shifted_citations, used_refs)

        for paragraph in paragraphs:
            if not isinstance(paragraph, dict):
                continue
            heading = str(paragraph.get("heading") or "").strip()
            text = str(paragraph.get("text") or "").strip()
            citation_refs = paragraph.get("citation_refs") or []
            rendered = attach_refs_to_sentence(text, citation_refs)
            rendered = self._offset_citation_markers(rendered, citation_offset)
            rendered = self._remap_citation_markers(rendered, ref_map)
            if heading:
                lines.append(f"**{heading}**")
                lines.append("")
            if rendered:
                lines.append(rendered)
                lines.append("")

        # Reasoning cards are kept as internal audit metadata only; do not render
        # the visible **观点卡片：** block in this batch.

        self._append_section_citations(lines, display_refs, shifted_citations, include_url=True)
        return "\n".join(lines)

    def _curated_external_grouped_addendum(
        self,
        topic_groups: Dict[str, Any],
        citations: Dict[str, Any],
        citation_offset: int,
        lines: List[str],
    ) -> str:
        used_refs = self._curated_external_used_refs_from_grouped_rows(topic_groups, citation_offset)
        shifted_citations = self._offset_citations(citations, citation_offset)
        ref_map, display_refs = self._curated_external_display_ref_map(shifted_citations, used_refs)

        group_index = 1
        for topic_key, label in CURATED_EXTERNAL_TOPIC_LABELS:
            rows = topic_groups.get(topic_key) or []
            rows = [row for row in rows if isinstance(row, dict)]
            if not rows:
                continue
            lines.extend([
                f"#### 4.4.{group_index} {label}",
                "",
            ])
            group_index += 1
            for row in rows:
                heading = str(row.get("heading") or "").strip()
                text = str(row.get("text") or "").strip()
                citation_refs = row.get("citation_refs") or []
                rendered = attach_refs_to_sentence(text, citation_refs)
                rendered = self._offset_citation_markers(rendered, citation_offset)
                rendered = self._remap_citation_markers(rendered, ref_map)
                if heading:
                    lines.append(f"**{heading}**")
                    lines.append("")
                if rendered:
                    lines.append(rendered)
                    lines.append("")

        self._append_section_citations(lines, display_refs, shifted_citations, include_url=True)
        return "\n".join(lines)

    @staticmethod
    def _curated_external_used_refs_from_rows(rows: List[Any], citation_offset: int) -> set:
        used_refs = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            for ref in row.get("citation_refs") or []:
                try:
                    used_refs.add(int(ref) + citation_offset)
                except (TypeError, ValueError):
                    continue
        return used_refs

    def _curated_external_used_refs_from_grouped_rows(
        self,
        topic_groups: Dict[str, Any],
        citation_offset: int,
    ) -> set:
        rows = []
        for value in (topic_groups or {}).values():
            if isinstance(value, list):
                rows.extend(value)
        return self._curated_external_used_refs_from_rows(rows, citation_offset)

    def _curated_external_display_ref_map(self, shifted_citations: Dict[int, Any], used_refs: set) -> tuple[dict, set]:
        canonical_by_key = {}
        ref_map = {}
        display_refs = set()
        for ref_id in sorted(used_refs):
            meta = shifted_citations.get(ref_id, {})
            key = self._curated_external_citation_identity(meta)
            if not key:
                canonical = ref_id
            elif key in canonical_by_key:
                canonical = canonical_by_key[key]
            else:
                canonical_by_key[key] = ref_id
                canonical = ref_id
            ref_map[ref_id] = canonical
            display_refs.add(canonical)
        return ref_map, display_refs

    @staticmethod
    def _curated_external_citation_identity(meta: Any) -> tuple:
        if not isinstance(meta, dict):
            return ()
        url = str(meta.get("url") or "").strip()
        source = str(meta.get("source") or "").strip()
        author = str(meta.get("author") or "").strip()
        title = str(meta.get("title") or "").strip()
        if url:
            return ("url", url)
        if source and (author or title):
            return ("fallback", source, author, title)
        return ()

    @staticmethod
    def _remap_citation_markers(text: str, ref_map: dict) -> str:
        if not ref_map:
            return DeepAnalysisRenderer._dedupe_citation_marker_clusters(text)
        remapped = re.sub(
            r"\[\^(\d+)\]",
            lambda match: f"[^{ref_map.get(int(match.group(1)), int(match.group(1)))}]",
            text,
        )
        return DeepAnalysisRenderer._dedupe_citation_marker_clusters(remapped)

    @staticmethod
    def _dedupe_citation_marker_clusters(text: str) -> str:
        """Collapse repeated adjacent footnotes after source de-duplication."""
        if not text:
            return text

        def replace_cluster(match: re.Match) -> str:
            seen = set()
            refs = []
            for ref in re.findall(r"\[\^(\d+)\]", match.group(0)):
                if ref in seen:
                    continue
                seen.add(ref)
                refs.append(ref)
            return "".join(f"[^{ref}]" for ref in refs)

        return re.sub(r"(?:\[\^\d+\]){2,}", replace_cluster, text)

    @staticmethod
    def _split_curated_observations(text: str) -> List[str]:
        text = re.sub(r"^精选外部材料仅作为专业观察，提示[^：:]+[：:]", "", text).strip()
        parts = re.split(r"；(?=《)", text)
        return [part.strip(" ；。") for part in parts if part.strip(" ；。")]

    @staticmethod
    def _offset_citation_markers(text: str, offset: int) -> str:
        if offset <= 0:
            return text
        return re.sub(r"\[\^(\d+)\]", lambda m: f"[^{int(m.group(1)) + offset}]", text)

    @staticmethod
    def _max_citation_id(citations: Dict) -> int:
        refs = []
        for key in citations.keys():
            try:
                refs.append(int(key))
            except (TypeError, ValueError):
                continue
        return max(refs) if refs else 0

    def _merged_citations(self, baseline: Dict, curated: Dict) -> Dict:
        merged = {self._citation_key(key): value for key, value in (baseline or {}).items()}
        offset = self._max_citation_id(merged)
        merged.update(self._offset_citations(curated or {}, offset))
        return merged

    @staticmethod
    def _offset_citations(citations: Dict, offset: int) -> Dict:
        shifted = {}
        for key, value in (citations or {}).items():
            try:
                ref_id = int(key)
            except (TypeError, ValueError):
                continue
            shifted[ref_id + offset] = value
        return shifted

    @staticmethod
    def _visible_citations_only(citations: Dict, body_text: str) -> Dict:
        if not citations:
            return {}
        visible_refs = {
            int(ref)
            for ref in re.findall(r"\[\^(\d+)\]", body_text or "")
        }
        return {
            ref_id: meta
            for ref_id, meta in (citations or {}).items()
            if isinstance(ref_id, int) and ref_id in visible_refs
        }

    @staticmethod
    def _citation_key(key: Any) -> Any:
        try:
            return int(key)
        except (TypeError, ValueError):
            return key

    @staticmethod
    def _has_curated_external_citation(synthesis: Dict[str, Any]) -> bool:
        citations = synthesis.get("citations", {}) or {}
        for meta in citations.values():
            if not isinstance(meta, dict):
                continue
            if meta.get("source_type") == "curated_external_analysis_evidence":
                return True
        return False

    @classmethod
    def _is_main_analysis_display_allowed(cls, synthesis: Dict[str, Any]) -> bool:
        """Allow formal/professional display supplements, but not social/curated viewpoints."""
        citations = synthesis.get("citations", {}) or {}
        for meta in citations.values():
            if is_external_viewpoint_source(meta):
                return False
            if not is_formal_display_source(meta):
                return False
        return True

    @staticmethod
    def _truncate_title(title: Any, max_chars: int) -> str:
        text = str(title or "")
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3].rstrip() + "..."

    def _verified_claim_summary_section(self, summary: Any) -> str:
        """Render verified/supported claim verification rows as read-only facts."""
        rows = self._verified_claim_summary_rows(summary)
        if not rows:
            return ""

        lines = [
            "### 事实核验摘要",
            "",
            "> 以下展示 claim verification 结果，不新增编号引用，不直接参与综合评分或最终建议。",
            "",
            "| 结论 | 核验状态 | 支撑来源 | 置信度 |",
            "|------|----------|----------|--------|",
        ]
        for row in rows:
            status_label = self._status_display_label(row['status'])
            lines.append(
                f"| {row['claim_text']} | {status_label} | {row['source']} | {row['confidence']} |"
            )
        return "\n".join(lines)

    @staticmethod
    def _status_display_label(status: str) -> str:
        if status == "verified":
            return "已验证"
        if status == "supported":
            return "部分支持，非官方确认"
        return status

    def _verified_claim_summary_rows(self, summary: Any) -> List[Dict[str, str]]:
        if not isinstance(summary, dict):
            return []

        rows = []
        for bucket_names, status_label in (
            (("verified_claims", "verified"), "verified"),
            (("supported_claims", "supported"), "supported"),
        ):
            claims = self._claim_summary_bucket(summary, bucket_names)
            for claim in claims:
                if len(rows) >= MAX_VERIFIED_CLAIM_SUMMARY_ROWS:
                    return rows
                row = self._verified_claim_summary_row(claim, status_label)
                if row:
                    rows.append(row)
        return rows

    def _claim_summary_bucket(self, summary: Dict[str, Any], names: tuple) -> List[Any]:
        for name in names:
            if name not in summary:
                continue
            claims = summary.get(name, [])
            if isinstance(claims, list):
                return claims
        return []

    def _verified_claim_summary_row(self, claim: Any, expected_status: str) -> Dict[str, str]:
        if not isinstance(claim, dict):
            return {}

        status = claim.get("status") or claim.get("action") or expected_status
        if status != expected_status:
            return {}

        claim_text = self._clean_verified_claim_text(claim.get("claim_text", ""))
        if not claim_text:
            return {}

        return {
            "claim_text": self._escape_table_cell(claim_text),
            "status": expected_status,
            "source": self._escape_table_cell(
                self._verified_claim_source(claim.get("verified_by_titles"), expected_status)
            ),
            "confidence": self._verified_claim_confidence(claim.get("confidence")),
        }

    def _clean_verified_claim_text(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return self._strip_citation_markers(value).strip()

    def _verified_claim_source(self, titles: Any, status: str = "verified") -> str:
        fallback = "部分支持来源" if status == "supported" else "高信用来源"
        if not isinstance(titles, list):
            return fallback

        cleaned = []
        for title in titles:
            if not isinstance(title, str):
                continue
            text = self._strip_citation_markers(title)
            text = re.sub(r"https?://\S+", "", text)
            text = re.sub(r"\bAgentReach(?:\(web\))?\b", "", text, flags=re.IGNORECASE)
            text = re.sub(r"^\s*Title:\s*", "", text, flags=re.IGNORECASE)
            text = self._humanize_cninfo_pdf_title(text)
            text = text.replace("|", " ")
            text = re.sub(r"\s+", " ", text).strip(" -")
            if text:
                cleaned.append(text[:40])
            if len(cleaned) >= 2:
                break
        return "、".join(cleaned) if cleaned else fallback

    def _verified_claim_confidence(self, confidence: Any) -> str:
        if isinstance(confidence, (int, float)):
            return str(int(confidence)) if float(confidence).is_integer() else f"{confidence:.1f}"
        if isinstance(confidence, str):
            text = confidence.strip()
            return self._escape_table_cell(self._strip_citation_markers(text)) if text else "—"
        return "—"

    def _strip_citation_markers(self, text: str) -> str:
        text = re.sub(r"\[\^\d+\]", "", text)
        text = re.sub(r"\[\d+\]", "", text)
        # Also remove non-numeric markers such as [^supported] / [^needs_review].
        text = sanitize_citation_markers(text)
        return text

    def _escape_table_cell(self, text: str) -> str:
        return text.replace("|", "\\|")

    def _humanize_cninfo_pdf_title(self, title: str) -> str:
        match = re.search(r"\b(\d{8,})\.PDF\b", title, flags=re.IGNORECASE)
        if not match:
            return title
        announcement_id = match.group(1)
        return _CNINFO_PDF_TITLE_MAP.get(announcement_id, title)

    def _citations_section(self, title: str, citations: Dict) -> str:
        """报告末尾的全局引用汇总板块。"""
        lines = [f"## {title}", ""]
        if not citations:
            lines.append("*无引用信息*")
            lines.append("")
            return "\n".join(lines)

        lines.append(f"> 本报告共引用 **{len(citations)}** 条信息来源：")
        lines.append("")

        for ref_id in sorted(citations.keys()):
            meta = citations[ref_id]
            source = meta.get("source", "未知")
            author = meta.get("author", "")
            title_text = meta.get("title", "")
            url = meta.get("url", "")
            date = meta.get("date", "")
            parts = [f"[^{ref_id}]"]
            if source:
                parts.append(f"**{source}**")
            if author:
                parts.append(f"作者: {author}")
            if title_text:
                parts.append(f"《{title_text[:50]}》")
            if date:
                parts.append(date)
            line = " | ".join(parts)
            if url:
                line = f"{line} [{url}]"
            lines.append(f"- {line}")
        lines.append("")
        return "\n".join(lines)
