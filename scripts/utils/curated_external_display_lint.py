"""Citation-aware safety lint for curated external display synthesis."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


DEFAULT_CURATED_SOURCE_TYPE = "curated_external_analysis_evidence"
DEFAULT_MAX_CURATED_SOURCE_CREDIT = 65

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

_NARRATIVE_FIELDS = [
    "industry_logic",
    "fundamentals",
    "valuation_debate",
    "funding_sentiment",
    "events_catalysts",
]

_SENTENCE_DELIMITERS = re.compile(r"[。；;\n]+")
_CITATION_RE = re.compile(r"\[\^(\d+)\]")


def lint_curated_external_display_text(
    synthesis: dict,
    *,
    curated_source_type: str = DEFAULT_CURATED_SOURCE_TYPE,
    max_curated_source_credit: int = DEFAULT_MAX_CURATED_SOURCE_CREDIT,
) -> dict:
    """Return whether display synthesis text safely cites curated external evidence.

    A sentence fails when any numeric citation cannot be resolved, or when:
    - it contains a strong-confirmation term; and
    - every resolved numeric citation in that sentence is curated external
      (source_type == curated_source_type and source_credit <= threshold).

    Sentences with no numeric citations are allowed. Strong-confirmation
    sentences with at least one non-curated citation are allowed.
    """
    violations: List[Dict[str, Any]] = []
    citations = synthesis.get("citations") or {}

    for field in _NARRATIVE_FIELDS:
        text = str(synthesis.get(field) or "")
        if not text:
            continue
        for sentence in _split_sentences(text):
            if not sentence.strip():
                continue
            ref_ids = _extract_numeric_refs(sentence)
            if not ref_ids:
                continue

            curated_refs: List[int] = []
            non_curated = False
            unresolved_refs: List[int] = []
            for ref_id in ref_ids:
                meta = _lookup_citation(citations, ref_id)
                if not meta:
                    unresolved_refs.append(ref_id)
                    continue
                if _is_curated_external_citation(meta, curated_source_type, max_curated_source_credit):
                    curated_refs.append(ref_id)
                else:
                    non_curated = True
                    break

            if unresolved_refs:
                violations.append(
                    {
                        "field": field,
                        "sentence": sentence,
                        "refs": unresolved_refs,
                        "term": "unresolved_citation",
                    }
                )
                continue

            if non_curated:
                continue

            term = _find_strong_confirmation_term(sentence)
            if term:
                violations.append(
                    {
                        "field": field,
                        "sentence": sentence,
                        "refs": curated_refs,
                        "term": term,
                    }
                )

    return {"ok": not violations, "violations": violations}


def _split_sentences(text: str) -> List[str]:
    parts = _SENTENCE_DELIMITERS.split(text)
    return [part.strip() for part in parts if part.strip()]


def _extract_numeric_refs(sentence: str) -> List[int]:
    refs: List[int] = []
    for match in _CITATION_RE.finditer(sentence):
        try:
            refs.append(int(match.group(1)))
        except ValueError:
            continue
    return refs


def _lookup_citation(citations: Dict[Any, Any], ref_id: int) -> Dict[str, Any]:
    meta = citations.get(ref_id)
    if meta is None:
        meta = citations.get(str(ref_id))
    if not isinstance(meta, dict):
        return {}
    return meta


def _is_curated_external_citation(
    meta: Dict[str, Any],
    curated_source_type: str,
    max_curated_source_credit: int,
) -> bool:
    source_type = str(meta.get("source_type") or "").strip()
    if source_type != curated_source_type:
        return False
    source_credit = meta.get("source_credit")
    try:
        credit = int(source_credit) if source_credit is not None else None
    except (TypeError, ValueError):
        credit = None
    if credit is None:
        return False
    return credit <= max_curated_source_credit


def _find_strong_confirmation_term(sentence: str) -> str:
    for term in _STRONG_CONFIRMATION_TERMS:
        if term in sentence:
            return term
    return ""
