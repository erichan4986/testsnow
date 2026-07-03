"""
SourceAdapter: 统一多源数据格式，供 KnowledgeSynthesizer 使用。

支持来源：雪球、知乎、研报、公告、资金流向、新闻、（预留）微信公众号
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

if __name__.startswith("utils."):
    from .fundflow_material import normalize_fundflow_row
    from .source_credit import score_source_credit
else:
    from scripts.utils.fundflow_material import normalize_fundflow_row
    from scripts.utils.source_credit import score_source_credit


@dataclass
class SynthesisItem:
    """KnowledgeSynthesizer 的标准输入单元"""
    title: str
    content: str
    author: str
    source_platform: str  # "雪球" | "知乎" | "知乎全网(网易)" | "研报" | "公告" | "资金流向" | "新闻"
    url: str
    publish_time: str  # ISO date or datetime string
    interaction_score: int = 0  # likes + comments + reposts (or equivalent)
    extra: Dict = field(default_factory=dict)


class SourceAdapter(Protocol):
    """源适配器协议。每个来源实现静态方法 to_synthesis_item。"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        ...


class XueqiuAdapter:
    """雪球帖子适配器"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        content = raw.get("content", "")
        if not content:
            content = raw.get("content_text", "")
        return SynthesisItem(
            title=raw.get("title", ""),
            content=content,
            author=raw.get("author", ""),
            source_platform=raw.get("source", "雪球"),
            url=raw.get("url", ""),
            publish_time=raw.get("time", ""),
            interaction_score=(
                raw.get("like_count", 0)
                + raw.get("comment_count", 0)
                + raw.get("repost_count", 0)
            ),
            extra={"track": raw.get("_track", ""), "is_repost": raw.get("is_repost", False)},
        )


class ZhihuAdapter:
    """知乎及全网内容适配器"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        platform = raw.get("source_platform", "知乎")
        source_type = raw.get("_source_type", "site")
        source_label = f"知乎全网({platform})" if platform != "知乎" else "知乎"
        content = raw.get("content", "") or raw.get("content_text", "")
        edit_time = raw.get("edit_time", 0)
        publish_time = ""
        if edit_time:
            publish_time = datetime.fromtimestamp(edit_time).strftime("%Y-%m-%d")
        return SynthesisItem(
            title=raw.get("title", ""),
            content=content,
            author=raw.get("author_name", "未知"),
            source_platform=source_label,
            url=raw.get("url", ""),
            publish_time=publish_time,
            interaction_score=raw.get("vote_up_count", 0) + raw.get("comment_count", 0),
            extra={"search_keyword": raw.get("search_keyword", ""), "source_type": source_type},
        )


class ReportAdapter:
    """券商研报适配器"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        content_parts = []
        if raw.get("rating"):
            content_parts.append(f"[评级: {raw['rating']}]")
        if raw.get("target_price"):
            content_parts.append(f"[目标价: {raw['target_price']}]")
        content_parts.append(raw.get("content", ""))
        return SynthesisItem(
            title=raw.get("title", ""),
            content=" ".join(content_parts),
            author=raw.get("institution", ""),
            source_platform="研报",
            url=raw.get("url", ""),
            publish_time=raw.get("publish_date", ""),
            interaction_score=0,
            extra={"rating": raw.get("rating", ""), "target_price": raw.get("target_price", "")},
        )


class AnnouncementAdapter:
    """公司公告适配器"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        return SynthesisItem(
            title=raw.get("title", ""),
            content=raw.get("content", ""),
            author=raw.get("company", ""),
            source_platform="公告",
            url=raw.get("url", ""),
            publish_time=raw.get("date", ""),
            interaction_score=0,
            extra={"announcement_type": raw.get("type", "")},
        )


class FundFlowAdapter:
    """资金流向适配器（将单条记录转为文本描述）"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        row = normalize_fundflow_row(raw)
        date = row.get("date", "")
        net = row.get("main_net", 0.0)

        detail_parts = []
        if "super_net_in" in raw or "super_big_net" in raw:
            detail_parts.append(f"超大单 {row.get('super_net_in', 0.0):.0f}万")
        if "large_net_in" in raw or "big_net" in raw:
            detail_parts.append(f"大单 {row.get('large_net_in', 0.0):.0f}万")
        if "medium_net_in" in raw or "mid_net" in raw:
            detail_parts.append(f"中单 {row.get('medium_net', 0.0):.0f}万")
        if "small_net_in" in raw or "small_net" in raw:
            detail_parts.append(f"小单 {row.get('small_net', 0.0):.0f}万")
        if "change_pct" in raw:
            detail_parts.append(f"涨跌 {row.get('change_pct', 0.0):.1f}%")
        elif "main_pct" in raw:
            detail_parts.append(f"主力占比 {row.get('main_pct', 0.0):.1f}%")

        suffix = f"（{'；'.join(detail_parts)}）" if detail_parts else ""
        content = f"日期 {date}: 主力净流入 {net:.0f}万{suffix}"
        return SynthesisItem(
            title=f"资金流向 {date}",
            content=content,
            author="",
            source_platform="资金流向",
            url="",
            publish_time=date,
            interaction_score=0,
            extra={
                "main_inflow": row.get("main_inflow", 0.0),
                "main_outflow": row.get("main_outflow", 0.0),
                "net": net,
                "super_net_in": row.get("super_net_in", 0.0),
                "large_net_in": row.get("large_net_in", 0.0),
                "medium_net_in": row.get("medium_net", 0.0),
                "small_net_in": row.get("small_net", 0.0),
                "change_pct": row.get("change_pct", 0.0),
                "main_pct": row.get("main_pct", 0.0),
                "source": row.get("source", ""),
            },
        )


class NewsAdapter:
    """新闻适配器"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        return SynthesisItem(
            title=raw.get("title", ""),
            content=raw.get("content", ""),
            author=raw.get("source", ""),
            source_platform="新闻",
            url=raw.get("url", ""),
            publish_time=raw.get("date", ""),
            interaction_score=0,
            extra={},
        )


class WechatAdapter:
    """微信公众号适配器（预留接口）"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        return SynthesisItem(
            title=raw.get("title", ""),
            content=raw.get("content", ""),
            author=raw.get("author", ""),
            source_platform="微信公众号",
            url=raw.get("url", ""),
            publish_time=raw.get("publish_time", ""),
            interaction_score=raw.get("read_count", 0),
            extra={"account": raw.get("account", "")},
        )


class AgentReachAdapter:
    """Agent-Reach 多平台适配器（Twitter / Reddit / Bilibili / Wechat / Xiaohongshu）"""

    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        platform = raw.get("_platform", "") or raw.get("platform", "")
        source_platform = f"AgentReach({platform})" if platform else "AgentReach"

        title = raw.get("title", "") or ""
        content = raw.get("content", "") or raw.get("summary", "") or raw.get("text", "") or ""
        author = raw.get("author", "") or raw.get("author_name", "") or raw.get("user", "") or ""
        url = raw.get("url", "") or ""
        publish_time = raw.get("publish_time", "") or raw.get("created_at", "") or raw.get("time", "") or ""

        interaction_score = 0
        for key in ("interaction_score", "likes", "like_count", "upvotes", "votes", "reads", "read_count", "comments", "comment_count", "shares", "reposts", "repost_count"):
            val = raw.get(key)
            if isinstance(val, (int, float)):
                interaction_score = int(val)
                break

        extra = {"raw": raw}

        # Attach deterministic source-credit metadata without changing
        # SynthesisItem fields or constructor signature.
        credit = score_source_credit(
            url=url,
            source_platform=source_platform,
            author=author,
            raw=raw,
        )
        extra.update({
            "source_credit": credit.source_credit,
            "source_type": credit.source_type,
            "source_domain": credit.source_domain,
            "verification_status": credit.verification_status,
            "credit_reasons": credit.credit_reasons,
            "knowledge_eligible": credit.knowledge_eligible,
            "report_eligible": credit.report_eligible,
        })

        return SynthesisItem(
            title=title,
            content=content,
            author=author,
            source_platform=source_platform,
            url=url,
            publish_time=publish_time,
            interaction_score=interaction_score,
            extra=extra,
        )


def _as_records(value: Any) -> List[Dict]:
    if not value:
        return []
    if isinstance(value, dict):
        return [value]
    return [item for item in value if isinstance(item, dict)]


def adapt_all(
    xueqiu_items: List[Dict] = None,
    zhihu_items: List[Dict] = None,
    reports: List[Dict] = None,
    announcements: List[Dict] = None,
    fundflow: List[Dict] = None,
    news: List[Dict] = None,
    wechat_items: List[Dict] = None,
    agent_reach_items: List[Dict] = None,
) -> List[SynthesisItem]:
    """批量适配所有来源的数据为统一 SynthesisItem 列表。"""
    result = []
    result.extend([XueqiuAdapter.to_synthesis_item(i) for i in _as_records(xueqiu_items)])
    result.extend([ZhihuAdapter.to_synthesis_item(i) for i in _as_records(zhihu_items)])
    result.extend([ReportAdapter.to_synthesis_item(i) for i in _as_records(reports)])
    result.extend([AnnouncementAdapter.to_synthesis_item(i) for i in _as_records(announcements)])
    result.extend([FundFlowAdapter.to_synthesis_item(i) for i in _as_records(fundflow)])
    result.extend([NewsAdapter.to_synthesis_item(i) for i in _as_records(news)])
    result.extend([WechatAdapter.to_synthesis_item(i) for i in _as_records(wechat_items)])
    result.extend([AgentReachAdapter.to_synthesis_item(i) for i in _as_records(agent_reach_items)])
    return result
