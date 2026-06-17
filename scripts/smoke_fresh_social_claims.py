#!/usr/bin/env python3
"""Bounded fresh social low-credit claim smoke for one stock.

Default is dry-run and writes nothing. Use --write to persist one low-credit
note under knowledge/10-Stocks/<stock>/<YYYYMMDD>-新鲜外部社媒claims.md.

Reads only explicit URLs through Jina Reader (r.jina.ai). No open search.
No browser, no cookies, no CDP, no Xueqiu detail scraping.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence

sys.path.insert(0, str(Path(__file__).parent / "utils"))

from fresh_social_claim_intake import (
    DEFAULT_MAX_CLAIMS,
    DEFAULT_MAX_RAW_ITEMS,
    _classify_provider_status,
    _is_community_like_url,
    build_provider_record,
    build_url_reader_url,
    extract_claims_from_provider_records,
    write_fresh_social_claim_note,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


MAX_URLS = 5
PER_CALL_TIMEOUT_SECONDS = 15
GLOBAL_BUDGET_SECONDS = 60
MAX_RETRIES = 1
MAX_PAGE_CHARS = 12_000
USER_AGENT = "Mozilla/5.0 (compatible; testsnow-fresh-social-smoke/1.0)"


def _repo_root() -> Path:
    return Path(__file__).parent.parent


def _infer_platform(url: str) -> str:
    from urllib.parse import urlparse

    host = (urlparse(str(url or "")).hostname or "").lower()
    if "guba.eastmoney" in host:
        return "股吧"
    if "xueqiu" in host:
        return "雪球"
    if "weibo" in host:
        return "微博"
    return "external_social"


def _fetch_url(
    url: str,
    timeout: float = PER_CALL_TIMEOUT_SECONDS,
    stock_name: str = "",
    stock_code: str = "",
) -> Dict[str, Any]:
    """Fetch one URL through Jina Reader and return a provider record.

    This function performs a network call. It never crashes; failures are
    captured as provider status entries.
    """
    if not _is_community_like_url(url):
        return {
            "url": url,
            "status": "blocked",
            "platform": _infer_platform(url),
            "claims": [],
            "error": "blocked_by_domain_filter",
        }

    reader_url = build_url_reader_url(url)
    last_error = ""

    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                reader_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/plain, text/html, */*",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.getcode()
                text = resp.read().decode("utf-8", errors="ignore")
                text = text[:MAX_PAGE_CHARS]
                if not text or len(text.strip()) < 30:
                    return {
                        "url": url,
                        "status": "empty",
                        "platform": _infer_platform(url),
                        "claims": [],
                        "error": "empty_or_placeholder_response",
                    }
                record = build_provider_record(
                    url=url,
                    raw_text=text,
                    status=_classify_provider_status(status),
                    platform=_infer_platform(url),
                    stock_name=stock_name,
                    stock_code=stock_code,
                )
                return record
        except urllib.error.HTTPError as exc:
            status = exc.code
            last_error = f"http_{status}"
            if status == 429:
                return {
                    "url": url,
                    "status": "rate_limited",
                    "platform": _infer_platform(url),
                    "claims": [],
                    "error": last_error,
                }
            if status in (401, 403):
                return {
                    "url": url,
                    "status": "blocked",
                    "platform": _infer_platform(url),
                    "claims": [],
                    "error": last_error,
                }
            if attempt < MAX_RETRIES:
                time.sleep(1.0)
                continue
            return {
                "url": url,
                "status": _classify_provider_status(status),
                "platform": _infer_platform(url),
                "claims": [],
                "error": last_error,
            }
        except Exception as exc:
            last_error = str(exc)
            if attempt < MAX_RETRIES:
                time.sleep(1.0)
                continue
            return {
                "url": url,
                "status": "error",
                "platform": _infer_platform(url),
                "claims": [],
                "error": last_error,
            }

    # Fallback (should not reach here).
    return {
        "url": url,
        "status": "error",
        "platform": _infer_platform(url),
        "claims": [],
        "error": last_error or "unknown_fetch_error",
    }


def _eastmoney_guba_list_url(stock_code: str) -> str:
    return f"https://guba.eastmoney.com/list,{stock_code}.html"


def _build_eastmoney_guba_provider_record(
    stock_name: str,
    stock_code: str,
    list_url: str,
    posts: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build one provider record from Eastmoney guba list-page titles.

    The list page is already stock-scoped, so each title is prefixed with the
    stock name before passing through the same strict low-credit claim gate.
    Details/comments are intentionally not fetched here.
    """
    claims: List[Dict[str, Any]] = []
    post_count = 0

    for post in list(posts or [])[:DEFAULT_MAX_RAW_ITEMS]:
        if not isinstance(post, dict):
            continue
        title = str(post.get("title") or "").strip()
        if not title:
            continue
        post_count += 1
        post_url = str(post.get("url") or list_url)
        scoped_text = f"股吧帖子：{stock_name}{title}"
        record = build_provider_record(
            url=post_url,
            raw_text=scoped_text,
            status="ok",
            platform="股吧",
            stock_name=stock_name,
            stock_code=stock_code,
        )
        for claim in record.get("claims", []):
            claim["source_url"] = post_url
            claim["source_platform"] = "股吧"
            claims.append(claim)
            if len(claims) >= DEFAULT_MAX_CLAIMS:
                break
        if len(claims) >= DEFAULT_MAX_CLAIMS:
            break

    status = "ok" if post_count else "empty"
    return {
        "url": list_url,
        "status": status,
        "platform": "股吧",
        "claims": claims,
        "error": "",
        "post_count": post_count,
    }


def _fetch_eastmoney_guba_list(
    stock_code: str,
    stock_name: str,
    timeout: float = PER_CALL_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Fetch Eastmoney guba list page directly and parse titles only."""
    url = _eastmoney_guba_list_url(stock_code)
    try:
        import requests
        from parser import EastmoneyParser
    except Exception as exc:
        return {
            "url": url,
            "status": "error",
            "platform": "股吧",
            "claims": [],
            "error": f"dependency_error: {exc}",
            "post_count": 0,
        }

    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        status = resp.status_code
        if status != 200:
            return {
                "url": url,
                "status": _classify_provider_status(status),
                "platform": "股吧",
                "claims": [],
                "error": f"http_{status}",
                "post_count": 0,
            }
        posts = EastmoneyParser().parse_post_list(resp.text, stock_code)
        return _build_eastmoney_guba_provider_record(stock_name, stock_code, url, posts)
    except Exception as exc:
        return {
            "url": url,
            "status": "error",
            "platform": "股吧",
            "claims": [],
            "error": str(exc),
            "post_count": 0,
        }


def _read_urls_sequentially(
    urls: Sequence[str],
    stock_name: str,
    stock_code: str,
) -> List[Dict[str, Any]]:
    """Read explicit URLs sequentially within global time budget."""
    providers: List[Dict[str, Any]] = []
    budget_start = time.monotonic()

    for url in urls:
        elapsed = time.monotonic() - budget_start
        if elapsed >= GLOBAL_BUDGET_SECONDS:
            providers.append({
                "url": url,
                "status": "error",
                "platform": _infer_platform(url),
                "claims": [],
                "error": "global_budget_exceeded",
            })
            continue

        remaining = max(1.0, GLOBAL_BUDGET_SECONDS - elapsed)
        timeout = min(PER_CALL_TIMEOUT_SECONDS, remaining)
        record = _fetch_url(url, timeout=timeout, stock_name=stock_name, stock_code=stock_code)

        # Re-run claim extraction with stock context if text is present.
        if record.get("status") == "ok" and not record.get("claims"):
            # build_provider_record already extracted claims; no-op.
            pass

        providers.append(record)

    return providers


def run_smoke(
    stock_name: str,
    stock_code: str = "300777",
    base_dir: str = None,
    output_dir: str = None,
    urls: Sequence[str] = None,
    eastmoney_guba: bool = False,
    date_str: str = None,
    write: bool = False,
    overwrite: bool = False,
    write_audit: bool = False,
    max_claims: int = DEFAULT_MAX_CLAIMS,
) -> Dict[str, Any]:
    """Run fresh social claim smoke and optionally write a note."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    if base_dir is None:
        base_dir = str(_repo_root() / "knowledge")
    if output_dir is None:
        output_dir = str(_repo_root() / "reports")

    urls = list(urls or [])

    providers: List[Dict[str, Any]] = []
    if eastmoney_guba:
        providers.append(_fetch_eastmoney_guba_list(stock_code=stock_code, stock_name=stock_name))

    if urls:
        providers.extend(_read_urls_sequentially(urls, stock_name, stock_code))

    # Enforce caps per provider by truncating claim lists.
    for provider in providers:
        claims = provider.get("claims", [])
        if isinstance(claims, list) and len(claims) > DEFAULT_MAX_CLAIMS:
            provider["claims"] = claims[:DEFAULT_MAX_CLAIMS]

    claims = extract_claims_from_provider_records(providers, stock_name, stock_code, max_claims=max_claims)

    note_result = write_fresh_social_claim_note(
        stock_name=stock_name,
        stock_code=stock_code,
        claims=claims,
        base_dir=Path(base_dir),
        date_str=date_str,
        dry_run=not write,
        overwrite=overwrite,
    )

    summary = {
        "stock_name": stock_name,
        "stock_code": stock_code,
        "status": note_result["status"],
        "claim_count": note_result["claim_count"],
        "path": note_result["path"],
        "providers": [
            {
                "url": p.get("url", ""),
                "status": p.get("status", ""),
                "platform": p.get("platform", ""),
                "claim_count": len(p.get("claims", [])) if isinstance(p.get("claims"), list) else 0,
                "error": p.get("error", ""),
                "post_count": p.get("post_count", 0),
            }
            for p in providers
        ],
        "write": write,
        "overwrite": overwrite,
        "write_audit": write_audit,
        "eastmoney_guba": eastmoney_guba,
        "date_str": date_str,
    }

    if write_audit:
        _write_audit(summary, Path(output_dir), date_str, stock_name)

    return summary


def _write_audit(summary: Dict[str, Any], output_dir: Path, date_str: str, stock_name: str) -> None:
    """Write a compact audit JSON without full page content."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = stock_name.replace("/", "_")
    audit_path = output_dir / f"fresh_social_{safe_name}_{date_str}_audit.json"
    audit = {
        "stock_name": summary["stock_name"],
        "stock_code": summary["stock_code"],
        "date_str": date_str,
        "status": summary["status"],
        "claim_count": summary["claim_count"],
        "path": summary["path"],
        "providers": summary["providers"],
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_summary(summary: Dict[str, Any]) -> None:
    print("=" * 64)
    print(f"Fresh Social Claims: {summary.get('stock_name', '')}")
    print("=" * 64)
    print(f"  status:      {summary.get('status', '')}")
    print(f"  claims:      {summary.get('claim_count', 0)}")
    print(f"  output path: {summary.get('path', '')}")
    print("  providers:")
    for p in summary.get("providers", []):
        print(f"    {p.get('status', ''):12} {p.get('platform', ''):10} {p.get('url', '')}")
        if p.get("error"):
            print(f"      error: {p['error']}")
    print("=" * 64)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="从 explicit 社区 URL 生成低信用 claim note")
    parser.add_argument("--stock", required=True, help="股票名称，如 中简科技")
    parser.add_argument("--code", default="300777", help="股票代码，默认 300777")
    parser.add_argument("--url", action="append", default=[], help="explicit 社区 URL；最多 5 个")
    parser.add_argument("--date", default=None, help="输出 note 日期，默认今天")
    parser.add_argument("--base-dir", default=None, help="knowledge 根目录，默认 ./knowledge")
    parser.add_argument("--output-dir", default=None, help="audit JSON 输出目录，默认 ./reports")
    parser.add_argument("--write", action="store_true", help="实际写入 knowledge；默认 dry-run")
    parser.add_argument("--overwrite", action="store_true", help="覆盖同名 fresh note")
    parser.add_argument("--write-audit", action="store_true", help="写入 audit JSON 到 reports/")
    parser.add_argument("--max-claims", type=int, default=DEFAULT_MAX_CLAIMS)
    parser.add_argument("--eastmoney-guba", action="store_true", help="直接读取东财股吧列表页标题，不抓详情")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args([] if argv is None else argv)
    if len(args.url) > MAX_URLS:
        parser.error(f"最多接受 {MAX_URLS} 个 --url")
    return args


def main(argv=None):
    args = _parse_args(argv)
    summary = run_smoke(
        stock_name=args.stock,
        stock_code=args.code,
        base_dir=args.base_dir,
        output_dir=args.output_dir,
        urls=args.url,
        eastmoney_guba=args.eastmoney_guba,
        date_str=args.date,
        write=args.write,
        overwrite=args.overwrite,
        write_audit=args.write_audit,
        max_claims=args.max_claims,
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    else:
        _print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
