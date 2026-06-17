#!/usr/bin/env python3
"""Render a compact markdown audit for claim verification.

This is a local-only smoke helper. It reads existing knowledge notes through
``build_claim_verification_plan`` and writes a human-readable markdown summary.
It does not access network, run LLMs, mutate knowledge, or enter the report
pipeline.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

sys.path.insert(0, str(Path(__file__).parent / "utils"))

from claim_verification import build_claim_verification_plan


_CITATION_RE = re.compile(r"\[\^?\d+\]")


def _repo_root() -> Path:
    return Path(__file__).parent.parent


def _clean_cell(value: Any, limit: int = 120) -> str:
    text = str(value or "")
    text = _CITATION_RE.sub("", text)
    text = re.sub(r"https?://\S+", "", text)
    text = text.replace("|", "/")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[: limit - 1] + "..."
    return text


def _candidate_label(candidate: Any) -> str:
    title = _clean_cell(getattr(candidate, "title", ""), 80)
    if title:
        return title
    source_file = Path(str(getattr(candidate, "source_file", "") or "")).name
    return _clean_cell(source_file or getattr(candidate, "claim_id", ""), 80)


def _source_file_label(value: Any) -> str:
    labels = []
    for part in str(value or "").split(", "):
        name = Path(part).name
        if name and name not in labels:
            labels.append(name)
    return _clean_cell(", ".join(labels), 120)


def _source_label(candidate: Any) -> str:
    files = getattr(candidate, "source_files", []) or []
    if files:
        return _source_file_label(", ".join(str(f) for f in files))
    return _source_file_label(getattr(candidate, "source_file", ""))


def _verification_map(plan: Any) -> Dict[str, Any]:
    return {getattr(v, "claim_id", ""): v for v in getattr(plan, "verifications", [])}


def _high_credit_map(plan: Any) -> Dict[str, Any]:
    return {getattr(c, "claim_id", ""): c for c in getattr(plan, "high_credit_claims", [])}


def _rows_for_action(plan: Any, action: str) -> List[List[str]]:
    verifications = _verification_map(plan)
    high_by_id = _high_credit_map(plan)
    rows: List[List[str]] = []

    for low in getattr(plan, "low_credit_claims", []):
        verification = verifications.get(getattr(low, "claim_id", ""))
        if verification is None or getattr(verification, "action", "") != action:
            continue

        verified_by = []
        for ref in getattr(verification, "verified_by", []) or []:
            high = high_by_id.get(ref)
            verified_by.append(_candidate_label(high) if high is not None else _clean_cell(ref, 40))

        reasons = "; ".join(str(r) for r in getattr(verification, "reasons", []) or [])
        rows.append([
            _clean_cell(getattr(low, "claim_text", ""), 140),
            str(getattr(verification, "confidence", "") or ""),
            _clean_cell("、".join(verified_by), 100),
            str(getattr(low, "max_source_credit", "") or ""),
            str(getattr(low, "source_count", "") or ""),
            _clean_cell(reasons, 140),
            _source_label(low),
        ])

    return rows


def _table(headers: Iterable[str], rows: List[List[str]]) -> List[str]:
    headers = list(headers)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    if not rows:
        lines.append("| " + " | ".join(["-" for _ in headers]) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def render_claim_verification_audit(plan: Any) -> str:
    """Render a compact markdown audit for one claim verification plan."""
    counts = {
        "high_credit_claims": len(getattr(plan, "high_credit_claims", [])),
        "low_credit_claims": len(getattr(plan, "low_credit_claims", [])),
        "verified": sum(1 for v in getattr(plan, "verifications", []) if getattr(v, "action", "") == "verified"),
        "supported": sum(1 for v in getattr(plan, "verifications", []) if getattr(v, "action", "") == "supported"),
        "unverified": sum(1 for v in getattr(plan, "verifications", []) if getattr(v, "action", "") == "unverified"),
        "needs_review": sum(1 for v in getattr(plan, "verifications", []) if getattr(v, "action", "") == "needs_review"),
        "skipped_files": len(getattr(plan, "skipped_files", [])),
    }

    stock = _clean_cell(getattr(plan, "stock", ""), 60)
    lines = [
        f"# {stock} Claim Verification Audit",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "> This audit is read-only. It does not affect scoring, risk, EV, technical analysis, synthesis, citations, or recommendations.",
        "",
        "## Counts",
        "",
    ]
    lines.extend(_table(["Bucket", "Count"], [[k, str(v)] for k, v in counts.items()]))

    sections = [
        ("Verified", "verified"),
        ("Supported", "supported"),
        ("Unverified", "unverified"),
        ("Needs Review", "needs_review"),
    ]
    for title, action in sections:
        lines.extend([
            "",
            f"## {title}",
            "",
        ])
        lines.extend(_table(["Claim", "Confidence", "Verified By", "Max Credit", "Source Count", "Reason", "Sources"], _rows_for_action(plan, action)))

    lines.append("")
    return "\n".join(lines)


def run_audit(stock: str, base_dir: str = None, output: str = None) -> Dict[str, Any]:
    if base_dir is None:
        base_dir = str(_repo_root() / "knowledge")
    if output is None:
        date_str = datetime.now().strftime("%Y%m%d")
        output = str(_repo_root() / "docs" / "agent_workflow" / f"{date_str}-{stock}-claim-verification-audit.md")

    plan = build_claim_verification_plan(stock, base_dir)
    text = render_claim_verification_audit(plan)
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return {
        "status": "written",
        "stock": stock,
        "path": str(out_path),
        "low_credit_claims": len(getattr(plan, "low_credit_claims", [])),
        "high_credit_claims": len(getattr(plan, "high_credit_claims", [])),
        "verifications": len(getattr(plan, "verifications", [])),
    }


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Render claim verification audit markdown")
    parser.add_argument("--stock", required=True, help="Stock name, e.g. 中简科技")
    parser.add_argument("--base-dir", default=None, help="Knowledge root, default ./knowledge")
    parser.add_argument("--output", default=None, help="Output markdown path")
    return parser.parse_args([] if argv is None else argv)


def main(argv=None):
    args = _parse_args(argv)
    result = run_audit(stock=args.stock, base_dir=args.base_dir, output=args.output)
    print(f"written: {result['path']}")
    print(f"high={result['high_credit_claims']} low={result['low_credit_claims']} verifications={result['verifications']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
