"""Report assembly skill."""

from pathlib import Path
from skill_pipeline import BaseSkill, SkillContext


class ReportAssemblySkill(BaseSkill):
    """Markdown + HTML Dashboard 组装。"""
    name = "report_assembly"

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
        return ctx

    def _assemble_markdown(self, ctx: SkillContext) -> str:
        """组装 Markdown 报告。"""
        stock_name = ctx.get("stock_name")
        date_str = ctx.get("date_str", "")
        date_display = f"{date_str[:4]}年{date_str[4:6]}月{date_str[6:]}日" if len(date_str) == 8 else date_str
        total_score = ctx.get("total_score", 0)
        pillar = ctx.get("pillar_scores", {})
        synthesis = ctx.get("synthesis", {})
        quote = ctx.get("quote") or {}

        lines = [
            f"# {stock_name} 舆情深度报告",
            f"",
            f"> 生成日期：{date_display}",
            f"> 综合评分：{total_score}/10",
            f"",
            f"## 一、综合评分与推荐",
            f"",
            f"| 维度 | 评分 |",
            f"|------|------|",
            f"| 估值 | {pillar.get('valuation', 0)} |",
            f"| 技术 | {pillar.get('technical', 0)} |",
            f"| 情绪 | {pillar.get('sentiment', 0)} |",
            f"| 基本面 | {pillar.get('fundamental', 0)} |",
            f"| 资金流 | {pillar.get('fundflow', 0)} |",
            f"",
            f"## 二、核心观点",
            f"",
            f"**行业逻辑**：{synthesis.get('industry_logic', 'N/A')}",
            f"",
            f"**基本面**：{synthesis.get('fundamentals', 'N/A')}",
            f"",
            f"**估值多空**：{synthesis.get('valuation_debate', 'N/A')}",
            f"",
            f"**资金情绪**：{synthesis.get('funding_sentiment', 'N/A')}",
            f"",
            f"**事件催化**：{synthesis.get('events_catalysts', 'N/A')}",
            f"",
            f"## 三、行情数据",
            f"",
            f"- PE(TTM): {quote.get('pe_ttm', 'N/A')}",
            f"- 市值: {quote.get('market_cap', 'N/A')}",
            f"",
        ]
        return "\n".join(lines)

    def _assemble_html(self, ctx: SkillContext) -> str:
        """组装 HTML Dashboard。"""
        stock_name = ctx.get("stock_name")
        date_str = ctx.get("date_str")
        md_path = f"{stock_name}_{date_str}.md"

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{stock_name} 舆情 Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 p-6">
<div class="max-w-5xl mx-auto">
  <h1 class="text-3xl font-bold mb-4">{stock_name} 舆情 Dashboard</h1>
  <p class="text-gray-600 mb-6">日期: {date_str}</p>
  <div class="bg-white rounded-lg shadow p-6">
    <p>完整报告请查看：<a href="{md_path}" class="text-blue-600 underline">{md_path}</a></p>
  </div>
</div>
</body>
</html>"""