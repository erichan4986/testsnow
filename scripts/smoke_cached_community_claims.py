#!/usr/bin/env python3
"""Create low-credit claim notes from cached Xueqiu/community raw data.

This script never accesses Xueqiu, Chrome, CDP, Playwright, LLMs, or the
network. It reads local ``data/raw/xueqiu_data_*`` JSON and writes, only when
``--write`` is passed, one conservative social-discussion claim note.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from utils.community_claim_note_writer import write_cached_community_claim_note

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).parent.parent


def load_cached_posts(stock_name: str, raw_dir: Path = None, date_str: str = None) -> Tuple[List[dict], Path]:
    """Load cached Xueqiu posts for a stock, preferring the requested/latest date."""
    if raw_dir is None:
        raw_dir = _repo_root() / "data" / "raw"
    raw_dir = Path(raw_dir)

    if date_str:
        candidates = [raw_dir / f"xueqiu_data_{date_str}_{stock_name}.json"]
    else:
        candidates = sorted(raw_dir.glob(f"xueqiu_data_*_{stock_name}.json"), reverse=True)

    for path in candidates:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        posts = payload.get("posts", [])
        if isinstance(posts, list):
            return posts, path

    return [], Path("")


def _parse_markdown_post(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meta = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1].strip()
            body = parts[2]
            if yaml is not None and fm_text:
                loaded = yaml.safe_load(fm_text)
                if isinstance(loaded, dict):
                    meta = loaded

    interactions = meta.get("interactions") if isinstance(meta.get("interactions"), dict) else {}
    return {
        "title": str(meta.get("title") or path.stem),
        "content": body.strip(),
        "url": str(meta.get("source_url") or meta.get("url") or ""),
        "like_count": int(interactions.get("likes") or 0),
        "comment_count": int(interactions.get("comments") or 0),
        "repost_count": int(interactions.get("reposts") or 0),
        "_track": "posts_dir",
    }


def load_markdown_posts(posts_dir: Path) -> Tuple[List[dict], Path]:
    """Load local Markdown posts from a knowledge posts directory."""
    posts_dir = Path(posts_dir)
    if not posts_dir.exists():
        return [], Path("")
    posts = [_parse_markdown_post(path) for path in sorted(posts_dir.glob("*.md"))]
    return posts, posts_dir


def default_posts_dir(stock_name: str, base_dir: str = None) -> Path:
    """Return the conventional local knowledge posts directory for a stock."""
    if base_dir is None:
        base = _repo_root() / "knowledge"
    else:
        base = Path(base_dir)
    return base / "10-Stocks" / stock_name / "posts"


def run_smoke(
    stock_name: str,
    stock_code: str = "",
    base_dir: str = None,
    raw_dir: str = None,
    posts_dir: str = None,
    date_str: str = None,
    raw_date: str = None,
    write: bool = False,
    overwrite: bool = False,
    max_posts: int = 20,
    max_claims: int = 40,
) -> dict:
    """Run cached community claim extraction and optionally write the note."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    if base_dir is None:
        base_dir = str(_repo_root() / "knowledge")

    if posts_dir:
        loaded = load_markdown_posts(Path(posts_dir))
    else:
        loaded = load_cached_posts(stock_name, Path(raw_dir) if raw_dir else None, date_str=raw_date)
    if isinstance(loaded, tuple):
        posts, raw_path = loaded
    else:
        posts, raw_path = loaded, Path("")
    if not posts and not posts_dir:
        fallback_dir = default_posts_dir(stock_name, base_dir=base_dir)
        fallback_posts, fallback_path = load_markdown_posts(fallback_dir)
        if fallback_posts:
            posts, raw_path = fallback_posts, fallback_path
    result = write_cached_community_claim_note(
        stock_name=stock_name,
        stock_code=stock_code,
        posts=posts,
        base_dir=Path(base_dir),
        date_str=date_str,
        dry_run=not write,
        overwrite=overwrite,
        max_posts=max_posts,
        max_claims=max_claims,
    )
    result.update({
        "stock_name": stock_name,
        "stock_code": stock_code,
        "raw_path": str(raw_path) if raw_path else "",
        "post_count": len(posts),
        "write": write,
        "overwrite": overwrite,
    })
    return result


def print_summary(summary: dict) -> None:
    print("=" * 64)
    print(f"Cached Community Claims: {summary.get('stock_name', '')}")
    print("=" * 64)
    print(f"  status:      {summary.get('status', '')}")
    print(f"  raw path:    {summary.get('raw_path', '')}")
    print(f"  posts:       {summary.get('post_count', 0)}")
    print(f"  claims:      {summary.get('claim_count', 0)}")
    print(f"  output path: {summary.get('path', '')}")
    print("=" * 64)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="从本地雪球缓存生成低信用 claim note")
    parser.add_argument("--stock", required=True, help="股票名称，如 黑芝麻智能")
    parser.add_argument("--code", default="", help="股票代码，如 02533")
    parser.add_argument("--date", default=None, help="输出 note 日期，默认今天")
    parser.add_argument("--raw-date", default=None, help="指定 xueqiu_data 日期；默认使用最新缓存")
    parser.add_argument("--base-dir", default=None, help="knowledge 根目录，默认 ./knowledge")
    parser.add_argument("--raw-dir", default=None, help="raw 数据目录，默认 ./data/raw")
    parser.add_argument("--posts-dir", default=None, help="本地 knowledge posts 目录；提供后优先读取 Markdown posts")
    parser.add_argument("--write", action="store_true", help="实际写入 knowledge；默认 dry-run")
    parser.add_argument("--overwrite", action="store_true", help="覆盖同名 claim note")
    parser.add_argument("--max-posts", type=int, default=20)
    parser.add_argument("--max-claims", type=int, default=40)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser.parse_args([] if argv is None else argv)


def main(argv=None):
    args = _parse_args(argv)
    summary = run_smoke(
        stock_name=args.stock,
        stock_code=args.code,
        base_dir=args.base_dir,
        raw_dir=args.raw_dir,
        posts_dir=args.posts_dir,
        date_str=args.date,
        raw_date=args.raw_date,
        write=args.write,
        overwrite=args.overwrite,
        max_posts=args.max_posts,
        max_claims=args.max_claims,
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    else:
        print_summary(summary)
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
