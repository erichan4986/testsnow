"""Curated external analysis preview section renderer."""

from __future__ import annotations

import re
from typing import Any, Dict, List


DEFAULT_MAX_DISPLAY_ITEMS = 6
DEFAULT_MAX_CONTENT_CHARS = 500
_UNLIMITED_WECHAT_CATEGORIES = {"high_quality_analysis", "customer_order_or_design_win"}
_WECHAT_CATEGORY_ORDER = (
    ("high_quality_analysis", "深度分析", "公司、行业、财务、竞争格局或估值争议的分析材料。"),
    ("customer_order_or_design_win", "商业化事件", "客户、订单、定点、量产、供货或明确商业化合作信号。"),
    ("capacity_supply_chain_signal", "产能/供应链信号", "产能、交付、供应链约束或上游变化。"),
    ("industry_cycle_price_signal", "周期/价格信号", "涨价、供需、库存周期或行业景气变化。"),
    ("earnings_financial_context", "财务/业绩背景", "业绩预告、快报、财报或经营数据背景。"),
    ("certification_policy_standard", "认证/政策/标准", "认证、政策、标准或监管审查信号。"),
    ("product_or_event_signal", "产品/事件信号", "新品、方案、展会、平台发布或单一事件。"),
    ("capital_market_context", "资本市场背景", "IPO、再融资、减持、市值、股价或市场表现背景。"),
)
_WECHAT_CATEGORY_LABELS = {key: label for key, label, _description in _WECHAT_CATEGORY_ORDER}
_WECHAT_CATEGORY_DESCRIPTIONS = {key: description for key, _label, description in _WECHAT_CATEGORY_ORDER}


class CuratedExternalAnalysisRenderer:
    """Render curated external materials as a preview-only report section."""

    @staticmethod
    def required_keys() -> List[str]:
        return []

    def render(self, ctx: Dict[str, Any]) -> str:
        items = self._collect_items(ctx)
        if not items:
            return ""

        max_items = self._as_int(ctx.get("curated_external_analysis_max_display_items"), DEFAULT_MAX_DISPLAY_ITEMS)
        curated_items, wechat_items = self._split_display_items(items, max(0, max_items))
        wechat_groups = self._group_wechat_items(wechat_items)
        if not curated_items and not wechat_groups:
            return ""

        lines = [
            "## 精选外部观察（Preview）",
            "",
            "> Preview-only：本节只展示人工精选外部材料的摘要，不写 Knowledge，不接 canonical synthesis，不进入评分或风险评分。",
            "> 微信材料只作为外部观察线索；深度分析与商业化事件不设固定条数上限，但仍需去重和质量过滤，不等同于已验证事实。",
            "",
        ]

        if curated_items:
            lines.extend(["### 精选长内容", ""])
            for index, item in enumerate(curated_items, start=1):
                lines.extend(self._render_item(index, item))

        if wechat_groups:
            if curated_items:
                lines.append("")
            lines.extend([
                "### 微信精选观察",
                "",
                "> 本组按材料类型分组展示。深度分析与商业化事件完整保留；普通产品、周期、财务和资本市场背景按展示上限收敛。",
                "",
            ])
            for category, group_items in wechat_groups:
                lines.extend([
                    f"#### {_WECHAT_CATEGORY_LABELS.get(category, category)}",
                    "",
                    f"> {_WECHAT_CATEGORY_DESCRIPTIONS.get(category, '微信外部观察线索。')}",
                    "",
                ])
                for index, item in enumerate(group_items, start=1):
                    lines.extend(self._render_item(index, item, prefix="W", heading_level=5))

        return "\n".join(lines).rstrip() + "\n"

    def _collect_items(self, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_items = ctx.get("curated_external_analysis_items") or []
        if not raw_items:
            summary = ctx.get("curated_external_analysis_summary") or {}
            if isinstance(summary, dict):
                raw_items = summary.get("items") or []

        items = [dict(item) for item in raw_items if isinstance(item, dict)]
        return [item for item in items if self._is_preview_safe(item)]

    @staticmethod
    def _split_display_items(items: List[Dict[str, Any]], max_items: int) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if max_items <= 0:
            return [], []

        curated_all = [item for item in items if not CuratedExternalAnalysisRenderer._is_wechat_item(item)]
        wechat_all = [item for item in items if CuratedExternalAnalysisRenderer._is_wechat_item(item)]
        unlimited_wechat = [item for item in wechat_all if CuratedExternalAnalysisRenderer._is_unlimited_wechat_item(item)]
        limited_wechat = [item for item in wechat_all if not CuratedExternalAnalysisRenderer._is_unlimited_wechat_item(item)]
        if not curated_all:
            return [], [*unlimited_wechat, *limited_wechat[:max_items]]
        if not limited_wechat and not unlimited_wechat:
            return curated_all[:max_items], []

        curated_limit = max(1, max_items // 2)
        wechat_limit = max_items - curated_limit
        curated_items = curated_all[:curated_limit]
        wechat_items = [*unlimited_wechat, *limited_wechat[:wechat_limit]]

        leftover = max_items - len(curated_items) - len(wechat_items)
        if leftover > 0 and len(curated_all) > len(curated_items):
            extra = curated_all[len(curated_items) : len(curated_items) + leftover]
            curated_items.extend(extra)
            leftover -= len(extra)
        if leftover > 0 and len(limited_wechat) > wechat_limit:
            wechat_items.extend(limited_wechat[wechat_limit : wechat_limit + leftover])

        return curated_items, wechat_items

    @staticmethod
    def _is_wechat_item(item: Dict[str, Any]) -> bool:
        source_kind = str(item.get("source_kind") or "")
        return bool(item.get("wechat_signal_category")) or source_kind == "wechat_product_signal" or source_kind.startswith("wechat_")

    @staticmethod
    def _is_unlimited_wechat_item(item: Dict[str, Any]) -> bool:
        return CuratedExternalAnalysisRenderer._wechat_category(item) in _UNLIMITED_WECHAT_CATEGORIES

    @staticmethod
    def _wechat_category(item: Dict[str, Any]) -> str:
        category = str(item.get("wechat_signal_category") or "").strip()
        if category:
            return "product_or_event_signal" if category == "product_signal" else category
        source_kind = str(item.get("source_kind") or "")
        if source_kind == "wechat_product_signal":
            return "product_or_event_signal"
        if source_kind == "wechat_analysis_candidate":
            return "high_quality_analysis"
        if source_kind.startswith("wechat_"):
            return source_kind[len("wechat_") :]
        return ""

    @staticmethod
    def _group_wechat_items(items: List[Dict[str, Any]]) -> List[tuple[str, List[Dict[str, Any]]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            category = CuratedExternalAnalysisRenderer._wechat_category(item) or "product_or_event_signal"
            grouped.setdefault(category, []).append(item)
        ordered: List[tuple[str, List[Dict[str, Any]]]] = []
        for category, _label, _description in _WECHAT_CATEGORY_ORDER:
            if grouped.get(category):
                ordered.append((category, grouped.pop(category)))
        for category, group_items in grouped.items():
            ordered.append((category, group_items))
        return ordered

    @staticmethod
    def _is_preview_safe(item: Dict[str, Any]) -> bool:
        if item.get("quality_action") not in (None, "", "preview_only"):
            return False
        for key in ("knowledge_eligible", "synthesis_eligible", "scoring_eligible", "risk_score_eligible"):
            if bool(item.get(key)):
                return False
        return True

    def _render_item(self, index: int, item: Dict[str, Any], *, prefix: str = "", heading_level: int = 4) -> List[str]:
        heading_id = f"{prefix}{index}" if prefix else str(index)
        title = self._escape_markdown_control_chars(
            self._text(item.get("title") or item.get("url") or item.get("path") or "未命名材料"),
            escape_leading_heading=True,
        )
        lines = [
            f"{'#' * max(1, heading_level)} {heading_id}. {title}",
            "",
            f"- source_kind: `{self._text(item.get('source_kind') or 'unknown')}`",
        ]
        if item.get("source_type"):
            lines.append(f"- source_type: `{self._text(item.get('source_type'))}`")
        if item.get("wechat_signal_category"):
            lines.append(f"- wechat_signal_category: `{self._text(item.get('wechat_signal_category'))}`")
        lines.extend([
            f"- quality_action: `{self._text(item.get('quality_action') or 'preview_only')}`",
            f"- knowledge_eligible: `{str(bool(item.get('knowledge_eligible'))).lower()}`",
            f"- synthesis_eligible: `{str(bool(item.get('synthesis_eligible'))).lower()}`",
            f"- scoring_eligible: `{str(bool(item.get('scoring_eligible'))).lower()}`",
            f"- risk_score_eligible: `{str(bool(item.get('risk_score_eligible'))).lower()}`",
        ])
        if item.get("account"):
            lines.append(f"- account: {self._escape_markdown_control_chars(self._text(item.get('account')))}")
        if item.get("publish_time"):
            lines.append(f"- publish_time: {self._escape_markdown_control_chars(self._text(item.get('publish_time')))}")
        if item.get("url"):
            lines.append(f"- url: {self._text(item.get('url'))}")
        if item.get("path"):
            lines.append(f"- path: `{self._escape_markdown_control_chars(self._text(item.get('path')))}`")

        content = self._truncate(
            self._escape_markdown_control_chars(
                self._normalize_content(self._text(item.get("content"))),
                escape_leading_heading=True,
            ),
            DEFAULT_MAX_CONTENT_CHARS,
        )
        if content:
            lines.extend(["", self._blockquote(content), ""])
        else:
            lines.append("")
        return lines

    @staticmethod
    def _normalize_content(text: str) -> str:
        text = re.sub(r"\r\n?", "\n", text or "")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        if max_chars <= 0 or len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "..."

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _blockquote(value: str) -> str:
        return "\n".join(f"> {line}" if line else ">" for line in value.splitlines())

    @staticmethod
    def _escape_markdown_control_chars(value: str, *, escape_leading_heading: bool = False) -> str:
        text = value or ""
        text = re.sub(r"(?<!\\)\|", r"\\|", text)
        text = re.sub(r"(?<!\\)`", r"\\`", text)
        text = re.sub(r"(?<!\\)\*", r"\\*", text)
        text = re.sub(r"(?<!\\)_", r"\\_", text)
        if escape_leading_heading:
            text = re.sub(r"(?m)^(\s*)(#{1,6})(\s+)", r"\1\\\2\3", text)
        return text
