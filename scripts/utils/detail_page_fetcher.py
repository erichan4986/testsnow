"""
雪球帖子详情页抓取器

使用有头 Playwright 浏览器抓取雪球帖子详情页完整正文，
输出写入 Obsidian Vault（knowledge/10-Stocks/）。
"""

import json
import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DetailPageFetcher:
    """
    雪球帖子详情页抓取器

    Usage:
        fetcher = DetailPageFetcher(
            vault_base=Path("knowledge/10-Stocks"),
            user_data_dir=Path.home() / "Library/Application Support/Google/Chrome",
        )
        success_urls = fetcher.fetch_posts("黑芝麻智能", posts_list)
    """

    def __init__(
        self,
        vault_base: Path,
        user_data_dir: Optional[Path] = None,
        headless: bool = False,
        delay_range: Tuple[int, int] = (3, 8),
        request_interval: int = 5,
    ):
        """
        Args:
            vault_base: Obsidian Vault 根目录
            user_data_dir: Chrome profile 目录
            headless: 是否无头模式（默认 False）
            delay_range: 页面加载后随机停留秒数
            request_interval: 请求最小间隔秒数
        """
        self.vault_base = Path(vault_base)
        self.user_data_dir = Path(user_data_dir) if user_data_dir else None
        self.headless = headless
        self.delay_range = delay_range
        self.request_interval = request_interval
        self._context = None
        self._playwright = None

    def _extract_post_id(self, url: str) -> str:
        """Extract post ID from Xueqiu URL (last path segment)."""
        # Remove query parameters and trailing slash
        clean_url = url.split("?")[0].rstrip("/")
        # Last path segment is the post ID
        return clean_url.split("/")[-1]

    def _write_to_vault(
        self,
        stock_name: str,
        post_id: str,
        metadata: Dict,
        full_content: str,
    ) -> Path:
        """Write post content to Obsidian Vault as a Markdown file with YAML frontmatter."""
        stock_dir = self.vault_base / stock_name / "posts"
        stock_dir.mkdir(parents=True, exist_ok=True)

        output_path = stock_dir / f"{post_id}.md"

        frontmatter = {
            "source_url": metadata.get("source_url", ""),
            "stock_name": stock_name,
            "author": metadata.get("author", ""),
            "title": metadata.get("title", ""),
            "date": metadata.get("date", ""),
            "interactions": {
                "likes": metadata.get("likes", 0),
                "comments": metadata.get("comments", 0),
                "reposts": metadata.get("reposts", 0),
            },
            "collected_at": datetime.now().isoformat(),
        }

        yaml_lines = ["---"]
        for key, value in frontmatter.items():
            if isinstance(value, dict):
                yaml_lines.append(f"{key}:")
                for sub_key, sub_value in value.items():
                    yaml_lines.append(f"  {sub_key}: {sub_value}")
            else:
                yaml_lines.append(f"{key}: {value}")
        yaml_lines.append("---")

        title = metadata.get("title", "Untitled")
        md_content = "\n".join(yaml_lines) + f"\n\n# {title}\n\n{full_content}\n"

        output_path.write_text(md_content, encoding="utf-8")
        logger.info("Wrote post %s to %s", post_id, output_path)
        return output_path

    def _init_browser(self):
        """Initialize Playwright browser with anti-detection measures."""
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
        ]

        if self.user_data_dir:
            self._context = self._playwright.chromium.launch_persistent_context(
                str(self.user_data_dir),
                headless=self.headless,
                args=launch_args,
            )
        else:
            browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=launch_args,
            )
            self._context = browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

        # Set viewport and user agent on the default context
        self._context.set_viewport_size({"width": 1366, "height": 768})

        # Add init script to hide automation indicators
        self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            if (window.__playwright) {
                delete window.__playwright;
            }
        """)

        logger.info("Browser initialized (headless=%s)", self.headless)

    def _extract_content(self, url: str) -> Optional[str]:
        """Fetch and extract full post content from a Xueqiu detail page."""
        if self._context is None:
            raise RuntimeError("Browser not initialized. Call _init_browser() first.")

        page = self._context.new_page()
        try:
            logger.info("Navigating to %s", url)
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Random delay to mimic human reading
            delay = random.randint(self.delay_range[0], self.delay_range[1])
            logger.debug("Waiting %d seconds", delay)
            time.sleep(delay)

            # Check for login redirect or login dialog
            current_url = page.url
            if "login" in current_url.lower() or "signin" in current_url.lower():
                logger.error("Redirected to login page: %s", current_url)
                return None

            try:
                if page.locator(".login-dialog").is_visible(timeout=3000):
                    logger.error("Login dialog detected on %s", url)
                    return None
            except Exception:
                pass

            # Random scroll 2-5 times
            scroll_times = random.randint(2, 5)
            for _ in range(scroll_times):
                scroll_y = random.randint(300, 800)
                page.evaluate(f"window.scrollBy(0, {scroll_y})")
                time.sleep(random.uniform(0.5, 1.5))

            # Try content selectors in order of preference
            selectors = [
                ".article__bd",
                ".article-content",
                "#app .article",
                ".detail-main .content",
                "article",
            ]

            content = None
            for selector in selectors:
                element = page.locator(selector).first
                try:
                    element.wait_for(timeout=5000)
                except Exception:
                    continue
                if element.is_visible():
                    text = element.inner_text()
                    if text and len(text.strip()) >= 100:
                        content = text.strip()
                        logger.debug("Content extracted via selector: %s", selector)
                        break

            # Fallback to body inner text if no selector matched or content too short
            if not content:
                logger.warning("No content selector matched or content too short, falling back to body text")
                body_text = page.locator("body").inner_text()
                if body_text:
                    content = body_text.strip()

            if content and len(content) >= 100:
                return content
            else:
                logger.error("Content too short or empty for %s", url)
                return None

        except Exception as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            logger.error("Failed to extract content from %s: %s", url, exc)
            return None
        finally:
            page.close()

    def fetch_posts(self, stock_name: str, posts: List[Dict]) -> List[str]:
        """
        Fetch full content for a list of posts and write them to the vault.

        Args:
            stock_name: Name of the stock (used for directory naming)
            posts: List of post dicts, each expected to have at least:
                - url: str
                - title: str
                - author: str
                - date: str
                - likes: int (optional)
                - comments: int (optional)
                - reposts: int (optional)

        Returns:
            List of URLs successfully fetched and written.
        """
        self._init_browser()
        success_urls: List[str] = []

        try:
            for post in posts:
                url = post.get("url", "")
                if not url:
                    logger.warning("Skipping post without URL: %s", post)
                    continue

                post_id = self._extract_post_id(url)
                output_path = self.vault_base / stock_name / "posts" / f"{post_id}.md"

                if output_path.exists():
                    logger.info("Skipping already fetched post: %s", post_id)
                    success_urls.append(url)
                    continue

                full_content = self._extract_content(url)
                if full_content is None:
                    logger.error("Failed to fetch content for %s", url)
                    continue

                metadata = {
                    "source_url": url,
                    "title": post.get("title", ""),
                    "author": post.get("author", ""),
                    "date": post.get("date", ""),
                    "likes": post.get("likes", 0),
                    "comments": post.get("comments", 0),
                    "reposts": post.get("reposts", 0),
                }

                self._write_to_vault(stock_name, post_id, metadata, full_content)
                success_urls.append(url)

                # Respect request interval between requests
                time.sleep(self.request_interval)
        finally:
            self._close_browser()

        logger.info("Successfully fetched %d / %d posts", len(success_urls), len(posts))
        return success_urls

    def _close_browser(self):
        """Clean up browser and playwright resources."""
        if self._context:
            self._context.close()
            self._context = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        logger.info("Browser closed")
