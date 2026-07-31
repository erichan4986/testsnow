"""Explicitly refresh the local structured financial-history cache."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "utils"))
from reporter.data_fetcher import fetch_structured_financial_history_rows
from structured_financial_history import build_structured_financial_history_cache, write_structured_financial_history_cache

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", required=True, help="Configured stock name or code")
    parser.add_argument("--config", default=str(ROOT / "config" / "stocks.json"))
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw" / "structured_financial_history"))
    args = parser.parse_args(argv)
    stocks = json.loads(Path(args.config).read_text(encoding="utf-8"))
    stock = next((row for row in stocks if args.stock in {str(row.get("name")), str(row.get("code"))}), None)
    if not stock:
        parser.error(f"stock not found in config: {args.stock}")
    code, name = str(stock["code"]), str(stock["name"])
    rows = fetch_structured_financial_history_rows(code)
    pack = build_structured_financial_history_cache(
        stock_code=code, stock_name=name, provider_rows=rows,
        market="HK" if len(code) == 5 and code.startswith("0") else "A",
        fetched_at=datetime.now().astimezone().isoformat(timespec="seconds"))
    if not pack["records"]:
        print(f"[{name}] no valid annual CNY records; existing cache preserved", file=sys.stderr)
        return 2
    path = Path(args.cache_dir) / f"{code}.json"
    changed = write_structured_financial_history_cache(path, pack)
    print(f"[{name}] {'updated' if changed else 'unchanged'}: {path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
