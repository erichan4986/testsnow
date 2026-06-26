"""Curated external analysis preview section renderer."""

from __future__ import annotations

import re
from typing import Any, Dict, List


DEFAULT_MAX_DISPLAY_ITEMS = 6
DEFAULT_MAX_CONTENT_CHARS = 500


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
        if not curated_items and not wechat_items:
            return ""

        lines = [
            "## 精选外部观察（Preview）",
            "",
            "> Preview-only：本节只展示人工精选外部材料的摘要，不写 Knowledge，不接 canonical synthesis，不进入评分或风险评分。",
            "> 微信产品信号只作为产品路线与新品密度观察，不等同于订单、收入贡献或已验证事实。",
            "",
        ]

        if curated_items:
            lines.extend(["### 精选长内容", ""])
            for index, item in enumerate(curated_items, start=1):
                lines.extend(self._render_item(index, item))

        if wechat_items:
            if curated_items:
                lines.append("")
            lines.extend([
                "### 微信产品信号",
                "",
                "> 本组只作为产品路线与新品密度观察，后续仍需财报、订单、客户导入或供应链信息交叉验证。",
                "",
            ])
            for index, item in enumerate(wechat_items, start=1):
                lines.extend(self._render_item(index, item, prefix="W"))

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

        curated_all = [item for item in items if item.get("source_kind") != "wechat_product_signal"]
        wechat_all = [item for item in items if item.get("source_kind") == "wechat_product_signal"]
        if not curated_all:
            return [], wechat_all[:max_items]
        if not wechat_all:
            return curated_all[:max_items], []

        curated_limit = max(1, max_items // 2)
        wechat_limit = max_items - curated_limit
        curated_items = curated_all[:curated_limit]
        wechat_items = wechat_all[:wechat_limit]

        leftover = max_items - len(curated_items) - len(wechat_items)
        if leftover > 0 and len(curated_all) > len(curated_items):
            extra = curated_all[len(curated_items) : len(curated_items) + leftover]
            curated_items.extend(extra)
            leftover -= len(extra)
        if leftover > 0 and len(wechat_all) > len(wechat_items):
            wechat_items.extend(wechat_all[len(wechat_items) : len(wechat_items) + leftover])

        return curated_items, wechat_items

    @staticmethod
    def _is_preview_safe(item: Dict[str, Any]) -> bool:
        if item.get("quality_action") not in (None, "", "preview_only"):
            return False
        for key in ("knowledge_eligible", "synthesis_eligible", "scoring_eligible", "risk_score_eligible"):
            if bool(item.get(key)):
                return False
        return True

    def _render_item(self, index: int, item: Dict[str, Any], *, prefix: str = "") -> List[str]:
        heading_id = f"{prefix}{index}" if prefix else str(index)
        title = self._escape_markdown_control_chars(
            self._text(item.get("title") or item.get("url") or item.get("path") or "未命名材料"),
            escape_leading_heading=True,
        )
        lines = [
            f"#### {heading_id}. {title}",
            "",
            f"- source_kind: `{self._text(item.get('source_kind') or 'unknown')}`",
        ]
        if item.get("source_type"):
            lines.append(f"- source_type: `{self._text(item.get('source_type'))}`")
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
