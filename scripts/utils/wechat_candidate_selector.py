"""Preview-only selector for WeChat article candidates.

The selector is deliberately deterministic and local.  It decides whether a
candidate deserves follow-up review/download, but never writes Knowledge and
never promotes WeChat material into scoring, risk, or confirmed facts.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


DEFAULT_WECHAT_CANDIDATE_PREVIEW_PATH = Path("/tmp/wechat_candidate_selector_preview.md")

ACTION_KEEP = "keep"
ACTION_PRODUCT_SIGNAL = "product_signal"
ACTION_DROP = "drop"
ACTION_DUPLICATE = "duplicate"

_DROP_PATTERNS = (
    "展会",
    "邀请函",
    "邀您",
    "共赴",
    "招聘",
    "校招",
    "校园",
    "实习",
    "加入我们",
    "直播预约",
    "报名",
    "抽奖",
    "福利",
    "加星标",
    "荣获",
    "价值评选",
    "金牛奖",
    "奖项",
    "上市首日涨",
    "十个涨停",
    "涨停后",
    "股价将是",
)

_CAPITAL_MARKET_FLASH_PATTERNS = (
    "同日招股",
    "拟本月上市",
    "港交所",
    "03661.hk",
    "上市首日",
    "股价大涨",
)

_ANALYSIS_PATTERNS = (
    "深度",
    "复盘",
    "周期",
    "趋势",
    "格局",
    "分化",
    "观察",
    "谁能",
    "产业",
    "行业",
    "国产替代",
    "盈利",
    "涨价",
    "复苏",
    "火烧到了",
    "一哥",
    "港股",
    "递表",
    "招股",
    "上市",
    "IPO",
    "账本",
    "财务分析",
    "收入结构",
    "研发投入",
    "盈利质量",
)

_PRODUCT_PATTERNS = (
    "方案精选",
    "方案合集",
    "产品汇",
    "产品合集",
    "产品方案",
    "推出",
    "发布",
    "登场",
    "新品",
    "产品选型",
    "车规级",
    "Smart Power Stage",
    "电子保险丝",
    "驱动器",
    "稳压器",
    "ADC",
    "DAC",
    "PMIC",
    "LDO",
    "步进电机",
    "电机驱动",
    "微步进",
    "电流检测",
    "精密ADC",
    "同步采样",
    "高精度信号采集",
    "MSPS",
    "SNR",
    "dBFS",
    "运算放大器",
    "看门狗",
    "复位",
)

_HIGH_SIGNAL_PRODUCT_TERMS = (
    "方案精选",
    "方案合集",
    "产品汇",
    "产品合集",
    "产品方案",
    "电源模块",
    "降压芯片",
    "同步降压",
    "DCDC",
    "Smart Power Stage",
    "电子保险丝",
    "车规级",
    "步进电机",
    "电机驱动",
    "微步进",
    "电流检测",
    "精密ADC",
    "同步采样",
    "高精度信号采集",
    "MSPS",
    "SNR",
    "dBFS",
    "ADC",
    "DAC",
    "PMIC",
    "LDO",
    "运算放大器",
    "传感器",
    "看门狗",
    "复位",
)

_GENERIC_TERMS = {
    "行业",
    "研究",
    "研究报告",
    "深度",
    "深度报告",
    "产业链",
    "中期策略",
    "报告",
    "公司",
    "股份",
    "智能",
    "科技",
    "电子",
    "中国",
    "全球",
    "市场",
}


def select_wechat_candidates(
    candidates: Sequence[Dict[str, Any]],
    *,
    stock_config: Dict[str, Any] | None = None,
    extra_theme_terms: Iterable[str] | None = None,
) -> Dict[str, Any]:
    """Classify candidate article metadata into keep/product/drop/duplicate."""
    identity_terms = _company_identity_terms(stock_config or {})
    theme_terms = [
        term
        for term in build_company_theme_terms(stock_config or {}, extra_terms=extra_theme_terms or [])
        if term not in identity_terms
    ]
    if extra_theme_terms:
        theme_terms = _dedupe_terms([*theme_terms, *extra_theme_terms])

    seen_urls: Dict[str, str] = {}
    seen_fingerprints: Dict[str, str] = {}
    results: List[Dict[str, Any]] = []

    for raw in candidates:
        candidate = _normalize_candidate(raw)
        text = _candidate_text(candidate)
        url_key = _normalize_url(candidate.get("url", ""))
        fp = _fingerprint(candidate)
        label = url_key or fp or candidate.get("title", "")

        duplicate_of = ""
        if url_key and url_key in seen_urls:
            duplicate_of = seen_urls[url_key]
        elif fp and fp in seen_fingerprints:
            duplicate_of = seen_fingerprints[fp]

        if duplicate_of:
            result = _result(candidate, ACTION_DUPLICATE, "same_url_or_title_digest", [], "duplicate", 0)
            result["duplicate_of"] = duplicate_of
            results.append(result)
            continue

        if url_key:
            seen_urls[url_key] = label
        if fp:
            seen_fingerprints[fp] = label

        matched_theme_terms = _matched_terms(text, theme_terms)
        matched_identity_terms = _matched_terms(text, identity_terms)
        matched_product_terms = _matched_terms(text, _HIGH_SIGNAL_PRODUCT_TERMS)
        action, category, reason, score = _classify_candidate(
            text,
            matched_theme_terms=matched_theme_terms,
            matched_identity_terms=matched_identity_terms,
            matched_product_terms=matched_product_terms,
        )
        matched_terms = _dedupe_terms([*matched_theme_terms, *matched_product_terms])
        results.append(_result(candidate, action, reason, matched_terms, category, score))

    counts = dict(Counter(item["action"] for item in results))
    return {
        "status": "ok",
        "items": results,
        "counts": counts,
        "theme_terms": theme_terms,
        "identity_terms": identity_terms,
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }


def build_company_theme_terms(
    stock_config: Dict[str, Any] | None = None,
    *,
    extra_terms: Iterable[str] | None = None,
) -> List[str]:
    """Build a per-company theme pack from config and optional manual terms."""
    cfg = stock_config or {}
    terms: List[str] = []
    terms.extend(_company_identity_terms(cfg))
    terms.extend(_extract_config_terms(cfg))
    terms.extend(extra_terms or [])
    return _dedupe_terms(term for term in terms if _is_useful_term(term))


def read_wechat_candidate_file(path: str | Path) -> List[Dict[str, Any]]:
    """Read JSON/JSONL or pipe-separated text candidate files."""
    candidate_path = Path(path)
    text = candidate_path.read_text(encoding="utf-8")
    if candidate_path.suffix.lower() == ".json":
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload = payload.get("items") or payload.get("candidates") or []
        return [dict(item) for item in payload if isinstance(item, dict)]
    if candidate_path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    rows: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 5:
            date, account, title, url, digest = parts[:5]
        elif len(parts) >= 4:
            date, account, title, url = parts[:4]
            digest = ""
        elif len(parts) >= 2:
            title, url = parts[:2]
            date = account = digest = ""
        else:
            title = line
            url = date = account = digest = ""
        rows.append({"publish_time": date, "account": account, "title": title, "url": url, "digest": digest})
    return rows


def load_stock_config(stock_name: str, config_path: str | Path) -> Dict[str, Any]:
    """Load one stock's config block by name or code."""
    if not stock_name:
        return {}
    path = Path(config_path)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    for stock in payload if isinstance(payload, list) else []:
        if stock.get("name") == stock_name or stock.get("code") == stock_name:
            return dict(stock)
    return {}


def build_wechat_candidate_preview_markdown(summary: Dict[str, Any]) -> str:
    lines = [
        "# WeChat Candidate Selector Preview",
        "",
        "> Preview-only：不写 Knowledge，不接 canonical synthesis，不进入评分或风险评分。",
        "> `product_signal` 仅表示产品路线观察，不等同于订单、收入或已验证事实。",
        "",
        "## Summary",
        "",
        f"- status: `{summary.get('status', 'ok')}`",
    ]
    for action, count in (summary.get("counts") or {}).items():
        lines.append(f"- {action}: `{count}`")
    if summary.get("theme_terms"):
        lines.append(f"- theme_terms: `{', '.join(summary.get('theme_terms') or [])}`")
    lines.extend(["", "## Candidates", ""])

    for idx, item in enumerate(summary.get("items", []) or [], start=1):
        candidate = item.get("candidate", {})
        lines.extend(
            [
                f"### {idx}. {candidate.get('title') or '(untitled)'}",
                "",
                f"- action: `{item.get('action')}`",
                f"- category: `{item.get('category')}`",
                f"- reason: `{item.get('reason')}`",
                f"- matched_terms: `{', '.join(item.get('matched_terms') or [])}`",
                f"- account: `{candidate.get('account', '')}`",
                f"- publish_time: `{candidate.get('publish_time', '')}`",
                f"- url: {candidate.get('url', '')}",
            ]
        )
        if item.get("duplicate_of"):
            lines.append(f"- duplicate_of: `{item['duplicate_of']}`")
        excerpt = _shorten(candidate.get("digest") or candidate.get("content") or "", 600)
        if excerpt:
            lines.extend(["", f"> {excerpt}", ""])
        else:
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_wechat_candidate_preview(
    *,
    candidate_file: str | Path,
    output_path: str | Path = DEFAULT_WECHAT_CANDIDATE_PREVIEW_PATH,
    stock_config: Dict[str, Any] | None = None,
    extra_theme_terms: Iterable[str] | None = None,
) -> Dict[str, Any]:
    candidates = read_wechat_candidate_file(candidate_file)
    summary = select_wechat_candidates(
        candidates,
        stock_config=stock_config or {},
        extra_theme_terms=extra_theme_terms or [],
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_wechat_candidate_preview_markdown(summary), encoding="utf-8")
    summary["preview_path"] = str(output)
    return summary


def _classify_candidate(
    text: str,
    *,
    matched_theme_terms: Sequence[str],
    matched_identity_terms: Sequence[str],
    matched_product_terms: Sequence[str],
) -> tuple[str, str, str, int]:
    if _contains_any(text, _DROP_PATTERNS):
        return ACTION_DROP, "marketing_or_event", "marketing_event_recruiting_or_invitation", 0
    if _is_capital_market_flash(text):
        return ACTION_DROP, "capital_market_flash", "capital_market_flash_or_stock_price_hype", 0

    is_product = _is_product_release(text)
    has_theme = bool(matched_theme_terms)
    has_high_signal_product = bool(matched_product_terms)
    has_identity = bool(matched_identity_terms)
    is_analysis = _contains_any(text, _ANALYSIS_PATTERNS)

    if is_product:
        if has_theme or has_high_signal_product:
            return ACTION_PRODUCT_SIGNAL, "product_signal", "product_release_matches_company_theme", 65
        return ACTION_DROP, "plain_product_release", "product_release_without_theme_match", 15

    if is_analysis and (has_theme or has_identity):
        return ACTION_KEEP, "analysis", "analysis_or_company_event_matches_theme", 80
    if has_theme and len(text) >= 30:
        return ACTION_KEEP, "analysis", "theme_matched_longform_candidate", 70
    return ACTION_DROP, "weak_or_unrelated", "no_company_theme_or_analysis_signal", 10


def _is_product_release(text: str) -> bool:
    return _contains_any(text, _PRODUCT_PATTERNS) or bool(re.search(r"\bSGM[A-Z0-9]{3,}\b", text, re.IGNORECASE))


def _is_capital_market_flash(text: str) -> bool:
    if _contains_any(text, _CAPITAL_MARKET_FLASH_PATTERNS):
        return True
    compact = _compact(text)
    has_price_or_ipo = any(term in compact for term in ("涨价", "招股", "上市"))
    has_flash_mix = any(term in compact for term in ("同日", "短讯", "快讯", "拟本月", "03661.hk", "股价"))
    return has_price_or_ipo and has_flash_mix


def _company_identity_terms(cfg: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    name = str(cfg.get("name") or "").strip()
    code = str(cfg.get("code") or "").strip()
    if name:
        terms.append(name)
        if name.endswith("股份") and len(name) > 2:
            terms.append(name[: -len("股份")])
        if name.endswith("科技") and len(name) > 2:
            terms.append(name[: -len("科技")])
    if code:
        terms.append(code)
    return _dedupe_terms(terms)


def _extract_config_terms(value: Any) -> List[str]:
    terms: List[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"keywords", "queries", "themes", "theme_terms", "products", "industries"}:
                terms.extend(_extract_config_terms(child))
            elif key in {"industry", "sector", "business", "description"}:
                terms.extend(_split_terms(str(child)))
            elif key in {"source_intake", "a_stock", "eastmoney_global_news", "iwencai_industry_research"}:
                terms.extend(_extract_config_terms(child))
    elif isinstance(value, list):
        for item in value:
            terms.extend(_extract_config_terms(item))
    elif isinstance(value, str):
        terms.extend(_split_terms(value))
    return terms


def _split_terms(text: str) -> List[str]:
    text = _clean_text(text)
    raw_terms: List[str] = re.split(r"[\s,，/、|:：;；()（）\[\]【】]+", text)
    raw_terms.extend(_derive_theme_stems(raw_terms))
    return [term for term in raw_terms if _is_useful_term(term)]


def _derive_theme_stems(terms: Iterable[str]) -> List[str]:
    stems: List[str] = []
    for term in terms:
        clean = _clean_term(term)
        for marker in ("车规", "电源", "信号链", "光模块", "CPO", "800G", "1.6T", "AI"):
            if _compact(marker) in _compact(clean):
                stems.append(marker)
        for suffix in ("芯片", "行业", "产业链", "研究报告", "深度报告", "深度"):
            if clean.endswith(suffix) and len(clean) > len(suffix) + 1:
                stems.append(clean[: -len(suffix)])
    return stems


def _is_useful_term(term: str) -> bool:
    term = _clean_term(term)
    if len(term) < 2:
        return False
    if term in _GENERIC_TERMS:
        return False
    if re.fullmatch(r"\d{6}", term):
        return True
    return not term.endswith("研究报告") and term not in _GENERIC_TERMS


def _matched_terms(text: str, terms: Sequence[str]) -> List[str]:
    compact_text = _compact(text)
    matches: List[str] = []
    for term in terms:
        if _compact(term) and _compact(term) in compact_text:
            matches.append(term)
    return _dedupe_terms(matches)


def _normalize_candidate(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": _clean_text(str(raw.get("title") or raw.get("name") or "")),
        "account": _clean_text(str(raw.get("account") or raw.get("author") or raw.get("nickname") or "")),
        "publish_time": str(raw.get("publish_time") or raw.get("date") or raw.get("time") or ""),
        "url": str(raw.get("url") or raw.get("link") or raw.get("content_url") or ""),
        "digest": _clean_text(str(raw.get("digest") or raw.get("summary") or raw.get("snippet") or "")),
        "content": _clean_text(str(raw.get("content") or "")),
    }


def _candidate_text(candidate: Dict[str, Any]) -> str:
    return " ".join(
        part for part in [candidate.get("title"), candidate.get("account"), candidate.get("digest"), candidate.get("content")] if part
    )


def _result(
    candidate: Dict[str, Any],
    action: str,
    reason: str,
    matched_terms: Sequence[str],
    category: str,
    score: int,
) -> Dict[str, Any]:
    review_eligible = action in {ACTION_KEEP, ACTION_PRODUCT_SIGNAL}
    return {
        "action": action,
        "category": category,
        "reason": reason,
        "matched_terms": list(matched_terms),
        "quality_score": score,
        "candidate": candidate,
        # Selector output is review-only. These flags deliberately do not grant
        # permission to feed WeChat candidates into Knowledge or canonical synthesis.
        "knowledge_eligible": False,
        "synthesis_eligible": False,
        "scoring_eligible": False,
        "risk_score_eligible": False,
        "review_eligible": review_eligible,
        "display_eligible": review_eligible,
    }


def _fingerprint(candidate: Dict[str, Any]) -> str:
    basis = _compact(f"{candidate.get('title', '')}|{candidate.get('digest', '') or candidate.get('content', '')[:200]}")
    if not basis:
        return ""
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def _normalize_url(url: str) -> str:
    return str(url or "").split("#", 1)[0].strip()


def _contains_any(text: str, patterns: Sequence[str]) -> bool:
    compact_text = _compact(text)
    return any(_compact(pattern) in compact_text for pattern in patterns)


def _clean_text(text: str) -> str:
    text = html.unescape(str(text or ""))
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_term(term: str) -> str:
    return _clean_text(term).strip(" -_")


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", _clean_text(text)).lower()


def _dedupe_terms(terms: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for raw in terms:
        term = _clean_term(raw)
        key = _compact(term)
        if not term or key in seen:
            continue
        seen.add(key)
        result.append(term)
    return result


def _shorten(text: str, limit: int) -> str:
    clean = _clean_text(text)
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)].rstrip() + "..."
