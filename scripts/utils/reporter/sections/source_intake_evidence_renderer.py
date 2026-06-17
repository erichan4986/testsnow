"""Source Intake evidence section renderer."""

import re
from typing import Any, Dict, List, Optional


_SOURCE_TYPE_LABELS = {
    "exchange_announcement": "官方公告",
    "periodic_report_excerpt": "定期报告摘录",
    "news": "东方财富新闻",
    "research_report": "券商研报摘要",
}

_SOURCE_TYPE_PRIORITY = {
    "exchange_announcement": 0,
    "periodic_report_excerpt": 1,
    "research_report": 2,
    "news": 3,
}

_MAX_REPRESENTATIVE_ROWS = 6
_MAX_PERIODIC_ROWS = 8
_PERIODIC_STATUS_LABELS = {
    "risk_disclosure": "风险披露",
    "management_view": "管理层观点",
    "capital_action": "资本事项",
    "financial_forensics": "财报排雷观察",
}
_PERIODIC_ALLOWED_STATUSES = set(_PERIODIC_STATUS_LABELS)

_LOW_INFORMATION_TITLE_PATTERNS = [
    "权益分派",
    "股东大会",
    "董事会决议",
    "监事会决议",
    "法律意见书",
    "独立董事",
]

_HIGH_VALUE_ANNOUNCEMENT_PATTERNS = [
    "业绩预告",
    "业绩快报",
    "季度报告",
    "年度报告摘要",
    "重大合同",
    "中标",
    "定点",
    "客户认证",
    "产能",
    "募投",
    "固定资产投资",
    "CAPEX",
    "对外投资",
    "产业化项目",
    "并购",
    "收购",
    "设立子公司",
    "回购",
    "股权激励",
    "员工持股",
    "定增",
    "可转债",
    "融资",
    "风险提示",
    "诉讼",
    "仲裁",
    "监管处罚",
    "减持",
    "增持",
    "质押",
    "投资者关系活动",
    "调研",
]

_MARKET_WIDE_NEWS_PATTERNS = [
    "附股",
    "股东户数连续",
    "连续下降",
    "主力资金出逃股",
    "连续5日净流出",
    "连续净流出",
    "解密主力资金",
    "筹码连续",
    "股筹码",
    "股东户数降",
    "只创业板股",
]

_BUSINESS_SIGNAL_KEYWORDS = [
    "营业收入",
    "营收",
    "归属于上市公司股东的净利润",
    "净利润",
    "扣非",
    "毛利率",
    "研发费用",
    "研发投入",
    "同比",
    "增长",
    "下降",
    "减少",
    "亏损",
    "报告期内",
    "主要原因",
    "客户",
    "订单",
    "产品",
    "产能",
    "募投",
    "固定资产投资",
    "CAPEX",
    "对外投资",
    "产业化",
    "回购",
    "股权激励",
    "员工持股",
    "合同",
    "中标",
    "定点",
    "认证",
    "调研",
    "风险",
]

_BOILERPLATE_PATTERNS = [
    "本公司及董事会全体成员保证",
    "信息披露的内容真实",
    "没有虚假记载",
    "误导性陈述",
    "重大遗漏",
    "证券代码",
    "证券简称",
    "公告编号",
    "目录",
    "释义",
]


class SourceIntakeEvidenceRenderer:
    """Render Source Intake evidence as a credit-tier-aware Markdown section.

    This renderer is display-only: it reads ctx values and never mutates ctx or
    the SynthesisItem objects it renders.
    """

    @staticmethod
    def required_keys() -> List[str]:
        return []

    def render(self, ctx: Dict[str, Any]) -> str:
        enabled = bool(ctx.get("source_intake_enabled", False))
        if not enabled:
            return ""

        status = ctx.get("source_intake_status", "")
        if status in ("disabled", "error", "empty", "") or not status:
            return ""

        items = self._collect_items(ctx)
        if not items:
            return ""

        # Build credit-tier summary table.
        summary_rows = self._build_summary_rows(items)
        periodic_rows = self._build_periodic_rows(items)
        representative_rows = self._build_representative_rows(items)

        lines = [
            "## Source Intake 分层证据观察",
            "",
            "> 本节仅展示结构化外部证据来源分层，不参与综合评分、风险评分、技术面判断或最终建议。",
            "> 官方公告可用于事实确认；新闻与券商研报仅作为专业观察或背景线索，不等同于官方事实。",
            "",
            "### 来源分层概览",
            "",
            "| 来源类型 | 数量 | 信用等级 | 事实用途 | 状态 |",
            "|----------|------|----------|----------|------|",
        ]
        lines.extend(summary_rows)
        lines.append("")

        if periodic_rows:
            lines.extend([
                "### 定期报告关键摘录",
                "",
                "| 时间 | 类型 | 摘录 | 信用 | 用途 |",
                "|------|------|------|------|------|",
            ])
            lines.extend(periodic_rows)
            lines.append("")

        if representative_rows:
            lines.extend([
                "### 代表性证据摘录",
                "",
                "| 时间 | 来源层级 | 证据摘要 | 信用 | 用途 |",
                "|------|----------|----------|------|------|",
            ])
            lines.extend(representative_rows)
            lines.append("")

        return "\n".join(lines)

    def _collect_items(self, ctx: Dict[str, Any]) -> List[Any]:
        """Collect Source Intake items from the original list or merged keep items.

        Prefers `source_intake_items` to avoid double-counting with merged items.
        Falls back to `external_evidence_keep_items` filtered by source_type.
        """
        items = ctx.get("source_intake_items", []) or []
        if items:
            return [item for item in items if self._is_source_intake_item(item)]

        merged = ctx.get("external_evidence_keep_items", []) or []
        return [item for item in merged if self._is_source_intake_item(item)]

    def _is_source_intake_item(self, item: Any) -> bool:
        source_type = self._item_source_type(item)
        # Accept known source types and any other non-empty source_type so they
        # can be bucketed as "其他来源". Items without source_type metadata are
        # not considered Source Intake evidence.
        return bool(source_type)

    def _item_source_type(self, item: Any) -> str:
        extra = getattr(item, "extra", {}) or {}
        if not isinstance(extra, dict):
            extra = {}
        return str(extra.get("source_type", "")).lower().strip()

    def _item_credit(self, item: Any) -> int:
        extra = getattr(item, "extra", {}) or {}
        if not isinstance(extra, dict):
            extra = {}
        try:
            return int(extra.get("source_credit", 0))
        except (TypeError, ValueError):
            return 0

    def _item_verification_status(self, item: Any) -> str:
        source_type = self._item_source_type(item)
        extra = getattr(item, "extra", {}) or {}
        if not isinstance(extra, dict):
            extra = {}
        status = str(extra.get("verification_status", "")).lower().strip()

        # Normalize medium-credit sources down to professional_observation regardless
        # of malformed metadata claiming confirmed_fact.
        if source_type in ("news", "research_report"):
            return "professional_observation"
        if source_type == "periodic_report_excerpt":
            return status if status in _PERIODIC_ALLOWED_STATUSES else "management_view"
        return status if status else "unknown"

    def _build_summary_rows(self, items: List[Any]) -> List[str]:
        buckets: Dict[str, Dict[str, Any]] = {}
        for item in items:
            source_type = self._item_source_type(item)
            if source_type not in buckets:
                buckets[source_type] = {
                    "label": _SOURCE_TYPE_LABELS.get(source_type, "其他来源"),
                    "count": 0,
                    "credits": set(),
                    "status": self._item_verification_status(item),
                }
            buckets[source_type]["count"] += 1
            credit = self._item_credit(item)
            if credit:
                buckets[source_type]["credits"].add(credit)

        rows = []
        # Preserve priority order for known types, then append unknowns.
        ordered_types = sorted(
            buckets.keys(),
            key=lambda t: (_SOURCE_TYPE_PRIORITY.get(t, 99), t),
        )
        for source_type in ordered_types:
            bucket = buckets[source_type]
            credits = sorted(bucket["credits"])
            credit_text = str(credits[0]) if len(credits) == 1 else f"{credits[0]}-{credits[-1]}" if credits else "—"
            if source_type == "exchange_announcement":
                purpose = "可用于事实确认"
            elif source_type == "periodic_report_excerpt":
                purpose = "年报/半年报规则摘录"
            elif source_type == "news":
                purpose = "背景资讯"
            else:
                purpose = "专业观察"
            rows.append(f"| {bucket['label']} | {bucket['count']} | {credit_text} | {bucket['status']} | {purpose} |")
        return rows

    def _build_periodic_rows(self, items: List[Any]) -> List[str]:
        periodic_items = [
            item
            for item in items
            if self._item_source_type(item) == "periodic_report_excerpt"
        ]
        ordered = sorted(
            periodic_items,
            key=lambda item: (
                getattr(item, "publish_time", "") or "",
                getattr(item, "title", "") or "",
            ),
            reverse=True,
        )
        rows = []
        for item in ordered[:_MAX_PERIODIC_ROWS]:
            publish_time = getattr(item, "publish_time", "") or "—"
            status = self._item_verification_status(item)
            status_label = _PERIODIC_STATUS_LABELS.get(status, "管理层观点")
            title = self._clean_text(getattr(item, "title", "") or "")
            content = self._clean_text(getattr(item, "content", "") or "")
            excerpt = self._make_excerpt(title, content)
            credit = self._item_credit(item) or "—"
            rows.append(f"| {publish_time} | {status_label} | {excerpt} | {credit} | {status} |")
        return rows

    def _build_representative_rows(self, items: List[Any]) -> List[str]:
        ordered = sorted(
            [item for item in items if self._is_representative_item(item)],
            key=lambda item: (
                -self._item_evidence_score(item),
                _SOURCE_TYPE_PRIORITY.get(self._item_source_type(item), 99),
                -self._item_credit(item),
            ),
            reverse=False,
        )
        rows = []
        for item in ordered[:_MAX_REPRESENTATIVE_ROWS]:
            publish_time = getattr(item, "publish_time", "") or "—"
            source_label = _SOURCE_TYPE_LABELS.get(self._item_source_type(item), "其他来源")
            title = self._clean_text(getattr(item, "title", "") or "—")
            content = self._clean_text(getattr(item, "content", "") or "")
            excerpt = self._make_excerpt(title, content)
            credit = self._item_credit(item) or "—"
            status = self._item_verification_status(item)
            rows.append(
                f"| {publish_time} | {source_label} | {excerpt} | {credit} | {status} |"
            )
        return rows

    def _make_excerpt(self, title: str, content: str) -> str:
        signal_excerpt = self._extract_signal_excerpt(title, content)
        if signal_excerpt:
            text = f"{title} — {signal_excerpt}" if title and title not in signal_excerpt else signal_excerpt
        else:
            text = ""

        # Avoid rendering title twice if content starts with the title.
        if not text:
            if content.strip().startswith(title.strip()):
                text = content
            else:
                text = f"{title} — {content}" if content and content != title else title

        # Strip raw URLs from visible text; the URL may be shown separately as plain text if desired.
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"\s+", " ", text).strip()

        max_len = 120
        if len(text) > max_len:
            return text[:max_len].rstrip() + "..."
        return text

    def _item_evidence_score(self, item: Any) -> int:
        title = self._clean_text(getattr(item, "title", "") or "")
        content = self._clean_text(getattr(item, "content", "") or "")
        text = f"{title} {content}".strip()

        score = self._business_signal_score(text)
        if self._extract_signal_excerpt(title, content):
            score += 30

        extra = getattr(item, "extra", {}) or {}
        if isinstance(extra, dict) and extra.get("detail_content_status") == "ok":
            score += 10

        if not content or content == title:
            score -= 10
        if any(pattern in title for pattern in _LOW_INFORMATION_TITLE_PATTERNS):
            score -= 25
        if self._item_source_type(item) == "exchange_announcement" and any(
            pattern in title for pattern in _HIGH_VALUE_ANNOUNCEMENT_PATTERNS
        ):
            score += 20
        return score

    def _is_representative_item(self, item: Any) -> bool:
        title = self._clean_text(getattr(item, "title", "") or "")
        content = self._clean_text(getattr(item, "content", "") or "")
        source_type = self._item_source_type(item)

        if source_type == "periodic_report_excerpt":
            return False

        if source_type == "news" and self._is_market_wide_list_news(title, content):
            return False

        return True

    def _is_market_wide_list_news(self, title: str, content: str) -> bool:
        text = f"{title} {content}"
        return any(pattern in text for pattern in _MARKET_WIDE_NEWS_PATTERNS)

    def _extract_signal_excerpt(self, title: str, content: str) -> str:
        if not content or content == title:
            return ""

        candidates = self._split_excerpt_candidates(content)
        best_candidate = ""
        best_score = 0
        for candidate in candidates:
            if self._is_boilerplate_candidate(candidate):
                continue
            score = self._business_signal_score(candidate)
            if score > best_score:
                best_score = score
                best_candidate = candidate

        return best_candidate if best_score > 0 else ""

    def _split_excerpt_candidates(self, text: str) -> List[str]:
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return []
        parts = re.split(r"(?<=[。！？!?；;])\s*", text)
        return [part.strip() for part in parts if part and part.strip()]

    def _is_boilerplate_candidate(self, text: str) -> bool:
        return any(pattern in text for pattern in _BOILERPLATE_PATTERNS)

    def _business_signal_score(self, text: str) -> int:
        if not text:
            return 0
        score = 0
        for keyword in _BUSINESS_SIGNAL_KEYWORDS:
            if keyword in text:
                score += 2
        if re.search(r"\d+(?:\.\d+)?\s*(?:%|亿元|万元|元|吨|项|款|个|倍)", text):
            score += 4
        elif re.search(r"\d", text):
            score += 1
        return score

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        # Remove citation markers.
        text = re.sub(r"\[\^\d+\]", "", text)
        text = re.sub(r"\[\d+\]", "", text)
        # Remove raw AgentReach markers.
        text = re.sub(r"\bAgentReach\([^)]*\)", "", text, flags=re.IGNORECASE)
        # Strip common Jina Reader / cninfo PDF metadata prefixes and lines.
        text = re.sub(r"(?im)^\s*Title:\s*[^\n]*(?:\n|$)", "\n", text)
        text = re.sub(r"(?im)^\s*URL Source:\s*[^\n]*(?:\n|$)", "\n", text)
        text = re.sub(r"(?im)^\s*Published Time:\s*[^\n]*(?:\n|$)", "\n", text)
        text = re.sub(r"(?im)^\s*Number of Pages:\s*[^\n]*(?:\n|$)", "\n", text)
        text = re.sub(r"(?im)^\s*Markdown Content:\s*(?:\n|$)", "\n", text)
        # Remove standalone H1 lines that duplicate a title fragment.
        text = re.sub(r"(?m)^\s*#\s*[^\n]+\n?", "", text)
        # Escape markdown table pipes.
        text = text.replace("|", "\\|")
        # Collapse whitespace.
        text = re.sub(r"\s+", " ", text).strip()
        text = self._normalize_pdf_spacing_artifacts(text)
        return text

    def _normalize_pdf_spacing_artifacts(self, text: str) -> str:
        # Jina/PDF text sometimes splits percentages and Chinese words, e.g.
        # "17 8.72 %" or "减 少". Keep this display-only so raw evidence is unchanged.
        text = re.sub(r"(\d{1,3})\s+(\d(?:\.\d+)?)\s*%", r"\1\2%", text)
        text = re.sub(r"(?<=\d)\s+%", "%", text)
        text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=\d+(?:\.\d+)?%)", "", text)
        text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
        return text
