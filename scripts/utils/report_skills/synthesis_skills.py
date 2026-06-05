"""LLM synthesis skill."""

if __name__.startswith("utils."):
    from ..skill_pipeline import BaseSkill, SkillContext
else:
    from skill_pipeline import BaseSkill, SkillContext


class SynthesisSkill(BaseSkill):
    """LLM 综合叙事生成。"""
    name = "synthesis"

    def __init__(self, llm_client=None, **kwargs):
        super().__init__(**kwargs)
        self.llm_client = llm_client

    def run(self, ctx: SkillContext) -> SkillContext:
        stock_name = ctx.get("stock_name")
        stock_raw = ctx.get("stock_raw", {})
        keep_posts = ctx.get("keep_posts", [])

        synthesis = self._synthesize(stock_name, stock_raw, keep_posts)
        ctx.set("synthesis", synthesis)
        return ctx

    def _synthesize(self, stock_name: str, stock_raw: dict, keep_posts: list) -> dict:
        """调用 LLM 或模板生成综合叙事。"""
        if self.llm_client:
            return self._llm_synthesize(stock_name, stock_raw, keep_posts)
        return self._template_synthesize(stock_raw)

    def _llm_synthesize(self, stock_name: str, stock_raw: dict, keep_posts: list) -> dict:
        """使用 LLM 生成综合叙事。"""
        prompt = self._build_prompt(stock_name, stock_raw, keep_posts)
        try:
            response = self.llm_client.chat(prompt)
            if isinstance(response, dict):
                return response
            return self._template_synthesize(stock_raw)
        except Exception:
            return self._template_synthesize(stock_raw)

    def _build_prompt(self, stock_name: str, stock_raw: dict, keep_posts: list) -> str:
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
        return prompt

    def _template_synthesize(self, stock_raw: dict) -> dict:
        """无 LLM 时的降级模板。"""
        tech = stock_raw.get("technical", {})
        indicators = tech.get("indicators", {})
        resonance = indicators.get("_resonance", {})
        score = resonance.get("composite_score", 5)

        if score >= 7:
            trend = "整体偏多"
        elif score <= 3:
            trend = "整体偏空"
        else:
            trend = "震荡整理"

        return {
            "industry_logic": f"技术面综合评分 {score}，{trend}。",
            "fundamentals": "请结合最新财报与研报进一步分析。",
            "valuation_debate": "多空观点交织，建议关注后续催化。",
            "funding_sentiment": "资金流向待进一步确认。",
            "events_catalysts": "关注公司公告与行业政策动向。",
        }
