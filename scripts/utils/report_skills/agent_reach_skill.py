"""Agent-Reach fetch skill with connector registry.

Phase 0 implements only RSSConnector and WebConnector.
Other platforms are detection-only or unsupported.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

if __name__.startswith("utils."):
    from ..skill_pipeline import skill, SkillContext
    from ..source_adapter import SynthesisItem, adapt_all
else:
    from skill_pipeline import skill, SkillContext
    from source_adapter import SynthesisItem, adapt_all


logger = logging.getLogger(__name__)

_PER_COMMAND_TIMEOUT = 30
_PER_STOCK_BUDGET = 60
_TOTAL_CAP = 100
_PER_QUERY_CAP = 10


class Connector(ABC):
    """Base class for Agent-Reach platform connectors."""

    platform: str = ""

    @abstractmethod
    def check_deps(self) -> tuple[bool, str]:
        """Return (available, reason). Must not make network calls."""
        ...

    @abstractmethod
    def run(self, query_spec: Dict[str, Any]) -> tuple[List[Dict], List[str]]:
        """Execute the query and return (records, warnings).

        Each record must include _platform set to self.platform.
        Warnings must use `[platform] message` format.
        """
        ...


class RSSConnector(Connector):
    """Read and filter RSS feeds via feedparser."""

    platform = "rss"

    def check_deps(self) -> tuple[bool, str]:
        try:
            import feedparser
            _ = feedparser  # silence unused warning
            return True, ""
        except ImportError:
            return False, "feedparser not installed"

    def run(self, query_spec: Dict[str, Any]) -> tuple[List[Dict], List[str]]:
        records: List[Dict] = []
        warnings: List[str] = []

        feeds = query_spec.get("rss_feeds", [])
        limit = query_spec.get("rss_limit", 5)
        filter_terms = query_spec.get("rss_filter_terms", [])

        if not filter_terms:
            warnings.append("[rss] no filter terms, skipping to avoid noise")
            return records, warnings

        if not feeds:
            warnings.append("[rss] no feeds provided")
            return records, warnings

        try:
            import feedparser
        except ImportError as e:
            warnings.append(f"[rss] unavailable: {e}")
            return records, warnings

        for url in feeds:
            try:
                parsed = feedparser.parse(url)
                for entry in parsed.entries:
                    text_parts = [
                        entry.get("title", ""),
                        entry.get("summary", ""),
                        entry.get("description", ""),
                    ]
                    text = " ".join(p for p in text_parts if p)
                    if not any(term.lower() in text.lower() for term in filter_terms):
                        continue

                    record = {
                        "_platform": "rss",
                        "title": entry.get("title", ""),
                        "content": entry.get("summary", "") or entry.get("description", ""),
                        "url": entry.get("link", ""),
                        "author": entry.get("author", ""),
                        "publish_time": entry.get("published", ""),
                        "source_feed": url,
                        "tags": [],
                    }
                    records.append(record)
                    if len(records) >= limit:
                        break
            except Exception as e:
                warnings.append(f"[rss] parse/runtime error for {url}: {e}")

            if len(records) >= limit:
                break

        return records, warnings


class WebConnector(Connector):
    """Read known web URLs via Jina Reader."""

    platform = "web"

    def check_deps(self) -> tuple[bool, str]:
        try:
            import urllib.request
            _ = urllib.request  # silence unused warning
            return True, ""
        except ImportError:
            return False, "urllib.request not available"

    def run(self, query_spec: Dict[str, Any]) -> tuple[List[Dict], List[str]]:
        records: List[Dict] = []
        warnings: List[str] = []

        urls = query_spec.get("urls", [])
        timeout = query_spec.get("timeout", 15)
        official_domains = query_spec.get("official_domains", [])

        if not urls:
            warnings.append("[web] no URLs provided")
            return records, warnings

        def _is_official(url: str) -> bool:
            from urllib.parse import urlparse
            try:
                hostname = urlparse(url).hostname or ""
            except Exception:
                return False
            hostname = hostname.lower().lstrip("www.")
            for domain in official_domains:
                domain = domain.lower().strip().lstrip("www.")
                if not domain:
                    continue
                # exact match or subdomain match
                if hostname == domain or hostname.endswith("." + domain):
                    return True
            return False

        for url in urls:
            try:
                import urllib.request
                jina_url = f"https://r.jina.ai/{url}"
                req = urllib.request.Request(
                    jina_url,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    content = resp.read().decode("utf-8", errors="replace")

                if not content or not content.strip():
                    warnings.append(f"[web] empty content for {url}")
                    continue

                # Jina Reader returns title on first line if present
                lines = content.strip().splitlines()
                title = lines[0] if lines else ""
                body = "\n".join(lines[1:]) if len(lines) > 1 else content

                record = {
                    "_platform": "web",
                    "title": title,
                    "content": body,
                    "url": url,
                    "author": "",
                    "publish_time": "",
                    "user_provided_url": True,
                    "query_type": "web_read",
                    "official_seed_url": False,
                }
                if _is_official(url):
                    record["official_seed_url"] = True
                    record["source_type"] = "official"
                records.append(record)
            except Exception as e:
                warnings.append(f"[web] failed to read {url}: {e}")

        return records, warnings


class YouTubeConnector(Connector):
    """Detection-only connector for YouTube."""

    platform = "youtube"

    def check_deps(self) -> tuple[bool, str]:
        import shutil

        yt_dlp = shutil.which("yt-dlp") is not None
        node = shutil.which("node") is not None
        deno = shutil.which("deno") is not None

        if not yt_dlp:
            return False, "yt-dlp not found"
        if not (node or deno):
            return False, "no JS runtime (node or deno) found"
        return True, ""

    def run(self, query_spec: Dict[str, Any]) -> tuple[List[Dict], List[str]]:
        available, reason = self.check_deps()
        if not available:
            return [], [f"[youtube] unavailable: {reason}"]
        return [], ["[youtube] detection-only in Phase 0, no records"]


class ExaSearchConnector(Connector):
    """Detection-only connector for Exa semantic search."""

    platform = "exa_search"

    def check_deps(self) -> tuple[bool, str]:
        import shutil

        if shutil.which("mcporter") is None:
            return False, "mcporter not found"
        return True, ""

    def run(self, query_spec: Dict[str, Any]) -> tuple[List[Dict], List[str]]:
        available, reason = self.check_deps()
        if not available:
            return [], [f"[exa_search] unavailable: {reason}"]
        return [], ["[exa_search] detection-only in Phase 0, no records"]


class WechatConnector(Connector):
    """Detection-only connector for WeChat (shares Exa dependency)."""

    platform = "wechat"

    def check_deps(self) -> tuple[bool, str]:
        return ExaSearchConnector().check_deps()

    def run(self, query_spec: Dict[str, Any]) -> tuple[List[Dict], List[str]]:
        available, reason = self.check_deps()
        if not available:
            return [], [f"[wechat] unavailable: {reason}"]
        return [], ["[wechat] detection-only in Phase 0, no records"]


# Registry of fully-implemented Phase 0 connectors.
CONNECTOR_REGISTRY: Dict[str, Connector] = {
    "rss": RSSConnector(),
    "web": WebConnector(),
}

# Detection-only connectors (not registered by default).
_DETECTION_CONNECTORS: Dict[str, Connector] = {
    "youtube": YouTubeConnector(),
    "exa_search": ExaSearchConnector(),
    "wechat": WechatConnector(),
}


# Platforms that should never be registered.
_UNSUPPORTED_PLATFORMS = {
    "twitter",
    "xueqiu",
    "xiaohongshu",
    "douyin",
    "linkedin",
    "reddit",
    "bilibili",
    "v2ex",
}


def _get_connector(platform: str) -> Optional[Connector]:
    """Resolve a platform name to a connector instance."""
    if platform in CONNECTOR_REGISTRY:
        return CONNECTOR_REGISTRY[platform]
    if platform in _DETECTION_CONNECTORS:
        return _DETECTION_CONNECTORS[platform]
    return None


def _canonical_key(record: Dict) -> str:
    """Dedupe key by URL or (platform, title, publish_time)."""
    url = record.get("url", "")
    if url:
        return url
    platform = record.get("_platform", "")
    title = record.get("title", "")
    publish_time = record.get("publish_time", "")
    return f"{platform}::{title}::{publish_time}"


def _dedupe_records(records: List[Dict]) -> List[Dict]:
    """Deduplicate records by canonical key, preserving order."""
    seen = set()
    result = []
    for r in records:
        key = _canonical_key(r)
        if key and key not in seen:
            seen.add(key)
            result.append(r)
    return result


def _to_agent_reach_synthesis_items(records: List[Dict]) -> List[SynthesisItem]:
    """Normalize raw Agent-Reach records to SynthesisItem via adapt_all."""
    if not records:
        return []
    return adapt_all(agent_reach_items=records)


@skill(name="agent_reach_fetch")
def agent_reach_fetch_skill(ctx: SkillContext) -> SkillContext:
    """Fetch Agent-Reach data via connector registry when enabled.

    Stores results only on ctx, never mutates stock_raw or raw_data.
    """
    agent_reach_enabled = ctx.get("agent_reach_enabled", False)

    if not agent_reach_enabled:
        ctx.set("agent_reach_status", "disabled")
        ctx.set("agent_reach_items", [])
        ctx.set("agent_reach_warnings", [])
        return ctx

    search_queries = ctx.get("search_queries", [])
    if not search_queries:
        ctx.set("agent_reach_status", "empty")
        ctx.set("agent_reach_items", [])
        ctx.set("agent_reach_warnings", ["no queries generated"])
        return ctx

    warnings: List[str] = []
    all_records: List[Dict] = []
    start_time = time.time()

    # Cache dependency checks per skill run.
    _deps_cache: Dict[str, tuple[bool, str]] = {}

    for q_spec in search_queries:
        elapsed = time.time() - start_time
        if elapsed >= _PER_STOCK_BUDGET:
            warnings.append(f"per-stock budget {_PER_STOCK_BUDGET}s exceeded; stopping early")
            break

        platforms = q_spec.get("target_platforms", [])
        if not platforms:
            continue

        for platform in platforms:
            elapsed = time.time() - start_time
            if elapsed >= _PER_STOCK_BUDGET:
                warnings.append(f"per-stock budget {_PER_STOCK_BUDGET}s exceeded; stopping early")
                break

            if platform in _UNSUPPORTED_PLATFORMS:
                warnings.append(f"[{platform}] unsupported platform, skipping")
                continue

            connector = _get_connector(platform)
            if connector is None:
                warnings.append(f"[{platform}] unknown platform, skipping")
                continue

            # Dependency check (cached)
            if platform not in _deps_cache:
                _deps_cache[platform] = connector.check_deps()
            available, reason = _deps_cache[platform]
            if not available:
                warnings.append(f"[{platform}] unavailable: {reason}")
                continue

            # Run connector
            try:
                records, run_warnings = connector.run(q_spec)
            except Exception as e:
                warnings.append(f"[{platform}] runtime error: {e}")
                continue

            warnings.extend(run_warnings)

            # Per-query cap
            if len(records) > _PER_QUERY_CAP:
                warnings.append(f"[{platform}] per-query cap {_PER_QUERY_CAP} applied")
                records = records[:_PER_QUERY_CAP]

            all_records.extend(records)

    # Deduplicate
    all_records = _dedupe_records(all_records)

    # Total cap
    if len(all_records) > _TOTAL_CAP:
        warnings.append(f"total cap {_TOTAL_CAP} applied; truncated from {len(all_records)}")
        all_records = all_records[:_TOTAL_CAP]

    # Normalize to SynthesisItem
    items = _to_agent_reach_synthesis_items(all_records)

    has_timeout = any("timeout" in w or "budget" in w for w in warnings)
    has_runtime_error = any(
        "runtime error" in w or "parse/runtime error" in w or "failed to read" in w
        for w in warnings
    )

    # Determine status
    # Gather which platforms were attempted and available
    attempted_platforms = set()
    available_platforms = set()
    for q_spec in search_queries:
        for p in q_spec.get("target_platforms", []):
            attempted_platforms.add(p)
    for p, (avail, _) in _deps_cache.items():
        if avail:
            available_platforms.add(p)

    if not items:
        # No records returned
        if available_platforms:
            # At least one connector was available
            if has_runtime_error:
                status = "error"
            elif has_timeout:
                status = "timeout"
            else:
                status = "empty"
        else:
            # No connectors were available
            all_unavailable = all(not avail for avail, _ in _deps_cache.values()) if _deps_cache else True
            if all_unavailable:
                status = "missing_binary"
            else:
                status = "empty"
    else:
        # Records exist
        if has_timeout:
            status = "timeout"
        else:
            status = "ok"

    ctx.set("agent_reach_status", status)
    ctx.set("agent_reach_items", items)
    ctx.set("agent_reach_warnings", warnings)
    return ctx
