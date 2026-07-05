"""
雪球帖子内容质量评分与分类器

将列表页提取的帖子分流为：
- featured: 长文精选（进入详情页、Vault、报告精品帖）
- sentiment: 短帖情绪（仅参与情绪统计）

准入制：
  条件A: 截断标识("...") + 含数据 + 含逻辑词  → 强制 featured
  条件B: 正文长度 >= 120 字 + 互动数 > 15      → 也可以 featured

候选池内按 content_score 质量分排序，分高者优先进入详情页。
"""

import re
from typing import Dict

# 逻辑连接词
_LOGIC_WORDS = [
    "因为", "所以", "如果", "那么", "因此", "意味着", "结论",
    "前提", "推导", "验证", "由于", "导致", "说明", "反映",
    "对比", "相较于", "数据表明", "统计", "测算", "估算",
]

# 数据模式
_DATA_PATTERNS = [r"\d+[%％]", r"\d+\.\d+", r"\d+亿", r"\d+万", r"\d+元"]

# 高质量关键词（标题/摘要中出现表明可能是深度分析）
_QUALITY_KEYWORDS = [
    "深度", "分析", "研报", "调研", "逻辑", "拆解", "梳理",
    "产业链", "基本面", "估值", "财报", "业绩", "行业",
    "格局", "竞争", "壁垒", "护城河", "商业模式",
]


def _has_logic_words(text: str) -> bool:
    return any(w in text for w in _LOGIC_WORDS)


def _has_data(text: str) -> bool:
    return any(re.search(p, text) for p in _DATA_PATTERNS)


def _has_quality_keywords(text: str) -> bool:
    return any(kw in text for kw in _QUALITY_KEYWORDS)


def is_featured(post: Dict) -> bool:
    """
    准入制：判断帖子是否进入 featured 候选池。

    满足任一条件即可：
      A: 有截断标识("...") AND 含数据 AND 含逻辑词
      B: 正文长度 >= 120 字 AND 互动数 > 15
    """
    title = post.get("title") or ""
    content = post.get("content") or ""
    combined = f"{title} {content}"
    likes = post.get("like_count") or 0
    comments = post.get("comment_count") or 0
    content_len = len(content)
    interaction = likes + comments

    # 条件A: 看起来像长文 + 有实质内容
    # 雪球列表页长文被截断后会显示 "..." 或 "展开" 按钮
    has_truncation = "..." in content or "..." in title or "展开" in content
    condition_a = has_truncation and _has_data(combined) and _has_logic_words(combined)

    # 条件B: 足够长 + 有一定互动（门槛降低以捕获更多候选）
    condition_b = content_len >= 80 and interaction > 5

    return condition_a or condition_b


def content_score(post: Dict) -> float:
    """
    内容质量打分（用于候选池内排序）。

    分值越高表示内容质量越好，优先进入详情页。
    """
    title = post.get("title") or ""
    content = post.get("content") or ""
    combined = f"{title} {content}"
    likes = post.get("like_count") or 0
    comments = post.get("comment_count") or 0
    content_len = len(content)
    score = 0.0

    # 1. 截断标识（看起来像长文）
    if "..." in content or "..." in title or "展开" in content:
        score += 3.0

    # 2. 含数据（有实质数字）
    if _has_data(combined):
        score += 2.0

    # 3. 含逻辑词（有推导过程）
    if _has_logic_words(combined):
        score += 2.0

    # 4. 含高质量关键词
    if _has_quality_keywords(combined):
        score += 1.0

    # 5. 互动数（社区关注度）
    interaction = likes + comments
    if interaction > 20:
        score += 2.0
    elif interaction > 10:
        score += 1.0
    elif interaction > 3:
        score += 0.5

    # 6. 正文长度（内容体量）
    score += min(content_len / 100, 3.0)

    return score


def classify_post(post: Dict) -> str:
    """
    将帖子分类为 featured 或 sentiment。

    Returns:
        "featured" | "sentiment"
    """
    if is_featured(post):
        return "featured"
    return "sentiment"


def score_post(post: Dict) -> float:
    """
    兼容旧接口：返回 content_score（用于排序）。
    """
    return content_score(post)
