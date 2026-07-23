"""Report assembly skill."""

import json
import logging
import re
from pathlib import Path

if __name__.startswith("utils."):
    from ..skill_pipeline import BaseSkill, SkillContext
    from ..reporter.constants import COMPETITOR_MAP, INDUSTRY_MAP
    from ..reporter.chart_generator import generate_decision_chain_chart
    from ..reporter.executive_summary_view import build_executive_summary_view
else:
    from skill_pipeline import BaseSkill, SkillContext
    from reporter.constants import COMPETITOR_MAP, INDUSTRY_MAP
    from reporter.chart_generator import generate_decision_chain_chart
    from reporter.executive_summary_view import build_executive_summary_view

logger = logging.getLogger(__name__)

HEADER_TEMPLATE = """# {stock_name} 舆情深度报告

**报告日期**: {date_display}
**所属赛道**: {industry}
**可比公司**: {competitors}
**数据来源**: {data_sources}

---"""

FOOTER_TEMPLATE = """---

*本报告基于公开数据、技术指标、规则评分与可选 LLM 综合分析生成，仅供参考，不构成投资建议。*
*报告生成时间: {date_display}*
"""


class ReportAssemblySkill(BaseSkill):
    """Markdown + HTML Dashboard 组装。直接调用 SectionRenderers 生成报告。"""
    name = "report_assembly"

    RENDERERS = [
        ("executive_summary", "utils.reporter.sections.executive_summary_renderer", "ExecutiveSummaryRenderer"),
        ("composite_score", "utils.reporter.sections.composite_score_renderer", "CompositeScoreRenderer"),
        ("valuation", "utils.reporter.sections.valuation_renderer", "ValuationRenderer"),
        ("technical", "utils.reporter.sections.technical_renderer", "TechnicalRenderer"),
        ("deep_analysis", "utils.reporter.sections.deep_analysis_renderer", "DeepAnalysisRenderer"),
        ("source_intake_evidence", "utils.reporter.sections.source_intake_evidence_renderer", "SourceIntakeEvidenceRenderer"),
        ("curated_external_analysis", "utils.reporter.sections.curated_external_analysis_renderer", "CuratedExternalAnalysisRenderer"),
        ("agent_reach_evidence", "utils.reporter.sections.agent_reach_evidence_renderer", "AgentReachEvidenceRenderer"),
        ("risk", "utils.reporter.sections.risk_renderer", "RiskRenderer"),
    ]

    def run(self, ctx: SkillContext) -> SkillContext:
        """组装 Markdown + HTML Dashboard。"""
        stock_name = ctx.get("stock_name")
        output_dir = ctx.get("output_dir")
        date_str = ctx.get("date_str")

        md_content = self._assemble_markdown(ctx)
        html_content = self._assemble_html(ctx)

        md_path = Path(output_dir) / f"{stock_name}_{date_str}.md"
        html_path = Path(output_dir) / f"{stock_name}_{date_str}.html"

        md_path.write_text(md_content, encoding="utf-8")
        html_path.write_text(html_content, encoding="utf-8")

        ctx.set("md_path", str(md_path))
        ctx.set("html_path", str(html_path))

        self._persist_industry_relevance_manifest(ctx, output_dir, stock_name, date_str)
        self._persist_agent_reach_audit(ctx, output_dir, stock_name, date_str)
        self._persist_peer_comparison_material(ctx, output_dir, stock_name, date_str)
        self._persist_fundflow_material(ctx, output_dir, stock_name, date_str)
        return ctx

    def _persist_industry_relevance_manifest(self, ctx: SkillContext, output_dir: str, stock_name: str, date_str: str) -> None:
        """Persist industry relevance chain sidecar for report quality checks."""
        manifest = ctx.get("industry_relevance_manifest")
        if not isinstance(manifest, dict):
            return
        chains = manifest.get("events_catalysts_chains") or []
        if not chains:
            return
        try:
            manifest_path = Path(output_dir) / f"{stock_name}_{date_str}_industry_relevance_manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            ctx.set("industry_relevance_manifest_path", str(manifest_path))
            logger.info(f"Industry relevance manifest persisted: {manifest_path}")
        except Exception as e:
            logger.warning(f"Industry relevance manifest persistence failed: {e}")

    def _persist_agent_reach_audit(self, ctx: SkillContext, output_dir: str, stock_name: str, date_str: str) -> None:
        """Persist compact Agent-Reach audit summary to sidecar JSON."""
        if not ctx.get("agent_reach_enabled", False):
            return
        summary = ctx.get("agent_reach_run_summary")
        if not summary:
            return
        try:
            audit_path = Path(output_dir) / f"{stock_name}_{date_str}_agent_reach.json"
            audit_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            ctx.set("agent_reach_audit_path", str(audit_path))
            logger.info(f"Agent-Reach audit persisted: {audit_path}")
        except Exception as e:
            logger.warning(f"Agent-Reach audit persistence failed: {e}")

    def _persist_peer_comparison_material(self, ctx: SkillContext, output_dir: str, stock_name: str, date_str: str) -> None:
        """Persist peer comparison material sidecar for report quality checks."""
        material = ctx.get("peer_comparison_material")
        if not isinstance(material, dict):
            return
        rows = material.get("rows") or []
        if not rows:
            return
        try:
            material_path = Path(output_dir) / f"{stock_name}_{date_str}_peer_comparison_material.json"
            material_path.write_text(
                json.dumps(material, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            ctx.set("peer_comparison_material_path", str(material_path))
            logger.info(f"Peer comparison material persisted: {material_path}")
        except Exception as e:
            logger.warning(f"Peer comparison material persistence failed: {e}")

    def _persist_fundflow_material(self, ctx: SkillContext, output_dir: str, stock_name: str, date_str: str) -> None:
        """Persist deterministic fund-flow material sidecar for audit checks."""
        material = ctx.get("fundflow_material_pack")
        if not isinstance(material, dict):
            return
        rows = material.get("rows") or []
        if not rows:
            return
        try:
            material_path = Path(output_dir) / f"{stock_name}_{date_str}_fundflow_material.json"
            material_path.write_text(
                json.dumps(material, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            ctx.set("fundflow_material_path", str(material_path))
            logger.info(f"Fund-flow material persisted: {material_path}")
        except Exception as e:
            logger.warning(f"Fund-flow material persistence failed: {e}")

    def _header(self, ctx: SkillContext) -> str:
        stock_name = ctx.get("stock_name", "")
        date_str = ctx.get("date_str", "")
        date_display = f"{date_str[:4]}年{date_str[4:6]}月{date_str[6:]}日" if len(date_str) == 8 else date_str
        stock_config = ctx.get("stock_config", {}) or {}
        industry = stock_config.get("industry") or INDUSTRY_MAP.get(stock_name, "—")
        configured_competitors = stock_config.get("competitors")
        if isinstance(configured_competitors, list) and configured_competitors:
            competitor_names = configured_competitors
        else:
            competitor_names = COMPETITOR_MAP.get(stock_name, [])
        competitors = "、".join(str(name) for name in competitor_names if name) or "—"
        data_sources = self._data_sources(ctx)
        return HEADER_TEMPLATE.format(
            stock_name=stock_name,
            date_display=date_display,
            industry=industry,
            competitors=competitors,
            data_sources=data_sources,
        )

    def _data_sources(self, ctx: SkillContext) -> str:
        stock_raw = ctx.get("stock_raw", {}) or {}
        sources = []

        if ctx.get("all_posts"):
            sources.append("雪球/社区讨论")
        if ctx.get("synthesis_sources"):
            sources.extend(ctx.get("synthesis_sources", []))
        if stock_raw.get("technical") or ctx.get("technical"):
            sources.append("技术行情数据")
        if stock_raw.get("reports"):
            sources.append("券商研报")
        if stock_raw.get("announcements"):
            sources.append("公司公告")
        if stock_raw.get("fundflow"):
            sources.append("资金流向")
        if stock_raw.get("news"):
            sources.append("新闻资讯")
        if ctx.get("quote"):
            sources.append("实时行情/估值")

        ar_enabled = ctx.get("agent_reach_enabled", False)
        ar_quality_status = ctx.get("agent_reach_quality_status", "")
        ar_keep = ctx.get("agent_reach_keep_items", []) or []
        ar_demote = ctx.get("agent_reach_demote_items", []) or []
        if ar_enabled and ar_quality_status == "ok" and (ar_keep or ar_demote):
            sources.append("Agent-Reach外部检索")

        seen = set()
        unique = []
        for source in sources:
            if source and source not in seen:
                unique.append(source)
                seen.add(source)
        return "、".join(unique) if unique else "—"

    def _footer(self, ctx: SkillContext) -> str:
        date_str = ctx.get("date_str", "")
        date_display = f"{date_str[:4]}年{date_str[4:6]}月{date_str[6:]}日" if len(date_str) == 8 else date_str
        return FOOTER_TEMPLATE.format(date_display=date_display)

    def _render_section(self, name: str, module_path: str, class_name: str, ctx: SkillContext) -> str:
        try:
            module = __import__(module_path, fromlist=[class_name])
            renderer_cls = getattr(module, class_name)
        except Exception as e:
            logger.error(f"[{name}] 无法导入渲染器 {module_path}.{class_name}: {e}")
            return f"<!-- {name}: renderer import failed ({e}) -->"

        required = []
        try:
            required = renderer_cls.required_keys()
        except Exception:
            pass

        missing = [k for k in required if ctx.get(k) is None]
        if missing:
            logger.warning(f"[{name}] 跳过渲染，缺少键: {missing}")
            return f"<!-- {name}: skipped (missing keys: {', '.join(missing)}) -->"

        try:
            renderer = renderer_cls()
            return renderer.render(ctx)
        except Exception as e:
            logger.error(f"[{name}] 渲染失败: {e}")
            return f"<!-- {name}: rendering failed ({e}) -->"

    def _assemble_markdown(self, ctx: SkillContext) -> str:
        # Build central recommendation decision before any renderer runs so that
        # summary, section 1, and risk section all read the same source of truth.
        try:
            from utils.reporter.recommendation_decision import (
                DisplayOnlyExternalRiskSignal,
                build_recommendation_decision,
            )
        except ImportError:
            try:
                from reporter.recommendation_decision import (
                    DisplayOnlyExternalRiskSignal,
                    build_recommendation_decision,
                )
            except Exception as e:
                logger.warning(f"无法导入 recommendation_decision: {e}")
                DisplayOnlyExternalRiskSignal = None
                build_recommendation_decision = None

        if build_recommendation_decision is not None:
            display_only_risks = self._collect_display_only_external_risks(
                ctx, DisplayOnlyExternalRiskSignal
            )

            pillar = ctx.get("pillar")
            if pillar is None:
                pillar = ctx.get("pillar_scores")
            try:
                decision = build_recommendation_decision(
                    stock_name=ctx.get("stock_name", ""),
                    posts=ctx.get("keep_posts") or ctx.get("posts") or [],
                    stock_raw=ctx.get("stock_raw", {}),
                    quote=ctx.get("quote"),
                    consensus=ctx.get("consensus"),
                    industry_fwd_pe=ctx.get("industry_fwd_pe"),
                    pillar=pillar,
                    synthesis_text=ctx.get("synthesis_text", ""),
                    structured_risk_signals=ctx.get("structured_risk_signals", []) or [],
                    score_llm_keyword_risks=bool(ctx.get("score_llm_keyword_risks", False)),
                    display_only_external_risks=display_only_risks,
                )
                ctx.set("recommendation_decision", decision)
            except Exception as e:
                logger.warning(f"构建 RecommendationDecision 失败: {e}")

        self._prepare_executive_summary(ctx)

        sections = [self._header(ctx)]
        citation_appendix = ""

        for name, module_path, class_name in self.RENDERERS:
            rendered = self._render_section(name, module_path, class_name, ctx)
            if "本节引用来源" in rendered:
                raise ValueError("citation appendix ownership: local source list remains")
            if name == "deep_analysis":
                rendered, citation_appendix = self._detach_global_citation_section(rendered)
            elif re.search(r"(?m)^## 引用来源[ \t]*$", rendered):
                raise ValueError(f"citation appendix ownership: {name} emitted global sources")
            sections.append(rendered)

        sections.append(citation_appendix)
        sections.append(self._footer(ctx))

        return "\n\n".join(s for s in sections if s)

    @staticmethod
    def _detach_global_citation_section(markdown: str) -> tuple[str, str]:
        matches = list(re.finditer(r"(?m)^## 引用来源[ \t]*$", markdown or ""))
        if not matches:
            return markdown, ""
        if len(matches) > 1:
            raise ValueError("multiple global citation sections")
        start = matches[0].start()
        return markdown[:start].rstrip(), markdown[start:].strip()

    @staticmethod
    def _prepare_executive_summary(ctx: SkillContext) -> None:
        """Build one summary view and optionally materialize its primary image."""
        view = build_executive_summary_view(ctx)
        ctx.set("executive_summary_view", view)
        chart_paths = dict(ctx.get("chart_paths", {}) or {})
        chart_paths["executive_summary"] = None
        output_dir = ctx.get("output_dir")
        if view.image_ready and output_dir and view.stock_name and view.date_str:
            output_path = Path(output_dir) / f"{view.stock_name}_{view.date_str}_decision.png"
            try:
                chart_paths["executive_summary"] = generate_decision_chain_chart(
                    view, output_path
                )
            except Exception as e:
                logger.warning(f"执行摘要决策链图片生成失败，使用文字回退: {e}")
        ctx.set("chart_paths", chart_paths)

    @classmethod
    def _collect_display_only_external_risks(cls, ctx: SkillContext, signal_cls) -> list:
        """Collect structured display-only risk metadata without scanning rendered Markdown."""
        risks = []
        seen = set()

        def append_signal(name: str, source_kind: str = "", evidence_text: str = "") -> None:
            name = " ".join(str(name or "").split())[:80]
            if not name:
                return
            key = (name, source_kind)
            if key in seen:
                return
            seen.add(key)
            risks.append(
                signal_cls(
                    name=name,
                    source_kind=str(source_kind or ""),
                    evidence_text=str(evidence_text or ""),
                )
            )

        raw_risks = ctx.get("display_only_external_risks") or []
        if isinstance(raw_risks, list):
            for risk in raw_risks:
                if isinstance(risk, signal_cls):
                    append_signal(risk.name, risk.source_kind, risk.evidence_text)
                elif isinstance(risk, dict):
                    append_signal(
                        risk.get("name") or risk.get("title") or "",
                        risk.get("source_kind", ""),
                        risk.get("evidence_text", "") or risk.get("content", ""),
                    )

        for item in (ctx.get("curated_external_analysis_items") or []):
            if not isinstance(item, dict):
                continue
            if bool(item.get("display_only_risk_signal") or item.get("risk_observation")):
                append_signal(
                    item.get("title") or item.get("name") or "",
                    item.get("source_kind", ""),
                    item.get("content", ""),
                )

        for display_key in ("deep_analysis_display", "synthesis_display"):
            display = ctx.get(display_key) or {}
            if not isinstance(display, dict):
                continue

            for card in display.get("_curated_external_argument_cards") or []:
                if cls._is_structured_external_risk_row(card):
                    append_signal(
                        card.get("primary_family") or "外部待验证变量",
                        "curated_external_argument",
                        " ".join(str(unit.get("text") or "") for unit in card.get("evidence_units") or []),
                    )

        return risks

    @staticmethod
    def _is_structured_external_risk_row(row: object) -> bool:
        """Classify structured curated-external rows without reading final Markdown text."""
        if not isinstance(row, dict):
            return False
        if bool(row.get("display_only_risk_signal") or row.get("risk_observation")):
            return True

        topic = str(
            row.get("primary_family") or row.get("topic_family") or row.get("topic") or row.get("primary_topic") or ""
        ).strip()
        claim_type = str(row.get("claim_type") or "").strip()
        risk_topics = {"risk_rumor_rebuttal", "financial_quality", "capacity_delivery", "policy_geopolitics"}
        risk_claim_types = {"dissent"}
        if topic in risk_topics or claim_type in risk_claim_types:
            return True

        # Use structured labels only (heading/topic/title), never rendered 4.4 prose.
        label_text = " ".join(
            str(row.get(field) or "")
            for field in ("heading", "topic", "primary_topic", "title")
        )
        risk_terms = (
            "风险",
            "传闻",
            "疑虑",
            "预警",
            "警惕",
            "承压",
            "收缩",
            "约束",
            "限制",
            "挑战",
            "分歧",
            "不确定",
            "缺乏",
            "下调",
            "压力",
        )
        return any(term in label_text for term in risk_terms)

    def _assemble_html(self, ctx: SkillContext) -> str:
        try:
            from utils.reporter.sections.html_dashboard_renderer import HTMLDashboardRenderer
        except ImportError:
            try:
                import sys
                from pathlib import Path
                utils_dir = Path(__file__).parent.parent
                if str(utils_dir) not in sys.path:
                    sys.path.insert(0, str(utils_dir))
                from reporter.sections.html_dashboard_renderer import HTMLDashboardRenderer
            except Exception as e:
                logger.error(f"HTMLDashboardRenderer 导入失败: {e}")
                return f"<!-- HTML Dashboard rendering failed: {e} -->"

        required = HTMLDashboardRenderer.required_keys()
        missing = [k for k in required if ctx.get(k) is None]
        if missing:
            logger.warning(f"[html_dashboard] 跳过渲染，缺少键: {missing}")
            return f"<!-- html_dashboard: skipped (missing keys: {', '.join(missing)}) -->"

        try:
            renderer = HTMLDashboardRenderer()
            return renderer.render(ctx)
        except Exception as e:
            logger.error(f"[html_dashboard] 渲染失败: {e}")
            return f"<!-- html_dashboard: rendering failed ({e}) -->"
