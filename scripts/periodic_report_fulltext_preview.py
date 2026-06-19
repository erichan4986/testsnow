#!/usr/bin/env python3
"""Render a local annual/semiannual fulltext preview from cached report text.

This is a standalone experimental entrypoint. It reads only local cache files,
does not call LLMs by default, does not fetch network resources, and does not
write to reports/ or knowledge/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UTILS_DIR = PROJECT_ROOT / "scripts" / "utils"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from reporter.sections.source_intake_evidence_renderer import SourceIntakeEvidenceRenderer  # noqa: E402
from report_skills.periodic_report_fulltext_intake_skill import (  # noqa: E402
    build_periodic_report_fulltext_intake_items_from_cache,
)
from skill_pipeline import SkillContext  # noqa: E402


DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "periodic_reports"


def default_output_path(stock_name: str, stock_code: str, report_type: str) -> Path:
    """Return the default /tmp preview path."""
    label = stock_name or stock_code or "unknown"
    code = stock_code or "unknown"
    safe_label = _safe_filename(label)
    safe_code = _safe_filename(code)
    safe_report_type = _safe_filename(report_type or "annual_report")
    return Path("/tmp") / f"{safe_label}_{safe_code}_{safe_report_type}_fulltext_preview.md"


def build_preview_markdown(
    *,
    stock_code: str,
    stock_name: str = "",
    cache_dir: Union[str, Path] = DEFAULT_CACHE_DIR,
    report_type: str = "annual_report",
    source_intake_section: bool = False,
) -> str:
    """Build a deterministic Markdown preview from local report cache."""
    items = build_periodic_report_fulltext_intake_items_from_cache(
        stock_code=stock_code,
        stock_name=stock_name,
        cache_dir=cache_dir,
        report_type=report_type,
        enable_llm=False,
    )
    title_name = stock_name or stock_code or "未知公司"
    if not items:
        return "\n".join([
            "# 定期报告全文摘要 Preview",
            "",
            f"- 股票：{title_name}",
            f"- 代码：{stock_code or '—'}",
            f"- 报告类型：{report_type}",
            f"- 缓存目录：{Path(cache_dir)}",
            "",
            "未找到本地年报缓存。",
            "",
        ])

    if source_intake_section:
        ctx = SkillContext(input={
            "stock_name": title_name,
            "source_intake_enabled": True,
            "source_intake_status": "ok",
            "source_intake_items": [],
            "external_evidence_keep_items": [],
            "periodic_report_fulltext_items": items,
        })
        rendered = SourceIntakeEvidenceRenderer().render(ctx)
    else:
        rendered = "\n\n---\n\n".join(item.content for item in items)

    item = items[0]
    extra = item.extra or {}
    header = [
        "# 定期报告全文摘要 Preview",
        "",
        f"- 股票：{title_name}",
        f"- 代码：{stock_code or '—'}",
        f"- 报告类型：{extra.get('periodic_report_type', report_type)}",
        f"- 来源类型：{extra.get('source_type', 'periodic_report_fulltext_analysis')}",
        f"- 信用等级：{extra.get('source_credit', 75)}",
        f"- 状态：{extra.get('verification_status', 'professional_analysis')}",
        f"- 实验路径：{extra.get('experimental', True)}",
        "",
    ]
    return "\n".join(header) + rendered.rstrip() + "\n"


def _safe_filename(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render a local annual/semiannual fulltext preview from cached report text"
    )
    parser.add_argument("--stock-code", required=True, help="Stock code, e.g. 300777 or 09660")
    parser.add_argument("--stock-name", default="", help="Optional stock name used for cache matching and title")
    parser.add_argument(
        "--cache-dir",
        default=str(DEFAULT_CACHE_DIR),
        help="Local periodic report cache directory",
    )
    parser.add_argument(
        "--report-type",
        default="annual_report",
        choices=["annual_report", "annual", "semiannual_report", "semiannual", "interim_report"],
    )
    parser.add_argument(
        "--source-intake-section",
        action="store_true",
        help="Render through SourceIntakeEvidenceRenderer instead of raw item content",
    )
    parser.add_argument("--output", help="Output markdown path; defaults to /tmp")
    args = parser.parse_args(argv)

    markdown = build_preview_markdown(
        stock_code=args.stock_code,
        stock_name=args.stock_name,
        cache_dir=args.cache_dir,
        report_type=args.report_type,
        source_intake_section=args.source_intake_section,
    )
    out_path = Path(args.output) if args.output else default_output_path(
        args.stock_name,
        args.stock_code,
        args.report_type,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
