"""
微信公众号文章采集器（搜狗微信搜索版）

作为 wechat-article-exporter 的轻量替代方案：
- 无需微信账号登录
- 通过搜狗微信搜索获取公众号文章列表
- 使用 Playwright 模拟浏览器行为，降低被封风险
- 适合低频、小批量的文章采集

用法:
    fetcher = WechatSogouFetcher()
    articles = fetcher.search_articles("圣邦股份", max_pages=2)
    # articles -> [{title, url, summary, source_account, publish_time}]
"""

import logging
import random
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)


class WechatSogouFetcher:
    """
    基于搜狗微信搜索的公众号文章采集器
    """

    SOGOU_WECHAT_URL = "https://weixin.sogou.com/weixin"

    def __init__(self, headless: bool = True, slow_mo: int = 100):
        self.headless = headless
        self.slow_mo = slow_mo
        self._browser = None
        self._context = None
        self._page = None

    def _init_browser(self):
        """Lazy initialization of Playwright browser"""
        if self._browser is not None:
            return

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("playwright 未安装，请运行: pip install playwright && playwright install chromium")
            raise

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
        )
        self._context = self._browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        self._page = self._context.new_page()

    def search_articles(self, keyword: str, max_pages: int = 3) -> List[Dict]:
        """
        搜索关键词对应的微信公众号文章

        Args:
            keyword: 搜索关键词，如 "圣邦股份"、"模拟芯片"
            max_pages: 最大翻页数（每页约10条）

        Returns:
            List of dicts with keys: title, url, summary, source_account, publish_time
        """
        self._init_browser()

        articles = []
        encoded_kw = quote(keyword)

        for page_num in range(1, max_pages + 1):
            url = f"{self.SOGOU_WECHAT_URL}?type=2&query={encoded_kw}&page={page_num}"
            logger.info(f"[搜狗微信] 搜索 '{keyword}' 第 {page_num} 页...")

            try:
                self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(2, 4))

                # Check for anti-bot page
                if "antispider" in self._page.url or self._page.locator(".p2").count() > 0:
                    logger.warning("[搜狗微信] 触发反爬验证，请手动在浏览器中完成验证")
                    if not self.headless:
                        input("按回车继续...")
                    else:
                        logger.error("headless 模式下无法完成验证，建议设置 headless=False")
                        break

                # Parse article list
                page_articles = self._parse_list_page()
                if not page_articles:
                    logger.info(f"[搜狗微信] 第 {page_num} 页无结果，结束搜索")
                    break

                articles.extend(page_articles)
                logger.info(f"[搜狗微信] 第 {page_num} 页获取 {len(page_articles)} 条")

                # Random delay between pages
                if page_num < max_pages:
                    time.sleep(random.uniform(3, 6))

            except Exception as e:
                logger.error(f"[搜狗微信] 第 {page_num} 页获取失败: {e}")
                break

        logger.info(f"[搜狗微信] 总计获取 {len(articles)} 条文章")
        return articles

    def _parse_list_page(self) -> List[Dict]:
        """Parse article list from current page"""
        articles = []

        # 搜狗微信搜索结果页的文章列表选择器
        # 结构可能变化，需要定期检查
        selectors = [
            "ul.news-list li",
            ".news-list li",
        ]

        items = []
        for sel in selectors:
            items = self._page.locator(sel).all()
            if items:
                break

        for item in items:
            try:
                # Title
                title_el = item.locator("h3 a").first
                title = title_el.text_content().strip() if title_el.count() > 0 else ""

                # URL (搜狗跳转链接，需要解析真实微信URL)
                href = title_el.get_attribute("href") if title_el.count() > 0 else ""

                # Summary
                summary_el = item.locator("p").first
                summary = summary_el.text_content().strip() if summary_el.count() > 0 else ""

                # Source account
                account_el = item.locator("a.account").first
                account = account_el.text_content().strip() if account_el.count() > 0 else ""

                # Publish time
                time_el = item.locator("span.s2, .time").first
                pub_time = time_el.text_content().strip() if time_el.count() > 0 else ""

                if title and href:
                    articles.append({
                        "title": title,
                        "url": href,
                        "summary": summary,
                        "source_account": account,
                        "publish_time": pub_time,
                        "fetched_at": datetime.now().isoformat(),
                        "source": "wechat_sogou",
                    })
            except Exception as e:
                logger.debug(f"Parse item failed: {e}")
                continue

        return articles

    def get_article_content(self, sogou_url: str) -> Optional[str]:
        """
        通过搜狗跳转链接获取文章完整正文
        注意：搜狗链接会 302 跳转到微信原文，需要处理
        """
        self._init_browser()

        try:
            self._page.goto(sogou_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(2, 4))

            # Wait for redirect to wechat page
            if "mp.weixin.qq.com" in self._page.url:
                # Parse WeChat article content
                content_el = self._page.locator("#js_content").first
                if content_el.count() > 0:
                    return content_el.text_content().strip()

            logger.warning(f"[搜狗微信] 未能获取文章内容: {self._page.url}")
            return None

        except Exception as e:
            logger.error(f"[搜狗微信] 获取文章内容失败: {e}")
            return None

    def close(self):
        """Close browser and release resources"""
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if hasattr(self, "_pw"):
            self._pw.stop()
        self._browser = None
        self._context = None
        self._page = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(level=logging.INFO)

    with WechatSogouFetcher(headless=False) as fetcher:
        articles = fetcher.search_articles("圣邦股份", max_pages=2)
        print(f"\n找到 {len(articles)} 篇文章:")
        for a in articles[:5]:
            print(f"- [{a['source_account']}] {a['title'][:40]}...")
            print(f"  {a['url']}")
