"""执行摘要板块渲染器。"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _llm_extract_thesis(text: str) -> Dict:
    """调用 LLM 从合成文本中提取多空论点和结论。"""
    import os
    from openai import OpenAI

    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("MOONSHOT_API_KEY")
    if not api_key:
        raise RuntimeError("LLM API key not configured")

    base_url = (
        "https://api.deepseek.com/v1"
        if os.getenv("DEEPSEEK_API_KEY")
        else "https://api.moonshot.cn/v1"
    )
    model = (
        os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        if os.getenv("DEEPSEEK_API_KEY")
        else os.getenv("MOONSHOT_MODEL", "moonshot-v1-8k")
    )

    client = OpenAI(api_key=api_key, base_url=base_url)

    prompt = (
        "你是资深投资分析师。请基于以下分析文本，提取核心投资论点。\n\n"
        "要求：\n"
        "1. 看多论点：最多3条，每条不超过60字，只保留最核心的判断和数据支撑\n"
        "2. 看空论点：最多3条，每条不超过60字，只保留最核心的判断和数据支撑\n"
        "3. 给每条论点一个风险/机会等级（1-5星，整数）\n"
        "4. 一句话结论（不超过40字，概括多空博弈的核心）\n\n"
        "输出严格 JSON 格式，不要有任何其他内容：\n"
        '{\n'
        '  "bullish": [{"text": "...", "stars": 4}, ...],\n'
        '  "bearish": [{"text": "...", "stars": 3}, ...],\n'
        '  "conclusion": "..."\n'
        '}\n\n'
        "分析文本：\n"
        f"{text[:3000]}"
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是专业的中文投资分析师，擅长提炼多空核心论点。只输出JSON，不输出任何解释或markdown。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=800,
    )

    response_text = resp.choices[0].message.content.strip()
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.startswith("```"):
        response_text = response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]
    response_text = response_text.strip()

    import json
    result = json.loads(response_text)
    for key in ["bullish", "bearish"]:
        if key in result and isinstance(result[key], list):
            for pt in result[key]:
                if not isinstance(pt, dict):
                    continue
                pt.setdefault("text", "")
                pt.setdefault("stars", 3)
                pt["stars"] = max(1, min(5, int(pt.get("stars", 3))))
    result.setdefault("conclusion", "")
    return result


def _extract_thesis_points(text: str, direction: str) -> List[Dict]:
    """从合成文本中提取看多/看空论点。优先使用 LLM，失败时回退到启发式。"""
    points = []
    if not text:
        return points

    try:
        llm_result = _llm_extract_thesis(text)
        if direction == "bullish":
            return llm_result.get("bullish", [])
        else:
            return llm_result.get("bearish", [])
    except Exception as e:
        logger.warning(f"LLM 论点提取失败，回退到启发式: {e}")

    if direction == "bullish":
        keywords = ["增长", "放量", "突破", "拐点", "优势", "机遇", "看好", "上调", "超预期", "确定性"]
        for sentence in text.split("。"):
            if any(k in sentence for k in keywords) and len(sentence) > 20:
                points.append({"text": sentence.strip() + "。", "stars": 3})
            if len(points) >= 4:
                break
    else:
        keywords = ["亏损", "下滑", "压力", "风险", "落后", "减持", "解禁", "看空", "下调", "陷阱"]
        for sentence in text.split("。"):
            if any(k in sentence for k in keywords) and len(sentence) > 20:
                points.append({"text": sentence.strip() + "。", "stars": 3})
            if len(points) >= 4:
                break

    return points


def _extract_conclusion(stock_name: str, text: str) -> str:
    """提取一句话结论。优先使用 LLM，失败时返回空字符串。"""
    if not text:
        return ""
    try:
        llm_result = _llm_extract_thesis(text)
        return llm_result.get("conclusion", "")
    except Exception:
        return ""


class ExecutiveSummaryRenderer:
    """执行摘要板块 — 综合评分标题 + 核心投资论点 + 一句话结论。"""

    @staticmethod
    def required_keys() -> List[str]:
        return ["stock_name", "synthesis"]

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        synthesis = ctx.get("synthesis") or {}
        if not stock_name or not synthesis:
            return ""

        pillar = ctx.get("pillar")
        consensus = ctx.get("consensus")

        try:
            from ..scoring_engine import ev_expectation
        except ImportError:
            try:
                import sys
                from pathlib import Path
                utils_dir = Path(__file__).parent.parent.parent
                if str(utils_dir) not in sys.path:
                    sys.path.insert(0, str(utils_dir))
                from reporter.scoring_engine import ev_expectation
            except Exception:
                ev_expectation = lambda p, c: {"ev_pct": None, "signal": "N/A"}

        ev = ev_expectation(pillar or {}, consensus)
        if pillar is not None:
            total_score = round(
                pillar["valuation"] * 0.30 +
                pillar["technical"] * 0.25 +
                pillar["sentiment"] * 0.20 +
                pillar["fundamental"] * 0.15 +
                pillar["fundflow"] * 0.10,
                1,
            )
            ev_pct = ev.get("ev_pct")
            ev_signal = ev.get("signal") or "N/A"
            ev_pct_str = f"{ev_pct:+.2f}" if ev_pct is not None else "N/A"
            score_line = f"### 综合评分: {total_score}/10 | EV: {ev_pct_str}%（{ev_signal}）"
        else:
            score_line = "### 综合评分: 数据不足 | EV: N/A"

        lines = [
            "## 执行摘要",
            "",
            score_line,
            "",
            "### 核心投资论点",
            "",
        ]

        debate_text = synthesis.get("valuation_debate", "")
        fund_text = synthesis.get("fundamentals", "")
        combined = debate_text + "\n" + fund_text

        bullish_points = _extract_thesis_points(combined, "bullish")
        bearish_points = _extract_thesis_points(combined, "bearish")

        if bullish_points:
            lines.append("**看多：**")
            for pt in bullish_points[:4]:
                star = "⭐" * pt.get("stars", 3)
                lines.append(f"- {pt.get('text', '')} → {star}")
            lines.append("")

        if bearish_points:
            lines.append("**看空：**")
            for pt in bearish_points[:4]:
                star = "⭐" * pt.get("stars", 3)
                lines.append(f"- {pt.get('text', '')} → {star}")
            lines.append("")

        conclusion = _extract_conclusion(stock_name, combined)
        if conclusion:
            lines.append(f"> **一句话结论**：{conclusion}")
            lines.append("")

        chart_paths = ctx.get("chart_paths", ctx.get("_chart_paths", {}))
        bullbear_chart = chart_paths.get("bullbear")
        if bullbear_chart:
            lines.append("### 多空论点对比")
            lines.append("")
            lines.append(f"![{stock_name} 多空论点对比]({bullbear_chart})")
            lines.append("")

        return "\n".join(lines)
