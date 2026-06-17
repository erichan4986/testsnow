#!/usr/bin/env python3
"""CLI for extracting high-signal observations from A-share periodic reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

UTILS_DIR = Path(__file__).resolve().parent / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from periodic_report_extractor import extract_periodic_report, render_markdown, result_to_json


def _read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception as exc:
            raise SystemExit(
                "PDF text extraction requires pypdf or PyPDF2. "
                "Install one of them, or pass a pre-extracted --txt file."
            ) from exc

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _load_input(args: argparse.Namespace) -> str:
    if args.txt:
        return Path(args.txt).read_text(encoding=args.encoding)
    if args.pdf:
        return _read_pdf_text(Path(args.pdf))
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Please provide --txt, --pdf, or pipe report text via stdin.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract A-share annual/semiannual report observations")
    parser.add_argument("--txt", help="Path to pre-extracted report text")
    parser.add_argument("--pdf", help="Path to report PDF; requires optional pypdf/PyPDF2")
    parser.add_argument("--encoding", default="utf-8", help="Text file encoding, default utf-8")
    parser.add_argument(
        "--report-type",
        default="auto",
        choices=["auto", "annual_report", "semiannual_report", "quarterly_report", "earnings_preview"],
    )
    parser.add_argument(
        "--industry",
        default="generic",
        choices=["generic", "semiconductor", "hardtech", "manufacturing"],
    )
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", help="Optional output path")
    args = parser.parse_args()

    text = _load_input(args)
    result = extract_periodic_report(text, report_type=args.report_type, industry=args.industry)
    rendered = result_to_json(result) + "\n" if args.format == "json" else render_markdown(result)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
