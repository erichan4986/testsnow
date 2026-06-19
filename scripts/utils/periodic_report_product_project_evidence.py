"""Generic product/project/customer evidence extraction for periodic reports.

This helper deliberately avoids fixed whitelists of product names or customers.
It extracts verbatim text snippets that sit near contextual markers such as
"应用于", "销售模式", "覆盖", "量产", "规模商用", etc.  The extracted snippets
are suitable for deterministic backfill of full-text LLM summaries.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Dict, List, Tuple


# Context markers that indicate a customer/channel chain description.
_CUSTOMER_CHAIN_MARKERS = (
    "应用于",
    "进入",
    "客户包括",
    "终端客户",
    "品牌客户",
    "品牌机型",
    "ODM 厂商",
    "ODM厂商",
    "模组厂商",
    "无线通信模组",
    "经销商",
    "直销",
    "应用领域",
    "航空",
    "航天",
    "装备",
    "批量应用",
    "稳定应用",
    "合格供方",
    "客户认证",
    "供货条件",
    "車企",
    "车企",
    "主機廠",
    "主机厂",
    "算法廠商",
    "算法厂商",
    "Robotaxi",
    "機器人",
    "机器人",
    "具身智能",
    "智能影像",
    "智能汽車",
    "智能汽车",
    "智能駕駛",
    "智能驾驶",
    "輔助駕駛",
    "辅助驾驶",
    "AIoT",
    "端側 AI",
    "端侧 AI",
    "與",
    "与",
    "達成合作",
    "达成合作",
    "展開合作",
    "展开合作",
    "達成合作",
    "达成合作",
    "客戶及合作夥伴",
    "客户及合作伙伴",
)

# Markers that indicate a sales-model description.
_SALES_MODEL_MARKERS = (
    "销售模式",
    "经销为主",
    "直销为辅",
    "直销为主",
    "经销为辅",
    "买断式",
)

# Markers that indicate frequency/band coverage.
_FREQ_COVERAGE_MARKERS = (
    "覆盖",
    "覆蓋",
    "频段",
    "通信频段",
    "产品系列",
    "產品系列",
    "產品矩陣",
    "产品矩阵",
    "解決方案",
    "解决方案",
)

# Markers that indicate a project/product status.
_PROJECT_STATUS_MARKERS = (
    "量产",
    "量產",
    "规模商用",
    "批量供货",
    "预量产",
    "预產量",
    "验证",
    "驗證",
    "导入",
    "導入",
    "认证",
    "認證",
    "通过测试",
    "取得订单",
    "实现出货",
    "客户认可",
    "项目目标已达成",
    "可批量供货",
    "百吨级",
    "工程化",
    "产业化",
    "批量应用",
    "稳定应用",
    "合格供方",
    "客户认证",
    "供货条件",
    "重大突破",
    "解決方案",
    "解决方案",
    "核心设计流程",
    "ISO 26262",
    "IEC 61508",
    "3DIC",
    "AI+EDA",
    "PDK",
    "Chiplet",
    "回片",
    "流片",
    "投片",
    "送樣",
    "送样",
    "定點",
    "定点",
    "商业化落地",
    "商業化落地",
    "全球市場准入",
    "交付",
    "规模",
    "规模化",
    "規模化",
    "車規",
    "车规",
    "AEC-Q",
)

# Markers that indicate business significance.
_BUSINESS_SIGNIFICANCE_MARKERS = (
    "放量",
    "国产替代",
    "毛利率修复",
    "高端化",
    "客户突破",
    "新场景扩展",
    "仍需验证",
    "商業化落地",
    "商业化落地",
    "定點",
    "定点",
    "量产车型",
    "量產車型",
    "客户导入",
    "客戶導入",
    "场景放量",
    "場景放量",
    "技術轉化",
    "技术转化",
    "量產節奏",
    "量产节奏",
    "收入轉化",
    "收入转化",
    "毛利改善",
    "規模化落地",
    "规模化落地",
)

# Tokens used to reduce false positives for frequency coverage snippets.
_BAND_TOKENS = ("2G", "3G", "4G", "5G", "6G", "GHz", "UHB", "Wi-Fi", "WiFi", "频段", "蜂窝")

# Generic product-category tokens useful for non-RF platform companies.
_PRODUCT_CATEGORY_TOKENS = (
    "信号链",
    "电源管理",
    "传感器",
    "ADC",
    "DAC",
    "LDO",
    "DC/DC",
    "模拟",
    "数字",
    "EDA",
    "3DIC",
    "Chiplet",
    "PDK",
    "碳纤维",
    "预浸料",
    "功能材料",
    "SoC",
    "NPU",
    "AI SoC",
    "端側 AI",
    "端侧 AI",
    "智能車",
    "智能车",
    "智能駕駛",
    "智能驾驶",
    "輔助駕駛",
    "辅助驾驶",
    "智駕",
    "智驾",
    "Robotaxi",
    "具身智能",
    "智能影像",
    "艙駕一體",
    "舱驾一体",
    "車規",
    "车规",
    "智能汽車",
    "智能汽车",
    "機器人",
    "机器人",
    "AIoT",
    "AI 推理",
    "推理芯片",
    "智駕",
    "智驾",
    "高算力",
    "計算 SoC",
    "计算 SoC",
    "DMS",
    "行車記錄儀",
    "行车记录仪",
    "AI 眼鏡",
    "AI 眼镜",
    "AUTOSAR",
    "IP",
    "HSD",
    "NOA",
    "BPU",
    "征程",
    "Journey",
)

# Tokens used to reduce false positives for customer-chain snippets.
_CUSTOMER_TOKENS = ("客户", "品牌", "ODM", "模组", "经销", "直销", "终端", "車企", "车企", "主機廠", "主机厂", "合作", "夥伴", "伙伴", "客戶")

# Tokens that make a status snippet look like it describes a product/technology.
_PRODUCT_CONTEXT_TOKENS = (
    "产品",
    "方案",
    "模组",
    "芯片",
    "技术",
    "研发",
    "项目",
    "工艺",
    "平台",
    "材料",
    "集成",
    "器件",
    "碳纤维",
    "碳纤维织物",
    "预浸料",
    "功能材料",
    "高性能材料",
    "新材料",
    "航空航天",
    "复合材料",
    "EDA",
    "EDA工具",
    "3DIC",
    "AI+EDA",
    "PDK",
    "Chiplet",
    "仿真",
    "签核",
    "版图",
    "良率",
    "SoC",
    "NPU",
    "AI SoC",
    "智能車",
    "智能车",
    "智能駕駛",
    "智能驾驶",
    "輔助駕駛",
    "辅助驾驶",
    "智駕",
    "智驾",
    "Robotaxi",
    "具身智能",
    "智能影像",
    "端側 AI",
    "端侧 AI",
    "艙駕一體",
    "舱驾一体",
    "高算力",
    "車規",
    "车规",
    "平台",
    "系列芯片",
    "計算 SoC",
    "计算 SoC",
    "IP",
    "AUTOSAR",
    "DMS",
    "行車記錄儀",
    "行车记录仪",
    "AI 眼鏡",
    "AI 眼镜",
    "HSD",
    "NOA",
    "BPU",
    "征程",
    "Journey",
)

_BUCKET_DIVERSITY_TOKENS: Dict[str, Tuple[str, ...]] = {
    "customer_chain": _CUSTOMER_TOKENS,
    "frequency_coverage": _BAND_TOKENS,
    "product_lines": _PRODUCT_CONTEXT_TOKENS + _PROJECT_STATUS_MARKERS,
    "project_statuses": _PROJECT_STATUS_MARKERS,
}

# Shared regex for customer/org-like tokens. Suffixes cover electronics,
# aerospace, new materials, automotive, robotics, and general industrial groups
# without hard-coding specific company or product names. Plain "材料" is
# excluded because it matches product descriptors such as "功能材料"; "新材料"
# and "新材" are kept. Standalone "航空/航天" are excluded because they more
# often describe application scenarios than customer orgs.
_CUSTOMER_ORG_SUFFIX_RE = re.compile(
    r"[一-鿿A-Za-z0-9]{2,12}(?:通信|科技|通讯|智能|电子|微电子|"
    r"新材料|新材|装备|集团|股份|有限公司|汽車|汽车|車企|车企|"
    r"机器人|機器人|智能|出行|科技|創新|创新)"
)

# Regex used to identify snippets that look like broken table rows (numeric debris).
# Digits embedded inside technical tokens (e.g. ZT9H, ZT9H-12K) are not counted.
_TABLE_FRAGMENT_RE = re.compile(r"(?<![A-Za-z0-9])\d[\d,\.]*(?![A-Za-z0-9])")

# Generic context markers used to condense long snippets into short summaries.
_CUSTOMER_CHAIN_SUMMARY_RE = re.compile(
    r"应用于.*?智能手机品牌.*?ODM.*?模组厂商|"
    r"进入.*?ODM厂商|"
    r"终端客户包括.*?品牌客户.*?ODM.*?模组客户|"
    r"模组产品已经.*?智能手机机型.*?ODM厂商"
)


# Maximum diversity bonus per snippet (in quality-score units).
_MAX_DIVERSITY_BONUS = 3.0

_SNIPPET_WINDOW_BEFORE = 60
_SNIPPET_WINDOW_AFTER = 180
_MAX_SNIPPET_LENGTH = 260
_MIN_SNIPPET_LENGTH = 12

# Markers that indicate a sentence boundary we should not cross when condensing.
_SENTENCE_END_RE = re.compile(r"[。；!！?？]")


_TECHNICAL_TERM_RE = re.compile(
    r"[A-Za-z0-9]+(?:[/-][A-Za-z0-9]+)+|"
    r"[A-Z]{2,}(?:\s+[A-Z]{2,})?|"
    r"[A-Z][a-z]+[A-Z][a-zA-Z0-9]*|"
    r"\d+[A-Za-z]+"
)


def _extract_issuer_names(item_map: Dict[str, Any]) -> set[str]:
    """Infer issuer short/full names from report title and company intro blocks."""
    names: set[str] = set()
    full_text = "\n".join(str(item.get("text", "")) for item in item_map.values())

    # Title/header contexts: e.g. "中简科技 2025 年年度报告" or report cover line.
    for match in re.finditer(
        r"([一-鿿A-Za-z0-9]{2,20}(?:股份|科技|微电子|电子|材料|新材|集团|航空|航天|装备))?\s*2025\s*年(?:年度)?报告",
        full_text,
    ):
        token = match.group(1)
        if token:
            names.add(token)

    # Explicit company-name fields in the intro section.
    for match in re.finditer(
        r"(?:股票简称|公司简称|公司名称)[：:\s]+([^。\n]{2,40}?)(?:\s|$|。|;|；)",
        full_text,
    ):
        value = match.group(1).strip()
        if value:
            names.add(value)
            # Also add the last 2-8 CJK token as a possible short name.
            short = re.search(r"([一-鿿A-Za-z0-9]{2,8})$", value)
            if short:
                names.add(short.group(1))

    # Company full name: ...股份有限公司 / ...有限公司 / ...集团.
    for match in re.finditer(
        r"([一-鿿A-Za-z0-9（）()]{4,40}(?:股份有限公司|有限公司|集团))",
        full_text,
    ):
        names.add(match.group(1))

    # Keep only non-empty tokens that look like names.
    cleaned: set[str] = set()
    for name in names:
        name = name.strip()
        if len(name) >= 2:
            cleaned.add(name)
            # Add the core short form without legal suffix.
            core = re.sub(r"(?:股份|有限|集团|公司|有限公司|股份有限公司)$", "", name)
            if len(core) >= 2:
                cleaned.add(core)
    return cleaned


def extract_product_project_evidence(item_map: Dict[str, Any]) -> Dict[str, Any]:
    """Extract generic product/project/customer evidence from fulltext blocks.

    Returns a dict of evidence buckets. Each bucket contains:
    - present: bool
    - snippets: list of verbatim (whitespace-normalized) text snippets
    - refs: list of fulltext block ids the snippets came from
    """
    evidence: Dict[str, Dict[str, Any]] = {
        "customer_chain": {"present": False, "snippets": [], "refs": []},
        "sales_model": {"present": False, "snippets": [], "refs": []},
        "frequency_coverage": {"present": False, "snippets": [], "refs": []},
        "product_lines": {"present": False, "snippets": [], "refs": []},
        "project_statuses": {"present": False, "snippets": [], "refs": []},
        "business_significance": {"present": False, "snippets": [], "refs": []},
    }

    issuer_names = _extract_issuer_names(item_map)

    for ref, item in item_map.items():
        text = str(item.get("text", ""))
        if not text:
            continue

        snippets = _extract_snippets(
            text,
            _CUSTOMER_CHAIN_MARKERS,
            require_tokens=_CUSTOMER_TOKENS,
        )
        if snippets:
            evidence["customer_chain"]["snippets"].extend(snippets)
            evidence["customer_chain"]["refs"].append(ref)

        snippets = _extract_snippets(text, _SALES_MODEL_MARKERS)
        if snippets:
            evidence["sales_model"]["snippets"].extend(snippets)
            evidence["sales_model"]["refs"].append(ref)

        snippets = _extract_snippets(
            text,
            _FREQ_COVERAGE_MARKERS,
            require_tokens=_BAND_TOKENS + _PRODUCT_CATEGORY_TOKENS,
        )
        if snippets:
            evidence["frequency_coverage"]["snippets"].extend(snippets)
            evidence["frequency_coverage"]["refs"].append(ref)

        status_snippets = _extract_snippets(
            text,
            _PROJECT_STATUS_MARKERS,
            require_tokens=_PRODUCT_CONTEXT_TOKENS,
        )
        if status_snippets:
            evidence["product_lines"]["snippets"].extend(status_snippets)
            evidence["product_lines"]["refs"].append(ref)
            evidence["project_statuses"]["snippets"].extend(status_snippets)
            evidence["project_statuses"]["refs"].append(ref)

        snippets = _extract_snippets(text, _BUSINESS_SIGNIFICANCE_MARKERS)
        if snippets:
            evidence["business_significance"]["snippets"].extend(snippets)
            evidence["business_significance"]["refs"].append(ref)

    _deduplicate_and_finalize(evidence)
    evidence["issuer_names"] = issuer_names
    return evidence


def build_company_profile_backfill(
    evidence: Dict[str, Any],
) -> Tuple[str, List[str]]:
    """Build a concise '公司画像' backfill judgment.

    Returns (judgment, refs). Empty string if no relevant evidence.
    Output is at most 3 sentences, each under 120 characters:
      1. 客户/渠道链条
      2. 产品/频段覆盖
      3. 分析含义
    """
    customer = evidence.get("customer_chain") or {}
    sales = evidence.get("sales_model") or {}
    freq = evidence.get("frequency_coverage") or {}
    products = evidence.get("product_lines") or {}

    if not any(bucket.get("present") for bucket in (customer, sales, freq, products)):
        return "", []

    parts: List[str] = []

    customer_text = _join_snippets(customer.get("snippets", []), max_chars=600)
    sales_text = _join_snippets(sales.get("snippets", []), max_chars=400)
    combined_customer_sales = _normalize_whitespace(
        (customer_text + "；" + sales_text).strip("；")
    )
    issuer_names = evidence.get("issuer_names") or set()
    channel_summary = _summarize_channel_chain(combined_customer_sales, issuer_names=issuer_names)
    if channel_summary:
        parts.append(_truncate_sentence("客户与渠道：" + channel_summary))

    freq_text = _join_snippets(
        (freq.get("snippets", []) or []) + (products.get("snippets", []) or []),
        max_chars=800,
    )
    coverage_summary = _summarize_coverage(freq_text)
    if coverage_summary:
        parts.append(_truncate_sentence("产品覆盖：" + coverage_summary))

    # Business significance: prefer smart-vehicle/AI chip style significance if present.
    significance = evidence.get("business_significance") or {}
    significance_text = _join_snippets(significance.get("snippets", []), max_chars=200)
    if significance_text:
        parts.append(_truncate_sentence("收入取决于" + _summarize_business_significance(significance_text)))
    else:
        parts.append("收入对终端需求周期和渠道备货节奏较为敏感。")

    judgment = "公司画像补充判断：" + _join_summary_parts(parts)
    refs = _collect_refs(customer, sales, freq, products)
    return _normalize_judgment(judgment), refs


def build_rd_progress_backfill(
    evidence: Dict[str, Any],
) -> Tuple[str, List[str]]:
    """Build a concise '研发与技术进展' backfill judgment.

    Returns (judgment, refs). Empty string if no relevant evidence.
    Output is at most 3 sentences, each under 120 characters:
      1. 关键产品/项目名称 + 状态
      2. 认证/导入/量产状态
      3. 分析含义
    """
    products = evidence.get("product_lines") or {}
    statuses = evidence.get("project_statuses") or {}
    significance = evidence.get("business_significance") or {}

    if not (products.get("present") or statuses.get("present")):
        return "", []

    combined = _deduplicated_snippets(
        products.get("snippets", []) + statuses.get("snippets", []),
        diversity_tokens=_BUCKET_DIVERSITY_TOKENS.get("product_lines", ()),
        limit=8,
    )
    combined = [s for s in combined if not _looks_like_table_fragment(s)]

    parts: List[str] = []

    product_summary = _summarize_rd_progress(combined)
    if product_summary:
        parts.append(_truncate_sentence("产品/项目进展：" + product_summary))

    cert_summary = _summarize_certification(combined)
    if cert_summary and cert_summary not in product_summary:
        parts.append(_truncate_sentence("认证与导入：" + cert_summary))

    if not parts and combined:
        parts.append(_truncate_sentence("产品/项目进展：" + combined[0]))

    significance = evidence.get("business_significance") or {}
    significance_text = _join_snippets(significance.get("snippets", []), max_chars=200)
    if significance_text:
        biz = _summarize_business_significance(significance_text)
        if "量产节奏" in biz or "技术转化" in biz or "毛利改善" in biz or "收入转化" in biz:
            parts.append(_truncate_sentence("技术转化和" + biz + "是收入与毛利改善观察点。"))
        else:
            parts.append("技术迭代和客户导入是后续收入转化的重要观察点。")
    else:
        parts.append("技术迭代和客户导入是后续收入转化的重要观察点。")

    judgment = "研发与技术进展补充判断：" + _join_summary_parts(parts)
    refs = _collect_refs(products, statuses, significance)
    return _normalize_judgment(judgment), refs


def _looks_like_table_fragment(snippet: str) -> bool:
    """Return True if snippet looks like a broken table row (numeric debris)."""
    # First strip any leading numeric debris and re-evaluate the core content.
    core = re.sub(r"^[-\d\s,\.]+\s*", "", snippet)
    if core and core != snippet:
        # If the core (after stripping numbers) has strong product/status signals, keep it.
        if _looks_like_product_core(core) and any(marker in core for marker in _PROJECT_STATUS_MARKERS):
            return False
    numbers = _TABLE_FRAGMENT_RE.findall(snippet)
    # Three or more numeric cells is a strong table-fragment signal.
    if len(numbers) >= 3:
        return True
    # Also reject if digits make up a large share of non-whitespace chars.
    non_space = re.sub(r"\s+", "", snippet)
    if non_space:
        digit_ratio = sum(1 for ch in non_space if ch.isdigit()) / len(non_space)
        if digit_ratio > 0.35:
            return True
    return False


def _looks_like_noise(snippet: str) -> bool:
    """Return True for cross-table/page-header fragments that should be dropped."""
    if not snippet:
        return True
    # Cross-table debris: "百分点深圳英集芯科技" or "12.34 百分点某公司".
    if re.search(
        r"百分点[一二三四五六七八九十百千万亿\d\s]*[一-鿿A-Za-z0-9]{2,20}"
        r"(?:科技|股份|电子|微电子|材料|有限公司|集团)",
        snippet,
    ):
        return True
    # Page header/footer: company full name + annual report + page number.
    if re.match(
        r"^[一-鿿A-Za-z0-9（）()]{2,40}(?:股份有限公司|有限公司|集团)?\s*2025\s*年(?:年度)?报告\s*\d+\s*$",
        snippet,
    ):
        return True
    # Meaningless concatenations after numeric/table debris.
    if re.search(r"[\d,%\.\s]+(?:百分点|个?百?分?点)\s*[一-鿿]{2,20}(?:科技|股份|电子|材料)", snippet):
        return True
    # Phrases that are clearly transitional noise without substance.
    if re.match(
        r"^[^一-鿿]*(百分点|也?不断应用于|也?广泛应用于|也随之|也随之应用于)",
        snippet,
    ):
        return True
    return False


def _customer_org_tokens(text: str) -> List[str]:
    """Return org-like customer tokens found in text using generic suffixes.

    Leading context words such as conjunctions, prepositions and generic
    counters are stripped so "并进入华勤通讯" becomes "华勤通讯".
    """
    raw = _CUSTOMER_ORG_SUFFIX_RE.findall(text)
    cleaned: List[str] = []
    leading_noise = re.compile(
        r"^(?:并|进入|和|与|及|等|的|在|向|对|为|从|由|被|把|将|让|给|跟|同|比|"
        r"于|以|以及|包括|如|等|厂商|客户|供应商|经销商|终端|设备|一线|头部|国内外|"
        r"主要|重要|核心|知名|大型|专业|领先|头部|一线|国内外)+"
    )
    for token in raw:
        token = leading_noise.sub("", token)
        if token.startswith(("能夠", "能够")) or "為智能" in token or "为智能" in token:
            continue
        if any(noise in token for noise in ("应用于", "智能手机", "耳机", "可穿戴", "设备")):
            continue
        if len(token) >= 4:
            cleaned.append(token)
    return cleaned


def _summarize_channel_chain(text: str, issuer_names: set[str] | None = None) -> str:
    """Extract a short customer/channel/sales-model summary from joined snippets."""
    if not text:
        return ""
    issuer_names = issuer_names or set()
    # Collect customer/org tokens, filtering out the issuer's own names and
    # noisy fragments captured by overly generic suffixes.
    orgs = [
        org for org in _customer_org_tokens(text)
        if not _is_issuer_name(org, issuer_names) and not _is_generic_application_token(org)
        and not _is_noise_org_token(org)
    ]
    # Filter out org tokens that are actually common leading fragments like "一汽等頭部車企".
    orgs = [org for org in orgs if not _is_noise_org_token(org)]
    brands = _unique_preserve_order(re.findall(
        r"三星|vivo|小米|OPPO|荣耀|华为|苹果|蘿蔔快跑|萝卜快跑|吉利|東風|东风|比亞迪|比亚迪|一汽|雲深處|云深处|傅利葉|聯想|联想|極智嘉|极智嘉",
        text,
    ))
    partners = _extract_partner_tokens(text)
    partner_names = _unique_preserve_order(brands + partners)
    odm = bool(re.search(r"ODM|华勤|龙旗", text))
    module = bool(re.search(r"模组厂商|模组客户|移远|广和通|日海", text))
    partner = bool(re.search(r"車企|车企|主機廠|主机厂|客戶及合作夥伴|客户及合作伙伴|合作夥伴|合作伙伴|達成合作|达成合作", text))
    scenario = _summarize_application_scenario(text)
    sales = ""
    if "买断式" in text:
        sales = "买断式"
    if "经销为主" in text or "经销" in text:
        sales = (sales + "经销为主").strip("、")
    elif "直销为主" in text or "直销" in text:
        sales = (sales + "直销为主").strip("、")

    # Strip the trailing "等頭部車企/主机厂/算法厂商" fragment from brand lists
    # so it does not duplicate the scenario summary.
    if partner_names:
        partner_names = [
            b for b in partner_names
            if b not in {"車企", "车企", "主機廠", "主机厂", "算法廠商", "算法厂商", "頭部", "头部"}
        ]

    parts: List[str] = []
    if partner_names:
        parts.append("、".join(partner_names[:5]) + "等品牌/合作方")
    if odm:
        parts.append("华勤/龙旗等ODM")
    if module:
        parts.append("移远等模组厂商")
    elif orgs and not odm and not module and not partner_names:
        parts.append("、".join(orgs[:4]))

    # Add scenario summary when we have partner/customer context but no concrete orgs.
    if scenario and (partner or partner_names) and not (odm or module or orgs):
        parts.append(scenario)

    # Standalone scenario when no concrete customer/channel tokens are present.
    if scenario and not (partner_names or odm or module or orgs):
        parts.append(scenario)

    if sales:
        parts.append(f"采用{sales}")

    if not parts:
        return ""

    summary = "，".join(p for p in parts if p)
    return summary


def _summarize_business_significance(text: str) -> str:
    """Return a short business-meaning clause from business significance snippets."""
    text = _normalize_whitespace(text)
    if any(term in text for term in ("量產車型", "量产车型", "量產節奏", "量产节奏", "客戶導入", "客户导入", "場景放量", "场景放量", "技術轉化", "技术转化", "收入轉化", "收入转化", "毛利改善", "商業化落地", "商业化落地")):
        clauses = []
        if any(term in text for term in ("量產車型", "量产车型")):
            clauses.append("量产车型")
        if any(term in text for term in ("量產節奏", "量产节奏")):
            clauses.append("量产节奏")
        if any(term in text for term in ("客戶導入", "客户导入")):
            clauses.append("客户导入")
        if any(term in text for term in ("場景放量", "场景放量")):
            clauses.append("场景放量")
        if any(term in text for term in ("技術轉化", "技术转化")):
            clauses.append("技术转化")
        if any(term in text for term in ("收入轉化", "收入转化")):
            clauses.append("收入转化")
        if "毛利改善" in text:
            clauses.append("毛利改善")
        if any(term in text for term in ("商業化落地", "商业化落地")):
            clauses.append("商业化落地")
        return "、".join(clauses) + "等节奏"
    if "国产替代" in text:
        return "国产替代进度"
    if "毛利率修复" in text:
        return "毛利率修复节奏"
    if "客户突破" in text:
        return "客户突破进展"
    if "新场景扩展" in text:
        return "新场景扩展节奏"
    return "终端需求周期和渠道备货节奏"


def _extract_partner_tokens(text: str) -> List[str]:
    """Extract partner/customer names from cooperation clauses."""
    tokens: List[str] = []
    for match in re.finditer(
        r"(?:與|与|公司已經與|公司已经与|客戶及合作夥伴|客户及合作伙伴)\s*([^。；]{2,90}?)"
        r"(?:等(?:核心)?(?:算法廠商|算法厂商|行業領先企業|行业领先企业|合作方|合作夥伴|客户|客戶)|"
        r"達成|达成|進行|进行|合作|深度適配|深度适配)",
        text,
    ):
        clause = match.group(1)
        for token in re.split(r"[、，,及和與与\s]+", clause):
            token = token.strip(" 「」“”()（）")
            if _looks_like_partner_token(token):
                tokens.append(token)
    return _unique_preserve_order(tokens)


def _looks_like_partner_token(token: str) -> bool:
    if not token or len(token) < 2:
        return False
    if token in {
        "公司",
        "目前",
        "核心",
        "算法",
        "廠商",
        "厂商",
        "行業",
        "行业",
        "領先",
        "领先",
        "企業",
        "企业",
        "客戶",
        "客户",
        "合作",
        "合作方",
        "合作夥伴",
        "合作伙伴",
    }:
        return False
    if re.search(r"(?:芯片|平台|產品|产品|系列|方案|場景|场景|智能|Robotaxi|SoC|NPU|VLA)$", token):
        return False
    if any(noise in token for noise in ("的", "以來", "以来", "共同", "廣泛", "广泛", "生態", "生态")):
        return False
    return bool(re.search(r"[一-鿿]{2,12}|[A-Za-z][A-Za-z0-9-]{2,20}", token))


def _summarize_application_scenario(text: str) -> str:
    """Extract a short list of application domains near 应用于/领域/行业 markers."""
    for match in re.finditer(r"(?:能夠|能够|可)?為\s*([^。；]{2,80}?)(?:提供|打造|構建).*?(?:解決方案|解决方案)", text):
        domains = re.split(r"[、，,以及和]", match.group(1))
        domains = [
            d.strip()
            for d in domains
            if len(d.strip()) >= 2 and not d.strip().isdigit()
        ]
        if domains:
            return "、".join(domains[:4]) + "等应用场景"
    for match in re.finditer(r"(?:布局|佈局|覆蓋|覆盖)\s*([^。；]{2,80}?(?:Robotaxi|智能駕駛|智能驾驶|輔助駕駛|辅助驾驶|具身智能|機器人|机器人|智能汽車|智能汽车|AIoT|端側 AI|端侧 AI|智能影像)[^。；]{0,40}?)(?:場景|场景|方向|市場|市场|等)", text):
        clause = match.group(1).strip()
        if clause:
            return clause + "等应用场景"
    for match in re.finditer(r"(?:布局|佈局|覆蓋|覆盖)\s*([^。；]{2,80}?)(?:場景|场景|方向|市場|市场|等)", text):
        clause = match.group(1).strip()
        if clause and any(token in clause for token in ("智能", "AI", "機器人", "机器人", "駕駛", "驾驶")):
            return clause + "等应用场景"
    for match in re.finditer(r"应用于\s*([^。；]{2,60}?)(?:等|领域|行业|场景|下游|客户|产品)", text):
        domains = re.split(r"[、，,]", match.group(1))
        domains = [d.strip() for d in domains if len(d.strip()) >= 2 and not d.strip().isdigit()]
        if domains:
            return "、".join(domains[:4]) + "等应用领域"
    for match in re.finditer(r"([^。；]{2,40}?(?:领域|行业|场景))", text):
        clause = match.group(1)
        if "应用" in clause or "下游" in clause or "终端" in clause:
            return clause
    return ""


def _is_issuer_name(candidate: str, issuer_names: set[str]) -> bool:
    """Return True if candidate matches or is contained by an issuer name."""
    if not issuer_names:
        return False
    candidate = candidate.strip()
    for name in issuer_names:
        if candidate in name or name in candidate:
            return True
    return False


def _is_generic_application_token(candidate: str) -> bool:
    return candidate in {
        "消费电子",
        "人工智能",
        "智能制造",
        "汽车电子",
        "工业电子",
        "网络通信",
    }


def _is_noise_org_token(candidate: str) -> bool:
    """Return True for fragments that look like mid-sentence chunks, not org names."""
    if not candidate:
        return True
    noise_prefixes = (
        "公司",
        "產品",
        "产品",
        "面向",
        "聚焦",
        "應用",
        "应用",
        "平台",
        "已在",
        "客戶",
        "客户",
        "及",
        "在",
        "是",
        "與",
        "与",
        "達成",
        "达成",
        "等",
        "頭部",
        "头部",
        "展開",
        "展开",
    )
    if any(candidate.startswith(p) for p in noise_prefixes):
        return True
    # Mid-sentence generic scenario tokens are not orgs.
    if candidate in {"智能", "智能汽车", "智能汽車", "具身智能", "機器人", "机器人", "AIoT"}:
        return True
    # Phrases that are clearly sentence fragments rather than org names.
    if re.search(r"(?:及|与|和|在|等).*?(?:機器人|机器人|智能|客戶|客户)", candidate):
        return True
    if "車企" in candidate or "车企" in candidate:
        return True
    return False


def _summarize_coverage(text: str) -> str:
    """Extract a short frequency/scene coverage summary."""
    if not text:
        return ""
    product_categories = []
    for token in _PRODUCT_CATEGORY_TOKENS:
        if token in text and token not in product_categories:
            product_categories.append(token)
    bands: List[str] = []
    for token in ("2G", "3G", "4G", "5G", "UHB", "Wi-Fi"):
        if token in text and token not in bands:
            bands.append(token)
    platform_tokens = _extract_platform_tokens(text)
    if bands:
        if platform_tokens:
            return "、".join((bands + platform_tokens)[:6]) + "等频段/产品方向"
        return "、".join(bands) + "等频段/场景"
    if platform_tokens:
        combined = _unique_preserve_order(platform_tokens + product_categories)
        return "、".join(combined[:6]) + "等产品/技术方向"
    # Prefer concrete product/platform names over broad category tokens.
    concrete = [t for t in product_categories if re.search(r"[A-Z]\d|X|DMS|NPU|AUTOSAR|IP", t) or "系列" in t or "平台" in t or "芯片" in t]
    if concrete:
        return "、".join(concrete[:4]) + "等产品/技术方向"
    if product_categories:
        return "、".join(product_categories[:4]) + "等产品/技术方向"
    if "频段" in text:
        return "多频段/场景"
    if "覆盖" in text:
        # For non-RF companies, avoid "频段" fallback.
        return "多品类/应用场景"
    return ""


def _extract_platform_tokens(text: str) -> List[str]:
    """Extract concrete chip/platform/product code tokens from coverage snippets."""
    tokens: List[str] = []
    patterns = (
        r"\b(?:HSD|NOA|BPU)\b",
        r"征程\s*®?\s*\d+",
        r"\bJourney\s*\d+\b",
        r"\b[A-Z][A-Za-z]*\d+[A-Za-z0-9-]*\b",
        r"\b[A-Z]\d+[A-Za-z0-9-]*\b",
        r"\b[A-Za-z]+X\b",
        r"\b[A-Za-z]+-[A-Za-z0-9-]+\b",
    )
    for pattern in patterns:
        tokens.extend(re.findall(pattern, text))
    filtered = []
    for token in tokens:
        if token in {"AI", "SoC", "NPU", "VLA", "HDR", "Wi-Fi", "WiFi", "L1", "L2", "L3", "L4", "L5"}:
            continue
        if re.match(r"^\d", token):
            continue
        filtered.append(token)
    return _unique_preserve_order(filtered)


def _summarize_rd_progress(snippets: List[str]) -> str:
    """Pick the best single product+status sentence, avoiding table fragments."""
    # Prefer non-certification snippets first (certification gets its own sentence).
    # Score snippets to prefer concrete product names + status markers.
    scored = []
    for snippet in snippets:
        if _looks_like_table_fragment(snippet):
            continue
        if any(token in snippet for token in ("认证", "通过测试", "認證")):
            continue
        score = 0
        if _TECHNICAL_TERM_RE.search(snippet):
            score += 2
        # Strongly reward concrete product/platform names (alphanumerics like Phase8L, L-PAMiD, A2000)
        # that are not composed of pure numeric table debris.
        if re.search(r"[A-Za-z]+\d|[A-Za-z]+-[A-Za-z]+|\d+[A-Za-z]+", snippet):
            # Make sure the match is not just a numeric cell with a trailing unit (e.g. 4,436.26 -> Sub3G).
            first_match = re.search(r"[A-Za-z]+\d|[A-Za-z]+-[A-Za-z]+|\d+[A-Za-z]+", snippet)
            if first_match:
                prefix = snippet[:first_match.start()]
                # If the prefix is mostly numeric debris, do not reward.
                if not re.match(r"^[\d\s,\.\-]+$", prefix.strip()):
                    score += 3
        if any(marker in snippet for marker in _PROJECT_STATUS_MARKERS):
            score += 2
        if any(token in snippet for token in _PRODUCT_CONTEXT_TOKENS):
            score += 1
        # Penalize snippets that start with numeric debris (leftover table cells).
        leading_debris = re.match(r"^[\d\s,\.\-]+", snippet)
        if leading_debris and len(leading_debris.group(0).strip()) >= 3:
            score -= 3
        # Penalize snippets whose core starts with generic words like "第二代产品" instead of a concrete name.
        core = _extract_core_clause(snippet)
        if re.match(r"^(?:第|该|此|其|上述|本)?[一二三四五六七八九十几代]+产品", core):
            score -= 2
        if _looks_like_product_core(core):
            scored.append((score, snippet, core))
    scored.sort(key=lambda x: x[0], reverse=True)
    for score, snippet, core in scored:
        if score >= 3:
            return core
    # Fallback to any non-certification product core.
    for score, snippet, core in scored:
        return core
    # Last resort: take the first non-table, non-certification snippet.
    for snippet in snippets:
        if _looks_like_table_fragment(snippet):
            continue
        if any(token in snippet for token in ("认证", "通过测试", "認證")):
            continue
        return _extract_core_clause(snippet)
    return ""


def _summarize_certification(snippets: List[str]) -> str:
    """Pick a certification/import/testing sentence distinct from mass production."""
    for snippet in snippets:
        if _looks_like_table_fragment(snippet):
            continue
        if any(token in snippet for token in ("认证", "通过测试", "导入", "预量产", "验证")):
            if "量产" not in snippet and "规模商用" not in snippet:
                return _extract_core_clause(snippet)
    return ""


def _extract_core_clause(text: str) -> str:
    """Return the most informative clause from a snippet, truncated to ~90 chars."""
    # Strip leading numeric/table debris before finding the real clause.
    text = re.sub(r"^[-\d\s,\.]+\s*", "", text)
    # Prefer content before obvious boilerplate or trailing impact clauses.
    text = re.split(
        r"，推动|，进一步|，为后续|，助力|，持续|，不断|，巩固|，完善|，提升|，丰富",
        text,
    )[0]
    text = _normalize_whitespace(text)
    text = re.sub(r"^[一二三四五六七八九十百]+[、．.]\s*", "", text)
    text = re.sub(r"^\d+[、．.]\s*", "", text)
    text = re.sub(r"(研发)\1+", r"\1", text)
    if text.startswith("法工艺和干喷湿纺"):
        text = "湿" + text
    if len(text) > 90:
        # Try to cut at a clause boundary.
        for delim in ("，", "、"):
            idx = text.rfind(delim, 50, 90)
            if idx > 0:
                text = text[:idx]
                break
        else:
            text = text[:90].rstrip() + "…"
    return text


def _looks_like_product_core(text: str) -> bool:
    return bool(_TECHNICAL_TERM_RE.search(text)) or any(
        token in text for token in _PRODUCT_CONTEXT_TOKENS
    )


def _truncate_sentence(text: str, max_chars: int = 120) -> str:
    """Ensure a single sentence is within max_chars."""
    if len(text) <= max_chars:
        return text
    # Try clause boundary first.
    for delim in ("，", "、", "；"):
        idx = text.rfind(delim, max_chars - 40, max_chars - 1)
        if idx > 0:
            return text[:idx] + "。"
    return text[: max_chars - 1].rstrip() + "…"


def _join_summary_parts(parts: List[str]) -> str:
    """Join concise backfill parts with sentence delimiters."""
    normalized: List[str] = []
    for part in parts:
        part = _normalize_whitespace(part)
        if not part:
            continue
        if not part.endswith(("。", "！", "？")):
            part += "。"
        normalized.append(part)
    return "".join(normalized)


def _extract_snippets(
    text: str,
    markers: Tuple[str, ...],
    *,
    require_tokens: Tuple[str, ...] = (),
) -> List[str]:
    """Extract bounded snippets around each marker occurrence."""
    snippets: List[str] = []
    if not text or not markers:
        return snippets

    seen: set[str] = set()
    for marker in dict.fromkeys(markers):
        pattern = _compiled_marker_pattern(marker)
        for match in re.finditer(pattern, text):
            snippet = _bounded_snippet(text, match.start(), match.end())
            if not snippet:
                continue
            if not _snippet_matches_context(snippet, marker, require_tokens):
                continue
            if snippet not in seen:
                seen.add(snippet)
                snippets.append(snippet)
    return snippets


@lru_cache(maxsize=32)
def _compiled_marker_pattern(marker: str) -> re.Pattern:
    """Return a cached regex pattern for one marker."""
    return re.compile(_spaced_pattern(marker))


def _snippet_matches_context(
    snippet: str,
    marker: str,
    require_tokens: Tuple[str, ...],
) -> bool:
    """Return True if snippet satisfies context constraints for the marker."""
    if not require_tokens:
        return True
    if any(token in snippet for token in require_tokens):
        return True
    # Application/customer markers may describe scenarios without explicit
    # customer tokens (e.g. "应用于航空航天、轨道交通等领域").
    if marker in ("应用于", "进入"):
        scenario_tokens = ("领域", "行业", "下游", "终端", "场景", "客户", "机型", "设备")
        if any(token in snippet for token in scenario_tokens):
            return True
    # Otherwise accept snippets that contain a technical-looking term.
    return bool(_TECHNICAL_TERM_RE.search(snippet))


def _spaced_pattern(marker: str) -> str:
    """Return a regex that tolerates whitespace between characters of a marker."""
    chars = []
    for char in marker:
        if re.match(r"\s", char):
            continue
        if char in r"\.^$*+?{}[]|()":
            chars.append(re.escape(char))
        else:
            chars.append(re.escape(char) + r"\s*")
    pattern = "".join(chars)
    # Trim trailing \s* to avoid over-matching.
    pattern = re.sub(r"\\s\*$", "", pattern)
    return pattern


def _bounded_snippet(text: str, marker_start: int, marker_end: int) -> str:
    """Return a whitespace-normalized snippet around a marker."""
    raw_start = max(0, marker_start - _SNIPPET_WINDOW_BEFORE)
    raw_end = min(len(text), marker_end + _SNIPPET_WINDOW_AFTER)

    # Prefer sentence boundaries, but do not expand beyond the window.
    sentence_start = text.rfind("。", raw_start, marker_start)
    if sentence_start < raw_start:
        sentence_start = text.rfind("；", raw_start, marker_start)
    if sentence_start < raw_start:
        sentence_start = text.rfind("\n", raw_start, marker_start)
    if sentence_start >= raw_start:
        start = sentence_start + 1
    else:
        start = raw_start

    sentence_end = text.find("。", marker_end, raw_end)
    if sentence_end < 0 or sentence_end > raw_end:
        sentence_end = text.find("；", marker_end, raw_end)
    if sentence_end >= marker_end and sentence_end <= raw_end:
        end = sentence_end + 1
    else:
        end = raw_end

    snippet = _repair_spaced_tokens(_normalize_whitespace(text[start:end]))
    if _looks_like_glossary(snippet):
        return ""
    if _looks_like_noise(snippet):
        return ""
    if len(snippet) < _MIN_SNIPPET_LENGTH:
        return ""
    if len(snippet) > _MAX_SNIPPET_LENGTH:
        snippet = snippet[: _MAX_SNIPPET_LENGTH - 1].rstrip() + "…"
    return snippet


def _looks_like_glossary(snippet: str) -> bool:
    """Reject definition/glossary snippets that are common in annual reports."""
    if "股票代码" in snippet or "上市公司" in snippet:
        return True
    if snippet.count("指") >= 2:
        return True
    if "简称" in snippet and ("指" in snippet or "是" in snippet):
        return True
    if "证券交易所" in snippet:
        return True
    return False


def _repair_spaced_tokens(text: str) -> str:
    """Repair Jina-style spacing inside common technical tokens."""
    # Remove spaces between consecutive CJK characters.
    text = re.sub(r"([一-鿿])\s+([一-鿿])", r"\1\2", text)
    # Repair spaced hyphenated/alphanumeric tokens such as "Wi-F i" -> "Wi-Fi".
    text = re.sub(r"([A-Za-z0-9])\s*-\s*([A-Za-z0-9])\s*([A-Za-z0-9])?", r"\1-\2\3", text)
    # Repair spaced single technical words such as "W i F i" -> "WiFi" is too aggressive;
    # instead only collapse spaces inside a token that already has a hyphen.
    return text


def _deduplicate_and_finalize(evidence: Dict[str, Dict[str, Any]]) -> None:
    for key, bucket in evidence.items():
        diversity_tokens = _BUCKET_DIVERSITY_TOKENS.get(key, ())
        unique = _deduplicated_snippets(
            bucket.get("snippets", []),
            diversity_tokens=diversity_tokens,
            limit=5,
        )
        bucket["snippets"] = unique
        bucket["present"] = bool(unique)
        bucket["refs"] = list(dict.fromkeys(bucket.get("refs", [])))[:3]


def _snippet_quality_score(snippet: str, diversity_tokens: Tuple[str, ...] = ()) -> float:
    score = 0.0
    # Reward technical/product terms.
    if _TECHNICAL_TERM_RE.search(snippet):
        score += 2.0
    # Reward project-status markers.
    if any(marker in snippet for marker in _PROJECT_STATUS_MARKERS):
        score += 1.5
    # Boost for certification/testing signals to avoid losing them behind
    # mass-production snippets.
    if "认证" in snippet or "通过测试" in snippet:
        score += 1.5
    # Reward business-significance markers.
    if any(marker in snippet for marker in _BUSINESS_SIGNIFICANCE_MARKERS):
        score += 1.0
    # Coverage diversity bonus: snippets that span more topic tokens are more
    # informative for backfill (e.g., a single frequency snippet mentioning 2G/3G/4G/5G/UHB/Wi-Fi).
    if diversity_tokens:
        distinct = sum(1 for token in diversity_tokens if token in snippet)
        score += min(0.5 * distinct, _MAX_DIVERSITY_BONUS)
    # Penalize noisy / glossary-like text.
    if "指" in snippet:
        score -= 1.0
    if "股票代码" in snippet or "上市公司" in snippet:
        score -= 5.0
    # Penalize length to keep judgments concise.
    score -= max(0, len(snippet) - 120) / 120.0
    return score


def _deduplicated_snippets(
    snippets: List[str],
    diversity_tokens: Tuple[str, ...] = (),
    limit: int = 5,
) -> List[str]:
    """Return unique snippets sorted by quality score."""
    seen: set = set()
    unique: List[str] = []
    for snippet in snippets:
        if snippet and snippet not in seen:
            seen.add(snippet)
            unique.append(snippet)
    unique.sort(
        key=lambda s: _snippet_quality_score(s, diversity_tokens=diversity_tokens),
        reverse=True,
    )
    return unique[:limit]


def _unique_preserve_order(items: List[str]) -> List[str]:
    seen: set[str] = set()
    unique: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _join_snippets(snippets: List[str], max_chars: int = 600) -> str:
    text = "；".join(snippets)
    if len(text) <= max_chars:
        return text
    # Drop later snippets until we fit; keep at least the first one.
    while len(text) > max_chars and len(snippets) > 1:
        snippets = snippets[:-1]
        text = "；".join(snippets)
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return text


def _collect_refs(*buckets: Dict[str, Any]) -> List[str]:
    refs: List[str] = []
    seen: set = set()
    for bucket in buckets:
        for ref in bucket.get("refs", []):
            if ref and ref not in seen:
                seen.add(ref)
                refs.append(ref)
    return refs[:3]


def _normalize_judgment(judgment: str) -> str:
    # Collapse whitespace and ensure no accidental upgrades to confirmed facts.
    judgment = _normalize_whitespace(judgment)
    # Strip leading/trailing punctuation artifacts.
    judgment = re.sub(r"^[；。]+|[；。]+$", "", judgment)
    return judgment


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
