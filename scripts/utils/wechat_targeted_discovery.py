"""Preview-only WeChat targeted discovery helpers.

This module performs deterministic, local classification and deduplication of
WeChat article metadata.  It never writes Knowledge, never feeds WeChat content
into canonical synthesis, scoring, or risk pipelines, and never exposes auth
keys in output.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"

# Classification set used by the preview CLI.
CATEGORIES: List[str] = [
    "high_quality_analysis",
    "customer_order_or_design_win",
    "capacity_supply_chain_signal",
    "industry_cycle_price_signal",
    "earnings_financial_context",
    "certification_policy_standard",
    "product_or_event_signal",
    "capital_market_context",
    "duplicate",
    "drop",
]

PRIORITY: Dict[str, int] = {cat: idx for idx, cat in enumerate(CATEGORIES)}

DEFAULT_TARGET_ACCOUNTS: List[str] = [
    "电子工程专辑",
    "半导体行业观察",
    "半导体产业纵横",
    "集微网",
    "芯世圈",
    "全球半导体观察",
    "半导纵横",
    "与非网",
    "C114通信网",
    "光通信观察",
    "讯石光通讯",
    "ICC讯石光通讯",
    "OFweek光通讯",
    "高工智能汽车",
    "36氪",
    "甲子光年",
    "电子工程世界",
    "机器之心",
    "量子位",
    "新智元",
    "TrendForce集邦",
    "闪存市场",
    "DRAMeXchange",
    "CFM闪存市场",
]

DEFAULT_ANALYSIS_MEDIA: set[str] = {
    "电子工程专辑",
    "半导体行业观察",
    "半导体产业纵横",
    "集微网",
    "芯世圈",
    "全球半导体观察",
    "半导纵横",
    "与非网",
    "C114通信网",
    "光通信观察",
    "讯石光通讯",
    "ICC讯石光通讯",
    "OFweek光通讯",
    "高工智能汽车",
    "36氪",
    "36氪Pro",
    "36氪汽车",
    "甲子光年",
    "电子工程世界",
    "机器之心",
    "量子位",
    "新智元",
    "TrendForce集邦",
    "闪存市场",
    "DRAMeXchange",
    "CFM闪存市场",
    "汽车之心",
    "智车科技",
    "雷峰网",
}

_DROP_TERMS: List[str] = [
    "招聘",
    "校园",
    "活动",
    "祝福",
    "获奖",
    "邀您",
    "相约",
    "打卡",
    "开幕",
    "展位",
    "校招",
    "社招",
    "内推",
    "宣讲",
    "笔试",
    "面试",
    "录用",
    "入职",
    "热招岗位",
    "祝您",
    "节日快乐",
    "元旦",
    "新春",
    "春节",
    "元宵",
    "中秋",
    "国庆",
    "清明",
    "端午",
    "圣诞",
    "年会",
    "精彩回顾",
    "加入我们",
    "简历",
    "诚聘",
]

_DEEP_INDICATORS: List[str] = [
    "深度",
    "研报",
    "研究报告",
    "竞争格局",
    "行业格局",
    "产业链",
    "并购",
    "收购",
    "经营分析",
    "基本面",
    "护城河",
    "行业分析",
    "商业模式",
    "盈利能力",
    "盈利预测",
    "投资逻辑",
    "市场空间",
    "壁垒",
    "竞争力",
    "估值",
    "国产替代",
]

_CUSTOMER_ORDER_TERMS: List[str] = [
    "客户",
    "订单",
    "定点",
    "供货",
    "量产",
    "配套",
    "搭载",
    "拿下",
    "中标",
    "进入供应链",
    "大客户",
    "云厂商",
    "车企",
    "主机厂",
    "Tier1",
    "Tier 1",
    "供应商",
    "服务器",
    "数据中心",
    "智算中心",
    "算力中心",
]

_CUSTOMER_COLLAB_TERMS: List[str] = ["合作", "携手", "签约", "战略"]
_CUSTOMER_CONTEXT_TERMS: List[str] = [
    "客户",
    "订单",
    "定点",
    "供货",
    "配套",
    "搭载",
    "量产",
    "车型",
    "车企",
    "主机厂",
    "Tier1",
    "服务器",
    "数据中心",
    "智算中心",
    "算力中心",
]

_CAPACITY_SUPPLY_CHAIN_TERMS: List[str] = [
    "扩产",
    "产能",
    "良率",
    "交付",
    "供应链卡点",
    "上游",
    "材料",
    "封测",
    "设备",
    "晶圆",
    "代工",
    "制造",
    "工厂",
    "产线",
    "爬坡",
    "达产",
    "满产",
    "紧缺",
    "供不应求",
    "稼动率",
    "出货量",
    "二供",
    "供应商",
    "流片",
    "先进封装",
]

_INDUSTRY_CYCLE_PRICE_TERMS: List[str] = [
    "涨价",
    "供需",
    "库存周期",
    "行业景气",
    "上行周期",
    "下行周期",
    "复苏",
    "回暖",
    "低谷",
    "过剩",
    "产能利用率",
    "价格战",
    "提价",
    "调价",
    "成本压力",
    "供需缺口",
    "供不应",
    "存储周期",
    "存储器涨价",
    "NAND",
    "DRAM",
    "Flash涨价",
    "存储涨价",
    "存储行情",
    "存储芯片",
]

_CERTIFICATION_TERMS: List[str] = [
    "认证",
    "标准",
    "监管",
    "审查",
    "资质",
    "专利",
    "合规",
    "ISO",
    "AEC-Q",
    "车规认证",
    "功能安全",
    "ASIL",
    "可靠性测试",
    "入网",
    "许可",
    "国产替代政策",
    "制裁",
    "实体清单",
    "出口管制",
]

_EARNINGS_TERMS: List[str] = [
    "财报",
    "业绩",
    "营收",
    "利润",
    "亏损",
    "盈利",
    "净利润",
    "毛利率",
    "业绩快报",
    "业绩预告",
    "年报",
    "一季报",
    "中报",
    "三季报",
    "季报",
]

_CAPITAL_TERMS: List[str] = [
    "IPO",
    "上市",
    "招股",
    "募资",
    "股价",
    "市值",
    "涨停",
    "行情",
    "券商",
    "估值",
    "基石",
    "配售",
    "认购",
    "减持",
    "增持",
    "回购",
    "分红",
    "配股",
    "转债",
    "融资",
    "解禁",
    "股东",
    "股东大会",
]

_PRODUCT_EVENT_TERMS: List[str] = [
    "新品",
    "新推",
    "推出",
    "发布",
    "方案",
    "产品",
    "参数",
    "应用",
    "场景",
    "选型",
    "解决方案",
    "技术路线",
    "升级",
    "更新",
    "亮相",
    "展会",
    "展示",
    "论坛",
    "峰会",
    "演讲",
    "专访",
    "介绍",
    "演示",
    "思元",
    "云端",
    "训练",
    "推理",
    "AI芯片",
    "GPU",
    "ASIC",
    "NOR",
    "EEPROM",
    "MCU",
    "Flash",
]


# ---------------------------------------------------------------------------
# Config / auth helpers
# ---------------------------------------------------------------------------


def load_auth_key(env_path: str | Path = DEFAULT_ENV_PATH) -> str:
    path = Path(env_path)
    if not path.exists():
        raise RuntimeError(f".env not found: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("WECHAT_EXPORTER_AUTH_KEY"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("WECHAT_EXPORTER_AUTH_KEY not found in .env")


def load_stock_config(stock_name: str, config_path: str | Path) -> Dict[str, Any]:
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


def _company_short_name(name: str) -> str:
    for suffix in ("股份", "科技", "智能", "电子", "半导体", "信息"):
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return name


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
    raw = re.split(r"[\s,，/、|:：;；()（）\[\]【】]+", text)
    return [t for t in raw if _is_useful_term(t)]


def _is_useful_term(term: str) -> bool:
    term = _clean_term(term)
    if len(term) < 2:
        return False
    return not term.endswith("研究报告")


def build_search_keywords(
    stock_config: Dict[str, Any],
    extra_keywords: Optional[Iterable[str]] = None,
) -> List[str]:
    """Build keyword list for account/article discovery from config + CLI extras."""
    terms: List[str] = []
    name = str(stock_config.get("name") or "").strip()
    code = str(stock_config.get("code") or "").strip()
    if name:
        terms.append(name)
        short = _company_short_name(name)
        if short and short != name:
            terms.append(short)
    if code:
        terms.append(code)
    terms.extend(_extract_config_terms(stock_config))
    if extra_keywords:
        terms.extend(extra_keywords)
    return _dedupe_terms(terms)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify(
    title: str,
    digest: str,
    account: str,
    stock_code: str,
    analysis_media: Optional[set[str]] = None,
) -> Tuple[str, str]:
    """Classify one article into a preview category and reason."""
    text = f"{title} {digest}"
    media = analysis_media or DEFAULT_ANALYSIS_MEDIA

    if any(t in text for t in _DROP_TERMS):
        return "drop", "节日祝福/招聘/活动/营销等无关内容"

    has_deep = any(t in title for t in _DEEP_INDICATORS)
    capital_terms = [t for t in _CAPITAL_TERMS if t] + ([stock_code] if stock_code else [])
    is_capital_short = any(t in title for t in capital_terms) and not has_deep

    if has_deep and not ("股价" in title and "研报" not in title and "深度" not in title):
        return "high_quality_analysis", "标题含深度/研报/产业链/竞争格局/财务/经营/壁垒/估值等分析要素"

    if account in media:
        if any(t in title for t in _DEEP_INDICATORS):
            return "high_quality_analysis", "分析媒体来源，标题含深度分析要素"
        if any(t in title for t in ["定点", "订单", "客户", "供货", "配套", "拿下"]) and any(
            t in title for t in ["车型", "车企", "主机厂", "产业链", "格局", "服务器", "数据中心"]
        ):
            return "high_quality_analysis", "分析媒体来源，标题含客户/定点/产业链/格局等深度要素"

    if any(t in title for t in _CUSTOMER_ORDER_TERMS):
        return "customer_order_or_design_win", "标题含客户/订单/定点/供货/配套/搭载/量产/拿下/中标/大客户等"

    if any(t in title for t in _CUSTOMER_COLLAB_TERMS) and any(t in title for t in _CUSTOMER_CONTEXT_TERMS):
        return "customer_order_or_design_win", "标题含合作/签约且关联客户/车型/量产/服务器/数据中心等"

    if any(t in title for t in _CAPACITY_SUPPLY_CHAIN_TERMS):
        return "capacity_supply_chain_signal", "标题含扩产/产能/良率/交付/上游/材料/封测/设备/供应链等"

    if is_capital_short:
        return "capital_market_context", "涉及IPO/上市/招股/募资/股价/市值/再融资等资本市场信息"

    if any(t in title for t in _INDUSTRY_CYCLE_PRICE_TERMS):
        if "股价" not in title and "市值" not in title:
            return "industry_cycle_price_signal", "标题含涨价/供需/库存周期/行业景气/复苏/价格战/存储周期等"

    if any(t in title for t in _CERTIFICATION_TERMS):
        return "certification_policy_standard", "标题含认证/标准/监管/审查/资质/专利/合规/功能安全/政策等"

    if any(t in title for t in _EARNINGS_TERMS):
        return "earnings_financial_context", "标题含财报/业绩/营收/利润/亏损/盈利/毛利率等"

    if any(t in text for t in _PRODUCT_EVENT_TERMS):
        return "product_or_event_signal", "新品/方案/产品/参数/应用场景/展会/论坛/技术路线/AI芯片/存储等"

    return "drop", "未命中任何分类标准"


# ---------------------------------------------------------------------------
# Date / preview helpers
# ---------------------------------------------------------------------------


def ts_to_date(ts: Any) -> Optional[date]:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts)).date()
    except Exception:
        return None


def add_preview_fields(item: Dict[str, Any]) -> Dict[str, Any]:
    item["quality_action"] = "preview_only"
    item["knowledge_eligible"] = False
    item["synthesis_eligible"] = False
    item["scoring_eligible"] = False
    item["risk_score_eligible"] = False
    return item


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _normalize_url(url: str) -> str:
    return str(url or "").split("#", 1)[0].strip()


def _title_fingerprint(title: str) -> str:
    return re.sub(r"[^一-龥a-zA-Z0-9]", "", str(title or "")).lower()


def _content_fingerprint(digest: str, content: str = "") -> str:
    text = _clean_text(f"{digest or ''} {content or ''}")[:240]
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _source_score(candidate: Dict[str, Any], analysis_media: set[str]) -> int:
    score = 0
    account = str(candidate.get("account") or "")
    if account in analysis_media:
        score += 3
    digest_len = len(_clean_text(candidate.get("digest") or ""))
    if digest_len >= 60:
        score += 2
    elif digest_len >= 20:
        score += 1
    return score


def deduplicate(
    candidates: Sequence[Dict[str, Any]],
    stock_config: Optional[Dict[str, Any]] = None,
    analysis_media: Optional[set[str]] = None,
) -> Dict[str, Any]:
    """Deduplicate by URL/title/content fingerprint; keep the best representative.

    Returns a summary dict with classified unique items, duplicate stats, and counts.
    """
    media = analysis_media or DEFAULT_ANALYSIS_MEDIA
    code = str((stock_config or {}).get("code") or "")

    # Pre-classify every candidate so duplicates keep the same classification.
    classified = []
    for cand in candidates:
        norm = {
            "title": str(cand.get("title") or ""),
            "url": str(cand.get("url") or cand.get("link") or ""),
            "digest": str(cand.get("digest") or cand.get("summary") or ""),
            "content": str(cand.get("content") or ""),
            "account": str(cand.get("account") or cand.get("author") or ""),
            "publish_date": str(cand.get("publish_date") or cand.get("date") or ""),
            "publish_time_ts": cand.get("publish_time_ts") or cand.get("create_time") or cand.get("update_time"),
            "author_name": str(cand.get("author_name") or ""),
        }
        category, reason = classify(norm["title"], norm["digest"], norm["account"], code, media)
        norm["classification"] = category
        norm["reason"] = reason
        classified.append(norm)

    # Sort so the best representative appears first within each duplicate group.
    classified.sort(key=lambda c: (_source_score(c, media), c["publish_date"]), reverse=True)

    seen_urls: Dict[str, Dict[str, Any]] = {}
    seen_titles: Dict[str, Dict[str, Any]] = {}
    seen_digests: Dict[str, Dict[str, Any]] = {}
    unique_items: List[Dict[str, Any]] = []
    duplicate_items: List[Dict[str, Any]] = []

    for cand in classified:
        url_key = _normalize_url(cand["url"])
        title_key = _title_fingerprint(cand["title"])
        digest_key = ""
        if _clean_text(cand["digest"]) or _clean_text(cand["content"]):
            digest_key = _content_fingerprint(cand["digest"], cand["content"])

        existing = None
        duplicate_key = ""
        if url_key and url_key in seen_urls:
            existing = seen_urls[url_key]
            duplicate_key = f"url:{url_key}"
        elif title_key and title_key in seen_titles:
            existing = seen_titles[title_key]
            duplicate_key = f"title:{title_key}"
        elif digest_key and digest_key in seen_digests:
            existing = seen_digests[digest_key]
            duplicate_key = f"digest:{digest_key}"

        if existing is not None:
            dup = dict(cand)
            dup["classification"] = "duplicate"
            dup["reason"] = f"与 {existing.get('title')} 重复 ({duplicate_key})"
            duplicate_items.append(dup)
            continue

        if url_key:
            seen_urls[url_key] = cand
        if title_key:
            seen_titles[title_key] = cand
        if digest_key:
            seen_digests[digest_key] = cand
        unique_items.append(cand)

    # Sort unique items by classification priority and then date.
    unique_items.sort(
        key=lambda x: (PRIORITY.get(x["classification"], 99), x["publish_date"]),
        reverse=False,
    )

    counts: Dict[str, int] = dict(Counter(item["classification"] for item in unique_items))
    for cat in CATEGORIES:
        counts.setdefault(cat, 0)

    return {
        "items": unique_items,
        "duplicates": duplicate_items,
        "unique_count": len(unique_items),
        "duplicate_count": len(duplicate_items),
        "counts": counts,
    }


# ---------------------------------------------------------------------------
# Discovery (network-facing)
# ---------------------------------------------------------------------------


def discover_articles(
    client: Any,
    stock_config: Dict[str, Any],
    since_date: date,
    *,
    max_accounts: int = 80,
    max_pages_per_account: int = 3,
    extra_keywords: Optional[Iterable[str]] = None,
    extra_accounts: Optional[Iterable[str]] = None,
    delay_seconds: float = 1.2,
    errors: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Search accounts and list recent articles matching a stock."""
    errors = errors if errors is not None else []
    target_accounts = _dedupe_terms([*DEFAULT_TARGET_ACCOUNTS, *(extra_accounts or [])])
    keywords = build_search_keywords(stock_config, extra_keywords)
    short_name = _company_short_name(str(stock_config.get("name") or ""))
    if not short_name:
        errors.append("stock_config missing name; cannot list articles")
        return []

    account_map: Dict[str, str] = {}

    # Target accounts first.
    for nickname in target_accounts:
        try:
            res = client.search_accounts(nickname)
            accounts = res.get("list", []) if isinstance(res, dict) else []
            for acc in accounts:
                fakeid = acc.get("fakeid")
                acc_nick = acc.get("nickname", "")
                if fakeid and acc_nick:
                    account_map[fakeid] = acc_nick
            time.sleep(delay_seconds)
        except Exception as exc:
            errors.append(f"search_accounts({nickname}): {exc}")
            time.sleep(delay_seconds)

    # Keyword-driven account discovery.
    for kw in keywords:
        try:
            res = client.search_accounts(kw)
            accounts = res.get("list", []) if isinstance(res, dict) else []
            for acc in accounts:
                fakeid = acc.get("fakeid")
                acc_nick = acc.get("nickname", "")
                if fakeid and acc_nick:
                    account_map[fakeid] = acc_nick
            time.sleep(delay_seconds)
        except Exception as exc:
            errors.append(f"search_accounts({kw}): {exc}")
            time.sleep(delay_seconds)

    # Prefer target accounts in ordering; trim to max_accounts.
    ordered_fakeids: List[str] = []
    target_fakeids = [fid for fid, nick in account_map.items() if nick in set(target_accounts)]
    other_fakeids = [fid for fid in account_map if fid not in target_fakeids]
    ordered_fakeids.extend(target_fakeids)
    ordered_fakeids.extend(other_fakeids)
    if len(ordered_fakeids) > max_accounts:
        ordered_fakeids = ordered_fakeids[:max_accounts]

    all_articles: List[Dict[str, Any]] = []
    for fakeid in ordered_fakeids:
        page = 1
        consecutive_old = 0
        while page <= max_pages_per_account:
            try:
                res = client.list_articles(fakeid, keyword=short_name, page=page)
                articles = res.get("articles", []) if isinstance(res, dict) else []
                if not articles:
                    break
                page_old = 0
                for art in articles:
                    pub_date = ts_to_date(art.get("create_time") or art.get("update_time"))
                    if not pub_date:
                        continue
                    if pub_date < since_date:
                        page_old += 1
                        continue
                    title = _strip_html(art.get("title", ""))
                    digest = _strip_html(art.get("digest", ""))
                    all_articles.append({
                        "title": title,
                        "url": art.get("link", ""),
                        "digest": digest,
                        "publish_date": pub_date.isoformat(),
                        "publish_time_ts": art.get("create_time") or art.get("update_time"),
                        "account": account_map.get(fakeid, ""),
                        "fakeid": fakeid,
                        "author_name": art.get("author_name", ""),
                    })
                if page_old >= len(articles):
                    break
                page += 1
                time.sleep(delay_seconds)
            except Exception as exc:
                errors.append(f"list_articles({account_map.get(fakeid, fakeid)}, page={page}): {exc}")
                break

    return all_articles


# ---------------------------------------------------------------------------
# Download (network-facing)
# ---------------------------------------------------------------------------


def _slug_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_") or "article"
    h = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
    return f"{path}_{h}"


def _download_sort_key(candidate: Dict[str, Any]) -> Tuple[int, str]:
    classification = str(candidate.get("classification") or "")
    # Newer material is preferable within the same class; invert ISO date by
    # sorting with reverse=True at the caller where needed would make category
    # priority awkward, so use a simple negative ordinal string fallback.
    publish_date = str(candidate.get("publish_date") or "")
    return (PRIORITY.get(classification, 99), _reverse_iso_date(publish_date))


def _reverse_iso_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value[:10])
    except ValueError:
        return "99999999"
    return f"{99999999 - parsed.toordinal():08d}"


def select_download_targets(
    candidates: Sequence[Dict[str, Any]],
    download_top: int,
) -> List[Dict[str, Any]]:
    """Choose download targets with category breadth before filling by rank.

    A pure top-N often over-selects one noisy class (for example metadata-heavy
    earnings snippets).  Taking one item from each high-value class first keeps
    body enrichment broad enough to find substantive material when it exists.
    """
    if download_top <= 0:
        return []

    safe_candidates = [c for c in candidates if c.get("classification") != "drop"]
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for cand in safe_candidates:
        buckets.setdefault(str(cand.get("classification") or ""), []).append(cand)
    for bucket in buckets.values():
        bucket.sort(key=_download_sort_key)

    selected: List[Dict[str, Any]] = []
    selected_ids: set[int] = set()
    for category in CATEGORIES:
        if category in {"duplicate", "drop"}:
            continue
        bucket = buckets.get(category) or []
        if not bucket:
            continue
        candidate = bucket[0]
        selected.append(candidate)
        selected_ids.add(id(candidate))
        if len(selected) >= download_top:
            return selected

    for candidate in sorted(safe_candidates, key=_download_sort_key):
        if id(candidate) in selected_ids:
            continue
        selected.append(candidate)
        selected_ids.add(id(candidate))
        if len(selected) >= download_top:
            break
    return selected


def download_articles(
    client: Any,
    candidates: Sequence[Dict[str, Any]],
    *,
    download_top: int = 0,
    download_dir: Optional[str | Path] = None,
    download_delay_seconds: float = 3.2,
    errors: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Download up to `download_top` articles in priority order."""
    errors = errors if errors is not None else []
    if download_top <= 0:
        return []

    targets = select_download_targets(candidates, download_top)
    if not targets:
        return []

    out_dir = Path(download_dir or "/tmp/wechat_targeted_discovery_exports")
    out_dir.mkdir(parents=True, exist_ok=True)

    downloaded: List[Dict[str, Any]] = []
    for cand in targets:
        url = cand.get("url", "")
        try:
            article = client.download_article(url, fmt="markdown")
            slug = _slug_from_url(url)
            file_path = out_dir / f"{slug}.md"
            file_path.write_text(
                f"# {article.title}\n\n"
                f"Source: {url}\n"
                f"Account: {cand.get('account', '')}\n"
                f"Date: {cand.get('publish_date', '')}\n"
                f"Classification: {cand.get('classification', '')}\n\n"
                f"{article.content}",
                encoding="utf-8",
            )
            downloaded.append({
                "title": cand.get("title", ""),
                "path": str(file_path),
                "classification": cand.get("classification", ""),
            })
            time.sleep(download_delay_seconds)
        except Exception as exc:
            errors.append(f"download_article({url}): {exc}")
            time.sleep(download_delay_seconds)

    return downloaded


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def build_markdown(
    summary: Dict[str, Any],
    *,
    stock_name: str = "",
    keywords: Optional[Sequence[str]] = None,
    accounts: Optional[Sequence[str]] = None,
    errors: Optional[Sequence[str]] = None,
    downloaded: Optional[Sequence[Dict[str, Any]]] = None,
    since_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> str:
    lines = [
        f"# 微信 targeted discovery preview（{stock_name or 'stock'}）",
        "",
        "> Preview-only：不写 Knowledge，不接 canonical synthesis，不进入评分或风险评分。",
        "",
        "## API 状态",
        "- 调用状态：完成",
        "- 认证状态：已加载（未回显）",
        f"- 风控/错误：{'无' if not errors else f'{len(errors)} 项，见下方错误列表'}",
        "",
        "## 查询配置",
    ]
    if since_date and to_date:
        lines.append(f"- 日期范围：{since_date.isoformat()} ~ {to_date.isoformat()}")
    lines.append(f"- 候选总数（去重前）：{summary.get('raw_count', summary.get('unique_count', 0) + summary.get('duplicate_count', 0))}")
    lines.append(f"- 去重后数量：{summary.get('unique_count', 0)}")
    lines.append(f"- 重复数量：{summary.get('duplicate_count', 0)}")
    lines.append(f"- 重复率：{summary.get('duplicate_rate', 0.0):.1%}")
    lines.append("")

    lines.append("## 查询关键词")
    for kw in keywords or []:
        lines.append(f"- {kw}")
    lines.append("")

    lines.append("## 查询账号")
    for acc in sorted(set(accounts or [])):
        lines.append(f"- {acc}")
    lines.append("")

    lines.append("## 分类统计")
    counts = summary.get("counts", {})
    for cat in CATEGORIES:
        if cat == "duplicate":
            continue
        lines.append(f"- {cat}：`{counts.get(cat, 0)}`")
    lines.append("")

    for cat in CATEGORIES:
        if cat == "duplicate":
            continue
        items = [it for it in summary.get("items", []) if it.get("classification") == cat]
        lines.append(f"## {cat}")
        if items:
            lines.append("")
            for idx, it in enumerate(items, 1):
                lines.append(f"{idx}. **{it.get('title', '')}**")
                lines.append(f"   - 账号：{it.get('account', '')} | 日期：{it.get('publish_date', '')} | URL: {it.get('url', '')}")
                lines.append(f"   - 理由：{it.get('reason', '')}")
                lines.append("")
        else:
            lines.append("- 未发现该类文章。")
            lines.append("")

    drops_sample = [it for it in summary.get("items", []) if it.get("classification") == "drop"][:5]
    if drops_sample:
        lines.append("## 典型 drop 样例")
        lines.append("")
        for idx, it in enumerate(drops_sample, 1):
            lines.append(f"{idx}. **{it.get('title', '')}**")
            lines.append(f"   - 账号：{it.get('account', '')} | 日期：{it.get('publish_date', '')}")
            lines.append(f"   - 原因：{it.get('reason', '')}")
            lines.append("")

    if downloaded:
        lines.append("## 正文下载确认")
        lines.append("")
        lines.append(f"- 下载数量：{len(downloaded)}")
        for d in downloaded:
            lines.append(f"- [{d.get('classification')}] {d.get('title')} → `{d.get('path')}`")
        lines.append("")

    if errors:
        lines.append("## 错误列表")
        lines.append("")
        for e in errors:
            lines.append(f"- {e}")
        lines.append("")

    lines.append("## 结论")
    lines.append("所有 item 已标记为 preview_only，不写 Knowledge、不接 synthesis、不进评分/风险。")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", str(text or ""))


def _clean_text(text: str) -> str:
    text = html.unescape(str(text or ""))
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_term(term: str) -> str:
    return _clean_text(term).strip(" -_")


def _dedupe_terms(terms: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for raw in terms:
        term = _clean_term(raw)
        if not term or term in seen:
            continue
        seen.add(term)
        result.append(term)
    return result
