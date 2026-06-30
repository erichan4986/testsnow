"""深度分析板块渲染器。"""

import re
from typing import Any, Dict, List

try:
    from ...synthesis_credit import sanitize_citation_markers
    from ...synthesis_source_policy import is_external_viewpoint_source, is_formal_display_source
except ImportError:
    try:
        from scripts.utils.synthesis_credit import sanitize_citation_markers
        from scripts.utils.synthesis_source_policy import is_external_viewpoint_source, is_formal_display_source
    except ImportError:
        from utils.synthesis_credit import sanitize_citation_markers
        from utils.synthesis_source_policy import is_external_viewpoint_source, is_formal_display_source


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
CURATED_EXTERNAL_TOPIC_ALIASES = {
    "supply_delivery_capacity": "order_capacity_delivery",
    "order_capacity": "order_capacity_delivery",
    "delivery_capacity": "order_capacity_delivery",
    "technology_route": "technology_route",
    "tech_route": "technology_route",
    "industry_logic": "technology_route",
    "financial_quality": "financial_quality",
    "fundamentals": "financial_quality",
    "earnings_quality": "financial_quality",
    "competition_commercialization": "competition_commercialization",
    "commercialization": "competition_commercialization",
    "market_expectation": "market_expectation",
    "capital_market": "market_expectation",
    "risk_rumor_rebuttal": "risk_rumor_rebuttal",
    "watch_variable": "risk_rumor_rebuttal",
    "dissent": "risk_rumor_rebuttal",
}

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
        deep_analysis_display = ctx.get("deep_analysis_display") or {}
        uses_curated_external_display = self._has_curated_external_citation(deep_analysis_display)
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
        if not stock_name or not synthesis:
            return ""

        core_facts = ctx.get("core_facts", [])
        lines = []

        # 核心事实基座
        core_facts_md = self._core_facts_table(core_facts)
        if core_facts_md:
            lines.append(core_facts_md)

        # 深度分析
        deep_md = self._deep_analysis(
            stock_name,
            synthesis,
            ctx.get("claim_verification_summary"),
            curated_external_display=curated_display if uses_curated_external_display else None,
            curated_citation_offset=self._max_citation_id(synthesis.get("citations", {}) or {}),
        )
        if deep_md:
            lines.append(deep_md)

        # 全局引用
        citations = self._merged_citations(
            synthesis.get("citations", {}) or {},
            curated_display.get("citations", {}) if uses_curated_external_display else {},
        )
        if citations:
            lines.append(self._citations_section("引用来源", citations))

        return "\n".join(lines)

    def _core_facts_table(self, core_facts: List[Dict]) -> str:
        """渲染核心事实基座表格。"""
        if not core_facts:
            return ""

        # Phase 1: only facts with at least one accepted citation are shown as a
        # supportable base.  Rows that are entirely invalid_ref / missing_ref are
        # not presented as a "core facts base".
        supportable_statuses = {"supported", "partially_supported"}
        supportable_facts = [
            f for f in core_facts
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
        for f in core_facts:
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
        stock_name: str,
        synthesis: Dict[str, str],
        claim_verification_summary: Any = None,
        curated_external_display: Dict[str, Any] | None = None,
        curated_citation_offset: int = 0,
    ) -> str:
        """
        深度分析板块：合并原5个合成板块为3个子板块。
        4.1 产业逻辑与竞争格局
        4.2 业绩路径与多空分歧
        4.3 资金面与催化剂时间线
        """
        citations = synthesis.get("citations", {})
        lines = ["## 四、深度分析", ""]

        verified_summary = self._verified_claim_summary_section(claim_verification_summary)
        if verified_summary:
            lines.append(verified_summary)
            lines.append("")

        # 4.1 产业逻辑与竞争格局
        industry_logic = synthesis.get("industry_logic", "")
        if industry_logic:
            lines.extend([
                "### 4.1 产业逻辑与竞争格局",
                "",
                industry_logic,
                "",
            ])
            used_refs = set(int(m) for m in re.findall(r"\[\^(\d+)\]", industry_logic))
            if used_refs:
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
                    lines.append(line)
                lines.append("")

        # 4.2 业绩路径与多空分歧
        fundamentals = synthesis.get("fundamentals", "")
        valuation_debate = synthesis.get("valuation_debate", "")
        if fundamentals or valuation_debate:
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

            used_refs = set()
            used_refs.update(int(m) for m in re.findall(r"\[\^(\d+)\]", fundamentals))
            used_refs.update(int(m) for m in re.findall(r"\[\^(\d+)\]", valuation_debate))
            if used_refs:
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
                    lines.append(line)
                lines.append("")

        # 4.3 资金面与催化剂时间线
        funding = synthesis.get("funding_sentiment", "")
        events = synthesis.get("events_catalysts", "")
        if funding or events:
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

            used_refs = set()
            used_refs.update(int(m) for m in re.findall(r"\[\^(\d+)\]", funding))
            used_refs.update(int(m) for m in re.findall(r"\[\^(\d+)\]", events))
            if used_refs:
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
                    lines.append(line)
                lines.append("")

        curated_md = self._curated_external_addendum(curated_external_display, curated_citation_offset)
        if curated_md:
            lines.append(curated_md)
            lines.append("")

        return "\n".join(lines)

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
            lines.append("**本节引用来源：**")
            for ref_id in sorted(used_refs):
                meta = shifted_citations.get(ref_id, {})
                source = meta.get("source", "未知")
                author = meta.get("author", "")
                title_text = meta.get("title", "")
                url = meta.get("url", "")
                line = f"- [^{ref_id}] {source}"
                if author:
                    line += f" | 作者: {author}"
                if title_text:
                    line += f" | 《{self._truncate_title(title_text, 40)}》"
                if url:
                    line += f" | {url}"
                lines.append(line)
        return "\n".join(lines)

    def _curated_external_narrative_addendum(
        self,
        curated_display: Dict[str, Any],
        citation_offset: int,
        lines: List[str],
    ) -> str:
        paragraphs = curated_display.get("_curated_external_narrative_paragraphs") or []
        used_refs = self._curated_external_used_refs_from_rows(paragraphs, citation_offset)
        shifted_citations = self._offset_citations(curated_display.get("citations", {}) or {}, citation_offset)
        ref_map, display_refs = self._curated_external_display_ref_map(shifted_citations, used_refs)

        for paragraph in paragraphs:
            if not isinstance(paragraph, dict):
                continue
            heading = str(paragraph.get("heading") or "").strip()
            text = str(paragraph.get("text") or "").strip()
            citation_refs = paragraph.get("citation_refs") or []
            rendered = self._attach_refs_to_sentence(text, citation_refs)
            rendered = self._offset_citation_markers(rendered, citation_offset)
            rendered = self._remap_citation_markers(rendered, ref_map)
            if heading:
                lines.append(f"**{heading}**")
                lines.append("")
            if rendered:
                lines.append(rendered)
                lines.append("")

        if display_refs:
            lines.append("**本节引用来源：**")
            for ref_id in sorted(display_refs):
                meta = shifted_citations.get(ref_id, {})
                source = meta.get("source", "未知")
                author = meta.get("author", "")
                title_text = meta.get("title", "")
                url = meta.get("url", "")
                line = f"- [^{ref_id}] {source}"
                if author:
                    line += f" | 作者: {author}"
                if title_text:
                    line += f" | 《{self._truncate_title(title_text, 40)}》"
                if url:
                    line += f" | {url}"
                lines.append(line)
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
                rendered = self._attach_refs_to_sentence(text, citation_refs)
                rendered = self._offset_citation_markers(rendered, citation_offset)
                rendered = self._remap_citation_markers(rendered, ref_map)
                if heading:
                    lines.append(f"**{heading}**")
                    lines.append("")
                if rendered:
                    lines.append(rendered)
                    lines.append("")

        if display_refs:
            lines.append("**本节引用来源：**")
            for ref_id in sorted(display_refs):
                meta = shifted_citations.get(ref_id, {})
                source = meta.get("source", "未知")
                author = meta.get("author", "")
                title_text = meta.get("title", "")
                url = meta.get("url", "")
                line = f"- [^{ref_id}] {source}"
                if author:
                    line += f" | 作者: {author}"
                if title_text:
                    line += f" | 《{self._truncate_title(title_text, 40)}》"
                if url:
                    line += f" | {url}"
                lines.append(line)
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

    def _topic_groups_from_paragraphs(self, paragraphs: List[Any]) -> Dict[str, List[dict]]:
        groups = {key: [] for key, _ in CURATED_EXTERNAL_TOPIC_LABELS}
        for paragraph in paragraphs:
            if not isinstance(paragraph, dict):
                continue
            topic_key = self._curated_external_topic_key(paragraph)
            if not topic_key:
                topic_key = "other"
            groups.setdefault(topic_key, []).append(paragraph)
        return {key: rows for key, rows in groups.items() if rows}

    @classmethod
    def _curated_external_topic_key(cls, row: Dict[str, Any]) -> str:
        raw_topic = str(row.get("topic") or row.get("primary_topic") or "").strip()
        if raw_topic:
            alias = CURATED_EXTERNAL_TOPIC_ALIASES.get(raw_topic)
            if alias:
                return alias
            if raw_topic.lower() in {"misc", "other", "unknown", "uncategorized"}:
                return "other"

        text = " ".join(
            str(row.get(field) or "")
            for field in ("topic", "primary_topic", "heading", "text", "claim", "why_incremental")
        )
        lower_text = text.lower()
        if any(token in text for token in ("传言", "否认", "制裁", "清单", "反证", "回应", "1260H")):
            return "risk_rumor_rebuttal"
        if any(token in text for token in ("预付款", "交付", "产能", "订单", "供应链", "物料", "客户需求", "需求指引")):
            return "order_capacity_delivery"
        if any(token in text for token in ("NPO", "XPO", "CPO", "LPO", "硅光", "可插拔", "光进铜退", "技术路线")):
            return "technology_route"
        if any(token in text for token in ("营收", "利润", "毛利率", "费用", "现金流", "亏损", "研发开支")):
            return "financial_quality"
        if any(token in text for token in ("竞争", "商业化", "定点", "标杆车型", "市场份额", "客户拓展")):
            return "competition_commercialization"
        if any(token in text for token in ("估值", "股价", "市值", "资金", "情绪", "预期差", "机构持仓", "IPO")):
            return "market_expectation"
        if any(token in lower_text for token in ("capex", "800g", "1.6t", "scale up", "scale out")):
            return "technology_route"
        return "other"

    @staticmethod
    def _attach_refs_to_sentence(text: str, refs: list) -> str:
        unique_refs = []
        seen = set()
        for ref in refs:
            if not str(ref).isdigit():
                continue
            ref_id = int(ref)
            if ref_id in seen:
                continue
            seen.add(ref_id)
            unique_refs.append(ref_id)
        ref_text = "".join(f"[^{ref_id}]" for ref_id in unique_refs)
        stripped = str(text or "").strip()
        if not ref_text:
            return stripped
        if stripped.endswith(("。", "；", ";", "！", "？")):
            return f"{stripped[:-1]}{ref_text}{stripped[-1]}"
        return f"{stripped}{ref_text}"

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
