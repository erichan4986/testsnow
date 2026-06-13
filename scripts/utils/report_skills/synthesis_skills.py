"""LLM synthesis skill."""

from pathlib import Path
from typing import Dict, List

if __name__.startswith("utils."):
    from ..skill_pipeline import BaseSkill, SkillContext
    from ..knowledge_synthesizer import KnowledgeSynthesizer
    from ..source_adapter import adapt_all
else:
    from skill_pipeline import BaseSkill, SkillContext
    from knowledge_synthesizer import KnowledgeSynthesizer
    from source_adapter import adapt_all


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

        synthesis = self._synthesize(stock_name, stock_raw, keep_posts, ctx)
        ctx.set("synthesis", synthesis)
        ctx.set("core_facts", synthesis.get("core_facts", []))
        ctx.set("synthesis_text", self._flatten_synthesis_text(synthesis))
        ctx.set("synthesis_items_count", synthesis.get("_items_count", 0))
        ctx.set("synthesis_sources", synthesis.get("_sources", []))
        return ctx

    def _synthesize(self, stock_name: str, stock_raw: dict, keep_posts: list, ctx: SkillContext = None) -> dict:
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

        items = self._build_synthesis_items(stock_raw, keep_posts)
        if not items:
            return self._template_synthesize(stock_raw, items_count=0, sources=[])

        synthesizer = self.synthesizer or KnowledgeSynthesizer(client=self.llm_client)
        all_data = {"items": items}
        if cv_context:
            all_data["claim_verification_context"] = cv_context
        result = synthesizer.synthesize(stock_name, all_data)
        result = self._fill_citation_metadata(result, items)

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

    def _build_synthesis_items(self, stock_raw: dict, keep_posts: list):
        zhihu = stock_raw.get("zhihu", {})
        return adapt_all(
            xueqiu_items=keep_posts,
            zhihu_items=zhihu.get("report_items", []),
            reports=stock_raw.get("reports", []),
            announcements=stock_raw.get("announcements", []),
            fundflow=stock_raw.get("fundflow", []),
            news=stock_raw.get("news", []),
        )

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

            filled[ref_id] = {
                "source": item.source_platform,
                "author": item.author,
                "title": item.title,
                "url": item.url,
                "date": item.publish_time,
                "interaction_score": item.interaction_score,
            }
        synthesis["citations"] = filled
        return synthesis

    def _source_list(self, items: list) -> List[str]:
        return sorted({item.source_platform for item in items if item.source_platform})

    def _flatten_synthesis_text(self, synthesis: dict) -> str:
        return "\n".join(str(synthesis.get(k, "")) for k in SYNTHESIS_KEYS if synthesis.get(k))

    def _build_prompt(self, stock_name: str, stock_raw: dict, keep_posts: list, cv_context: Dict = None) -> str:
        """构建 LLM prompt。"""
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
        if not context or not context.get("enabled"):
            return ""
        counts = context.get("counts", {})
        lines = [
            "Claim Verification Context（以下不是新的引用来源）",
            "",
            "重要约束：以下内容不是新的引用来源，不能用 [^n] 引用，也不能单独作为事实写入正文。",
            f"统计：已验证 {counts.get('verified', 0)} 条，中等支持 {counts.get('supported', 0)} 条，未验证 {counts.get('unverified', 0)} 条。",
            "",
            "使用规则：",
            "- verified：只有当同一事实也出现在其他可引用来源中时，才可作为重点线索使用。",
            "- supported：仅表示有中等信用来源支持，不得写成已确认事实。",
            "- unverified：只能作为待验证市场观点/社区讨论，不得进入核心事实。",
        ]
        for bucket, label in (
            ("verified_claims", "已验证声明"),
            ("supported_claims", "中等支持声明"),
            ("unverified_claims", "未验证声明"),
        ):
            rows = context.get(bucket, [])
            if rows:
                lines.extend(["", f"{label}："])
                for row in rows:
                    text = row.get("claim_text", "")
                    action = row.get("action", "")
                    confidence = row.get("confidence")
                    reason = row.get("reason", "")
                    titles = row.get("verified_by_titles", [])
                    parts = [f"- [{action}] {text}"]
                    if confidence is not None:
                        parts.append(f"（置信度 {confidence}）")
                    if titles:
                        parts.append(f"[依据: {' / '.join(titles)}]")
                    if reason:
                        parts.append(f"[原因: {reason}]")
                    lines.append(" ".join(parts))
        return "\n".join(lines)

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
