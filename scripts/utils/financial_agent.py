import json
import logging
import os
from typing import Dict, Any
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


class FinancialAgent:
    """
    FinancialAgent: 跨数据源深度分析器
    调用 Kimi API 对多源数据进行关联分析
    """

    def __init__(self, api_key: str = None, model: str = None, base_url: str = None):
        self.api_key = api_key or os.getenv("MOONSHOT_API_KEY")
        self.model = model or os.getenv("MOONSHOT_MODEL", "moonshot-v1-128k")
        self.base_url = base_url or os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")

        if not self.api_key:
            logger.warning("MOONSHOT_API_KEY 未设置，FinancialAgent 将不可用")
            self.client = None
        elif OpenAI is None:
            logger.warning("openai 包未安装")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def analyze(self, stock_name: str, code: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        对单只股票的所有数据源进行深度分析
        Args:
            data: {technical, reports, announcements, fundflow, news, sentiment}
        Returns:
            结构化分析结果
        """
        if not self.client:
            logger.error("FinancialAgent 客户端未初始化")
            return self._fallback_analysis(stock_name, data)

        prompt = self._build_prompt(stock_name, code, data)

        try:
            logger.info(f"调用 Kimi API 分析 {stock_name}...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=8000,
            )
            content = response.choices[0].message.content
            return self._extract_json(content)
        except Exception as e:
            logger.error(f"Kimi API 调用失败: {e}")
            return self._fallback_analysis(stock_name, data)

    def _system_prompt(self) -> str:
        return """你是一位专业的半导体行业研究员，擅长跨数据源关联分析。

## 任务
基于提供的多源数据，生成结构化的深度分析报告。

## 分析框架
### A. 确认事实（基于公告、研报、财报的明确信息）
- 列出 3-5 条不可辩驳的事实

### B. 我推断（基于多源交叉的合理推论）
- 技术面与基本面的共振/背离
- 资金流向与舆情的验证/矛盾
- 机构评级与当前股价的偏离

### C. 我认为（基于推理的主观判断，需明确假设前提）
- 短期（1-4周）走势判断
- 中期（1-3个月）关键催化/风险
- 仓位建议（加仓/持有/减仓/观望）

## 输出格式
必须返回有效的 JSON：
{
  "confirmed_facts": ["事实1"],
  "inferences": [{"claim": "推断", "basis": "依据", "confidence": 0.8}],
  "opinions": [{"claim": "观点", "assumptions": ["假设1"], "timeframe": "短期"}],
  "key_risks": ["风险1"],
  "catalysts": ["催化1"],
  "position_suggestion": "持有",
  "report_sections": {
    "technical_analysis": "用于报告 Section 3 的 Markdown",
    "report_summary": "用于报告 Section 4 的机构共识",
    "announcement_signals": "用于报告 Section 5 的公告信号",
    "fundflow_interpretation": "用于报告 Section 6 的资金解读"
  }
}
"""

    def _build_prompt(self, stock_name: str, code: str, data: Dict[str, Any]) -> str:
        lines = [
            f"# 股票多维度分析请求: {stock_name} ({code})",
            f"分析日期: {datetime.now().strftime('%Y-%m-%d')}",
            "",
        ]

        tech = data.get("technical", {})
        if tech:
            lines.append("## 1. 技术面数据")
            indicators = tech.get("indicators", {})
            for k, v in indicators.items():
                lines.append(f"- {k}: {v}")
            lines.append("")

        reports = data.get("reports", [])
        if reports:
            lines.append(f"## 2. 最新研报（{len(reports)} 篇）")
            for r in reports[:5]:
                lines.append(f"- [{r.get('institution', '')}] {r.get('title', '')} | 评级: {r.get('rating', 'N/A')} | 目标价: {r.get('target_price', 'N/A')}")
            lines.append("")

        anns = data.get("announcements", [])
        if anns:
            lines.append(f"## 3. 近期公告（{len(anns)} 条）")
            for a in anns[:5]:
                lines.append(f"- [{a.get('date', '')}] {a.get('title', '')} ({a.get('type', '')})")
            lines.append("")

        fund = data.get("fundflow", [])
        if fund:
            lines.append(f"## 4. 资金流向（近 {len(fund)} 日）")
            for f in fund[:5]:
                lines.append(f"- {f.get('date', '')}: 主力净流入 {f.get('main_inflow', 0)} 万")
            lines.append("")

        news = data.get("news", [])
        if news:
            lines.append(f"## 5. 个股新闻（{len(news)} 条）")
            for n in news[:5]:
                lines.append(f"- [{n.get('source', '')}] {n.get('title', '')}")
            lines.append("")

        sentiment = data.get("sentiment", [])
        if sentiment:
            lines.append(f"## 6. 社区舆情（{len(sentiment)} 条帖子）")
            for p in sentiment[:5]:
                lines.append(f"- {p.get('title', '')}")
            lines.append("")

        return "\n".join(lines)

    def _extract_json(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        import re
        patterns = [
            r'```json\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
        ]
        for pat in patterns:
            match = re.search(pat, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass

        return {"raw_text": text, "report_markdown": text}

    def _fallback_analysis(self, stock_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "confirmed_facts": ["Kimi API 未启用，无法生成深度分析"],
            "inferences": [],
            "opinions": [],
            "key_risks": ["AI分析暂缺"],
            "catalysts": [],
            "position_suggestion": "观望",
            "report_sections": {
                "technical_analysis": "*AI分析暂缺*",
                "report_summary": "*AI分析暂缺*",
                "announcement_signals": "*AI分析暂缺*",
                "fundflow_interpretation": "*AI分析暂缺*",
            }
        }
