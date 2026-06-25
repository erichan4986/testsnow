"""Client for wechat-article-exporter public/private API.

The client only wraps explicit API calls.  It does not search or scrape WeChat
directly and never persists the auth key.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


DEFAULT_WECHAT_EXPORTER_BASE_URL = "https://down.mptext.top"


class WechatExporterError(RuntimeError):
    """Raised when the exporter API cannot return a usable article."""


@dataclass
class DownloadedWechatArticle:
    url: str
    fmt: str
    content: str
    title: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw: Any = None


class WechatExporterClient:
    """Small wrapper around the exporter REST API."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_WECHAT_EXPORTER_BASE_URL,
        auth_key: str = "",
        opener: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.base_url = (base_url or DEFAULT_WECHAT_EXPORTER_BASE_URL).rstrip("/")
        self.auth_key = (auth_key or "").strip()
        self.opener = opener or urllib.request.urlopen

    def download_article(self, url: str, *, fmt: str = "markdown", timeout: int = 20) -> DownloadedWechatArticle:
        """Download one explicit mp.weixin.qq.com article through the exporter."""
        if not self.auth_key:
            raise WechatExporterError("WECHAT_EXPORTER_AUTH_KEY is required for article download")
        article_url = (url or "").strip()
        if not article_url:
            raise WechatExporterError("article url is required")

        endpoint = self._build_url(
            "/api/public/v1/download",
            {"url": article_url, "format": fmt},
        )
        request = urllib.request.Request(
            endpoint,
            headers={
                "X-Auth-Key": self.auth_key,
                "User-Agent": "testsnow-wechat-export-batch/1.0",
            },
        )
        try:
            with self.opener(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                content_type = ""
                try:
                    content_type = response.headers.get("Content-Type", "")
                except Exception:
                    content_type = ""
        except urllib.error.HTTPError as exc:
            raise WechatExporterError(f"wechat exporter HTTP {exc.code}") from exc
        except Exception as exc:
            raise WechatExporterError(self._sanitize_error(str(exc))) from exc

        return self._parse_download_response(
            body,
            article_url=article_url,
            fmt=fmt,
            content_type=content_type,
        )

    def search_accounts(self, keyword: str, *, timeout: int = 20) -> Any:
        """Search accounts by keyword. Kept separate from batch download."""
        return self._get_json("/api/public/v1/account", {"keyword": keyword}, timeout=timeout)

    def list_articles(self, fakeid: str, *, keyword: str = "", page: int = 1, timeout: int = 20) -> Any:
        """List articles for a known account fakeid."""
        params: Dict[str, Any] = {"fakeid": fakeid, "page": page}
        if keyword:
            params["keyword"] = keyword
        return self._get_json("/api/public/v1/article", params, timeout=timeout)

    def _get_json(self, path: str, params: Dict[str, Any], *, timeout: int = 20) -> Any:
        if not self.auth_key:
            raise WechatExporterError("WECHAT_EXPORTER_AUTH_KEY is required for exporter API calls")
        endpoint = self._build_url(path, params)
        request = urllib.request.Request(
            endpoint,
            headers={
                "X-Auth-Key": self.auth_key,
                "User-Agent": "testsnow-wechat-export-batch/1.0",
            },
        )
        try:
            with self.opener(request, timeout=timeout) as response:
                text = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise WechatExporterError(f"wechat exporter HTTP {exc.code}") from exc
        except Exception as exc:
            raise WechatExporterError(self._sanitize_error(str(exc))) from exc
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise WechatExporterError("wechat exporter returned non-JSON response") from exc

    def _build_url(self, path: str, params: Dict[str, Any]) -> str:
        query = urllib.parse.urlencode(params)
        return f"{self.base_url}{path}?{query}"

    def _parse_download_response(
        self,
        body: str,
        *,
        article_url: str,
        fmt: str,
        content_type: str = "",
    ) -> DownloadedWechatArticle:
        raw: Any = body
        metadata: Dict[str, Any] = {}
        content = body
        title = ""

        is_json = "json" in (content_type or "").lower() or body.lstrip().startswith(("{", "["))
        if is_json:
            try:
                raw = json.loads(body)
            except json.JSONDecodeError:
                raw = body
            if isinstance(raw, dict):
                if raw.get("code") not in (None, 0, "0", 200, "200"):
                    message = raw.get("message") or raw.get("msg") or "wechat exporter API error"
                    raise WechatExporterError(self._sanitize_error(str(message)))
                data = raw.get("data", raw)
                if isinstance(data, dict):
                    metadata = dict(data)
                    title = str(data.get("title") or data.get("name") or "")
                    content = _first_text(
                        data,
                        ("markdown", "content", "text", "html", "article_content", "articleContent"),
                    )
                elif isinstance(data, str):
                    content = data
                if not content and isinstance(raw, dict):
                    content = _first_text(raw, ("markdown", "content", "text", "html"))
                    metadata = dict(raw)

        if not content.strip():
            raise WechatExporterError("wechat exporter returned empty article content")

        return DownloadedWechatArticle(
            url=article_url,
            fmt=fmt,
            content=content,
            title=title,
            metadata=metadata,
            raw=raw,
        )

    def _sanitize_error(self, message: str) -> str:
        safe = message or "wechat exporter request failed"
        if self.auth_key:
            safe = safe.replace(self.auth_key, "[redacted]")
        return safe


def _first_text(data: Dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""
