#!/usr/bin/env python3
"""Build a local preview of broker research digest cards from downloaded PDFs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UTILS_DIR = PROJECT_ROOT / "scripts" / "utils"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from broker_research_digest import (  # noqa: E402
    build_broker_research_digest_cards,
    build_broker_research_digest_preview_markdown,
    deduplicate_broker_digest_cards_by_viewpoint,
    extract_pdf_text,
)
from broker_research_digest_note_writer import write_broker_research_digest_card_notes  # noqa: E402
from source_adapter import SynthesisItem  # noqa: E402


DEFAULT_BROKER_RESEARCH_ROOT = PROJECT_ROOT / "data" / "raw" / "broker_research_reports"


def _safe_filename(value: str) -> str:
    """Return a filesystem-safe filename fragment."""
    cleaned = re.sub(r"[\\/:*?\"<>|\s]+", "_", str(value or "").strip())
    return cleaned.strip("_") or "unknown"


def _stock_cache_folder(stock_name: str, stock_code: str) -> str:
    return _safe_filename("_".join(part for part in [stock_name, stock_code] if part))


def _parse_pdf_filename(path: Path) -> Dict[str, str]:
    """Infer report metadata from the Eastmoney PDF filename convention."""
    stem = path.stem
    parts = stem.split("_", 2)
    if len(parts) == 3 and re.match(r"\d{4}-\d{2}-\d{2}$", parts[0]):
        publish_time, institution, title = parts
    else:
        publish_time, institution, title = "", "", stem
    return {
        "publish_time": publish_time,
        "institution": institution,
        "title": title,
    }


_KNOWN_STOCK_ALIASES = (
    ("乐鑫科技", "688018"),
    ("圣邦股份", "300661"),
    ("中际旭创", "300308"),
    ("中简科技", "300777"),
)


def _infer_stock_from_text(title: str, fallback_name: str, fallback_code: str, text_hint: str = "") -> Dict[str, str]:
    text = f"{title or ''} {text_hint or ''}"
    for name, code in _KNOWN_STOCK_ALIASES:
        if name in text or code in text:
            return {"stock_name": name, "stock_code": code}
    return {"stock_name": fallback_name, "stock_code": fallback_code}


def _research_item_from_pdf(
    path: Path,
    *,
    stock_name: str,
    stock_code: str,
    page_count: int = 0,
    text_hint: str = "",
) -> SynthesisItem:
    """Build a broker research SynthesisItem from a local PDF path."""
    meta = _parse_pdf_filename(path)
    title = meta["title"] or f"{stock_name}研报"
    institution = meta["institution"] or "券商研报"
    inferred_stock = _infer_stock_from_text(title, stock_name, stock_code, text_hint)
    return SynthesisItem(
        title=title,
        content=title,
        author=institution,
        source_platform="研报",
        url="",
        publish_time=meta["publish_time"],
        extra={
            "source_type": "broker_research",
            "source_credit": 72,
            "verification_status": "professional_observation",
            "institution": institution,
            "stock_name": inferred_stock["stock_name"],
            "stock_code": inferred_stock["stock_code"],
            "pdf_local_path": str(path),
            "pdf_page_count": page_count,
        },
    )


def build_broker_research_digest_preview(
    *,
    pdf_paths: Sequence[str | Path],
    stock_name: str,
    stock_code: str = "",
    max_cards_per_pdf: int = 5,
    extractor: Callable[[str], str] = extract_pdf_text,
) -> Dict[str, Any]:
    """Build digest cards and preview markdown from local broker PDF paths."""
    all_cards: List[Dict[str, Any]] = []
    processed: List[str] = []
    errors: List[Dict[str, str]] = []

    for raw_path in pdf_paths:
        path = Path(raw_path)
        try:
            pdf_text = extractor(str(path))
        except Exception as exc:
            errors.append({"path": str(path), "error": str(exc)})
            continue
        item = _research_item_from_pdf(
            path,
            stock_name=stock_name,
            stock_code=stock_code,
            page_count=_infer_pdf_page_count(pdf_text),
            text_hint=pdf_text[:1200],
        )
        cards = build_broker_research_digest_cards(
            item,
            pdf_text,
            max_cards=max_cards_per_pdf,
        )
        all_cards.extend(cards)
        processed.append(str(path))

    all_cards = deduplicate_broker_digest_cards_by_viewpoint(all_cards)

    markdown = build_broker_research_digest_preview_markdown(
        stock_name=stock_name,
        stock_code=stock_code,
        cards=all_cards,
    )
    if errors:
        markdown += "\n## Extraction Errors\n\n"
        for err in errors:
            markdown += f"- `{err['path']}`: {err['error']}\n"

    return {
        "stock_name": stock_name,
        "stock_code": stock_code,
        "pdf_count": len(pdf_paths),
        "processed_pdf_count": len(processed),
        "cards_count": len(all_cards),
        "cards": all_cards,
        "processed_pdfs": processed,
        "errors": errors,
        "markdown": markdown,
    }


def _infer_pdf_page_count(pdf_text: str) -> int:
    """Infer page count from extractor output when page separators are available."""
    markers = re.findall(r"\n\f\n|\f", pdf_text or "")
    if markers:
        return len(markers) + 1
    return 0


def _standard_pdf_dir(cache_root: str | Path, stock_name: str, stock_code: str) -> Path:
    return Path(cache_root) / _stock_cache_folder(stock_name, stock_code) / "_downloads"


def _discover_pdfs(pdf_dir: str | Path, limit: int | None = None) -> List[Path]:
    """Return local PDFs in deterministic order."""
    root = Path(pdf_dir)
    pdfs = sorted(root.glob("*.pdf"))
    return pdfs[:limit] if limit is not None else pdfs


def write_broker_research_digest_preview(
    *,
    pdf_dir: str | Path | None = None,
    cache_root: str | Path = DEFAULT_BROKER_RESEARCH_ROOT,
    stock_name: str,
    stock_code: str = "",
    output: str | Path | None = None,
    base_dir: str | Path = "knowledge",
    write_knowledge: bool = False,
    dry_run: bool = False,
    max_cards_per_pdf: int = 5,
    limit_pdfs: int | None = None,
    extractor: Callable[[str], str] = extract_pdf_text,
) -> Dict[str, Any]:
    """Write a broker research digest preview markdown file and return summary."""
    resolved_pdf_dir = Path(pdf_dir) if pdf_dir else _standard_pdf_dir(cache_root, stock_name, stock_code)
    pdfs = _discover_pdfs(resolved_pdf_dir, limit=limit_pdfs)
    if output is None:
        output_path = Path("/tmp") / f"{_safe_filename(stock_name)}_broker_research_digest_preview.md"
    else:
        output_path = Path(output)
    result = build_broker_research_digest_preview(
        pdf_paths=pdfs,
        stock_name=stock_name,
        stock_code=stock_code,
        max_cards_per_pdf=max_cards_per_pdf,
        extractor=extractor,
    )
    write_plan = None
    if write_knowledge:
        write_plan = write_broker_research_digest_card_notes(
            stock_name=stock_name,
            stock_code=stock_code,
            cards=result["cards"],
            base_dir=base_dir,
            dry_run=dry_run,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result["markdown"], encoding="utf-8")
    knowledge_written_count = len(write_plan.written) if write_plan else 0
    return {
        key: value
        for key, value in result.items()
        if key not in {"markdown", "cards"}
    } | {
        "preview_path": str(output_path),
        "pdf_dir": str(resolved_pdf_dir),
        "wrote_knowledge": bool(write_knowledge),
        "knowledge_written_count": knowledge_written_count,
        "knowledge_filtered_count": len(write_plan.filtered) if write_plan else 0,
        "knowledge_skipped_existing_count": len(write_plan.skipped_existing) if write_plan else 0,
    }


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf-dir",
        default="",
        help="Explicit local broker PDF directory. Defaults to data/raw/broker_research_reports/<stock>_<code>/_downloads.",
    )
    parser.add_argument(
        "--cache-root",
        default=str(DEFAULT_BROKER_RESEARCH_ROOT),
        help="Standard broker research cache root.",
    )
    parser.add_argument("--stock", required=True, help="Stock name for preview metadata.")
    parser.add_argument("--code", default="", help="Stock code for preview metadata.")
    parser.add_argument("--output", default="", help="Preview markdown output path. Defaults to /tmp.")
    parser.add_argument("--base-dir", default="knowledge", help="Knowledge base directory for --write-knowledge.")
    parser.add_argument("--write-knowledge", action="store_true", help="Persist eligible broker digest cards to Knowledge.")
    parser.add_argument("--dry-run", action="store_true", help="Plan Knowledge writes without creating notes.")
    parser.add_argument("--max-cards-per-pdf", type=int, default=5)
    parser.add_argument("--limit-pdfs", type=int, default=0, help="Optional PDF count limit; 0 means all.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = write_broker_research_digest_preview(
        pdf_dir=args.pdf_dir or None,
        cache_root=args.cache_root,
        stock_name=args.stock,
        stock_code=args.code,
        output=args.output or None,
        base_dir=args.base_dir,
        write_knowledge=args.write_knowledge,
        dry_run=args.dry_run,
        max_cards_per_pdf=args.max_cards_per_pdf,
        limit_pdfs=args.limit_pdfs or None,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
