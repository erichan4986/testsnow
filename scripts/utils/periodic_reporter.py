import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from data_collector import TechnicalCollector
from financial_agent import FinancialAgent
from obsidian_writer import ObsidianWriter

logger = logging.getLogger(__name__)


class PeriodicReporter:
    """生成季报/半年报/年报"""

    def __init__(self):
        self.tech_collector = TechnicalCollector()
        self.agent = FinancialAgent()
        self.writer = ObsidianWriter()

    def generate(self, report_type: str, year: int, stock_code: str, stock_name: str,
                 quarter: int = None, half: int = None):
        """
        Args:
            report_type: quarterly | semiannual | annual
            year: 年份
            stock_code: 如 "300661"
            stock_name: 如 "圣邦股份"
            quarter: 1-4 (for quarterly)
            half: 1-2 (for semiannual)
        """
        if report_type == "quarterly":
            kline_days = 60
            ma_keys = ["ma_20", "ma_60"]
            period_label = f"{year}Q{quarter}"
        elif report_type == "semiannual":
            kline_days = 120
            ma_keys = ["ma_60", "ma_120"]
            period_label = f"{year}H{half}"
        else:  # annual
            kline_days = 250
            ma_keys = ["ma_120", "ma_250"]
            period_label = f"{year}"

        logger.info(f"生成 {stock_name} {period_label} {report_type} 报告...")

        # 1. Re-collect cycle-matching technical data
        market = 0 if stock_code.startswith(("00", "30")) else 1
        tech_data = self.tech_collector.collect(stock_code, market=market, days=kline_days)

        # 2. Collect historical weekly analyses
        index_path = Path("knowledge/99-Meta/weekly_index.json")
        weekly_analyses = []
        if index_path.exists():
            index = json.loads(index_path.read_text(encoding="utf-8"))
            entries = index.get(stock_code, [])
            for entry in entries:
                entry_date = datetime.strptime(entry["date"], "%Y%m%d")
                if self._is_in_period(entry_date, report_type, year, quarter, half):
                    note_path = Path(entry["note_path"])
                    if note_path.exists():
                        content = note_path.read_text(encoding="utf-8")
                        weekly_analyses.append({"date": entry["date"], "content": content})

        # 3. Call FinancialAgent for periodic analysis
        prompt_data = self._build_periodic_prompt(
            stock_name, stock_code, report_type, period_label,
            tech_data, weekly_analyses, ma_keys
        )
        result = self._call_periodic_agent(prompt_data)

        # 4. Write periodic report
        self._write_periodic_report(stock_name, stock_code, report_type, period_label, result, tech_data)

    def _is_in_period(self, dt: datetime, report_type: str, year: int, quarter: int, half: int) -> bool:
        if dt.year != year:
            return False
        if report_type == "quarterly":
            q_start = (quarter - 1) * 3 + 1
            q_end = quarter * 3
            return q_start <= dt.month <= q_end
        elif report_type == "semiannual":
            if half == 1:
                return dt.month <= 6
            else:
                return dt.month >= 7
        return True  # annual

    def _build_periodic_prompt(self, stock_name, code, report_type, period_label,
                               tech_data, weekly_analyses, ma_keys) -> str:
        lines = [
            f"# {stock_name} ({code}) {period_label} {report_type} 复盘",
            "",
            "## 周期技术指标",
        ]
        if tech_data:
            indicators = tech_data.get("indicators", {})
            for k in ma_keys:
                if k in indicators:
                    lines.append(f"- {k}: {indicators[k]}")
            lines.append(f"- 周期收盘价: {indicators.get('close', 'N/A')}")
            lines.append("")

        lines.append(f"## 周期内每周分析记录（共 {len(weekly_analyses)} 周）")
        for wa in weekly_analyses:
            lines.append(f"\n### {wa['date']}")
            lines.append(wa['content'][:1000])
            lines.append("")

        return "\n".join(lines)

    def _call_periodic_agent(self, prompt: str) -> Dict[str, Any]:
        if not self.agent.client:
            return self.agent._fallback_analysis("", {})

        system_prompt = """你是一位投资组合经理，正在基于多周分析记录复盘股票表现。
请输出 JSON 格式：
{
  "period_facts": [{"fact": "", "evidence": ""}],
  "fact_evolution": [{"fact": "", "change": "", "weeks": []}],
  "judgment_review": [{"week": "", "claim": "", "outcome": "", "reason": ""}],
  "key_themes": [{"theme": "", "mentions": 0, "trend": ""}],
  "period_conclusion": {"confirmed_facts": [], "inferences": [], "opinions": [], "position_suggestion": ""},
  "lessons": [],
  "report_markdown": ""
}"""

        try:
            response = self.agent.client.chat.completions.create(
                model=self.agent.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=8000,
            )
            return self.agent._extract_json(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"周期性分析失败: {e}")
            return self.agent._fallback_analysis("", {})

    def _write_periodic_report(self, stock_name, code, report_type, period_label, result, tech_data):
        periodics_dir = Path("knowledge/30-Periodics")
        periodics_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{period_label}-{stock_name}-{report_type}.md"
        filepath = periodics_dir / filename

        frontmatter = {
            "type": report_type,
            "period": period_label,
            "stock": stock_name,
            "code": code,
            "generated_at": datetime.now().strftime("%Y-%m-%d"),
        }

        lines = [
            "---",
            json.dumps(frontmatter, ensure_ascii=False, indent=2),
            "---",
            "",
            f"# {stock_name} {period_label} {report_type}复盘",
            "",
            "## 一、周期数据概览",
        ]

        if tech_data:
            indicators = tech_data.get("indicators", {})
            lines.append("### 技术面（周期视角）")
            lines.append("| 指标 | 数值 |")
            lines.append("|------|------|")
            for k, v in indicators.items():
                lines.append(f"| {k} | {v} |")
            lines.append("")

        md = result.get("report_markdown", "")
        if md:
            lines.append(md)
        else:
            lines.append("*分析生成失败*")

        lines.append("")
        lines.append(f"---")
        lines.append(f"*基于 {len(result.get('judgment_review', []))} 周周报 + 重新采集的周期技术指标生成*")

        filepath.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"周期性报告已生成: {filepath}")
