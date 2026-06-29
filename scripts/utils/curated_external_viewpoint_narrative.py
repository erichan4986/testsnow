"""Preview-only narrative composer for curated external viewpoint claims."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List

from curated_external_display_lint import lint_curated_external_display_text


NARRATIVE_SCHEMA_VERSION = "curated_external_viewpoint_narrative.v1"
CLAIM_SCHEMA_VERSION = "curated_external_viewpoint_claim.v1"
SOURCE_TYPE = "curated_external_analysis_evidence"
DEFAULT_SOURCE_CREDIT = 55

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

    paragraphs, citations, reasons = _validate_paragraphs(payload, claims_by_id)
    if reasons:
        base["status"] = "invalid_narrative"
        base["stats"]["drop_reasons"].extend(reasons)
        return base

    display = _display_synthesis_from_paragraphs(paragraphs, citations)
    lint = lint_curated_external_display_text(display)
    base["stats"]["lint"] = lint
    if not lint.get("ok"):
        base["status"] = "lint_failed"
        base["stats"]["drop_reasons"].extend(
            f"overclaim:{item.get('term')}" for item in lint.get("violations") or []
        )
        return base

    markdown = render_narrative_markdown(stock, paragraphs, citations)
    return {
        **base,
        "status": "ok",
        "paragraphs": paragraphs,
        "paragraphs_count": len(paragraphs),
        "citations": {str(key): value for key, value in citations.items()},
        "preview_markdown": markdown,
        "stats": {
            **base["stats"],
            "claims_seen": len(claims),
            "paragraphs_count": len(paragraphs),
            "citations_count": len(citations),
        },
    }


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
        lines.append(_attach_refs_to_sentence(text, paragraph.get("citation_refs", [])))
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
) -> tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]], List[str]]:
    raw_paragraphs = payload.get("paragraphs") or []
    if not isinstance(raw_paragraphs, list) or not raw_paragraphs:
        return [], {}, ["missing paragraphs"]

    paragraphs: List[Dict[str, Any]] = []
    citations: Dict[int, Dict[str, Any]] = {}
    claim_to_ref: Dict[str, int] = {}
    reasons: List[str] = []

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
        for claim_ref in claim_refs:
            claim_id = str(claim_ref)
            claim = claims_by_id.get(claim_id)
            if not claim:
                reasons.append(f"unresolved claim_ref: {claim_id}")
                continue
            if claim_id not in claim_to_ref:
                ref_id = len(claim_to_ref) + 1
                claim_to_ref[claim_id] = ref_id
                citations[ref_id] = _citation_from_claim(claim)
            citation_refs.append(claim_to_ref[claim_id])
        if reasons:
            continue
        paragraphs.append(
            {
                "heading": _clean_text(raw.get("heading"))[:60],
                "text": text,
                "claim_refs": [str(ref) for ref in claim_refs],
                "citation_refs": citation_refs,
            }
        )
    return paragraphs, citations, reasons


def _display_synthesis_from_paragraphs(
    paragraphs: List[Dict[str, Any]], citations: Dict[int, Dict[str, Any]]
) -> Dict[str, Any]:
    text = "\n\n".join(
        f"{paragraph.get('heading', '')}："
        + _attach_refs_to_sentence(paragraph["text"], paragraph.get("citation_refs", []))
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


def _citation_from_claim(claim: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": "微信公众号精选观察",
        "author": claim.get("source_account") or claim.get("account") or "",
        "title": claim.get("source_title") or claim.get("title") or "外部观点",
        "url": claim.get("source_ref") or claim.get("source_url") or "",
        "source_type": SOURCE_TYPE,
        "source_credit": claim.get("source_credit", DEFAULT_SOURCE_CREDIT),
        "verification_status": claim.get("verification_status", "professional_observation"),
        "claim_id": claim.get("claim_id", ""),
        "source_quote_hash": claim.get("source_quote_hash", ""),
    }


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
    return """你是一名中文投研报告编辑。请把已验证的外部观点 claims 组织成 2-3 段连贯的 4.4 外部观点叙事。

股票：{{stock_name}}

当前报告 4.1-4.3 baseline：
{{baseline_text}}

可使用的 claims：
{{claims_text}}

要求：
1. 只组织已有 claims，不新增事实、数字、来源或投资建议。
2. 每段必须是“观点 -> 证据 -> 推导”的投研式叙事，并引用 1 个或多个 claim_id。
3. 使用谨慎措辞：外部材料提示/认为/指出/需要跟踪。不要写成官方确认事实。
4. 不要输出评分、风险评分、目标价、买卖建议或最终建议。
5. 输出合法 JSON，不要 markdown 代码块：
{
  "paragraphs": [
    {
      "heading": "段落小标题",
      "text": "连贯叙事段落，不要带脚注标记",
      "claim_refs": ["claim_id_1", "claim_id_2"]
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


def _attach_refs_to_sentence(text: str, refs: List[int]) -> str:
    ref_text = "".join(f"[^{ref}]" for ref in refs)
    stripped = str(text or "").strip()
    if not ref_text:
        return stripped
    if stripped.endswith(("。", "；", ";", "！", "？")):
        return f"{stripped[:-1]}{ref_text}{stripped[-1]}"
    return f"{stripped}{ref_text}"
