"""Preview-only narrative composer for curated external viewpoint claims."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List

from curated_external_display_lint import lint_curated_external_display_text
from curated_external_display import attach_refs_to_sentence, truncate_curated_source_excerpt


NARRATIVE_SCHEMA_VERSION = "curated_external_viewpoint_narrative.v1"
CLAIM_SCHEMA_VERSION = "curated_external_viewpoint_claim.v1"
SOURCE_TYPE = "curated_external_analysis_evidence"
DEFAULT_SOURCE_CREDIT = 55
MODEL_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z]{1,8}\d[A-Za-z0-9.]{0,12}|\d+(?:\.\d+)?[A-Za-z]{1,8})(?![A-Za-z0-9])"
)
QUANTITY_PATTERNS = [
    re.compile(r"\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?"),
    re.compile(r"\d+(?:\.\d+)?\s*(?:%|％)\s*[-–—~至到]\s*\d+(?:\.\d+)?\s*(?:%|％)"),
    re.compile(r"\d+(?:\.\d+)?\s*[-–—~至到]\s*\d+(?:\.\d+)?\s*(?:%|％)"),
    re.compile(r"\d+(?:\.\d+)?\s*(?:%|％)"),
    re.compile(r"\d+(?:\.\d+)?\s*(?:亿元|万元|个月|万|亿|元|只|台|款|家|个|倍|年|月|G|T)"),
    re.compile(r"(?<![A-Za-z0-9.])\d{3,}(?:\.\d+)?(?![A-Za-z0-9.])"),
    re.compile(r"[一二三四五六七八九十两半]+分之[一二三四五六七八九十两半]+"),
]

Composer = Callable[[List[Dict[str, Any]], str, str], Dict[str, Any]]


class NarrativeComposerError(Exception):
    """Structured fail-closed narrative composer exception."""

    def __init__(self, status: str, message: str = ""):
        super().__init__(message or status)
        self.status = status


def build_viewpoint_narrative(
    digest: Dict[str, Any],
    baseline_text: str,
    *,
    composer: Composer,
    stock_name: str = "",
) -> Dict[str, Any]:
    """Build a cited 4.4-style narrative from a validated viewpoint digest."""
    stock = stock_name or str(digest.get("stock_name") or "")
    base = _empty_result(stock)

    if digest.get("status") != "ok":
        base["status"] = "source_digest_not_ok"
        base["stats"]["drop_reasons"].append(f"source digest status={digest.get('status')}")
        return base

    claims = [claim for claim in digest.get("claims") or [] if _is_safe_claim(claim)]
    if not claims:
        base["status"] = "no_safe_claims"
        base["stats"]["drop_reasons"].append("no safe display-only claims")
        return base

    claims_by_id = {str(claim.get("claim_id") or ""): claim for claim in claims}
    try:
        payload = composer(claims, baseline_text, stock)
    except NarrativeComposerError as exc:
        base["status"] = exc.status
        base["stats"]["drop_reasons"].append(str(exc))
        return base
    except Exception as exc:
        base["status"] = "composer_failed"
        base["stats"]["drop_reasons"].append(str(exc))
        return base

    paragraphs, citations, reasons, claim_ref_repairs = _validate_paragraphs(payload, claims_by_id)
    base["stats"]["claim_ref_repaired_count"] = len(claim_ref_repairs)
    base["stats"]["claim_ref_repairs"] = claim_ref_repairs
    reasons.extend(_unsupported_model_token_reasons(paragraphs, claims_by_id, stock))
    reasons.extend(_unsupported_quantity_reasons(paragraphs, claims_by_id))
    if reasons:
        base["status"] = "invalid_narrative"
        base["stats"]["drop_reasons"].extend(reasons)
        return base

    paragraphs, citations, lint_drop_stats = _drop_overclaim_paragraphs(paragraphs, citations)
    base["stats"].update(lint_drop_stats)
    if not paragraphs:
        base["status"] = "lint_failed"
        base["stats"]["drop_reasons"].extend(
            f"overclaim:{item.get('term')}"
            for dropped in lint_drop_stats.get("final_overclaim_dropped", [])
            for item in dropped.get("violations", [])
        )
        return base
    base["stats"]["lint"] = lint_curated_external_display_text(
        _display_synthesis_from_paragraphs(paragraphs, citations)
    )

    reasoning_cards = _normalize_reasoning_cards(payload.get("reasoning_cards") or [], citations)
    markdown = render_narrative_markdown(stock, paragraphs, citations)
    return {
        **base,
        "status": "ok",
        "paragraphs": paragraphs,
        "paragraphs_count": len(paragraphs),
        "reasoning_cards": reasoning_cards,
        "citations": {str(key): value for key, value in citations.items()},
        "preview_markdown": markdown,
        "stats": {
            **base["stats"],
            "claims_seen": len(claims),
            "paragraphs_count": len(paragraphs),
            "citations_count": len(citations),
        },
    }


def _drop_overclaim_paragraphs(
    paragraphs: List[Dict[str, Any]],
    citations: Dict[int, Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]], Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    for idx, paragraph in enumerate(paragraphs, start=1):
        paragraph_citations = {
            ref: citations[ref] for ref in paragraph.get("citation_refs", []) if ref in citations
        }
        lint = lint_curated_external_display_text(
            _display_synthesis_from_paragraphs([paragraph], paragraph_citations)
        )
        if lint.get("ok"):
            kept.append(paragraph)
            continue
        dropped.append(
            {
                "paragraph_index": idx,
                "heading": paragraph.get("heading", ""),
                "violations": lint.get("violations") or [],
            }
        )

    kept, citations = _compact_citations(kept, citations)
    return kept, citations, {
        "final_overclaim_dropped_count": len(dropped),
        "final_overclaim_dropped": dropped,
    }


def _compact_citations(
    paragraphs: List[Dict[str, Any]],
    citations: Dict[int, Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]]]:
    old_to_new: Dict[int, int] = {}
    compacted_citations: Dict[int, Dict[str, Any]] = {}
    compacted_paragraphs: List[Dict[str, Any]] = []

    for paragraph in paragraphs:
        compacted_refs: List[int] = []
        for old_ref in paragraph.get("citation_refs", []):
            if old_ref not in citations:
                continue
            if old_ref not in old_to_new:
                new_ref = len(old_to_new) + 1
                old_to_new[old_ref] = new_ref
                compacted_citations[new_ref] = citations[old_ref]
            compacted_refs.append(old_to_new[old_ref])
        compacted_paragraphs.append({**paragraph, "citation_refs": compacted_refs})

    return compacted_paragraphs, compacted_citations


def heuristic_narrative_composer(
    claims: List[Dict[str, Any]], baseline_text: str, stock_name: str
) -> Dict[str, Any]:
    """Offline fallback composer for tests and local shape previews."""
    del baseline_text
    first = claims[:3]
    if not first:
        return {"paragraphs": []}
    refs = [str(claim.get("claim_id") or "") for claim in first]
    joined = "；".join(str(claim.get("claim") or "").rstrip("。") for claim in first)
    return {
        "paragraphs": [
            {
                "heading": "外部观点主线",
                "text": (
                    f"外部材料对{stock_name}的增量主要集中在这些待验证变量：{joined}。"
                    "这些线索需要和公司交付能力、上游供给和客户需求持续性一起观察。"
                ),
                "claim_refs": refs,
            }
        ]
    }


def llm_narrative_composer_factory(
    model: str,
    base_url: str,
    api_key: str,
    *,
    client: Any | None = None,
    prompt_path: str | Path | None = None,
) -> Composer:
    """Return an OpenAI-compatible composer for validated claim narratives."""

    def _compose(claims: List[Dict[str, Any]], baseline_text: str, stock_name: str) -> Dict[str, Any]:
        prompt = _build_prompt(prompt_path, claims, baseline_text, stock_name)
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
        try:
            return _extract_json(raw)
        except Exception as exc:
            raise NarrativeComposerError("parse_failed", str(exc)) from exc

    return _compose


def render_narrative_markdown(
    stock_name: str,
    paragraphs: List[Dict[str, Any]],
    citations: Dict[int, Dict[str, Any]],
) -> str:
    lines = [
        f"# {stock_name} 精选外部观点叙事 Preview",
        "",
        "### 4.4 精选外部观察（Preview）",
        "",
        "> 精选外部材料仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。",
        "",
    ]
    for paragraph in paragraphs:
        heading = str(paragraph.get("heading") or "").strip()
        if heading:
            lines.append(f"**{heading}**")
            lines.append("")
        text = str(paragraph.get("text") or "").strip()
        lines.append(attach_refs_to_sentence(text, paragraph.get("citation_refs", [])))
        lines.append("")

    lines.append("**本节引用来源：**")
    for ref_id in sorted(citations):
        meta = citations[ref_id]
        line = f"- [^{ref_id}] {meta.get('source', '微信公众号精选观察')}"
        if meta.get("author"):
            line += f" | 作者: {meta['author']}"
        if meta.get("title"):
            line += f" | 《{meta['title']}》"
        if meta.get("url"):
            line += f" | {meta['url']}"
        lines.append(line)
    lines.append("")
    return "\n".join(lines)


def _validate_paragraphs(
    payload: Dict[str, Any],
    claims_by_id: Dict[str, Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]], List[str], List[Dict[str, str]]]:
    raw_paragraphs = payload.get("paragraphs") or []
    if not isinstance(raw_paragraphs, list) or not raw_paragraphs:
        return [], {}, ["missing paragraphs"], []

    paragraphs: List[Dict[str, Any]] = []
    citations: Dict[int, Dict[str, Any]] = {}
    claim_to_ref: Dict[str, int] = {}
    reasons: List[str] = []
    claim_ref_repairs: List[Dict[str, str]] = []

    for idx, raw in enumerate(raw_paragraphs[:4], start=1):
        if not isinstance(raw, dict):
            reasons.append(f"paragraph {idx} is not an object")
            continue
        text = _clean_text(raw.get("text"))
        if len(text) < 20:
            reasons.append(f"paragraph {idx} too short")
            continue
        claim_refs = raw.get("claim_refs") or []
        if not isinstance(claim_refs, list) or not claim_refs:
            reasons.append(f"paragraph {idx} missing claim_refs")
            continue
        citation_refs: List[int] = []
        resolved_claim_refs: List[str] = []
        for claim_ref in claim_refs:
            claim_id, claim, repair, error = _resolve_claim_ref(claim_ref, claims_by_id)
            if error:
                reasons.append(error)
                continue
            if not claim:
                continue
            if repair:
                claim_ref_repairs.append(repair)
            if claim_id not in claim_to_ref:
                ref_id = len(claim_to_ref) + 1
                claim_to_ref[claim_id] = ref_id
                citations[ref_id] = _citation_from_claim(claim)
            citation_refs.append(claim_to_ref[claim_id])
            resolved_claim_refs.append(claim_id)
        if reasons:
            continue
        paragraphs.append(
            {
                "heading": _clean_text(raw.get("heading"))[:60],
                "text": text,
                "claim_refs": resolved_claim_refs,
                "citation_refs": citation_refs,
            }
        )
    return paragraphs, citations, reasons, claim_ref_repairs


def _resolve_claim_ref(
    raw_claim_ref: Any,
    claims_by_id: Dict[str, Dict[str, Any]],
) -> tuple[str, Dict[str, Any], Dict[str, str], str]:
    claim_ref = str(raw_claim_ref or "").strip()
    if not claim_ref:
        return "", {}, {}, "unresolved claim_ref: "
    exact = claims_by_id.get(claim_ref)
    if exact:
        return claim_ref, exact, {}, ""

    matches = [
        claim_id
        for claim_id in claims_by_id
        if claim_id.rsplit(":", 1)[-1] == claim_ref or claim_id.endswith(f":{claim_ref}")
    ]
    if len(matches) == 1:
        repaired = matches[0]
        return repaired, claims_by_id[repaired], {"from": claim_ref, "to": repaired}, ""
    if len(matches) > 1:
        return "", {}, {}, f"ambiguous claim_ref: {claim_ref}"
    return "", {}, {}, f"unresolved claim_ref: {claim_ref}"


def _display_synthesis_from_paragraphs(
    paragraphs: List[Dict[str, Any]], citations: Dict[int, Dict[str, Any]]
) -> Dict[str, Any]:
    text = "\n\n".join(
        f"{paragraph.get('heading', '')}："
        + _attach_refs_to_each_sentence_for_lint(paragraph["text"], paragraph.get("citation_refs", []))
        for paragraph in paragraphs
    )
    return {
        "industry_logic": text,
        "fundamentals": "",
        "valuation_debate": "",
        "funding_sentiment": "",
        "events_catalysts": "",
        "citations": citations,
    }


def _normalize_reasoning_cards(
    raw_cards: Any,
    citations: Dict[int, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not isinstance(raw_cards, list):
        return []
    claim_to_ref = {
        str(meta.get("claim_id") or "").strip(): ref_id
        for ref_id, meta in citations.items()
        if str(meta.get("claim_id") or "").strip()
    }
    cards: List[Dict[str, Any]] = []
    for raw in raw_cards:
        if not isinstance(raw, dict):
            continue
        claim_id = str(raw.get("claim_id") or "").strip()
        ref_id = claim_to_ref.get(claim_id)
        if not ref_id:
            continue
        excerpt, truncated = truncate_curated_source_excerpt(_clean_text(raw.get("source_excerpt", "")))
        cards.append({
            "claim_id": claim_id,
            "display_topic": _clean_text(raw.get("display_topic"))[:60],
            "claim": _clean_text(raw.get("claim"))[:160],
            "source_excerpt": excerpt,
            "excerpt_truncated": bool(raw.get("excerpt_truncated")) or truncated,
            "reasoning_steps": _clean_text_list(raw.get("reasoning_steps")),
            "numbers_used": _clean_text_list(raw.get("numbers_used")),
            "assumptions": _clean_text_list(raw.get("assumptions")),
            "counterpoints": _clean_text_list(raw.get("counterpoints")),
            "verification_need": _clean_text(raw.get("verification_need"))[:160],
            "citation_refs": [ref_id],
        })
    return cards[:8]


def _clean_text_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item)[:120] for item in value if _clean_text(item)][:4]


def _unsupported_model_token_reasons(
    paragraphs: List[Dict[str, Any]],
    claims_by_id: Dict[str, Dict[str, Any]],
    stock_name: str = "",
) -> List[str]:
    reasons: List[str] = []
    stock_tokens = _model_tokens(stock_name)
    for idx, paragraph in enumerate(paragraphs, start=1):
        paragraph_tokens = _model_tokens(
            f"{paragraph.get('heading', '')} {paragraph.get('text', '')}"
        )
        if not paragraph_tokens:
            continue
        allowed_texts: List[str] = []
        for claim_id in paragraph.get("claim_refs") or []:
            claim = claims_by_id.get(str(claim_id)) or {}
            allowed_texts.extend(
                str(claim.get(field) or "")
                for field in (
                    "claim",
                    "source_quote",
                    "source_title",
                    "why_incremental",
                    "topic",
                )
            )
        allowed_tokens = _model_tokens(" ".join(allowed_texts))
        allowed_tokens.update(stock_tokens)
        for token in sorted(paragraph_tokens - allowed_tokens):
            reasons.append(f"paragraph {idx} unsupported_model_token:{token}")
    return reasons


def _unsupported_quantity_reasons(
    paragraphs: List[Dict[str, Any]],
    claims_by_id: Dict[str, Dict[str, Any]],
) -> List[str]:
    reasons: List[str] = []
    for idx, paragraph in enumerate(paragraphs, start=1):
        paragraph_quantities = _quantity_tokens(
            f"{paragraph.get('heading', '')} {paragraph.get('text', '')}"
        )
        if not paragraph_quantities:
            continue
        allowed_quantities = _quantity_tokens(
            " ".join(_claim_allowed_texts(paragraph.get("claim_refs") or [], claims_by_id))
        )
        for quantity in sorted(paragraph_quantities - allowed_quantities):
            reasons.append(f"paragraph {idx} unsupported_quantity:{quantity}")
    return reasons


def _claim_allowed_texts(
    claim_refs: List[str],
    claims_by_id: Dict[str, Dict[str, Any]],
) -> List[str]:
    allowed_texts: List[str] = []
    for claim_id in claim_refs:
        claim = claims_by_id.get(str(claim_id)) or {}
        allowed_texts.extend(
            str(claim.get(field) or "")
            for field in (
                "claim",
                "source_quote",
                "source_title",
                "why_incremental",
                "topic",
            )
        )
    return allowed_texts


def _model_tokens(text: str) -> set[str]:
    return {match.group(0).upper() for match in MODEL_TOKEN_RE.finditer(str(text or ""))}


def _quantity_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    clean = str(text or "")
    for pattern in QUANTITY_PATTERNS:
        for match in pattern.finditer(clean):
            token = _normalize_quantity_token(match.group(0))
            if token:
                tokens.add(token)
    return tokens


def _normalize_quantity_token(token: str) -> str:
    normalized = re.sub(r"\s+", "", str(token or ""))
    return (
        normalized.replace("％", "%")
        .replace("–", "-")
        .replace("—", "-")
        .replace("~", "-")
        .replace("至", "-")
        .replace("到", "-")
    )


def _citation_from_claim(claim: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": _source_label_from_claim(claim),
        "author": claim.get("source_account") or claim.get("account") or "",
        "title": claim.get("source_title") or claim.get("title") or "外部观点",
        "url": claim.get("source_ref") or claim.get("source_url") or "",
        "source_type": SOURCE_TYPE,
        "source_credit": claim.get("source_credit", DEFAULT_SOURCE_CREDIT),
        "verification_status": claim.get("verification_status", "professional_observation"),
        "claim_id": claim.get("claim_id", ""),
        "source_quote_hash": claim.get("source_quote_hash", ""),
    }


def _source_label_from_claim(claim: Dict[str, Any]) -> str:
    explicit_label = str(claim.get("source_label") or "").strip()
    if explicit_label:
        return explicit_label
    kind = str(claim.get("source_kind") or "").lower()
    platform = str(claim.get("source_platform") or "").lower()
    ref = str(claim.get("source_ref") or claim.get("source_url") or "").lower()
    title = str(claim.get("source_title") or claim.get("title") or "")
    marker = " ".join([kind, platform, ref, title.lower()])
    if "xueqiu" in marker or "雪球" in marker:
        if "回复@" in marker or "回复 @" in marker:
            return "雪球评论观察"
        if "专栏" in marker:
            return "雪球专栏观察"
        return "雪球精选观察"
    if "zhihu" in marker or "知乎" in marker:
        return "知乎精选观察"
    if "eastmoney" in marker or "东方财富" in marker:
        return "东方财富精选观察"
    if "wechat" in marker or "weixin" in marker or "mp.weixin.qq.com" in marker:
        return "微信公众号精选观察"
    return "外部精选观察"


def _is_safe_claim(claim: Dict[str, Any]) -> bool:
    if not isinstance(claim, dict):
        return False
    return (
        claim.get("schema_version") == CLAIM_SCHEMA_VERSION
        and claim.get("quality_action") == "preview_only"
        and claim.get("knowledge_eligible") is False
        and claim.get("synthesis_display_only") is True
        and claim.get("scoring_eligible") is False
        and claim.get("risk_score_eligible") is False
        and claim.get("verification_status") == "professional_observation"
        and str(claim.get("claim_id") or "").strip()
        and str(claim.get("source_quote_hash") or "").strip()
    )


def _empty_result(stock_name: str) -> Dict[str, Any]:
    return {
        "schema_version": NARRATIVE_SCHEMA_VERSION,
        "status": "not_started",
        "stock_name": stock_name,
        "paragraphs": [],
        "paragraphs_count": 0,
        "citations": {},
        "preview_markdown": "",
        "stats": {"drop_reasons": []},
        "wrote_repo_path": False,
        "wrote_knowledge": False,
        "connected_synthesis": False,
        "connected_scoring": False,
        "connected_risk": False,
    }


def _build_prompt(
    prompt_path: str | Path | None,
    claims: List[Dict[str, Any]],
    baseline_text: str,
    stock_name: str,
) -> str:
    if prompt_path:
        template = Path(prompt_path).read_text(encoding="utf-8")
    else:
        template = _default_prompt()

    claims_text = []
    for claim in claims:
        claims_text.append(
            "\n".join(
                [
                    f"claim_id: {claim.get('claim_id', '')}",
                    f"type: {claim.get('claim_type', '')}",
                    f"topic: {claim.get('topic', '')}",
                    f"title: {claim.get('source_title', '')}",
                    f"claim: {claim.get('claim', '')}",
                    f"why_incremental: {claim.get('why_incremental', '')}",
                    f"source_quote: {claim.get('source_quote', '')}",
                ]
            )
        )
    return (
        template.replace("{{stock_name}}", stock_name)
        .replace("{{baseline_text}}", baseline_text)
        .replace("{{claims_text}}", "\n\n".join(claims_text))
    )


def _default_prompt() -> str:
    return """你是一名中文投研报告编辑。请把已验证的外部观点 claims 组织成报告 4.4 的连贯叙事。

股票：{{stock_name}}

当前报告 4.1-4.3 baseline：
{{baseline_text}}

可使用的已验证 claims：
{{claims_text}}

工作方式：
1. 先做叙事规划：根据 claims 的真实内容，自动识别 2-4条最适合该股票的外部观点主线。
2. 不要硬套固定分类，也不要复用其他股票的标题或个股专属结构。
3. 不要平均分配 claims。只保留能解释公司基本面、上下游、竞争格局、商业化节奏、技术路线、财务质量或市场预期的增量主线。
4. 同一主题、同一来源或高度重复的 claims 应合并到同一段；低质量、只有情绪、或缺乏推导价值的 claims 可以丢弃。

写作要求：
1. 生成 2-4 段中文投研叙事，每段遵循“观点 -> 证据 -> 推导”的结构。
2. 重点回答：外部材料相对 baseline 新增了什么；这些增量如何影响公司基本面、上游/下游或竞争格局判断。
3. 只使用 claims 中已有信息，不新增事实、数字、来源、评级、目标价或投资建议。
   - 不得计算、换算、推导或概括任何数字。
   - 不得生成 claims 中未逐字出现的比例、倍数、排名、体量比较或市场份额。
   - 如果 claims 只有定性表达，就只能写定性推导，不要补充量化比较。
4. 必须使用谨慎措辞，例如“外部材料提示/认为/指出/仍需跟踪”，不要写成官方确认事实。
5. 不要使用“确认/证实/必然/确定/已落地/公司披露/公告显示/锁定”等强确认措辞。
6. 每段必须引用 1 个或多个 claim_id，并把它们放在 claim_refs。
   - claim_refs 必须逐字复制完整 claim_id，包括 curated-viewpoint:股票名: 前缀。
   - 不得只输出尾部 hash，不得改写、截断、省略或重新编号 claim_id。
7. 输出合法 JSON，不要 markdown 代码块：
{
  "paragraphs": [
    {
      "heading": "段落小标题",
      "text": "连贯叙事段落，不要带脚注标记",
      "claim_refs": ["curated-viewpoint:股票名:完整hash"]
    }
  ]
}
"""


def _extract_json(text: str) -> Dict[str, Any]:
    text = str(text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found")
    return json.loads(match.group(0))


def _clean_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text.strip("`")


def _attach_refs_to_each_sentence_for_lint(text: str, refs: List[int]) -> str:
    ref_text = "".join(f"[^{ref}]" for ref in refs)
    stripped = str(text or "").strip()
    if not ref_text or not stripped:
        return stripped

    parts = re.split(r"([。；;！？\n]+)", stripped)
    rendered: List[str] = []
    for i in range(0, len(parts), 2):
        sentence = parts[i].strip()
        delimiter = parts[i + 1] if i + 1 < len(parts) else ""
        if not sentence:
            if delimiter:
                rendered.append(delimiter)
            continue
        rendered.append(f"{sentence}{ref_text}{delimiter}")
    return "".join(rendered)
