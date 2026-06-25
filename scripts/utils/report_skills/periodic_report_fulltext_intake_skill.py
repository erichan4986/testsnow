"""Helper-only Source Intake wrapper for the annual/semiannual full-text path.

This module converts local periodic-report text/cache into ``SynthesisItem``
material-layer objects.  The optional pipeline skill writes only to
``ctx["periodic_report_fulltext_items"]``; it does **not** render Source Intake
sections, and does **not** write to knowledge/reports.

Hard boundaries enforced by every public function:
- source_type = periodic_report_fulltext_analysis
- source_credit = 75
- verification_status = professional_analysis
- claim_status = professional_analysis
- knowledge_eligible = False
- report_eligible = False
- experimental = True
- LLM is off by default
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

if __name__.startswith("utils."):
    from ..periodic_report_evidence_pack import build_periodic_report_evidence_pack
    from ..periodic_report_fulltext_llm_analysis import (
        backfill_periodic_report_fulltext_analysis_sections,
        build_empty_periodic_report_fulltext_analysis,
        build_periodic_report_fulltext_item_map,
        build_periodic_report_fulltext_pack,
        render_periodic_report_fulltext_markdown,
        summarize_periodic_report_fulltext_with_llm,
    )
    from ..periodic_report_required_financial_metrics import build_required_financial_risk_metrics
    from ..periodic_report_required_metrics import build_required_business_metrics
    from ..periodic_report_structured_facts import (
        build_periodic_report_structured_fact_pack,
        filing_facts_to_core_facts,
    )
    from ..skill_pipeline import skill, SkillContext
    from ..source_adapter import SynthesisItem
else:
    from periodic_report_evidence_pack import build_periodic_report_evidence_pack
    from periodic_report_fulltext_llm_analysis import (
        backfill_periodic_report_fulltext_analysis_sections,
        build_empty_periodic_report_fulltext_analysis,
        build_periodic_report_fulltext_item_map,
        build_periodic_report_fulltext_pack,
        render_periodic_report_fulltext_markdown,
        summarize_periodic_report_fulltext_with_llm,
    )
    from periodic_report_required_financial_metrics import build_required_financial_risk_metrics
    from periodic_report_required_metrics import build_required_business_metrics
    from periodic_report_structured_facts import (
        build_periodic_report_structured_fact_pack,
        filing_facts_to_core_facts,
    )
    from skill_pipeline import skill, SkillContext
    from source_adapter import SynthesisItem

logger = logging.getLogger(__name__)


_DEFAULT_REPORT_TYPE = "annual_report"
_SOURCE_TYPE = "periodic_report_fulltext_analysis"
_FIXED_SOURCE_CREDIT = 75
_FIXED_VERIFICATION_STATUS = "professional_analysis"
_FIXED_CLAIM_STATUS = "professional_analysis"
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "periodic_reports"


def _build_stable_fulltext_id(stock_code: str, announcement_id: str, report_type: str) -> str:
    """Return a stable 12-char hex id for the full-text analysis item."""
    payload = f"{stock_code}|{announcement_id}|{report_type}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def _build_title(report_type: str, publish_time: str) -> str:
    """Return a default title for the full-text preview item."""
    label = "年度报告" if report_type == "annual_report" else "定期报告"
    if report_type == "semiannual_report":
        label = "半年度报告"
    year = ""
    if publish_time:
        match = re.search(r"(\d{4})", publish_time)
        if match:
            year = match.group(1)
    prefix = f"{year}年{label}" if year else label
    return f"{prefix} | 定期报告全文摘要（实验路径）"


def _normalize_report_type(report_type: str) -> str:
    """Normalize report type to annual_report or semiannual_report."""
    if report_type in ("annual_report", "annual"):
        return "annual_report"
    if report_type in ("semiannual_report", "semiannual", "interim_report"):
        return "semiannual_report"
    return report_type or _DEFAULT_REPORT_TYPE


def _filter_invalid_evidence_refs(
    sections: List[Dict[str, Any]],
    item_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Drop judgments whose evidence_refs are missing from item_map.

    This prevents the rendered Markdown from citing blocks that do not exist.
    """
    result = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        cleaned = dict(section)
        judgments = []
        section_title = str(section.get("title", ""))
        for judgment in section.get("judgments") or []:
            if not isinstance(judgment, dict):
                continue
            refs = judgment.get("evidence_refs") or []
            if not isinstance(refs, list) or not refs:
                continue
            if all(str(ref) in item_map for ref in refs):
                judgments.append(judgment)
            else:
                logger.warning(
                    "[%s] dropping judgment with invalid refs: %s",
                    section_title,
                    refs,
                )
        cleaned["judgments"] = judgments
        result.append(cleaned)
    return result


def build_periodic_report_fulltext_intake_item(
    stock_code: str,
    raw_text: str,
    *,
    report_type: str = "annual_report",
    announcement_id: str = "",
    publish_time: str = "",
    url: str = "",
    title: str = "",
    source_domain: str = "cninfo.com.cn",
    enable_llm: bool = False,
    llm_client: Any = None,
) -> SynthesisItem:
    """Build a single Source Intake material-layer item from periodic-report text.

    By default this produces a deterministic preview (required business metrics,
    required financial-risk metrics, and product/project/customer backfill)
    without calling an LLM.  Set ``enable_llm=True`` and provide ``llm_client``
    to augment the preview with LLM-generated sections.
    """
    report_type = _normalize_report_type(report_type)

    fulltext_pack = build_periodic_report_fulltext_pack(raw_text, report_type=report_type)
    item_map = build_periodic_report_fulltext_item_map(fulltext_pack)

    evidence_pack = build_periodic_report_evidence_pack(raw_text, report_type=report_type)
    required_metrics = build_required_business_metrics(evidence_pack, raw_text=raw_text)
    required_financial_metrics = build_required_financial_risk_metrics(
        evidence_pack, raw_text=raw_text
    )

    if enable_llm and llm_client is not None:
        analysis = summarize_periodic_report_fulltext_with_llm(
            fulltext_pack,
            llm_client,
            required_metrics=required_metrics,
            required_financial_metrics=required_financial_metrics,
        )
    else:
        analysis = build_empty_periodic_report_fulltext_analysis(
            fulltext_pack,
            include_fixed_sections=True,
        )

    # Backfill 公司画像 and 研发与技术进展 from generic product/project evidence.
    # This is deterministic and does not require an LLM.
    analysis["sections"] = backfill_periodic_report_fulltext_analysis_sections(
        analysis["sections"],
        item_map,
    )
    analysis["sections"] = _filter_invalid_evidence_refs(analysis["sections"], item_map)

    content = render_periodic_report_fulltext_markdown(
        analysis,
        required_metrics=required_metrics,
        required_financial_metrics=required_financial_metrics,
    )

    stable_id = _build_stable_fulltext_id(stock_code, announcement_id, report_type)

    return SynthesisItem(
        title=title or _build_title(report_type, publish_time),
        content=content,
        author="",
        source_platform="定期报告全文",
        url=url,
        publish_time=publish_time,
        interaction_score=0,
        extra={
            "source_type": _SOURCE_TYPE,
            "source_credit": _FIXED_SOURCE_CREDIT,
            "source_domain": source_domain or "cninfo.com.cn",
            "verification_status": _FIXED_VERIFICATION_STATUS,
            "claim_status": _FIXED_CLAIM_STATUS,
            "knowledge_eligible": False,
            "report_eligible": False,
            "source_intake_display_eligible": True,
            "periodic_report_type": report_type,
            "periodic_report_audit_status": fulltext_pack.get("audit_status", "unknown"),
            "periodic_report_fulltext_id": stable_id,
            "experimental": True,
        },
    )


def build_periodic_report_fulltext_intake_items_from_cache(
    stock_code: str,
    cache_dir: Union[str, Path],
    *,
    stock_name: str = "",
    report_type: str = "annual_report",
    enable_llm: bool = False,
    llm_client: Any = None,
) -> List[SynthesisItem]:
    """Build full-text intake items from local cache files.

    Reads ``data/raw/periodic_reports/*_annual_jina.txt`` or
    ``*_semiannual_jina.txt`` style caches.  If multiple caches match, the
    most recently modified file is used and only one item is returned.

    Missing cache directories return an empty list without raising.
    """
    latest = _find_latest_periodic_report_cache_file(
        stock_code=stock_code,
        stock_name=stock_name,
        cache_dir=cache_dir,
        report_type=report_type,
    )
    if latest is None:
        return []

    try:
        raw_text = latest.read_text(encoding="utf-8")
    except Exception:
        return []

    # Use the cache filename stem as a fallback announcement id so the stable id
    # is still deterministic and distinct from the original cninfo announcement.
    announcement_id = latest.stem

    item = build_periodic_report_fulltext_intake_item(
        stock_code=stock_code,
        raw_text=raw_text,
        report_type=report_type,
        announcement_id=announcement_id,
        source_domain=_infer_source_domain_from_cache_file(latest),
        enable_llm=enable_llm,
        llm_client=llm_client,
    )
    return [item]


def build_periodic_report_filing_core_facts_from_cache(
    *,
    stock_code: str,
    stock_name: str,
    cache_dir: Union[str, Path],
    report_type: str = "annual_report",
) -> List[Dict[str, Any]]:
    """Build deterministic core facts from the latest local periodic report cache."""
    latest = _find_latest_periodic_report_cache_file(
        stock_code=stock_code,
        stock_name=stock_name,
        cache_dir=cache_dir,
        report_type=report_type,
    )
    if latest is None:
        return []
    try:
        raw_text = latest.read_text(encoding="utf-8")
    except Exception:
        return []
    if not raw_text.strip():
        return []

    normalized_report_type = _normalize_report_type(report_type)
    structured_report_type = _structured_report_type(normalized_report_type)
    report_year = _infer_report_year_from_cache_file(latest)
    evidence_pack = build_periodic_report_evidence_pack(
        raw_text,
        report_type=structured_report_type,
    )
    required_financial_metrics = build_required_financial_risk_metrics(
        evidence_pack,
        raw_text=raw_text,
    )
    fact_pack = build_periodic_report_structured_fact_pack(
        stock_code=stock_code,
        stock_name=stock_name,
        report_year=report_year,
        report_type=structured_report_type,
        evidence_pack=evidence_pack,
        required_financial_metrics=required_financial_metrics,
    )
    return filing_facts_to_core_facts(fact_pack.get("filing_facts") or [])


def _find_latest_periodic_report_cache_file(
    *,
    stock_code: str,
    stock_name: str = "",
    cache_dir: Union[str, Path],
    report_type: str = "annual_report",
) -> Optional[Path]:
    cache_path = Path(cache_dir)
    if not cache_path.exists() or not cache_path.is_dir():
        return None

    report_type = _normalize_report_type(report_type)
    prefixes = [stock_code]
    if stock_name:
        prefixes.append(stock_name)
    if report_type == "annual_report":
        patterns = tuple(
            pattern
            for prefix in prefixes
            for pattern in (
                f"{prefix}_*_annual_jina*.txt",
                f"{prefix}_*annual_jina*.txt",
                f"{prefix}_*_annual_zh_jina*.txt",
                f"{prefix}_*_annual_en_jina*.txt",
            )
        )
    elif report_type == "semiannual_report":
        patterns = tuple(
            pattern
            for prefix in prefixes
            for pattern in (
                f"{prefix}_*_semiannual_jina*.txt",
                f"{prefix}_*semiannual_jina*.txt",
                f"{prefix}_*_semiannual_zh_jina*.txt",
                f"{prefix}_*_semiannual_en_jina*.txt",
                f"{prefix}_*_interim_zh_jina*.txt",
                f"{prefix}_*_interim_en_jina*.txt",
            )
        )
    else:
        patterns = tuple(f"{prefix}_*_jina*.txt" for prefix in prefixes)

    files: List[Path] = []
    search_dirs = [cache_path]
    hk_cache_path = cache_path / "hk"
    if hk_cache_path.exists() and hk_cache_path.is_dir():
        search_dirs.append(hk_cache_path)
    for directory in search_dirs:
        for pattern in patterns:
            files.extend(directory.glob(pattern))

    if not files:
        return None
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def _infer_report_year_from_cache_file(cache_file: Path) -> int:
    match = re.search(r"(20\d{2})", cache_file.stem)
    return int(match.group(1)) if match else 0


def _structured_report_type(report_type: str) -> str:
    if report_type == "annual_report":
        return "annual"
    if report_type == "semiannual_report":
        return "semiannual"
    return report_type


def _infer_source_domain_from_cache_file(cache_file: Path) -> str:
    """Infer source domain from cache layout/name."""
    if cache_file.parent.name == "hk" or re.search(r"_(?:zh|en)_jina", cache_file.name):
        return "hkexnews.hk"
    return "cninfo.com.cn"


@skill(name="periodic_report_fulltext_intake")
def periodic_report_fulltext_intake_skill(ctx: SkillContext) -> SkillContext:
    """Read periodic report fulltext cache and write items to a dedicated ctx key.

    This skill does NOT write to external_evidence_keep_items, does NOT call
    LLMs, and does NOT fetch URLs.  Missing cache is silently ignored.
    """
    stock_name = ctx.get("stock_name", "")
    stock_codes = ctx.get("stock_codes", {}) or {}
    stock_code = stock_codes.get(stock_name, "")

    if not stock_code:
        ctx.set("periodic_report_fulltext_items", [])
        ctx.set("periodic_report_fulltext_status", "skipped_no_stock_code")
        return ctx

    cache_dir = ctx.get("periodic_report_fulltext_cache_dir", _DEFAULT_CACHE_DIR)
    report_type = ctx.get("periodic_report_fulltext_report_type", _DEFAULT_REPORT_TYPE)

    items = build_periodic_report_fulltext_intake_items_from_cache(
        stock_code=stock_code,
        cache_dir=cache_dir,
        stock_name=stock_name,
        report_type=report_type,
        enable_llm=False,
        llm_client=None,
    )
    filing_core_facts = build_periodic_report_filing_core_facts_from_cache(
        stock_code=stock_code,
        stock_name=stock_name,
        cache_dir=cache_dir,
        report_type=report_type,
    )

    ctx.set("periodic_report_fulltext_items", items)
    ctx.set("periodic_report_filing_core_facts", filing_core_facts)
    ctx.set("periodic_report_fulltext_status", "ok" if items else "empty")
    return ctx
