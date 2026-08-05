"""深度分析板块渲染器。"""

import json
import re
from typing import Any, Dict, List

try:
    from ...external_evidence import EXTERNAL_DISPLAY_TOPIC_ORDER, external_family_title
    from ...curated_external_display import attach_refs_to_sentence
    from ...deep_analysis_material_snapshot import (
        Chapter4ViewModel,
        ExternalTopicNarrative,
        MaterialRow,
        build_chapter4_view_model,
        build_deep_analysis_material_snapshot,
        is_informative_variable_title,
        select_annual_display_rows,
        select_incremental_external_display_rows,
        select_external_topic_narratives,
    )
    from ...synthesis_credit import citation_identity, sanitize_citation_markers
    from ...synthesis_source_policy import is_external_viewpoint_source, is_formal_display_source
    from .executive_summary_renderer import _build_pe_spread_facts, _sanitize_pe_spread_in_text
except ImportError:
    try:
        from scripts.utils.external_evidence import EXTERNAL_DISPLAY_TOPIC_ORDER, external_family_title
        from scripts.utils.curated_external_display import attach_refs_to_sentence
        from scripts.utils.deep_analysis_material_snapshot import (
            Chapter4ViewModel,
            ExternalTopicNarrative,
            MaterialRow,
            build_chapter4_view_model,
            build_deep_analysis_material_snapshot,
            is_informative_variable_title,
            select_annual_display_rows,
            select_incremental_external_display_rows,
            select_external_topic_narratives,
        )
        from scripts.utils.synthesis_credit import citation_identity, sanitize_citation_markers
        from scripts.utils.synthesis_source_policy import is_external_viewpoint_source, is_formal_display_source
        from scripts.utils.reporter.sections.executive_summary_renderer import _build_pe_spread_facts, _sanitize_pe_spread_in_text
    except ImportError:
        from utils.external_evidence import EXTERNAL_DISPLAY_TOPIC_ORDER, external_family_title
        from utils.curated_external_display import attach_refs_to_sentence
        from utils.deep_analysis_material_snapshot import (
            Chapter4ViewModel,
            ExternalTopicNarrative,
            MaterialRow,
            build_chapter4_view_model,
            build_deep_analysis_material_snapshot,
            is_informative_variable_title,
            select_annual_display_rows,
            select_incremental_external_display_rows,
            select_external_topic_narratives,
        )
        from utils.synthesis_credit import citation_identity, sanitize_citation_markers
        from utils.synthesis_source_policy import is_external_viewpoint_source, is_formal_display_source
        from reporter.sections.executive_summary_renderer import _build_pe_spread_facts, _sanitize_pe_spread_in_text


MAX_VERIFIED_CLAIM_SUMMARY_ROWS = 6
_CNINFO_PDF_TITLE_MAP: Dict[str, str] = {
    "1225145344": "2026年第一季度报告",
    "1225106812": "2026年第一季度业绩预告",
    "1225102392": "补缴税款及滞纳金事项公告",
    "1225362219": "2025年年度权益分派实施公告",
}
_EXTERNAL_DISPLAY_TOPIC_RANK = {
    title: index for index, title in enumerate(EXTERNAL_DISPLAY_TOPIC_ORDER)
}
_EXTERNAL_PARAGRAPH_CHAR_TARGET = 240


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

        deep_analysis_display = {}
        uses_curated_external_display = False
        if profile_name != "formal_medium":
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
        elif profile_name == "formal_medium":
            synthesis = ctx.get("synthesis") or {}
            curated_display = {}
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
        baseline_citations = synthesis.get("citations", {}) or {}
        chapter4_citation_offset = self._max_citation_id(baseline_citations)
        chapter4_view_model = None
        material_snapshot = None
        annual_material_rows = ()
        broker_material_rows = ()
        external_material_rows = ()
        external_topic_narratives = ()
        annual_citation_offset = chapter4_citation_offset
        external_citation_offset = chapter4_citation_offset
        if profile_name == "formal_medium":
            material_snapshot = ctx.get("deep_analysis_material_snapshot") or build_deep_analysis_material_snapshot(ctx)
            chapter4_view_model = ctx.get("chapter4_view_model") or build_chapter4_view_model(
                material_snapshot,
                profile,
            )
        elif profile_name == "formal_thin_external_rich":
            material_snapshot = ctx.get("deep_analysis_material_snapshot") or build_deep_analysis_material_snapshot(ctx)
            annual_material_rows, _ = select_annual_display_rows(
                row for row in material_snapshot.rows if row.source_layer == "annual"
            )
            broker_material_rows = tuple(
                row for row in material_snapshot.rows if row.source_layer == "broker"
            )
            broker_owner_rows = tuple(
                row for row in broker_material_rows if row.body and row.attribution
            )
            external_material_rows, _ = select_incremental_external_display_rows(
                material_snapshot.rows,
                material_snapshot.citations,
                (*annual_material_rows, *broker_owner_rows),
            )
            external_topic_narratives = select_external_topic_narratives(
                material_snapshot.external_topic_narratives,
                external_material_rows,
                (*annual_material_rows, *broker_owner_rows),
            )
        deep_md = self._deep_analysis(
            synthesis,
            ctx,
            profile=profile,
            chapter4_view_model=chapter4_view_model,
            chapter4_citation_offset=chapter4_citation_offset,
            curated_external_display=curated_display,
            curated_citation_offset=external_citation_offset,
            annual_citation_offset=annual_citation_offset,
            annual_material_rows=annual_material_rows,
            broker_material_rows=broker_material_rows,
            external_material_rows=external_material_rows,
            external_topic_narratives=external_topic_narratives,
        )
        pe_facts = _build_pe_spread_facts(ctx.get("peer_comparison_material"), ctx.get("stock_name", ""))
        deep_md = _sanitize_pe_spread_in_text(deep_md, pe_facts, ctx.get("stock_name", ""))
        deep_line_index = None
        if deep_md:
            lines.append(deep_md)
            deep_line_index = len(lines) - 1

        # 全局引用：baseline → deep-analysis material snapshot.
        # Snapshot citations contain only rows that are admitted into the
        # chapter-4 material read model, avoiding stale memo citation entries.
        if chapter4_view_model is not None:
            citations = {self._citation_key(k): v for k, v in (baseline_citations or {}).items()}
            citations.update(self._offset_citations(chapter4_view_model.citations, chapter4_citation_offset))
        elif material_snapshot is not None:
            citations = {self._citation_key(k): v for k, v in (baseline_citations or {}).items()}
            citations.update(self._offset_citations(material_snapshot.citations, self._max_citation_id(citations)))
        else:
            citations = self._merged_citations(
                baseline_citations,
                (curated_display or {}).get("citations", {}),
            )
        freshness_candidate = ((ctx.get("evidence_freshness") or {}).get("summary_candidate") or {})
        reserved_refs = tuple(int(ref) for ref in freshness_candidate.get("citation_refs") or () if str(ref).isdigit())
        reserved_citations = {ref: citations[ref] for ref in reserved_refs if ref in citations}
        if deep_line_index is not None and reserved_citations:
            lines[deep_line_index] = self._alias_reserved_citations(
                lines[deep_line_index], citations, reserved_citations
            )
        citations = self._visible_citations_only(citations, "\n".join(lines), reserved_refs=reserved_refs)
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
        for f in supportable_facts:
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
        chapter4_view_model: Chapter4ViewModel | None = None,
        chapter4_citation_offset: int = 0,
        curated_external_display: Dict[str, Any] | None = None,
        curated_citation_offset: int = 0,
        annual_citation_offset: int = 0,
        annual_material_rows: tuple[MaterialRow, ...] = (),
        broker_material_rows: tuple[MaterialRow, ...] = (),
        external_material_rows: tuple[MaterialRow, ...] = (),
        external_topic_narratives: tuple[ExternalTopicNarrative, ...] = (),
    ) -> str:
        """
        深度分析板块：根据 evidence profile 渲染不同布局。
        """
        profile = profile or {"profile": "formal_rich"}
        profile_name = profile.get("profile", "formal_rich")
        badge = self._profile_badge(profile_name)
        profile_json = json.dumps(profile, ensure_ascii=False)
        lines = ["## 四、深度分析", "", f"<!-- deep_analysis_profile: {profile_json} -->", "", f"> {badge}", ""]
        coverage = ctx.get("deep_analysis_material_coverage")
        if isinstance(coverage, dict) and coverage:
            coverage_json = json.dumps(coverage, ensure_ascii=False)
            lines[3:3] = [f"<!-- deep_analysis_material_coverage: {coverage_json} -->", ""]

        if profile_name == "formal_rich":
            lines.extend(self._legacy_deep_analysis_body(
                synthesis, ctx.get("claim_verification_summary"),
                curated_external_display=curated_external_display,
                curated_citation_offset=curated_citation_offset,
            ))
        elif profile_name == "formal_medium":
            if chapter4_view_model is None:
                raise ValueError("formal_medium requires Chapter4ViewModel")
            lines.extend(self._formal_medium_source_layer_body(
                chapter4_view_model,
                citation_offset=chapter4_citation_offset,
                preface=bool((ctx.get("evidence_freshness") or {}).get("preface")),
            ))
        elif profile_name == "formal_thin_external_rich":
            lines.extend(self._formal_thin_external_rich_body(
                ctx,
                annual_citation_offset=annual_citation_offset,
                annual_material_rows=annual_material_rows,
                broker_material_rows=broker_material_rows,
                external_material_rows=external_material_rows,
                external_topic_narratives=external_topic_narratives,
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

        curated_md = self._curated_external_addendum(curated_external_display, curated_citation_offset)
        if curated_md:
            lines.append(curated_md)
            lines.append("")

        return lines

    def _formal_medium_source_layer_body(
        self,
        view_model: Chapter4ViewModel,
        citation_offset: int = 0,
        preface: bool = False,
    ) -> List[str]:
        """Render formal-medium reports as source-layer-first analysis."""
        lines: List[str] = []

        lines.extend(["### 4.1 官方材料确认：业务与财务基座", ""])
        lines.extend(self._annual_material_profile_section(
            view_model.section("4.1").rows,
            citation_offset,
            fallback="当前未取得足够官方材料，无法形成业务与财务基座。",
            financial_label="财务基座",
        ))

        lines.extend(["### 4.2 机构观点与盈利假设", ""])
        lines.extend(self._formal_medium_broker_assumption_section(
            view_model.section("4.2").rows,
            citation_offset,
        ))

        external_section = view_model.section("4.3")
        external_map = self._formal_medium_external_variable_map(
            external_section.rows,
            citation_offset,
            external_section.disclaimer,
            preface=preface,
            narratives=external_section.narratives,
        )
        lines.extend(external_map or [
            "### 4.3 外部观察与待验证变量（Preview，不参与评分）",
            "",
            "> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或目标价。",
            "",
            "当前外部材料未提供相对正式材料或研报的新增待验证变量。",
            "",
        ])
        return lines

    def _annual_material_profile_section(
        self,
        material_rows: tuple[MaterialRow, ...],
        citation_offset: int = 0,
        *,
        fallback: str,
        financial_label: str = "财务变化原因",
    ) -> List[str]:
        """Format already-selected annual MaterialRows for Chapter 4.1."""
        lines: List[str] = []
        portrait = next((row for row in material_rows if row.editorial_slot == "portrait"), None)
        seen = set()
        if portrait:
            body = self._compact_annual_text(portrait.body, 140)
            seen.add(re.sub(r"\s+", "", body))
            refs = [ref + citation_offset for ref in portrait.citation_refs]
            lines.extend(["**一句话画像**", f"- {attach_refs_to_sentence(body, refs)}", ""])

        groups = (
            ("业务结构", {"business_structure"}),
            ("经营变化", {"operating_progress", "market_competition_outlook"}),
            ("研发与产品进展", {"technology_product_progress"}),
            (financial_label, {"financial_quality_explanation"}),
        )
        for label, roles in groups:
            rows = [row for row in material_rows if row.render_role in roles]
            if label == financial_label:
                rows.extend(row for row in material_rows if row.claim_status == "formal_fact" and row not in rows)
            visible = []
            for row in rows:
                body = self._compact_annual_text(row.body, 140)
                key = re.sub(r"\s+", "", body)
                if not key or key in seen:
                    continue
                seen.add(key)
                if (
                    label == financial_label
                    and is_informative_variable_title(row.title)
                    and row.title not in body
                    and "原因" not in body
                ):
                    body = f"{row.title}：{body}"
                visible.append((body, [ref + citation_offset for ref in row.citation_refs]))
            if visible:
                lines.extend([f"**{label}**"])
                lines.extend(f"- {attach_refs_to_sentence(body, refs)}" for body, refs in visible)
                lines.append("")
        return lines or [fallback, ""]

    def _formal_medium_broker_assumption_section(
        self,
        material_rows: tuple[MaterialRow, ...],
        citation_offset: int = 0,
    ) -> List[str]:
        """Render broker research as attributed assumptions, not official facts."""
        if not material_rows:
            return ["当前未取得足够可用研报 digest，不展开机构观点与盈利假设。", ""]

        rows: List[Dict[str, Any]] = []
        for material_row in material_rows:
            default_prefix = "研报提示" if material_row.render_role == "broker_risk" else (
                "研报预计" if material_row.render_role == "broker_forecast" else "研报认为"
            )
            view = self._normalize_broker_attribution(
                material_row.body,
                default_prefix=default_prefix,
                author="" if material_row.attribution == "研报" else material_row.attribution,
            )
            view = self._project_broker_assumption_view(view)
            rows.append({
                "assumption": "反方约束" if material_row.render_role == "broker_risk" else (
                    material_row.title or "机构核心观点"
                ),
                "view": view,
                "refs": [ref + citation_offset for ref in material_row.citation_refs],
            })

        lines: List[str] = []
        focus_titles = [row["assumption"] for row in rows if is_informative_variable_title(row["assumption"])]
        if focus_titles:
            lines.extend(["**机构关注重点**", f"- 研报重点关注{'、'.join(dict.fromkeys(focus_titles))}。", ""])
        lines.append("**关键盈利假设**")
        assumption_rows = [row for row in rows if row["assumption"] != "反方约束"]
        for row in assumption_rows:
            refs = row["refs"]
            view = attach_refs_to_sentence(self._compact_annual_text(row["view"], 320), refs)
            lines.append(f"- **{row['assumption']}**：{view}。")
        if not assumption_rows:
            lines.append("- 当前研报 digest 可用信息不足，不形成业绩假设，也不写成官方确认事实。")
        lines.append("")
        risk_rows = [row for row in rows if row["assumption"] == "反方约束"]
        if risk_rows:
            lines.extend(["**主要分歧 / 反方风险**"])
            for row in risk_rows:
                refs = row["refs"]
                lines.append(f"- {attach_refs_to_sentence(self._compact_annual_text(row['view'], 180), refs)}")
            lines.append("")
        return lines

    def _formal_medium_external_variable_map(
        self,
        material_rows: tuple[MaterialRow, ...],
        citation_offset: int = 0,
        disclaimer: str = "",
        preface: bool = False,
        heading: str = "### 4.3 外部观察与待验证变量（Preview，不参与评分）",
        narratives: tuple[ExternalTopicNarrative, ...] = (),
    ) -> List[str]:
        """Render curated external material as a compact variable map."""
        if not material_rows:
            return []

        lines = [
            heading,
            "",
            f"> {disclaimer}",
            "",
        ]
        if preface:
            lines.extend([
                "正式材料的时间点较早，以下近期外部观察仅补充订单、交付、成本、需求或产品验证等变量；不替代官方确认，不参与评分、风险评分或目标价。",
                "",
            ])
        for is_peer, scoped_rows in (
            (False, [row for row in material_rows if row.entity_scope != "peer_or_industry"]),
            (True, [row for row in material_rows if row.entity_scope == "peer_or_industry"]),
        ):
            if not scoped_rows:
                continue
            if is_peer:
                lines.extend([
                    "> **同业/行业背景（Preview）**：以下内容仅描述同业或行业背景，不代表目标公司已确认事实。",
                    "",
                ])
            grouped: Dict[str, List[MaterialRow]] = {}
            for row in scoped_rows:
                variable = row.title if row.title and row.title != "外部变量" else (
                    self._short_heading(row.body) or "外部变量"
                )
                variable = self._soften_external_unverified_terms(
                    re.sub(r"\s+", " ", str(variable or "")).strip(" ：:，,；;。")
                ) or "外部变量"
                grouped.setdefault(variable, []).append(row)
            ordered_groups = sorted(
                enumerate(grouped.items()),
                key=lambda item: (
                    _EXTERNAL_DISPLAY_TOPIC_RANK.get(item[1][0], len(_EXTERNAL_DISPLAY_TOPIC_RANK)),
                    item[0],
                ),
            )
            for _, (variable, rows) in ordered_groups:
                family = next((row.external_family for row in rows if row.external_family), "")
                narrative = next((item for item in narratives if (
                    item.scope_bucket == ("peer_or_industry" if is_peer else "target")
                    and item.primary_family == family
                )), None)
                if narrative is not None and not narrative.parts:
                    continue
                lines.extend([f"**{variable}**", ""])
                if narrative is not None:
                    lines.extend([self._external_topic_narrative_paragraph(narrative, variable, is_peer, citation_offset), ""])
                    continue
                verified_rows = [row for row in rows if row.evidence_status == "source_unit_verified"]
                if verified_rows:
                    paragraph = self._external_verified_rows_paragraph(
                        verified_rows, variable, is_peer, citation_offset,
                    )
                    if paragraph:
                        lines.extend([paragraph, ""])
                for row in rows:
                    if row.evidence_status == "source_unit_verified":
                        continue
                    refs = [ref + citation_offset for ref in row.citation_refs]
                    relation = "同业/行业背景观察：" if is_peer else (
                        "相对正式材料/机构假设，外部材料新增的待验证点："
                        if row.owner_relation == "owner_delta" else "外部新增待验证变量："
                    )
                    if row.external_claim:
                        claim = self._frame_external_claim(row.external_claim).removeprefix("外部材料称：")
                        lines.append(attach_refs_to_sentence(f"{relation}{claim.rstrip('。')}。", refs))
                        if row.external_evidence:
                            evidence_label = "外部原文依据" if row.evidence_status == "source_quote_verified" else "缓存材料摘录"
                            lines.extend(["", f"> **{evidence_label}**：{row.external_evidence}"])
                        lines.append("")
                        continue
                    for block in self._external_claim_blocks(self._external_claim_sentence(row.body, refs)):
                        lines.extend([block, ""])
        lines.append("")
        return lines

    @staticmethod
    def _external_topic_narrative_paragraph(
        narrative: ExternalTopicNarrative, variable: str, is_peer: bool, citation_offset: int,
    ) -> str:
        parts = [
            (part.quote, part.citation_refs, part.relation)
            for part in narrative.parts
        ]
        return DeepAnalysisRenderer._external_evidence_paragraph(
            parts, variable, is_peer, citation_offset,
        )

    @staticmethod
    def _external_verified_rows_paragraph(
        rows: List[MaterialRow], variable: str, is_peer: bool, citation_offset: int,
    ) -> str:
        parts = []
        for row in rows:
            for paragraph in (line.strip() for line in str(row.body or "").splitlines() if line.strip()):
                parts.append((paragraph, row.citation_refs, "first" if not parts else "continuation"))
        return DeepAnalysisRenderer._external_evidence_paragraph(
            parts, variable, is_peer, citation_offset,
        )

    @staticmethod
    def _external_evidence_paragraph(
        parts: list, variable: str, is_peer: bool, citation_offset: int,
    ) -> str:
        if not parts:
            return ""
        lead = (f"据外部材料，{variable}的同业/行业背景包括：" if is_peer
                else f"外部材料称，{variable}的新增待验证点包括：")
        paragraphs, current = [], lead
        for index, (raw_quote, citation_refs, relation) in enumerate(parts):
            quote = re.sub(r"[，,；;。！？!?：:]$", "", raw_quote.strip())
            cited = quote + "".join(f"[^{ref + citation_offset}]" for ref in dict.fromkeys(citation_refs))
            if index == 0:
                current += cited
            else:
                separator = "；"
                if relation == "continuation" and len(current) + len(separator) + len(cited) <= _EXTERNAL_PARAGRAPH_CHAR_TARGET:
                    current += separator + cited
                    continue
                paragraphs.append(f"{current}。")
                current = f"另据外部材料，{cited}"
        return "\n\n".join((*paragraphs, f"{current}。"))

    @staticmethod
    def _attach_external_refs_by_paragraph(text: str, refs: list, *, prefix: str = "") -> List[str]:
        paragraphs = [line.strip() for line in str(text or "").splitlines() if line.strip()]
        return [
            attach_refs_to_sentence(f"{prefix if index == 0 else ''}{paragraph}", refs)
            for index, paragraph in enumerate(paragraphs)
        ]

    def _formal_thin_external_rich_body(
        self,
        ctx: Dict[str, Any],
        annual_citation_offset: int = 0,
        annual_material_rows: tuple[MaterialRow, ...] = (),
        broker_material_rows: tuple[MaterialRow, ...] = (),
        external_material_rows: tuple[MaterialRow, ...] = (),
        external_topic_narratives: tuple[ExternalTopicNarrative, ...] = (),
    ) -> List[str]:
        """Render formal-thin layout: annual memo + broker placeholder + external map + checklist."""
        lines: List[str] = []
        lines.extend(["### 4.1 年报经营摘要", ""])
        lines.extend(self._annual_material_profile_section(
            annual_material_rows,
            annual_citation_offset,
            fallback="当前未取得足够年报材料，无法形成年报经营摘要。",
        ))
        lines.extend(["### 4.2 研报观点与假设", ""])
        lines.extend(self._formal_thin_broker_section(
            broker_material_rows,
            annual_citation_offset,
        ))
        map_md = self._formal_medium_external_variable_map(
            external_material_rows,
            citation_offset=annual_citation_offset,
            disclaimer="以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或目标价。",
            heading="### 4.3 外部观点与待验证变量（Preview，不参与评分）",
            preface=bool((ctx.get("evidence_freshness") or {}).get("preface")),
            narratives=external_topic_narratives,
        )
        lines.extend(map_md or [
            "### 4.3 外部观点与待验证变量（Preview，不参与评分）", "",
            "当前外部材料未提供相对正式材料或研报的新增待验证变量。", "",
        ])

        return lines

    def _formal_thin_broker_section(
        self,
        material_rows: tuple[MaterialRow, ...],
        citation_offset: int = 0,
    ) -> List[str]:
        """Render attributed professional assumptions from snapshot rows."""
        if not material_rows:
            return ["当前未取得足够可用研报 digest，不展开研报观点与假设。", ""]

        lines: List[str] = []
        if any(row.broker_memo_status == "single_institution" for row in material_rows):
            lines.extend(["**单篇研报观点 / 单机构观点**", ""])
        for row in material_rows:
            text = row.body.strip()
            refs = [ref + citation_offset for ref in row.citation_refs]
            author = "" if row.attribution in {"研报", "券商", "机构"} else row.attribution
            if row.render_role == "broker_assumption" and text:
                text = self._normalize_broker_attribution(
                    text,
                    default_prefix="研报认为",
                    author=author,
                )
                view = f"**{row.title}**：{text}" if row.title else text
                lines.append(f"- {attach_refs_to_sentence(view, refs)}")
            elif row.render_role == "broker_forecast":
                text = " ".join(filter(None, (row.broker_metric, row.broker_period, text)))
                prefix = f"{author}研报预计" if author else "研报预计"
                if text:
                    lines.append(f"- {attach_refs_to_sentence(f'{prefix}：{text}', refs)}")
            elif row.render_role == "broker_risk" and text:
                text = self._normalize_broker_attribution(
                    text,
                    default_prefix="研报提示",
                    author=author,
                )
                lines.append(f"- {attach_refs_to_sentence(text, refs)}")
        lines.append("")
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
    def _project_broker_assumption_view(text: str) -> str:
        value = re.sub(r"\s+", " ", str(text or "")).strip()
        if not value:
            return ""
        match = re.match(r"^(.{0,18}?研报(?:认为|预计|提示)|研报(?:认为|预计|提示))[：:]\s*(.+)$", value)
        if not match:
            return value
        prefix, body = match.group(1), match.group(2)
        projected = DeepAnalysisRenderer._clean_broker_assumption_body(body)
        return f"{prefix}：{projected}" if projected else value

    @staticmethod
    def _clean_broker_assumption_body(text: str) -> str:
        value = re.sub(r"\s+", " ", str(text or "")).strip(" ：:；;。")
        if not value:
            return ""
        value = re.sub(r"[▌•●]\s*", "", value)
        value = re.sub(r"^(?:业绩简评|经营分析|投资要点|事件|观点)[：:，,\s]*", "", value)
        value = re.sub(r"(?:(?<=^)|(?<=[。；;，,]))\s*(?:经营分析|投资要点|事件|观点|公司业务概况)[：:，,\s]*", "", value)
        value = re.sub(
            r"^20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日公司发布\s*20\d{2}\s*年[一二三四]季报[，,]\s*",
            "",
            value,
        )
        value = re.sub(
            r"^20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日[，,]\s*[^，,：:；;。]{0,18}?发布\s*20\d{2}\s*年[一二三四]季报[：:，,]\s*",
            "",
            value,
        )
        value = re.sub(r"(?<=预计)\s*20\s+(?=20\d{2}\s*年)", "", value)
        value = re.sub(r"(20\d{2})\s+年", r"\1年", value)
        value = re.sub(r"(?<=Q[1-4])\s*实现(?=(?:营业)?收入)", "", value)
        value = re.sub(r"(?<=Q[1-4])\s+(?=收入)", "", value)
        value = re.sub(r"(收入|营收|净利润|毛利率)\s+(\d)", r"\1\2", value)
        value = re.sub(r"(?<=\d)\s+(?=(?:亿元|%|pct|倍|G|T))", "", value)
        value = re.sub(r"\s*([，,；;。])\s*", r"\1", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip(" ：:；;。")

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
        return chunks[0].strip(" ；;。") if chunks else cleaned

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

    @staticmethod
    def _short_heading(text: str) -> str:
        heading = str(text or "").split("。", 1)[0].split("；", 1)[0].strip()
        return heading

    @staticmethod
    def _frame_external_claim(text: str) -> str:
        claim = re.sub(r"\s+", " ", str(text or "")).strip(" ，,；;。")
        if not claim:
            return ""
        claim = re.sub(
            r"^外部(?:材料|观点|文章|信息)?(?:称|认为|提示|讨论|指出|显示)[，,：:\s]*",
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
            r"^外部(?:材料|观点|文章|信息)?(?:称|认为|提示|讨论|指出|显示)[，,：:\s]*",
            "",
            variable,
        ).strip(" ：:，,；;。") or "外部变量"
        variable = DeepAnalysisRenderer._soften_external_unverified_terms(variable)
        claim_text = re.sub(r"\s+", " ", str(claim_text or "")).strip()
        if not claim_text:
            return
        lines.append(f"**{variable}**")
        for block in DeepAnalysisRenderer._external_claim_blocks(claim_text):
            lines.extend(["", block])
        lines.append("")

    @staticmethod
    def _external_claim_blocks(claim_text: str) -> List[str]:
        marker_match = re.search(r"(?P<markers>(?:\[\^\d+\])+)(?P<terminal>[。！？]?)$", claim_text)
        markers = marker_match.group("markers") if marker_match else ""
        terminal = marker_match.group("terminal") if marker_match else ""
        body = (claim_text[:marker_match.start()] + terminal).strip() if marker_match else claim_text
        prefix = "外部材料称：" if body.startswith("外部材料称：") else ""
        source_body = body[len(prefix):] if prefix else body
        clauses = re.findall(r"[^。！？；]+[。！？；]|[^。！？；]+$", source_body)
        seen = set()
        sentences = []
        pending = []
        for clause in clauses:
            normalized = re.sub(r"[\s，,。！？；;]+", "", clause)
            if normalized and normalized not in seen:
                seen.add(normalized)
                pending.append(clause)
                if clause.endswith(("。", "！", "？")):
                    sentences.append("".join(pending))
                    pending = []
        if pending:
            sentences.append("".join(pending))
        if not sentences:
            return [claim_text]
        blocks = []
        pending = []
        for sentence in sentences:
            if sentence.count("；") >= 2:
                if pending:
                    blocks.append("".join(pending).strip())
                    pending = []
                blocks.append(sentence.strip())
                continue
            pending.append(sentence)
            if len(pending) == 2:
                blocks.append("".join(pending).strip())
                pending = []
        if pending:
            blocks.append("".join(pending).strip())
        return [(prefix + block if prefix else block) + markers for block in blocks if block]

    @staticmethod
    def _soften_external_unverified_terms(text: str) -> str:
        softened = str(text or "")
        softened = softened.replace("后续订单落地情况", "后续订单进展")
        softened = softened.replace("订单落地情况", "订单进展")
        softened = softened.replace("订单落地", "订单进展")
        return softened

    def _curated_external_addendum(
        self,
        curated_display: Dict[str, Any] | None,
        citation_offset: int = 0,
    ) -> str:
        cards = (curated_display or {}).get("_curated_external_argument_cards") or []
        if not cards or not self._has_curated_external_citation(curated_display):
            return ""

        lines = [
            "### 4.4 外部观点与待验证变量（Preview）",
            "",
            "> 精选外部材料仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。",
            "",
        ]
        used_refs = {
            int(ref) + citation_offset
            for card in cards if isinstance(card, dict)
            for ref in card.get("citation_refs") or [] if str(ref).isdigit()
        }
        shifted_citations = self._offset_citations(curated_display.get("citations", {}) or {}, citation_offset)
        ref_map = self._curated_external_display_ref_map(shifted_citations, used_refs)
        ordered_cards = sorted(
            (card for card in cards if isinstance(card, dict)),
            key=lambda card: str(card.get("entity_scope") or "") == "peer_or_industry",
        )
        peer_section_started = False
        for card in ordered_cards:
            is_peer = str(card.get("entity_scope") or "") == "peer_or_industry"
            if is_peer and not peer_section_started:
                lines.extend([
                    "> **同业/行业背景（Preview）**：以下内容仅描述同业或行业背景，不代表目标公司已确认事实。", "",
                ])
                peer_section_started = True
            refs = [
                ref_map.get(int(ref) + citation_offset, int(ref) + citation_offset)
                for ref in card.get("citation_refs") or [] if str(ref).isdigit()
            ]
            evidence = "\n".join(
                str(unit.get("text") or "").strip()
                for unit in card.get("evidence_units") or []
                if isinstance(unit, dict) and str(unit.get("text") or "").strip()
            )
            rendered = self._attach_external_refs_by_paragraph(evidence, refs)
            if not rendered:
                continue
            family = str(card.get("primary_family") or "").strip()
            lines.extend([f"**{external_family_title(family, '外部待验证变量')}**", ""])
            for paragraph in rendered:
                lines.extend([paragraph, ""])

        return "\n".join(lines)

    @staticmethod
    def _curated_external_display_ref_map(shifted_citations: Dict[int, Any], used_refs: set) -> dict:
        canonical_by_key = {}
        ref_map = {}
        for ref_id in sorted(used_refs):
            meta = shifted_citations.get(ref_id, {})
            key = citation_identity(meta)
            if not key:
                canonical = ref_id
            elif key in canonical_by_key:
                canonical = canonical_by_key[key]
            else:
                canonical_by_key[key] = ref_id
                canonical = ref_id
            ref_map[ref_id] = canonical
        return ref_map

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
    def _visible_citations_only(citations: Dict, body_text: str, reserved_refs=()) -> Dict:
        if not citations:
            return {}
        visible_refs = {
            int(ref)
            for ref in re.findall(r"\[\^(\d+)\]", body_text or "")
        }
        visible_refs.update(int(ref) for ref in reserved_refs if str(ref).isdigit())
        return {
            ref_id: meta
            for ref_id, meta in (citations or {}).items()
            if isinstance(ref_id, int) and ref_id in visible_refs
        }

    @staticmethod
    def _alias_reserved_citations(body_text: str, citations: Dict, reserved_citations: Dict) -> str:
        identity_to_reserved = {
            citation_identity(meta, fallback_ref=ref): ref
            for ref, meta in reserved_citations.items()
        }

        def replace(match):
            ref = int(match.group(1))
            meta = citations.get(ref)
            target = identity_to_reserved.get(citation_identity(meta, fallback_ref=ref))
            return f"[^{target}]" if target is not None else match.group(0)

        return re.sub(r"\[\^(\d+)\]", replace, body_text or "")

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
