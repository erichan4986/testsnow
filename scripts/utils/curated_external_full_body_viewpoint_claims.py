"""Full-body external viewpoint claim extraction for preview workflows.

This module turns cleaned full-body source packets into a small set of cited,
novelty-gated external viewpoint claims. It is preview-only and never connects
to the report pipeline, Knowledge, scoring, risk, or final recommendations.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Set, Tuple


SOURCE_PACKET_SCHEMA_VERSION = "curated_external_source_packet.v1"
CLAIM_SCHEMA_VERSION = "curated_external_viewpoint_claim.v1"
DIGEST_SCHEMA_VERSION = "curated_external_viewpoint_digest.v1"
SOURCE_TYPE = "curated_external_analysis_evidence"
DEFAULT_SOURCE_CREDIT = 55

_MIN_REPAIR_EXACT_CHARS = 18
_MAX_REPAIR_WINDOW_FACTOR = 1.4
_REPAIR_MAX_CANDIDATES = 1

_STRONG_CONFIRMATION_TERMS = [
    "确认",
    "证实",
    "已验证",
    "必然",
    "确定",
    "公司披露",
    "公告显示",
    "已落地",
    "锁定",
]

# Event phrases the fingerprint should catch when present in baseline.
_BASELINE_EVENT_PHRASES = [
    "A2000通过审查",
    "A2000",
    "A1000",
    "500TOPS",
    "费用收缩",
    "具身智能",
    "预付款暴涨",
    "1260H",
    "800G",
    "1.6T",
    "1500万",
    "1200万",
    "产能爬坡",
    "获得定点",
    "通过美国审查",
]

_CLAIM_TYPE_LABELS = {
    "dissent": "分歧观点",
    "watch_variable": "待验证变量",
    "novel_mechanism": "增量机制",
    "context_extension": "产业链/竞争格局补充",
    "business_quality_signal": "经营质量信号",
    "interpretive_frame": "解释框架",
    "strategic_tradeoff": "战略取舍",
}

_INTERPRETIVE_CLAIM_TYPES = {
    "dissent",
    "watch_variable",
    "novel_mechanism",
    "business_quality_signal",
    "interpretive_frame",
    "strategic_tradeoff",
}

_INTERPRETIVE_TERMS = [
    "含义",
    "解释",
    "机制",
    "分歧",
    "变量",
    "节奏",
    "策略",
    "取舍",
    "经营质量",
    "费用",
    "投入",
    "现金流",
    "商业化",
    "竞争力",
    "资源分散",
    "窗口期",
    "验证",
    "待跟踪",
]

_NEAR_DUPLICATE_BUCKETS: List[Tuple[str, List[List[str]]]] = [
    (
        "expense_contraction_quality",
        [
            ["费用", "开支", "节衣缩食", "销售", "行政", "研发"],
            ["收缩", "减少", "压缩", "下降", "高投入", "现金流", "竞争力", "投入"],
        ],
    ),
    (
        "benchmark_model_conversion",
        [
            ["爆款", "标杆", "月销", "小众车型", "定点", "车型"],
            ["出货", "销量", "转化", "飞跃", "客户拓展", "复购"],
        ],
    ),
    (
        "a2000_market_window",
        [
            ["A2000", "华山A2000", "高阶智驾", "高阶芯片"],
            ["量产", "窗口", "滞后", "错失", "竞品", "Orin", "征程"],
        ],
    ),
    (
        "a2000_review_control",
        [
            ["A2000", "华山A2000", "美国", "商务部", "国防部"],
            ["审查", "获准", "全球销售", "出口管制", "审核"],
        ],
    ),
    (
        "embodied_ai_commercialization_timeline",
        [
            ["具身智能", "机器人"],
            ["商业化", "3-5年", "三到五年", "退回", "贡献营收", "成本"],
        ],
    ),
    (
        "embodied_ai_competition_resources",
        [
            ["具身智能", "机器人"],
            ["英伟达", "地平线", "竞争", "资源分散", "双线作战", "无法兼顾"],
        ],
    ),
    (
        "fundraising_industry_chain",
        [
            ["募资", "配售", "5.68亿", "5.689亿", "90%"],
            ["并购", "投资", "AI芯片", "机器人", "半导体产业链", "产业整合"],
        ],
    ),
]

DEFAULT_MULTIPASS_SPECS = [
    {
        "name": "supply_delivery_capacity",
        "focus": (
            "供应链、交付、产能、预付款、材料紧缺、客户订单或规模交付变量。"
            "特别检查 800G 交付计划从1500万只下调至1200万只的市场传言、"
            "以及公司是否否认该传言；如存在，只能写成外部待验证变量。"
            "不要遗漏预付款变化提示的上游材料紧张信号。"
        ),
    },
    {
        "name": "technology_path",
        "focus": (
            "技术路径、CPO/NPO/XPO、可插拔光模块、硅光、800G/1.6T 等路线差异。"
            "不要遗漏 CPO vs 可插拔光模块的技术路线分歧与演进时间表。"
        ),
    },
    {
        "name": "geopolitics_capex_customers",
        "focus": (
            "地缘政治、1260H/实体清单、出口管制、制裁清单、海外客户、"
            "云厂商 capex、全球算力投资、需求指引和宏观算力投资变量。"
            "不要遗漏地缘政治/出口管制相关非财务增量观点。"
        ),
    },
    {
        "name": "earnings_commercialization_dissent",
        "focus": (
            "财务质量、商业化节奏、利润率、费用收缩、竞争格局分歧和待验证风险。"
            "特别检查 2026-2028 年客户需求与 capex 指引。"
        ),
    },
]

THEME_PROFILES: Dict[str, Dict[str, Any]] = {
    "zhongji_ai_optics": {
        "themes": {
            "800G_rumor": {
                "keywords": [
                    "800G",
                    "1500万",
                    "1200万",
                    "交付计划",
                    "交付下调",
                    "交付量",
                    "传言",
                    "否认",
                ],
                "keyword_groups": [
                    ["800G"],
                    ["1500万", "1200万", "交付计划", "交付下调", "交付量", "传言", "否认"],
                ],
                "description": "800G delivery plan rumor and company response",
            },
            "CPO_vs_pluggable": {
                "keywords": [
                    "CPO",
                    "可插拔",
                    "pluggable",
                    "硅光",
                    "硅光平台",
                    "集成",
                    "封装",
                ],
                "keyword_groups": [
                    ["CPO"],
                    ["可插拔", "pluggable", "Scale Out", "scale out"],
                ],
                "description": "CPO vs pluggable optical module technology path",
            },
            "1260H_geopolitics": {
                "keywords": [
                    "1260H",
                    "实体清单",
                    "出口管制",
                    "制裁",
                    "制裁清单",
                    "地缘政治",
                    "政策清单",
                    "BIS",
                    "EAR",
                ],
                "description": "1260H entity list and export control geopolitics",
            },
            "global_capex": {
                "keywords": [
                    "capex",
                    "资本开支",
                    "云厂商",
                    "云厂商资本开支",
                    "算力投资",
                    "AI投资",
                    "全球资本开支",
                    "数据中心投资",
                ],
                "keyword_groups": [
                    ["capex", "资本开支", "算力投资", "AI投资", "数据中心投资"],
                    ["全球", "云厂商", "数据中心", "AI", "海外"],
                ],
                "description": "Global cloud vendor capex and AI investment",
            },
            "NPO_XPO_timeline": {
                "keywords": [
                    "NPO",
                    "XPO",
                    "CPO",
                    "时间表",
                    "roadmap",
                    "演进路线",
                    "技术路线",
                    "量产时间",
                ],
                "keyword_groups": [
                    ["NPO", "XPO"],
                    ["时间表", "roadmap", "演进路线", "技术路线", "量产时间", "2027"],
                ],
                "description": "NPO/XPO/CPO technology evolution timeline",
            },
            "prepayment_material_tightness": {
                "keywords": [
                    "预付款",
                    "材料紧缺",
                    "上游材料",
                    "供应链紧张",
                    "材料短缺",
                    "备货",
                    "磷化铟",
                    "光芯片紧缺",
                ],
                "description": "Prepayment changes and upstream material tightness",
            },
            "customer_demand_capex_guide_2026_2028": {
                "keywords": [
                    "2026",
                    "2027",
                    "2028",
                    "需求指引",
                    "capex guide",
                    "客户capex",
                    "需求预测",
                    "业绩指引",
                    "客户需求",
                ],
                "keyword_groups": [
                    ["2026", "2027", "2028"],
                    ["需求指引", "capex guide", "客户capex", "需求预测", "业绩指引", "客户需求"],
                ],
                "description": "2026-2028 customer demand and capex guidance",
            },
        },
    },
}

Extractor = Callable[[List[Dict[str, Any]], str, Set[str]], List[Dict[str, Any]]]


class _ClaimList(list):
    """List subclass that can carry extractor-level metadata such as failed passes."""

    def __init__(
        self,
        values: List[Dict[str, Any]] | None = None,
        *,
        failed_passes: List[Dict[str, str]] | None = None,
    ) -> None:
        super().__init__(values or [])
        self.failed_passes = failed_passes or []


class FullBodyExtractorError(Exception):
    """Structured exception carrying a fail-closed status."""

    def __init__(self, status: str, message: str = ""):
        super().__init__(message or status)
        self.status = status


def normalized_hash(text: str | None) -> str:
    normalized = _normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _normalize_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _clean_source_content(text: Any) -> str:
    """Remove markdown images/links and obvious nav/footer noise."""
    source = _normalize_text(text)
    # Drop markdown images.
    source = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", source)
    # Drop markdown links, keeping link text.
    source = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", source)
    # Drop raw URLs.
    source = re.sub(r"https?://\S+", "", source)
    # Drop stray HTML/JS fragments.
    source = re.sub(r"<[^>]+>", "", source)
    # Drop CSS blocks.
    source = re.sub(r"[#.]\w+[^{]*\{[^}]*\}", "", source)
    # Drop common footer/tail markers.
    tail_markers = [
        "免责声明",
        "风险提示",
        "点击上方",
        "关注公众号",
        "设为星标",
        "扫码",
        "原文链接",
        "阅读原文",
        "广告",
        "往期热文推荐",
        "相关推荐",
        "联系我们",
        "商务合作",
        "进群交流",
        "-END-",
        "End",
        "视频推荐",
        "文章推荐",
    ]
    cut_positions = [source.find(marker) for marker in tail_markers if source.find(marker) > 0]
    if cut_positions:
        source = source[: min(cut_positions)]
    return _normalize_text(source)


def _read_json_or_jsonl(path: str | Path) -> List[Any]:
    source = Path(path)
    if not source.exists():
        return []
    text = source.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("[") or text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("items", []) if isinstance(payload.get("items"), list) else [payload]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _source_id(item: Dict[str, Any]) -> str:
    ref = str(item.get("source_ref") or item.get("url") or "")
    kind = str(item.get("source_kind") or item.get("source_type") or "external")
    digest = normalized_hash(ref)[:16]
    return f"curated-source:{kind}:{digest}"


def build_source_packets(
    jsonl_path: str | Path,
    *,
    stock_name: str = "",
    max_sources: int | None = None,
    max_source_chars: int | None = None,
) -> List[Dict[str, Any]]:
    """Convert a body-enriched JSONL file into versioned source packets."""
    raw_items = _read_json_or_jsonl(jsonl_path)
    seen_refs: Set[str] = set()
    packets: List[Dict[str, Any]] = []

    def _score(item: Dict[str, Any]) -> float:
        return float(item.get("quality_score") or 0) * 10 + float(item.get("discovery_score") or 0)

    sorted_items = sorted(raw_items, key=_score, reverse=True)

    for item in sorted_items:
        ref = str(item.get("source_ref") or item.get("url") or "")
        if not ref:
            continue
        if ref in seen_refs:
            continue
        seen_refs.add(ref)

        content = _clean_source_content(item.get("content"))
        if max_source_chars and len(content) > max_source_chars:
            content = content[:max_source_chars]

        packet = {
            "schema_version": SOURCE_PACKET_SCHEMA_VERSION,
            "source_id": _source_id(item),
            "stock_name": stock_name,
            "title": _normalize_text(item.get("title")),
            "account": _normalize_text(item.get("account")),
            "publish_time": _normalize_text(item.get("publish_time")),
            "source_kind": str(item.get("source_kind") or item.get("source_type") or "external"),
            "source_ref": ref,
            "source_url": str(item.get("url") or ref),
            "content": content,
            "source_content_hash": normalized_hash(content),
            "quality_action": "preview_only",
            "knowledge_eligible": False,
            "scoring_eligible": False,
            "risk_score_eligible": False,
            "synthesis_eligible": bool(item.get("synthesis_eligible", True)),
            "synthesis_display_only": True,
            "verification_status": str(item.get("verification_status") or "professional_observation"),
        }
        packets.append(packet)
        if max_sources and len(packets) >= max_sources:
            break

    return packets


def baseline_fact_fingerprint(baseline_text: str) -> Set[str]:
    """Build a deterministic fingerprint of baseline facts.

    The fingerprint contains:
      - normalized number+unit tokens (e.g. 营收8.22亿元, 14.25亿元)
      - event phrases from _BASELINE_EVENT_PHRASES that appear in baseline
    """
    text = _normalize_text(baseline_text)
    fingerprint: Set[str] = set()

    # Number + unit / percentage tokens with a small left context window.
    for match in re.finditer(r"([^。；;\n]{0,12})([\d.,]+\s*[万亿佰仟]?[元美元港元%％])", text):
        context = match.group(1).strip()[-6:] if match.group(1) else ""
        token = (context + match.group(2)).strip()
        if token:
            fingerprint.add(token)
        fingerprint.add(match.group(2).strip())

    # Event phrases that actually appear in baseline. For short product/topic
    # terms, capture the surrounding context so we only drop exact repeated
    # facts, not all claims that merely mention the same product.
    for phrase in _BASELINE_EVENT_PHRASES:
        idx = text.find(phrase)
        if idx == -1:
            continue
        start = max(0, idx - 10)
        end = min(len(text), idx + len(phrase) + 10)
        fingerprint.add(text[start:end].strip())

    return fingerprint


def _contains_baseline_fact(text: str, fingerprint: Set[str]) -> Tuple[bool, str]:
    normalized = _normalize_text(text)
    for phrase in fingerprint:
        if phrase and phrase in normalized:
            return True, phrase
    return False, ""


def _is_interpretive_incremental_claim(claim: Dict[str, Any]) -> bool:
    """Return whether a claim adds interpretation rather than only a repeated fact.

    LLM source quotes often include the original financial number plus the
    author's interpretation in the same sentence.  The repeated number should
    not poison the whole claim when the claim text/why_incremental make a
    clear business-quality, mechanism, dissent, or watch-variable point.
    """
    overlap = str(claim.get("baseline_overlap") or "").strip().lower()
    if overlap == "duplicate":
        return False

    claim_type = str(claim.get("claim_type") or "").strip()
    text = _normalize_text(
        " ".join(
            [
                str(claim.get("claim") or ""),
                str(claim.get("why_incremental") or ""),
                str(claim.get("topic") or ""),
            ]
        )
    )

    if claim_type in _INTERPRETIVE_CLAIM_TYPES and any(term in text for term in _INTERPRETIVE_TERMS):
        return True

    return "baseline" in text and any(term in text for term in _INTERPRETIVE_TERMS)


def _longest_common_substring_positions(a: str, b: str) -> List[Tuple[int, int, int]]:
    """Return (len, start_a, start_b) for each maximal common substring.

    Only substrings with length >= _MIN_REPAIR_EXACT_CHARS are returned.
    """
    # Suffix automaton / DP for LCS positions. For simplicity, enumerate substrings
    # of `a` from longest to shortest and collect positions in `b`. Because source
    # bodies are large but quotes are short, this is acceptable for preview.
    positions: List[Tuple[int, int, int]] = []
    seen: Set[str] = set()
    min_len = _MIN_REPAIR_EXACT_CHARS
    for length in range(len(a), min_len - 1, -1):
        current_positions: List[Tuple[int, int, int]] = []
        for i in range(len(a) - length + 1):
            substr = a[i : i + length]
            if substr in seen:
                continue
            seen.add(substr)
            idx = b.find(substr)
            if idx == -1:
                continue
            # Collect all non-overlapping occurrences in b.
            start_b = idx
            count = 0
            while start_b != -1:
                count += 1
                if count > _REPAIR_MAX_CANDIDATES:
                    break
                current_positions.append((length, i, start_b))
                start_b = b.find(substr, start_b + length)
        if current_positions:
            positions = current_positions
            break
    return positions


def repair_quote(llm_quote: str, source_content: str) -> Tuple[str, str]:
    """Repair a LLM quote to a verbatim substring of source_content.

    Returns (repaired_quote, status). status is one of:
      - "exact": no repair needed
      - "repaired": a nearby verbatim substring was chosen
      - "failed": could not deterministically repair
    """
    norm_quote = _normalize_text(llm_quote)
    norm_source = _normalize_text(source_content)
    if not norm_quote:
        return "", "failed"

    if norm_quote in norm_source:
        return norm_quote, "exact"

    positions = _longest_common_substring_positions(norm_quote, norm_source)
    if not positions:
        return "", "failed"

    # If multiple non-overlapping source positions for the longest match, fail.
    source_starts = sorted({p[2] for p in positions})
    if len(source_starts) > 1:
        # Check if they are overlapping (same occurrence repeated).
        non_overlapping = [source_starts[0]]
        for s in source_starts[1:]:
            if s >= non_overlapping[-1] + positions[0][0]:
                non_overlapping.append(s)
        if len(non_overlapping) > 1:
            return "", "failed"

    match_len, quote_start, source_start = positions[0]
    # Expand around the match to approximate the LLM quote length.
    prefix_len = max(0, quote_start)
    suffix_len = max(0, len(norm_quote) - quote_start - match_len)
    window_start = max(0, source_start - prefix_len)
    window_end = min(len(norm_source), source_start + match_len + suffix_len)
    # Allow a little slack in the window.
    slack = max(5, int(len(norm_quote) * 0.1))
    window_start = max(0, window_start - slack)
    window_end = min(len(norm_source), window_end + slack)

    # Choose the best window of length close to the quote.
    best_start = window_start
    best_score = -1
    target_len = len(norm_quote)
    for start in range(window_start, min(window_end, len(norm_source) - target_len // 2) + 1):
        end = min(len(norm_source), start + target_len + slack)
        candidate = norm_source[start:end]
        score = _quote_similarity(norm_quote, candidate)
        if score > best_score:
            best_score = score
            best_start = start

    repaired = norm_source[best_start : min(len(norm_source), best_start + target_len + slack)]
    # Trim to a sentence/phrase boundary if possible.
    repaired = _trim_to_boundary(repaired, norm_source, best_start)
    if repaired and _quote_similarity(norm_quote, repaired) >= 0.5:
        return repaired, "repaired"
    return "", "failed"


def _quote_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_set = set(_ngrams(a, 2))
    b_set = set(_ngrams(b, 2))
    if not a_set:
        return 1.0 if not b_set else 0.0
    return len(a_set & b_set) / max(len(a_set), len(b_set))


def _ngrams(text: str, n: int) -> List[str]:
    return [text[i : i + n] for i in range(len(text) - n + 1)]


def _trim_to_boundary(quote: str, source: str, start: int) -> str:
    # Try to end at a punctuation mark within the source.
    end = start + len(quote)
    # Search forward for a sentence delimiter within a small window.
    for offset in range(0, min(30, len(source) - end)):
        ch = source[end + offset]
        if ch in "。；;!！?？":
            return source[start : end + offset + 1]
    return quote


def _build_extractor_prompt(
    prompt_path: str | Path | None,
    stock_name: str,
    baseline_text: str,
    sources: List[Dict[str, Any]],
    focus_instructions: str = "",
) -> str:
    if prompt_path:
        template = Path(prompt_path).read_text(encoding="utf-8")
    else:
        template = _default_extractor_prompt()

    sources_text_parts = []
    for idx, source in enumerate(sources, start=1):
        title = source.get("title", "")
        account = source.get("account", "")
        source_ref = source.get("source_ref", "")
        content = source.get("content", "")
        sources_text_parts.append(
            f"[source {idx}]\n"
            f"title: {title}\n"
            f"account: {account}\n"
            f"url: {source_ref}\n"
            f"source_id: {source.get('source_id', '')}\n"
            f"body:\n{content}\n"
        )
    sources_text = "\n".join(sources_text_parts)

    prompt = (
        template.replace("{{stock_name}}", stock_name)
        .replace("{{baseline_text}}", baseline_text)
        .replace("{{sources_text}}", sources_text)
    )
    if focus_instructions:
        prompt += (
            "\n\n本轮抽取重点：\n"
            f"{focus_instructions}\n"
            "如果该重点下没有高质量增量观点，可以返回空 claims；"
            "不要为了凑数输出低质量或重复观点。"
        )
    return prompt


def _default_extractor_prompt() -> str:
    return """你是一名专业的投研资料整理助手。你的任务是从外部微信文章正文中，提取对 "{{stock_name}}" 的增量、分歧或待验证的外部观点，用于报告的 4.4 "外部深度观点：增量、分歧与待验证变量" 小节。

以下是当前报告 4.1-4.3 的 baseline 分析：

{{baseline_text}}

以下是已清洗的微信文章全文（source_id 已标注）：

{{sources_text}}

要求：
1. 只保留相对于 baseline 增量、分歧、机制解释或待验证变量的观点。
2. 丢弃重复 baseline 的财务数字、产品发布事实、募资金额等已覆盖事实。
3. 每条观点必须属于以下四类之一：dissent（分歧观点）、watch_variable（待验证变量）、novel_mechanism（增量机制）、context_extension（产业链/竞争格局补充）。
4. 请提取所有高质量增量观点；如 source 内容有限，也可少于 5 条。不要为了凑数输出低质量或重复观点。
5. 每条观点必须：
   - 给出 claim_type、topic、claim（观点摘要，用谨慎措辞，不要写成确认事实）
   - 给出 source_id（必须来自上文 source_id）
   - 给出 source_quote：从对应文章正文中逐字摘录的原文短句（不要改写）
   - 给出 why_incremental：说明相对于 baseline 新增了什么
   - 给出 baseline_overlap：none / partial / duplicate
6. 使用谨慎措辞，如 "外部文章认为/提示/质疑/指出"，不要用 "确认/证实/必然/确定/已落地/公司披露/公告显示/锁定"。
7. 不要输出投资建议、评分、风险评分、目标价或最终建议。
8. 输出必须是合法的 JSON，格式如下（不要 markdown 代码块）：

{
  "claims": [
    {
      "claim_type": "...",
      "topic": "...",
      "claim": "...",
      "source_id": "...",
      "source_quote": "...",
      "why_incremental": "...",
      "baseline_overlap": "none"
    }
  ]
}

如果没有增量观点，返回 {"claims": []}。
"""


def _extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    # Remove markdown fences.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # Extract the first JSON object.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in extractor output")
    return json.loads(match.group(0))


def llm_extractor_factory(
    model: str,
    base_url: str,
    api_key: str,
    *,
    stock_name: str = "",
    max_source_chars: int | None = None,
    max_sources: int | None = None,
    client: Any | None = None,
    prompt_path: str | Path | None = None,
    focus_instructions: str = "",
    max_parse_retries: int = 1,
    max_api_retries: int = 2,
    sleep_fn: Callable[[float], None] | None = None,
) -> Extractor:
    """Return an extractor that calls an OpenAI-compatible chat API."""
    import time

    _sleep = sleep_fn if sleep_fn is not None else time.sleep

    def _extract(
        sources: List[Dict[str, Any]], baseline_text: str, fingerprint: Set[str]
    ) -> List[Dict[str, Any]]:
        if max_sources:
            sources = sources[:max_sources]
        if max_source_chars:
            sources = [
                {**s, "content": s["content"][:max_source_chars]} for s in sources
            ]

        prompt = _build_extractor_prompt(
            prompt_path,
            stock_name,
            baseline_text,
            sources,
            focus_instructions=focus_instructions,
        )
        api_attempts = 0
        parse_retries_used = 0
        last_api_error = ""
        last_parse_error = ""

        while True:
            try:
                if client is None:
                    import openai

                    openai_client = openai.OpenAI(base_url=base_url, api_key=api_key)
                    response = openai_client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                        timeout=120,
                    )
                    raw = response.choices[0].message.content or ""
                else:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                    )
                    raw = response.choices[0].message.content or ""
            except Exception as api_exc:
                last_api_error = str(api_exc)
                if api_attempts >= max(0, max_api_retries):
                    raise FullBodyExtractorError("extractor_failed", last_api_error) from api_exc
                api_attempts += 1
                _sleep(2 ** (api_attempts - 1))
                continue

            try:
                payload = _extract_json(raw)
                break
            except Exception as parse_exc:
                last_parse_error = str(parse_exc)
                if parse_retries_used >= max(0, max_parse_retries):
                    raise FullBodyExtractorError("parse_failed", last_parse_error) from parse_exc
                parse_retries_used += 1

        raw_claims = payload.get("claims") or []
        if not isinstance(raw_claims, list):
            raise FullBodyExtractorError("parse_failed", "claims is not a list")

        sources_by_id = {s["source_id"]: s for s in sources}
        claims: List[Dict[str, Any]] = []
        for raw_claim in raw_claims:
            claim = _normalize_claim(raw_claim, sources_by_id, stock_name)
            if claim:
                claims.append(claim)
        return claims

    return _extract


def multipass_llm_extractor_factory(
    model: str,
    base_url: str,
    api_key: str,
    *,
    stock_name: str = "",
    max_source_chars: int | None = None,
    max_sources: int | None = None,
    client: Any | None = None,
    prompt_path: str | Path | None = None,
    pass_specs: List[Dict[str, str]] | None = None,
    max_api_retries: int = 2,
    sleep_fn: Callable[[float], None] | None = None,
) -> Extractor:
    """Return a multi-pass LLM extractor that merges theme-focused passes.

    Each pass uses the same source packets and baseline but adds a focused
    instruction. Downstream validation performs quote/hash/novelty/lint gates
    once on the merged candidates. Pass-level API or parse failures are
    recorded; the extractor continues with remaining passes and only fails
    closed when every pass fails.
    """
    specs = pass_specs or DEFAULT_MULTIPASS_SPECS
    extractors = [
        (
            spec.get("name") or f"pass_{idx}",
            llm_extractor_factory(
                model=model,
                base_url=base_url,
                api_key=api_key,
                stock_name=stock_name,
                max_source_chars=max_source_chars,
                max_sources=max_sources,
                client=client,
                prompt_path=prompt_path,
                focus_instructions=spec.get("focus") or "",
                max_api_retries=max_api_retries,
                sleep_fn=sleep_fn,
            ),
        )
        for idx, spec in enumerate(specs, start=1)
    ]

    def _extract(
        sources: List[Dict[str, Any]], baseline_text: str, fingerprint: Set[str]
    ) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        failed_passes: List[Dict[str, str]] = []
        for pass_name, extractor in extractors:
            try:
                pass_claims = extractor(sources, baseline_text, fingerprint)
                for claim in pass_claims:
                    claim["_extraction_pass"] = pass_name
                    merged.append(claim)
            except FullBodyExtractorError as exc:
                failed_passes.append(
                    {
                        "pass": pass_name,
                        "status": exc.status,
                        "message": str(exc),
                    }
                )

        if not merged and failed_passes:
            raise FullBodyExtractorError(
                "extractor_failed",
                f"all passes failed: {failed_passes}",
            )

        return _ClaimList(merged, failed_passes=failed_passes)

    return _extract


def _normalize_claim(
    raw_claim: Dict[str, Any],
    sources_by_id: Dict[str, Dict[str, Any]],
    stock_name: str,
) -> Dict[str, Any] | None:
    source_id = str(raw_claim.get("source_id") or "")
    source = sources_by_id.get(source_id)
    if not source:
        # Try to resolve by source_ref if source_id missing.
        source_ref = str(raw_claim.get("source_ref") or raw_claim.get("source_url") or "")
        for s in sources_by_id.values():
            if s.get("source_ref") == source_ref or s.get("source_url") == source_ref:
                source = s
                source_id = s["source_id"]
                break
    if not source:
        return None

    raw_quote = str(raw_claim.get("source_quote") or "")
    repaired_quote, repair_status = repair_quote(raw_quote, source["content"])
    if not repaired_quote:
        return None

    evidence_refs = raw_claim.get("evidence_refs") or [source_id]
    if not isinstance(evidence_refs, list):
        evidence_refs = [source_id]

    claim = {
        "schema_version": CLAIM_SCHEMA_VERSION,
        "claim_id": f"curated-viewpoint:{stock_name}:{normalized_hash(repaired_quote)[:16]}",
        "stock_name": stock_name,
        "claim_type": str(raw_claim.get("claim_type", "context_extension")),
        "topic": str(raw_claim.get("topic", "commercialization")),
        "claim": str(raw_claim.get("claim", "")),
        "source_quote": repaired_quote,
        "source_quote_hash": normalized_hash(repaired_quote),
        "why_incremental": str(raw_claim.get("why_incremental", "")),
        "baseline_overlap": str(raw_claim.get("baseline_overlap", "none")),
        "source_id": source_id,
        "source_title": str(source.get("title") or ""),
        "source_account": str(source.get("account") or ""),
        "source_ref": str(source.get("source_ref") or ""),
        "source_url": str(source.get("source_url") or source.get("source_ref") or ""),
        "publish_time": str(source.get("publish_time") or ""),
        "evidence_refs": evidence_refs,
        "evidence_hashes": [
            {
                "source_id": source_id,
                "source_block_hash": source["source_content_hash"],
                "source_quote_hash": normalized_hash(repaired_quote),
            }
        ],
        "verification_status": "professional_observation",
        "source_credit": DEFAULT_SOURCE_CREDIT,
        "claim_source_credit": DEFAULT_SOURCE_CREDIT,
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "synthesis_display_only": True,
        "scoring_eligible": False,
        "risk_score_eligible": False,
        "_repair_status": repair_status,
    }
    return claim


def heuristic_extractor(
    sources: List[Dict[str, Any]], baseline_text: str, fingerprint: Set[str]
) -> List[Dict[str, Any]]:
    """Deterministic fallback extractor for offline preview/testing.

    Looks for sentences that signal dissent, watch variables, or mechanisms and
    are not obvious baseline duplicates.
    """
    signal_terms = [
        "质疑",
        "担忧",
        "风险",
        "或",
        "慢半拍",
        "缺口",
        "下调",
        "否认",
        "传言",
        "分歧",
        "变量",
        "不确定",
    ]
    claims: List[Dict[str, Any]] = []
    for source in sources:
        content = source["content"]
        for sentence in re.split(r"[。；;\n]+", content):
            sentence = _normalize_text(sentence)
            if len(sentence) < 20:
                continue
            if not any(term in sentence for term in signal_terms):
                continue
            if _contains_baseline_fact(sentence, fingerprint)[0]:
                continue
            claim = {
                "schema_version": CLAIM_SCHEMA_VERSION,
                "claim_id": f"curated-viewpoint:{source.get('stock_name', '')}:{normalized_hash(sentence)[:16]}",
                "stock_name": source.get("stock_name", ""),
                "claim_type": "watch_variable",
                "topic": source.get("source_kind", "commercialization"),
                "claim": f"外部文章提示：{sentence}",
                "source_quote": sentence,
                "source_quote_hash": normalized_hash(sentence),
                "why_incremental": "baseline未明确提及该外部观察。",
                "baseline_overlap": "none",
                "source_id": source["source_id"],
                "source_title": str(source.get("title") or ""),
                "source_account": str(source.get("account") or ""),
                "source_ref": str(source.get("source_ref") or ""),
                "source_url": str(source.get("source_url") or source.get("source_ref") or ""),
                "publish_time": str(source.get("publish_time") or ""),
                "evidence_refs": [source["source_id"]],
                "evidence_hashes": [
                    {
                        "source_id": source["source_id"],
                        "source_block_hash": source["source_content_hash"],
                        "source_quote_hash": normalized_hash(sentence),
                    }
                ],
                "verification_status": "professional_observation",
                "source_credit": DEFAULT_SOURCE_CREDIT,
                "claim_source_credit": DEFAULT_SOURCE_CREDIT,
                "quality_action": "preview_only",
                "knowledge_eligible": False,
                "synthesis_display_only": True,
                "scoring_eligible": False,
                "risk_score_eligible": False,
                "_repair_status": "exact",
            }
            claims.append(claim)
            break
    return claims


def validate_claim(
    claim: Dict[str, Any],
    sources_by_id: Dict[str, Dict[str, Any]],
    baseline_fingerprint: Set[str],
) -> Tuple[bool, str, Dict[str, Any]]:
    """Validate a single claim. Returns (ok, reason, metadata)."""
    meta: Dict[str, Any] = {"repaired": claim.get("_repair_status") == "repaired"}

    if claim.get("schema_version") != CLAIM_SCHEMA_VERSION:
        return False, "wrong schema version", meta

    # Display-only safety flags.
    safe_flags = (
        claim.get("knowledge_eligible") is False
        and claim.get("scoring_eligible") is False
        and claim.get("risk_score_eligible") is False
        and claim.get("synthesis_display_only") is True
        and claim.get("quality_action") == "preview_only"
    )
    if not safe_flags:
        return False, "unsafe display-only flags", meta

    evidence_refs = claim.get("evidence_refs") or []
    if not evidence_refs:
        return False, "missing evidence_refs", meta

    resolved_source = None
    for ref in evidence_refs:
        ref_str = str(ref)
        found = None
        for s in sources_by_id.values():
            if ref_str in (s.get("source_id", ""), s.get("source_ref", ""), s.get("source_url", "")):
                found = s
                break
        if not found:
            return False, "unresolved evidence ref", meta
        if resolved_source is None:
            resolved_source = found

    source_id = str(claim.get("source_id") or "")
    if not source_id and resolved_source:
        source_id = resolved_source["source_id"]
    source = sources_by_id.get(source_id) or resolved_source
    if not source:
        return False, "unresolved evidence ref", meta

    source_quote = str(claim.get("source_quote") or "")
    norm_source = _normalize_text(source["content"])
    norm_quote = _normalize_text(source_quote)
    if not norm_quote or norm_quote not in norm_source:
        return False, "source_quote is not a normalized substring of referenced source", meta

    expected_hash = normalized_hash(source_quote)
    if str(claim.get("source_quote_hash") or "") != expected_hash:
        return False, "source_quote_hash mismatch", meta

    evidence_hashes = claim.get("evidence_hashes")
    if not isinstance(evidence_hashes, list) or not evidence_hashes:
        return False, "missing evidence_hashes", meta
    expected_block_hash = str(source.get("source_content_hash") or "")
    source_refs = {
        str(source.get("source_id") or ""),
        str(source.get("source_ref") or ""),
        str(source.get("source_url") or ""),
    }
    evidence_hash_match = False
    for entry in evidence_hashes:
        if not isinstance(entry, dict):
            continue
        entry_source = str(entry.get("source_id") or entry.get("source_ref") or entry.get("source_url") or "")
        if entry_source and entry_source not in source_refs:
            continue
        if (
            str(entry.get("source_block_hash") or "") == expected_block_hash
            and str(entry.get("source_quote_hash") or "") == expected_hash
        ):
            evidence_hash_match = True
            break
    if not evidence_hash_match:
        return False, "evidence hash mismatch", meta

    # Overclaim lint on the claim text.
    claim_text = str(claim.get("claim") or "")
    lint_text = f"{claim_text} [^1]"
    lint_result = _lint_text(lint_text, {1: {"source_type": SOURCE_TYPE, "source_credit": DEFAULT_SOURCE_CREDIT}})
    if not lint_result["ok"]:
        return False, f"overclaim lint: {lint_result['violations'][0]['term']}", meta

    # Baseline novelty guard.
    if str(claim.get("baseline_overlap") or "") == "duplicate":
        return False, "deterministic novelty guard: duplicate baseline fact", meta

    duplicate, phrase = _contains_baseline_fact(claim_text, baseline_fingerprint)
    if duplicate:
        return False, f"deterministic novelty guard: duplicate baseline fact ({phrase})", meta

    quote_duplicate, phrase = _contains_baseline_fact(source_quote, baseline_fingerprint)
    if quote_duplicate and not _is_interpretive_incremental_claim(claim):
        return False, f"deterministic novelty guard: duplicate baseline fact ({phrase})", meta

    return True, "ok", meta


def _lint_text(text: str, citations: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    # Attach a citation marker to every sentence so the citation-aware lint
    # actually inspects each sentence.
    text_with_citations = re.sub(r"([。；;\n]+)", r"[^1]\1", text)
    if not text_with_citations.endswith("[^1]"):
        text_with_citations += "[^1]"
    try:
        from curated_external_display_lint import lint_curated_external_display_text
    except Exception:
        # Fallback if lint module unavailable during early tests.
        for term in _STRONG_CONFIRMATION_TERMS:
            if term in text:
                return {
                    "ok": False,
                    "violations": [{"field": "claim", "sentence": text, "term": term}],
                }
        return {"ok": True, "violations": []}

    synthesis = {"events_catalysts": text_with_citations, "citations": citations}
    return lint_curated_external_display_text(synthesis)


def render_preview_markdown(
    stock_name: str,
    claims: List[Dict[str, Any]],
    sources_by_id: Dict[str, Dict[str, Any]],
) -> str:
    lines = [
        f"# {stock_name} 外部深度观点摘要 Preview",
        "",
        "> 本节材料仅作为专业观察，不代表官方事实判断；不参与评分、风险评分或最终建议。",
        "",
        "## 外部深度观点：增量、分歧与待验证变量",
        "",
    ]
    citations: Dict[int, Dict[str, Any]] = {}
    bullet_lines: List[str] = []
    for idx, claim in enumerate(claims, start=1):
        bullet_lines.append(_render_claim_bullet(idx, claim))
        source_id = str(claim.get("source_id") or "")
        source = sources_by_id.get(source_id)
        if source:
            citations[idx] = {
                "source_type": SOURCE_TYPE,
                "source_credit": DEFAULT_SOURCE_CREDIT,
            }

    # Final citation-aware overclaim lint on the bullets only.
    bullets_text = "\n".join(bullet_lines)
    lint_result = _lint_text(bullets_text, citations)
    if not lint_result["ok"]:
        return ""

    lines.extend(bullet_lines)
    lines.append("")
    lines.append("## 引用来源")
    lines.append("")
    for idx, claim in enumerate(claims, start=1):
        source = sources_by_id.get(str(claim.get("source_id") or ""))
        if not source:
            continue
        title = source.get("title", "")
        account = source.get("account", "")
        url = source.get("source_ref") or source.get("source_url", "")
        lines.append(f"- [^{idx}] {account} | 《{title}》 [{url}]")
    lines.append("")

    return "\n".join(lines)


def _render_claim_bullet(idx: int, claim: Dict[str, Any]) -> str:
    label = _CLAIM_TYPE_LABELS.get(claim.get("claim_type"), "外部观察")
    claim_text = str(claim.get("claim") or "").rstrip("。")
    why = str(claim.get("why_incremental") or "").rstrip("。")
    return f"- **{label}**：{claim_text}（{why}）[^{idx}]"


def _claim_passes_final_render_lint(claim: Dict[str, Any]) -> bool:
    bullet = _render_claim_bullet(1, claim)
    lint_result = _lint_text(
        bullet,
        {1: {"source_type": SOURCE_TYPE, "source_credit": DEFAULT_SOURCE_CREDIT}},
    )
    return bool(lint_result.get("ok"))


def _match_themes(
    claims: List[Dict[str, Any]],
    theme_profile: Dict[str, Any],
) -> Tuple[Set[str], Set[str]]:
    """Match claims against a theme profile and return covered/missing theme keys."""
    themes = theme_profile.get("themes") or {}
    all_keys = set(themes.keys())
    covered: Set[str] = set()

    for claim in claims:
        text_to_search = (
            str(claim.get("claim", ""))
            + " "
            + str(claim.get("topic", ""))
            + " "
            + str(claim.get("source_quote", ""))
        ).lower()
        text_to_search = _normalize_text(text_to_search)
        for theme_key, theme_spec in themes.items():
            if theme_key in covered:
                continue
            keyword_groups = theme_spec.get("keyword_groups") or []
            if keyword_groups:
                if all(
                    any(_normalize_text(kw).lower() in text_to_search for kw in group)
                    for group in keyword_groups
                ):
                    covered.add(theme_key)
                    break
                continue
            keywords = theme_spec.get("keywords") or []
            if any(_normalize_text(kw).lower() in text_to_search for kw in keywords):
                covered.add(theme_key)
                break

    return covered, all_keys - covered


def _near_duplicate_key(claim: Dict[str, Any]) -> str:
    """Build a normalization key for near-duplicate detection.

    Uses normalized claim text + topic + claim_type, stripping common cautious
    prefixes so that semantically equivalent claims cluster together.
    """
    claim_text = _normalize_text(claim.get("claim", ""))
    claim_text = re.sub(
        r"^(外部文章认为|外部文章提示|外部文章质疑|外部文章指出|市场认为|分析认为)",
        "",
        claim_text,
    )
    semantic_bucket = _near_duplicate_semantic_bucket(claim)
    if semantic_bucket:
        source_id = str(claim.get("source_id") or "")
        return normalized_hash(f"semantic:{source_id}:{semantic_bucket}")

    topic = _normalize_text(claim.get("topic", ""))
    claim_type = str(claim.get("claim_type", ""))
    return normalized_hash(f"{claim_type}:{topic}:{claim_text}")


def _near_duplicate_semantic_bucket(claim: Dict[str, Any]) -> str:
    text = _normalize_text(
        " ".join(
            [
                str(claim.get("claim") or ""),
                str(claim.get("why_incremental") or ""),
                str(claim.get("topic") or ""),
            ]
        )
    )
    for bucket, keyword_groups in _NEAR_DUPLICATE_BUCKETS:
        if all(any(keyword in text for keyword in group) for group in keyword_groups):
            return bucket
    return ""


def _claim_informativeness(claim: Dict[str, Any]) -> int:
    """Score how informative a claim is; higher score wins during near-duplicate merge."""
    score = 0
    score += len(_normalize_text(claim.get("source_quote", "")))
    score += len(_normalize_text(claim.get("claim", ""))) * 2
    if claim.get("why_incremental"):
        score += 50
    evidence_refs = claim.get("evidence_refs") or []
    if isinstance(evidence_refs, list):
        score += len(evidence_refs) * 10
    return score


def build_viewpoint_digest(
    source_packets: List[Dict[str, Any]],
    baseline_text: str,
    *,
    extractor: Extractor,
    min_display_claims: int = 2,
    stock_name: str = "",
    max_display_claims: int | None = None,
    theme_profile: Dict[str, Any] | None = None,
    min_theme_coverage: float | None = None,
) -> Dict[str, Any]:
    """Run the full-body extraction pipeline and return a digest dict.

    All qualified claims are preserved in the returned JSON.  The optional
    ``max_display_claims`` parameter is kept for backward compatibility but no
    longer slices the JSON claim list.
    """
    sources_by_id = {s["source_id"]: s for s in source_packets}
    fingerprint = baseline_fact_fingerprint(baseline_text)

    try:
        raw_claims = extractor(source_packets, baseline_text, fingerprint)
    except FullBodyExtractorError as exc:
        return {
            "schema_version": DIGEST_SCHEMA_VERSION,
            "status": exc.status,
            "stock_name": stock_name,
            "claims": [],
            "claims_count": 0,
            "source_packets_count": len(source_packets),
            "min_display_claims": min_display_claims,
            "preview_markdown": "",
            "stats": _empty_stats(min_display_claims),
            "wrote_knowledge": False,
            "connected_synthesis": False,
        }

    if not isinstance(raw_claims, list):
        raw_claims = []

    failed_passes = getattr(raw_claims, "failed_passes", [])

    # Normalize raw claims (e.g. from tests or external extractors) so they have
    # the required display-only flags and hashes before validation.
    normalized_claims: List[Dict[str, Any]] = []
    for raw_claim in raw_claims:
        norm = _normalize_claim(raw_claim, sources_by_id, stock_name)
        if norm:
            normalized_claims.append(norm)
    raw_claims = normalized_claims

    claims_extracted = len(raw_claims)
    valid_claims: List[Dict[str, Any]] = []
    drop_reasons: List[str] = []
    repaired_count = 0
    repair_failed_count = 0
    duplicate_dropped_count = 0
    merge_duplicate_dropped_count = 0
    final_overclaim_dropped_count = 0

    for claim in raw_claims:
        ok, reason, meta = validate_claim(claim, sources_by_id, fingerprint)
        if meta.get("repaired"):
            repaired_count += 1
        if ok:
            valid_claims.append(claim)
        else:
            drop_reasons.append(reason)
            if "duplicate" in reason.lower():
                duplicate_dropped_count += 1
            if "source_quote" in reason.lower():
                repair_failed_count += 1

    deduped_claims: List[Dict[str, Any]] = []
    seen_claim_keys: Set[str] = set()
    for claim in valid_claims:
        key = str(claim.get("source_quote_hash") or normalized_hash(claim.get("source_quote")))
        if key in seen_claim_keys:
            merge_duplicate_dropped_count += 1
            continue
        seen_claim_keys.add(key)
        deduped_claims.append(claim)
    valid_claims = deduped_claims

    # Stage 2: near-duplicate merge by normalized claim/topic/claim_type.
    near_duplicate_dropped_count = 0
    best_by_near_key: Dict[str, Dict[str, Any]] = {}
    for claim in valid_claims:
        near_key = _near_duplicate_key(claim)
        if near_key in best_by_near_key:
            if _claim_informativeness(claim) > _claim_informativeness(best_by_near_key[near_key]):
                best_by_near_key[near_key] = claim
            near_duplicate_dropped_count += 1
        else:
            best_by_near_key[near_key] = claim
    valid_claims = list(best_by_near_key.values())

    # NOTE: max_display_claims is intentionally not applied here so that all
    # qualified claims are retained in the JSON output.
    _ = max_display_claims

    render_safe_claims: List[Dict[str, Any]] = []
    for claim in valid_claims:
        if _claim_passes_final_render_lint(claim):
            render_safe_claims.append(claim)
        else:
            final_overclaim_dropped_count += 1
            drop_reasons.append("claim failed final rendered Markdown overclaim lint")
    valid_claims = render_safe_claims

    display_claims = len(valid_claims)

    # Theme coverage evaluation.
    theme_coverage_count = 0
    theme_coverage_total = 0
    theme_coverage_ratio = 0.0
    covered_themes: List[str] = []
    missing_themes: List[str] = []
    if theme_profile:
        covered, missing = _match_themes(valid_claims, theme_profile)
        theme_coverage_total = len(theme_profile.get("themes", {}))
        theme_coverage_count = len(covered)
        theme_coverage_ratio = (
            theme_coverage_count / theme_coverage_total if theme_coverage_total > 0 else 0.0
        )
        covered_themes = sorted(covered)
        missing_themes = sorted(missing)

    if display_claims < min_display_claims:
        if display_claims > 0:
            drop_reasons.append(f"valid claims {display_claims} < min {min_display_claims}")
        status = "no_incremental_claims"
        preview_markdown = ""
    else:
        status = "ok"
        preview_markdown = render_preview_markdown(stock_name, valid_claims, sources_by_id)
        if not preview_markdown:
            status = "lint_failed"
            drop_reasons.append("final rendered Markdown failed overclaim lint")

    # Theme coverage gate (only enforced when both profile and threshold are set).
    if (
        status == "ok"
        and theme_profile
        and min_theme_coverage is not None
        and theme_coverage_ratio < min_theme_coverage
    ):
        status = "theme_coverage_failed"
        preview_markdown = ""
        drop_reasons.append(
            f"theme coverage {theme_coverage_ratio:.2f} < min {min_theme_coverage:.2f}; "
            f"missing: {', '.join(missing_themes)}"
        )

    stats = {
        "claims_extracted": claims_extracted,
        "claims_valid": len(valid_claims),
        "claims_dropped": claims_extracted - len(valid_claims),
        "display_claims": display_claims,
        "repaired_count": repaired_count,
        "repair_failed_count": repair_failed_count,
        "duplicate_dropped_count": duplicate_dropped_count,
        "merge_duplicate_dropped_count": merge_duplicate_dropped_count,
        "near_duplicate_dropped_count": near_duplicate_dropped_count,
        "final_overclaim_dropped_count": final_overclaim_dropped_count,
        "failed_passes_count": len(failed_passes),
        "failed_passes": failed_passes,
        "min_display_claims": min_display_claims,
        "theme_coverage_count": theme_coverage_count,
        "theme_coverage_total": theme_coverage_total,
        "theme_coverage_ratio": theme_coverage_ratio,
        "covered_themes": covered_themes,
        "missing_themes": missing_themes,
        "drop_reasons": drop_reasons,
    }

    return {
        "schema_version": DIGEST_SCHEMA_VERSION,
        "status": status,
        "stock_name": stock_name,
        "claims": valid_claims,
        "claims_count": len(valid_claims),
        "source_packets_count": len(source_packets),
        "min_display_claims": min_display_claims,
        "preview_markdown": preview_markdown,
        "stats": stats,
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }


def _empty_stats(min_display_claims: int) -> Dict[str, Any]:
    return {
        "claims_extracted": 0,
        "claims_valid": 0,
        "claims_dropped": 0,
        "display_claims": 0,
        "repaired_count": 0,
        "repair_failed_count": 0,
        "duplicate_dropped_count": 0,
        "merge_duplicate_dropped_count": 0,
        "near_duplicate_dropped_count": 0,
        "final_overclaim_dropped_count": 0,
        "failed_passes_count": 0,
        "failed_passes": [],
        "min_display_claims": min_display_claims,
        "theme_coverage_count": 0,
        "theme_coverage_total": 0,
        "theme_coverage_ratio": 0.0,
        "covered_themes": [],
        "missing_themes": [],
        "drop_reasons": [],
    }


if __name__ == "__main__":
    raise SystemExit(0)
