#!/usr/bin/env python3
"""Preview curated external evidence cards through the deep-analysis display path.

This CLI is a smoke/QA tool. It does not connect cards to the normal report
pipeline, Knowledge, scoring, or risk. It uses a deterministic local
synthesizer so the preview never calls an LLM.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPT_DIR / "utils"))

from skill_pipeline import SkillContext  # noqa: E402
from report_skills.synthesis_skills import SynthesisSkill  # noqa: E402
from reporter.sections.deep_analysis_renderer import DeepAnalysisRenderer  # noqa: E402


DEFAULT_CARDS_JSON = Path("/tmp/curated_external_body_enriched_evidence_cards.json")
DEFAULT_OUTPUT = Path("/tmp/curated_external_deep_analysis_display_preview.md")
DEFAULT_JSON_OUTPUT = Path("/tmp/curated_external_deep_analysis_display_preview.json")


class DeterministicPreviewSynthesizer:
    """Small local synthesizer for preview-only smoke output."""

    def synthesize(self, stock_name: str, all_data: dict[str, Any]) -> dict[str, Any]:
        items = all_data.get("items") or []
        refs = " ".join(f"[^{idx}]" for idx in range(1, min(len(items), 4) + 1))
        titles = "；".join(_safe_title(item.title) for item in items[:4])
        citations = {idx: {"_placeholder": True} for idx, _ in enumerate(items, start=1)}

        return {
            "industry_logic": (
                f"精选外部材料仅作为专业观察，提示 {stock_name} 的外部讨论集中在：{titles}。{refs}"
                if titles
                else ""
            ),
            "fundamentals": (
                f"外部材料仅作为专业观察，不能替代公告、财报或订单核验；相关收入和商业化节奏仍需后续验证。{refs}"
                if refs
                else ""
            ),
            "valuation_debate": "外部材料不直接支持估值结论，估值仍应回到官方财务、市场价格和评分模型。",
            "funding_sentiment": "本 preview 不引入资金面判断。",
            "events_catalysts": (
                f"可后续跟踪的事件包括商业化进展、财报窗口、产业政策和供需变化。{refs}"
                if refs
                else ""
            ),
            "core_facts": [],
            "citations": citations,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards-json", default=str(DEFAULT_CARDS_JSON), help="Input curated evidence cards JSON.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Markdown preview output path.")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT), help="Structured JSON summary output path.")
    parser.add_argument("--stock", default="", help="Stock name for preview text.")
    parser.add_argument("--max-items", type=int, default=8, help="Maximum eligible cards to include.")
    parser.add_argument("--min-cards", type=int, default=3, help="Minimum eligible cards required.")
    parser.add_argument(
        "--min-total-excerpt-chars",
        type=int,
        default=1200,
        help="Minimum total excerpt characters required.",
    )
    args = parser.parse_args(argv)

    ctx = SkillContext(
        input={
            "stock_name": args.stock or "目标公司",
            "include_curated_external_evidence_cards_in_synthesis_display": True,
            "curated_external_evidence_cards_json": args.cards_json,
            "curated_external_evidence_cards_max_display_items": args.max_items,
            "curated_external_evidence_cards_min_cards": args.min_cards,
            "curated_external_evidence_cards_min_total_excerpt_chars": args.min_total_excerpt_chars,
            "stock_raw": {
                "reports": [],
                "announcements": [],
                "fundflow": [],
                "news": [],
                "zhihu": {"report_items": []},
            },
            "keep_posts": [],
        }
    )

    result = SynthesisSkill(synthesizer=DeterministicPreviewSynthesizer()).run(ctx)
    rendered = ""
    if result.get("deep_analysis_display") is not None:
        rendered = DeepAnalysisRenderer().render(
            {
                "stock_name": args.stock or "目标公司",
                "synthesis": result.get("synthesis"),
                "core_facts": result.get("core_facts"),
                "deep_analysis_display": result.get("deep_analysis_display"),
                "synthesis_display": result.get("synthesis_display"),
            }
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")

    summary = _build_summary(result, output_path, Path(args.json_output))
    json_output_path = Path(args.json_output)
    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    json_output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _build_summary(result: SkillContext, output_path: Path, json_output_path: Path) -> dict[str, Any]:
    return {
        "status": result.get("curated_external_evidence_cards_status"),
        "stats": result.get("curated_external_evidence_cards_stats") or {},
        "lint": result.get("curated_external_evidence_cards_lint") or {},
        "has_deep_analysis_display": result.get("deep_analysis_display") is not None,
        "has_synthesis_display": result.get("synthesis_display") is not None,
        "has_synthesis_text_with_curated": result.get("synthesis_text_with_curated_external_evidence_cards") is not None,
        "deep_sources_count": len(result.get("deep_analysis_display_sources") or []),
        "canonical_keys": {
            "has_synthesis": result.get("synthesis") is not None,
            "has_core_facts": result.get("core_facts") is not None,
            "has_synthesis_text": result.get("synthesis_text") is not None,
            "has_synthesis_sources": result.get("synthesis_sources") is not None,
            "has_synthesis_display": result.get("synthesis_display") is not None,
        },
        "rendered_path": str(output_path),
        "json_output_path": str(json_output_path),
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }


def _safe_title(title: str) -> str:
    cleaned = " ".join(str(title or "").split())
    return cleaned[:80]


if __name__ == "__main__":
    raise SystemExit(main())
