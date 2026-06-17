"""执行摘要板块渲染器。"""

import logging
import re
from typing import Any, Dict, List, Optional

try:
    from ...synthesis_credit import sanitize_citation_markers
except ImportError:
    try:
        from scripts.utils.synthesis_credit import sanitize_citation_markers
    except ImportError:
        from utils.synthesis_credit import sanitize_citation_markers

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
        "信用层级约束（必须遵守）：\n"
        "- 只有被高信用来源验证过的事实（verified）才能作为看多确认论点。\n"
        "- supported（部分支持）线索只能描述为‘部分支持，但仍非官方确认’，"
        "  可放入看空/待验证/不确定性部分，不得放入看多确认论点。\n"
        "- unverified（未验证）和 needs_review（需复核）线索只能放入看空/待验证部分或跳过，"
        "  严禁放入看多确认论点或作为确认事实。\n"
        "- 不要输出 [^verified] / [^supported] / [^needs_review] / [^unverified] 等非法引用标记。\n\n"
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


_CLAIM_QUALIFIERS = (
    "部分支持",
    "非官方确认",
    "尚未官方确认",
    "未获官方确认",
    "待验证",
    "需复核",
    "未验证",
)


def _normalize_claim_text(text: str) -> str:
    text = sanitize_citation_markers(str(text or ""))
    return re.sub(r"[\s，。、“”‘’：:；;,.|（）()\[\]【】\-—]+", "", text)


def _claim_numeric_tokens(text: str) -> set:
    return set(re.findall(r"\d+(?:\.\d+)?%?", text or ""))


def _has_claim_qualifier(text: str) -> bool:
    return any(q in str(text or "") for q in _CLAIM_QUALIFIERS)


def _claim_matches_point(claim_text: str, point_text: str) -> bool:
    claim_norm = _normalize_claim_text(claim_text)
    point_norm = _normalize_claim_text(point_text)
    if not claim_norm or not point_norm:
        return False

    if point_norm in claim_norm or claim_norm in point_norm:
        return True

    shared_numbers = _claim_numeric_tokens(claim_norm) & _claim_numeric_tokens(point_norm)
    if not shared_numbers:
        return False

    keywords = ("净利润", "营收", "收入", "毛利率", "研发费用", "同比", "增长", "下降")
    shared_keywords = [kw for kw in keywords if kw in claim_norm and kw in point_norm]
    return bool(shared_keywords)


def _guard_claim_verification_points(
    points: List[Dict],
    direction: str,
    claim_verification_summary: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """Make non-verified claim-derived thesis points explicitly non-official."""
    if direction != "bullish" or not isinstance(claim_verification_summary, dict):
        return points

    caution_claims = []
    for bucket in ("supported_claims", "needs_review_claims", "unverified_claims"):
        rows = claim_verification_summary.get(bucket, [])
        if isinstance(rows, list):
            caution_claims.extend(row for row in rows if isinstance(row, dict))

    if not caution_claims:
        return points

    guarded = []
    for point in points:
        if not isinstance(point, dict):
            continue
        text = sanitize_citation_markers(str(point.get("text", ""))).strip()
        if not text:
            continue

        if not _has_claim_qualifier(text):
            for claim in caution_claims:
                if _claim_matches_point(claim.get("claim_text", ""), text):
                    text = f"{text}（部分支持，非官方确认）"
                    break

        point = dict(point)
        point["text"] = text
        guarded.append(point)

    return guarded


def _extract_thesis_points(
    text: str,
    direction: str,
    claim_verification_summary: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """从合成文本中提取看多/看空论点。优先使用 LLM，失败时回退到启发式。"""
    points = []
    if not text:
        return points

    text = sanitize_citation_markers(text)

    try:
        llm_result = _llm_extract_thesis(text)
        if direction == "bullish":
            return _guard_claim_verification_points(
                llm_result.get("bullish", []),
                direction,
                claim_verification_summary,
            )
        else:
            return _guard_claim_verification_points(
                llm_result.get("bearish", []),
                direction,
                claim_verification_summary,
            )
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

    return _guard_claim_verification_points(points, direction, claim_verification_summary)


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
        combined = sanitize_citation_markers(debate_text + "\n" + fund_text)

        claim_verification_summary = ctx.get("claim_verification_summary")
        bullish_points = _extract_thesis_points(combined, "bullish", claim_verification_summary)
        bearish_points = _extract_thesis_points(combined, "bearish", claim_verification_summary)

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
