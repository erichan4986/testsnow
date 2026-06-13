"""Agent-Reach evidence section renderer."""

import re
from typing import Any, Dict, List, Optional

# Some customer/competitor names are stock-centric for the first pass.
# Future phases can derive them from COMPETITOR_MAP / INDUSTRY_MAP or stock config.
_TOPIC_KEYWORDS: List[tuple] = [
    ("product_progress", ["产品", "芯片", "量产", "交付", "出货", "良率", "产能", "版本", "发布"]),
    ("customer_orders", ["客户", "定点", "订单", "合作", "供应商", "主机厂", "比亚迪", "理想", "蔚来", "小鹏"]),
    ("competition", ["竞争", "对手", "同业", "替代", "英伟达", "高通", "地平线", "Mobileye"]),
    ("earnings_business", ["财报", "营收", "收入", "利润", "毛利率", "指引", "同比", "环比", "亏损"]),
    ("market_sentiment", ["热度", "讨论", "舆情", "关注", "投资者", "机构", "评级", "观点"]),
]

_TOPIC_LABELS: Dict[str, str] = {
    "product_progress": "产品/量产进展",
    "customer_orders": "客户/定点/订单",
    "competition": "竞争对手动态",
    "earnings_business": "财报/业绩线索",
    "market_sentiment": "市场反馈/舆情变化",
    "to_verify": "待核查线索",
}


def classify_agent_reach_topic(item: Any, quality_result: Optional[Dict] = None) -> str:
    """Deterministic topic classification for an Agent-Reach SynthesisItem.

    Uses title + content + quality reasons text. First matching topic wins.
    """
    text_parts = [
        getattr(item, "title", "") or "",
        getattr(item, "content", "") or "",
    ]
    if quality_result:
        reasons = quality_result.get("reasons", []) or []
        text_parts.extend(str(r) for r in reasons)

    text = " ".join(text_parts)

    for topic_key, keywords in _TOPIC_KEYWORDS:
        for kw in keywords:
            if kw in text:
                return topic_key

    return "to_verify"


class AgentReachEvidenceRenderer:
    """Render filtered Agent-Reach evidence as a themed Markdown section.

    This is a display layer only; it does not generate analytical conclusions.
    """

    MAX_KEEP_ITEMS = 6
    MAX_DEMOTE_ITEMS = 4

    @staticmethod
    def required_keys() -> List[str]:
        return []

    def render(self, ctx: Dict[str, Any]) -> str:
        enabled = ctx.get("agent_reach_enabled", False)
        if not enabled:
            return ""

        quality_status = ctx.get("agent_reach_quality_status", "")
        if quality_status in ("disabled", "skipped", "error") or not quality_status:
            return ""

        if quality_status == "empty":
            return self._render_empty()

        keep_items = ctx.get("agent_reach_keep_items", []) or []
        demote_items = ctx.get("agent_reach_demote_items", []) or []

        if not keep_items and not demote_items:
            return ""

        quality_results = ctx.get("agent_reach_quality_results", []) or []
        summary = ctx.get("agent_reach_quality_summary", {}) or {}
        fetch_status = ctx.get("agent_reach_status", "")

        quality_lookup = self._build_quality_lookup(quality_results)

        # Classify keep items
        keep_by_topic: Dict[str, List[Any]] = {}
        for item in keep_items[: self.MAX_KEEP_ITEMS]:
            key = (getattr(item, "title", ""), getattr(item, "source_platform", ""), getattr(item, "url", ""))
            qr = quality_lookup.get(key, {})
            topic = classify_agent_reach_topic(item, qr)
            keep_by_topic.setdefault(topic, []).append((item, qr))

        lines = []
        lines.append("## Agent-Reach 外部证据观察")
        lines.append("")
        lines.append("> 本节仅展示外部检索证据，不参与综合评分、风险评分或 LLM 深度分析结论。")
        lines.append("")

        # Overview
        lines.append("### 本期外部证据概览")
        lines.append("")
        keep_count = summary.get("keep", 0)
        demote_count = summary.get("demote", 0)
        discard_count = summary.get("discard", 0)
        lines.append(f"- 高优先级证据：{keep_count} 条；低优先级观察：{demote_count} 条；已过滤：{discard_count} 条")

        keep_topic_keys = [k for k in _TOPIC_LABELS if keep_by_topic.get(k)]
        if keep_topic_keys:
            topic_labels = [_TOPIC_LABELS.get(k, k) for k in keep_topic_keys]
            lines.append(f"- 主要主题：{'、'.join(topic_labels)}")

        lines.append(f"- 检索状态：{fetch_status}；质量门：{quality_status}")
        lines.append("")

        # Themed evidence
        if keep_by_topic:
            lines.append("### 主题化证据观察")
            lines.append("")

            for topic_key in _TOPIC_LABELS:
                if topic_key not in keep_by_topic:
                    continue
                items = keep_by_topic[topic_key]
                label = _TOPIC_LABELS.get(topic_key, topic_key)
                lines.append(f"#### {label}")
                lines.append("")
                lines.append(self._render_table(items))
                lines.append("")

        # Demote items
        if demote_items:
            lines.append("### 待人工复核线索")
            lines.append("")
            lines.append("> 以下信息相关性或证据密度较弱，仅作为后续人工核查线索，不构成事实确认。")
            lines.append("")
            demote_with_qr = []
            for item in demote_items[: self.MAX_DEMOTE_ITEMS]:
                key = (getattr(item, "title", ""), getattr(item, "source_platform", ""), getattr(item, "url", ""))
                qr = quality_lookup.get(key, {})
                demote_with_qr.append((item, qr))
            lines.append(self._render_table(demote_with_qr))
            lines.append("")

        return "\n".join(lines)

    def _render_empty(self) -> str:
        lines = [
            "## Agent-Reach 外部证据观察",
            "",
            "> 本节仅展示外部检索证据，不参与综合评分、风险评分或 LLM 深度分析结论。",
            "",
            "Agent-Reach 未检索到可用外部证据。",
        ]
        return "\n".join(lines)

    def _build_quality_lookup(self, quality_results: List[Dict]) -> Dict:
        lookup = {}
        for r in quality_results:
            key = (r.get("title", ""), r.get("source", ""), r.get("url", ""))
            lookup[key] = r
        return lookup

    def _render_table(self, items: List[tuple]) -> str:
        lines = [
            "| 时间 | 证据摘要 | 来源 | 质量 | 链接 |",
            "|------|----------|------|------|------|",
        ]
        for item, qr in items:
            publish_time = getattr(item, "publish_time", "") or "—"
            source = self._escape_md(getattr(item, "source_platform", "") or "—")
            title = self._clean_jina_title(getattr(item, "title", "") or "—")
            title = self._escape_md(title)

            excerpt = self._make_excerpt(item)
            excerpt = self._escape_md(excerpt)
            display_text = f"{title} — {excerpt}" if excerpt and excerpt != title else title

            score = qr.get("score", "—") if qr else "—"
            reasons = "; ".join(qr.get("reasons", [])) if qr else "未评分"
            reasons = self._escape_md(reasons)
            quality_cell = f"{score} / {reasons}" if reasons != "未评分" else f"{score} / 未评分"

            url = getattr(item, "url", "")
            link = f"[原文]({url})" if url else "—"

            lines.append(
                f"| {publish_time} | {display_text} | {source} | {quality_cell} | {link} |"
            )

        return "\n".join(lines)

    def _make_excerpt(self, item: Any) -> str:
        content = getattr(item, "content", "") or ""
        if not content:
            content = getattr(item, "title", "") or ""

        title = getattr(item, "title", "") or ""
        title = self._clean_jina_title(title)
        cleaned = self._clean_jina_content(content, title)

        max_len = 120
        if len(cleaned) > max_len:
            return cleaned[:max_len].rstrip() + "..."
        return cleaned

    def _clean_jina_content(self, content: str, title: str) -> str:
        """Strip Jina Reader metadata prefixes and normalize to a single line."""
        if not content:
            return ""

        # Normalize line endings and whitespace first so multi-line prefix matching works.
        text = content.replace("\r\n", "\n").replace("\r", "\n")

        # Strip leading "Title: ..." line if present.
        if text.lstrip().startswith("Title:"):
            lines = text.split("\n", 1)
            text = lines[1] if len(lines) > 1 else ""

        # Remove "URL Source: <url>" lines anywhere in the text.
        text = re.sub(r"\n?URL Source:\s*\S+\n?", "\n", text)

        # Remove standalone "Markdown Content:" label line.
        text = re.sub(r"\n?Markdown Content:\n?", "\n", text)

        # Remove duplicated title/H1 fragments so we don't render "title — title...".
        if title:
            stripped_title = title.lstrip("#").strip()
            # Exact H1 line (with optional leading whitespace).
            text = re.sub(rf"(?m)^\s*#\s*{re.escape(stripped_title)}\s*\n?", "", text)
            # The title itself as a plain prefix.
            text = re.sub(rf"^\s*{re.escape(stripped_title)}\s*", "", text)
            # H1 whose heading body is a prefix of the title (common Jina shape).
            text = re.sub(rf"(?m)^\s*#\s*{re.escape(stripped_title[:40])}[^\n]*\n?", "", text)
            # Same heading appearing inline.
            text = re.sub(rf"#\s*{re.escape(stripped_title)}\s*", "", text)

        # Try to extract the real article body from Jina's full-page dump.
        # Strategy 1: Black Sesame award/news pages use a "获奖" image + YYYY/MM/DD.
        article_match = re.search(
            r"!\[Image \d+: 获奖\]\([^)]+\)\s*(?P<date>\d{4}/\d{2}/\d{2})\s*\n\s*(?P<body>.+?)\n(?:上一篇|下一篇|热门新闻|热门标签|关注我们)",
            text,
            re.DOTALL,
        )
        # Strategy 2: General Black Sesame cooperation pages use a leading date
        # paragraph (e.g. "2026年6月8日，..." or "4月24日，...") and end with
        # "上一篇"/"下一篇" footer.
        if not article_match:
            article_match = re.search(
                r"(?:\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}月\d{1,2}日|\d{4}/\d{2}/\d{2})\s*，(?P<body>.+?)(?:\n(?:上一篇|下一篇|热门新闻|热门标签|关注我们)|$)",
                text,
                re.DOTALL,
            )
        if article_match:
            text = article_match.group("body")

        # Remove markdown images and collapse link syntax to link text.
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", "", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

        # Remove duplicated title/H1 inline (Jina sometimes leaves the heading
        # in the body even after title stripping).
        if title:
            stripped_title = title.lstrip("#").strip()
            text = re.sub(rf"(?m)^\s*#\s*{re.escape(stripped_title[:60])}[^\n]*\n?", "", text)
            text = re.sub(rf"#\s*{re.escape(stripped_title[:60])}[^\n]*", "", text)
            # Also drop the title if it appears as a plain prefix in the body.
            text = re.sub(rf"^\s*{re.escape(stripped_title)}\s*", "", text)

        # Strip common Black Sesame official-site navigation boilerplate that
        # survives the article extraction (e.g. "联系我们", "商务合作", "首页",
        # "公司信息" and their trailing fragments).
        nav_phrases = {
            "联系我们", "商务合作", "加入我们", "媒体资讯", "选择语言",
            "中文", "English", "首页", "公司信息", "基本介绍", "概况",
            "团队", "DNA", "认证", "发展历程", "公司实力", "奖项",
            "认证&资质", "品牌文化", "合作共赢", "资料下载", "领先技术",
            "核心IP", "ISP", "NPU", "SoC设计", "山海工具链", "核心产品",
            "华山系列芯片", "华山A2000家族芯片", "华山A1000家族芯片",
            "华山A1000", "华山A1000L", "华山A1000 Pro", "武当系列芯片",
            "武当C1296", "武当C1236", "机器人平台", "瀚海中间件",
            "解决方案", "智能汽车", "智能道路", "行业应用", "消费电子",
            "公司动态", "新闻中心", "品牌中心", "投资者关系", "招股文件",
            "业绩报告", "公告及通函", "企业管制", "投资者关系联络",
            "网站地图", "知识产权声明", "关注我们", "当前位置", "热门新闻",
            "热门标签", "关键字", "上一篇：", "下一篇：", "上一篇", "下一篇",
        }

        def _drop_nav_tokens(segment: str) -> str:
            """Remove navigation tokens while preserving real article text."""
            tokens = segment.split()
            cleaned_tokens = []
            for t in tokens:
                # Drop standalone nav phrases; keep everything else.
                if t in nav_phrases:
                    continue
                cleaned_tokens.append(t)
            return " ".join(cleaned_tokens)

        # Apply token-level nav cleanup to the whole text. This is intentionally
        # conservative: it only removes tokens that exactly match known nav
        # phrases, so real article text like "与东风汽车达成平台级合作" is kept.
        text = _drop_nav_tokens(text)

        # Collapse remaining newlines, tabs, and repeated spaces into a single space.
        text = re.sub(r"[\s]+", " ", text).strip()

        return text

    @staticmethod
    def _clean_jina_title(title: str) -> str:
        """Strip the leading 'Title: ' prefix that Jina Reader puts on the first line."""
        if not title:
            return ""
        title = title.strip()
        if title.startswith("Title:"):
            title = title[len("Title:"):].strip()
        return title

    @staticmethod
    def _escape_md(text: str) -> str:
        if not text:
            return ""
        return text.replace("|", "\\|")
