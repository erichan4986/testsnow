import time
import random
import logging
import re
from typing import List, Dict, Optional
from pathlib import Path
import requests
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class EastmoneyFetcher:
    """东方财富股吧数据抓取器"""

    BASE_URL = "https://guba.eastmoney.com"
    LIST_URL_TEMPLATE = "{base}/list,{gid},99_{page}.html"

    def __init__(self, delay_range: tuple = (3, 5)):
        self.delay_range = delay_range
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })

    def _sleep(self):
        """随机延迟，模拟真人操作"""
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)

    def fetch_stock_posts(
        self,
        gid: str,
        stock_name: str,
        max_posts: int = 15,
        max_pages: int = 3
    ) -> List[Dict]:
        """
        抓取单只股票的帖子列表

        Args:
            gid: 东方财富股吧 GID
            stock_name: 股票名称（用于日志）
            max_posts: 最多抓取帖子数
            max_pages: 最多翻页数

        Returns:
            帖子列表，每个帖子为 dict
        """
        all_posts = []
        logger.info(f"开始抓取 [{stock_name}] (GID: {gid})")

        for page in range(1, max_pages + 1):
            if len(all_posts) >= max_posts:
                break

            url = self.LIST_URL_TEMPLATE.format(
                base=self.BASE_URL,
                gid=gid,
                page=page
            )

            try:
                logger.info(f"  抓取第 {page} 页: {url}")
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                resp.encoding = "utf-8"

                posts = self._parse_list_page(resp.text, gid)
                if not posts:
                    logger.warning(f"  第 {page} 页未解析到帖子，可能已到末页")
                    break

                all_posts.extend(posts)
                logger.info(f"  第 {page} 页解析到 {len(posts)} 条帖子")

            except requests.exceptions.RequestException as e:
                logger.error(f"  请求失败: {e}")
                break
            except Exception as e:
                logger.error(f"  解析异常: {e}")
                break

            if page < max_pages:
                self._sleep()

        # 截断到 max_posts
        result = all_posts[:max_posts]
        logger.info(f"[{stock_name}] 共抓取 {len(result)} 条帖子")
        return result

    def _parse_list_page(self, html: str, gid: str) -> List[Dict]:
        """解析列表页 HTML，提取帖子基本信息"""
        from .parser import EastmoneyParser
        parser = EastmoneyParser()
        return parser.parse_post_list(html, gid)

    def fetch_post_detail(self, post_url: str) -> Optional[str]:
        """
        抓取帖子详情页内容（用于获取正文和评论）

        Returns:
            帖子详情 HTML，失败返回 None
        """
        try:
            if not post_url.startswith("http"):
                post_url = urljoin(self.BASE_URL, post_url)

            resp = self.session.get(post_url, timeout=30)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            logger.error(f"抓取详情页失败 [{post_url}]: {e}")
            return None


class XueqiuFetcher:
    """
    雪球网数据抓取器（增强方案）
    通过 Playwright 连接用户已登录的 Chrome 实例
    """

    BASE_URL = "https://xueqiu.com"

    def __init__(self, cdp_url: str = "http://localhost:9222"):
        self.cdp_url = cdp_url
        self.playwright = None
        self.browser = None
        self._connection_failed = False  # 标记连接是否已永久失败

    def _connect(self):
        """连接到已打开的 Chrome"""
        from playwright.sync_api import sync_playwright

        if self._connection_failed:
            raise RuntimeError("Chrome CDP 连接已标记为失败，跳过重试")

        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_url)
            logger.info("已连接到 Chrome 实例")
        except Exception as e:
            # 连接失败，清理资源并标记为永久失败
            self._connection_failed = True
            if self.playwright:
                try:
                    self.playwright.stop()
                except Exception:
                    pass
                self.playwright = None
            raise RuntimeError(f"无法连接到 Chrome CDP ({self.cdp_url}): {e}")

    def wait_for_login(self, timeout_seconds: int = 300) -> bool:
        """打开雪球首页并轮询检测用户是否已登录。

        Returns:
            True if login detected within timeout.
        """
        if not self.browser:
            self._connect()

        context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
        page = context.new_page()
        try:
            logger.info("[雪球] 打开首页检测登录状态...")
            # 优先用 domcontentloaded 避免 networkidle 因广告追踪请求卡死
            try:
                page.goto("https://xueqiu.com", wait_until="domcontentloaded", timeout=60000)
            except Exception:
                logger.warning("[雪球] domcontentloaded 超时，尝试 load...")
                page.goto("https://xueqiu.com", wait_until="load", timeout=30000)
            time.sleep(3)

            start = time.time()
            while time.time() - start < timeout_seconds:
                try:
                    # 多策略检测登录状态
                    logged_in = page.evaluate(
                        """() => {
                            // 策略1: 检查 cookie 中是否有 access token
                            const cookies = document.cookie;
                            const hasToken = cookies.includes('xq_a_token') || cookies.includes('xq_r_token');
                            if (hasToken) return {ok: true, reason: 'cookie_token'};

                            // 策略2: 检查是否有用户头像
                            const avatar = document.querySelector('img.avatar, .user-avatar, [class*="avatar"]');
                            if (avatar) return {ok: true, reason: 'avatar_found'};

                            // 策略3: 检查是否有"退出"链接/按钮
                            const logout = Array.from(document.querySelectorAll('a, button')).find(
                                el => el.textContent.trim().includes('退出')
                            );
                            if (logout) return {ok: true, reason: 'logout_btn'};

                            // 策略4: 检查是否有用户个人主页链接
                            const userLink = document.querySelector('a[href^="/u/"], a[href^="/setting"]');
                            if (userLink) return {ok: true, reason: 'user_link'};

                            return {ok: false};
                        }"""
                    )
                    if logged_in and logged_in.get("ok"):
                        logger.info(f"[雪球] 登录检测成功 ({logged_in.get('reason')})")
                        return True

                    elapsed = int(time.time() - start)
                    if elapsed > 0 and elapsed % 10 == 0:
                        logger.info(f"[雪球] 等待登录中... ({elapsed}s / {timeout_seconds}s)")
                except Exception as e:
                    logger.warning(f"[雪球] 登录检测轮询异常: {e}")

                time.sleep(3)

            logger.warning(f"[雪球] 登录检测超时 ({timeout_seconds}s)")
            return False
        finally:
            try:
                page.close()
            except Exception:
                pass

    def fetch_stock_posts(
        self,
        stock_code: str,
        stock_name: str,
        max_list_pages: int = 30,
        max_detail_posts: int = 30,
        fetch_comments: bool = True,
    ) -> Dict[str, List[Dict]]:
        """
        抓取单只股票的雪球帖子（讨论区）

        Args:
            stock_code: 雪球股票代码，如 SZ000661
            stock_name: 股票名称（用于日志）
            max_list_pages: 最多浏览列表页数
            max_detail_posts: 对 featured 候选中互动最高的前 N 条进入详情页
            fetch_comments: 是否提取评论

        Returns:
            {"featured": [...], "sentiment": [...]}
        """
        if not self.browser:
            self._connect()

        all_posts: List[Dict] = []
        context = None
        page = None

        # 导入质量评分器
        from .content_quality import classify_post

        try:
            context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
            page = context.new_page()

            # 1. 打开股票页面
            url = f"{self.BASE_URL}/S/{stock_code}"
            logger.info(f"[雪球] 打开 {stock_name} 页面: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(2, 4))
            self._debug_screenshot(page, f"01_stock_page_{stock_code}")

            # 页面验证
            current_url = page.url
            if stock_code not in current_url:
                logger.warning(f"[雪球] 当前 URL 不匹配: {current_url} (期望包含 {stock_code})")
                self._debug_screenshot(page, f"url_mismatch_{stock_code}")

            # 2. 切换到讨论区（多策略）
            tab_ok = self._click_tab(page, "讨论")
            if not tab_ok:
                # 备用策略1: 尝试点击部分匹配 "讨论"
                tab_ok = self._click_tab(page, "讨论")
            if not tab_ok:
                # 备用策略2: 直接导航到 #article hash（雪球 SPA 常用）
                logger.info(f"[雪球] 尝试直接导航到讨论区 hash...")
                try:
                    page.goto(f"{url}#article", wait_until="domcontentloaded", timeout=30000)
                    time.sleep(2)
                    self._debug_screenshot(page, f"02b_hash_navigation_{stock_code}")
                    tab_ok = True
                except Exception as e:
                    logger.warning(f"[雪球] hash 导航失败: {e}")
            if not tab_ok:
                # 备用策略3: 尝试 query param
                logger.info(f"[雪球] 尝试 query param 导航...")
                try:
                    page.goto(f"{url}?tab=article", wait_until="domcontentloaded", timeout=30000)
                    time.sleep(2)
                    self._debug_screenshot(page, f"02c_query_navigation_{stock_code}")
                except Exception as e:
                    logger.warning(f"[雪球] query 导航失败: {e}")

            time.sleep(random.uniform(2, 4))
            self._debug_screenshot(page, f"02_after_discussion_tab_{stock_code}")

            # 3. 点击"热门排序"（保持现有流程）
            self._click_tab(page, "热门排序")
            time.sleep(random.uniform(2, 4))
            self._debug_screenshot(page, f"03_after_hot_sort_{stock_code}")

            # 4. 模拟人类浏览：随机滚动
            self._human_like_scroll(page)
            time.sleep(random.uniform(1, 3))

            # 5. 多页浏览提取帖子
            seen_urls = set()
            for page_num in range(1, max_list_pages + 1):
                posts = self._extract_posts_from_page(page, 100, stock_code)
                new_posts = [p for p in posts if p.get("url") and p["url"] not in seen_urls]
                if not new_posts:
                    logger.info(f"[雪球] [{stock_name}] 第 {page_num} 页无新帖子，停止翻页")
                    break

                all_posts.extend(new_posts)
                for p in new_posts:
                    seen_urls.add(p["url"])

                logger.info(f"[雪球] [{stock_name}] 第 {page_num} 页提取到 {len(new_posts)} 条新帖子，累计 {len(all_posts)} 条")

                if page_num < max_list_pages:
                    has_more = self._go_to_next_page(page)
                    if not has_more:
                        logger.info(f"[雪球] [{stock_name}] 第 {page_num} 页后无更多页，停止")
                        break
                    time.sleep(random.uniform(2, 4))

            logger.info(f"[雪球] [{stock_name}] 列表页共提取 {len(all_posts)} 条帖子")

            # 5. 双轨分流
            featured_candidates = []
            sentiment_posts = []
            for post in all_posts:
                bucket = classify_post(post)
                if bucket == "featured":
                    featured_candidates.append(post)
                else:
                    sentiment_posts.append(post)

            logger.info(
                f"[雪球] [{stock_name}] 分流结果: featured={len(featured_candidates)}, "
                f"sentiment={len(sentiment_posts)}"
            )

            # 6. 对 featured 候选做详情页抓取计划。第一批后若有效内容不足，
            # 只允许一次补录，并始终受 max_detail_posts 总上限约束。
            from .xueqiu_detail_selection import (
                build_detail_plan,
                build_refill_plan,
                evaluate_detail_attempts,
            )

            detail_plan = build_detail_plan(
                featured_candidates,
                {
                    "first_batch_size": min(max_detail_posts, 15),
                    "refill_batch_size": min(max(0, max_detail_posts - min(max_detail_posts, 15)), 8),
                    "max_detail_pages_total": max_detail_posts,
                    "enabled_extension_buckets": ["semiconductor_product", "aerospace"],
                },
            )
            featured_posts = []
            detail_attempts = []

            def attempt_detail_batch(batch, batch_name: str):
                for post in batch:
                    if not post.get("url"):
                        continue
                    attempt = {
                        "url": post.get("url", ""),
                        "title": post.get("title", ""),
                        "author": post.get("author", ""),
                        "publish_time": post.get("time", ""),
                        "topics": post.get("detail_topic_buckets", []),
                        "attempt_batch": batch_name,
                    }
                    try:
                        detail = self._fetch_post_detail(page, post["url"])
                        if detail:
                            post["content"] = detail.get("content", "")
                            post["comments"] = detail.get("comments", [])
                            attempt["content"] = post.get("content", "")
                            # 二次过滤: 详情页正文 < 60 字降级为 sentiment
                            if len(post.get("content", "")) < 60:
                                attempt["drop_reason"] = "too_short"
                                logger.info(
                                    f"[雪球] [{stock_name}] 详情页正文过短，降级: "
                                    f"{post.get('title', '')[:20]}..."
                                )
                                sentiment_posts.append(post)
                            else:
                                attempt["status"] = "usable"
                                featured_posts.append(post)
                                logger.info(
                                    f"[雪球] [{stock_name}] 详情页提取: "
                                    f"{post.get('title', '')[:20]}... "
                                    f"正文 {len(post['content'])} 字"
                                )
                        else:
                            attempt["drop_reason"] = "fetch_failed"
                            sentiment_posts.append(post)
                        detail_attempts.append(attempt)
                        time.sleep(random.uniform(2, 4))
                    except Exception as e:
                        logger.warning(f"[雪球] 详情页提取失败: {e}")
                        attempt["drop_reason"] = "fetch_failed"
                        detail_attempts.append(attempt)
                        sentiment_posts.append(post)

            attempt_detail_batch(detail_plan["first_batch"], "first")
            evaluation = evaluate_detail_attempts(
                detail_attempts,
                {
                    "populated_non_sentiment_candidate_buckets": detail_plan["audit"].get("populated_topic_buckets", []),
                    "max_detail_pages_total": max_detail_posts,
                },
            )
            refill_plan = build_refill_plan(
                detail_plan["candidates"],
                detail_attempts,
                evaluation,
                {
                    "refill_batch_size": min(max(0, max_detail_posts - len(detail_attempts)), 8),
                    "max_detail_pages_total": max_detail_posts,
                },
            )
            if refill_plan.get("should_refill"):
                logger.info(
                    f"[雪球] [{stock_name}] 详情页有效内容不足，补录 "
                    f"{len(refill_plan.get('refill_batch', []))} 条"
                )
                attempt_detail_batch(refill_plan.get("refill_batch", []), "refill")

            # 剩余未进详情页的 featured 候选降级到 sentiment
            attempted_urls = {attempt.get("url") for attempt in detail_attempts}
            for post in detail_plan["candidates"]:
                if post.get("url") not in attempted_urls:
                    sentiment_posts.append(post)

            page.close()

            return {
                "featured": featured_posts,
                "sentiment": sentiment_posts,
                "_selection_audit": {
                    "first_batch_urls": [post.get("url") for post in detail_plan["first_batch"]],
                    "refill_batch_urls": [post.get("url") for post in refill_plan.get("refill_batch", [])],
                    "attempted_urls": list(attempted_urls),
                    "drop_reasons": evaluation.get("drop_reasons", {}),
                    "refill_reasons": refill_plan.get("audit", {}).get("refill_reasons", []),
                    "topic_buckets": detail_plan["audit"].get("populated_topic_buckets", []),
                    "total_detail_pages": len(detail_attempts),
                },
            }

        except Exception as e:
            logger.error(f"[雪球] 抓取失败 [{stock_name}]: {e}")
            if page:
                try:
                    page.close()
                except Exception:
                    pass
            return {"featured": [], "sentiment": []}

    def _debug_screenshot(self, page, name: str):
        """保存调试截图到 data/raw/debug/"""
        try:
            debug_dir = Path(__file__).parent.parent.parent / "data" / "raw" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            path = debug_dir / f"{name}_{int(time.time())}.png"
            page.screenshot(path=str(path), full_page=True)
            logger.info(f"[雪球] 调试截图已保存: {path}")
        except Exception as e:
            logger.warning(f"[雪球] 截图失败: {e}")

    def _click_tab(self, page, tab_text: str) -> bool:
        """点击页面上的 tab（支持 a/button/span/div 等多种元素）"""
        try:
            # 策略1: Playwright locator 精确匹配（对 React/Vue 更友好）
            for selector in [
                f"role=tab[name='{tab_text}']",
                f"text='{tab_text}'",
            ]:
                try:
                    loc = page.locator(selector).first
                    if loc.count() > 0 and loc.is_visible(timeout=2000):
                        loc.click()
                        logger.info(f"[雪球] 已点击 tab: {tab_text} (via {selector})")
                        return True
                except Exception:
                    continue

            # 策略2: JavaScript 精确匹配
            result = page.evaluate(
                """(tabText) => {
                    const allEls = Array.from(document.querySelectorAll('a, button, span, div, li, [role="tab"]'));
                    // 精确匹配
                    let target = allEls.find(el => el.textContent.trim() === tabText);
                    // 部分匹配（tab 可能包含图标字符，或 tabText 比实际文本长）
                    if (!target) {
                        target = allEls.find(el => {
                            const txt = el.textContent.trim();
                            return txt.includes(tabText) || tabText.includes(txt);
                        });
                    }
                    // 属性匹配（aria-label, title）
                    if (!target) {
                        target = allEls.find(el =>
                            (el.getAttribute('aria-label') || '').includes(tabText) ||
                            (el.getAttribute('title') || '').includes(tabText)
                        );
                    }
                    if (target) {
                        target.click();
                        return {found: true, tag: target.tagName, text: target.textContent.trim().substring(0, 50)};
                    }
                    return {found: false};
                }""",
                tab_text
            )
            if result and result.get("found"):
                logger.info(f"[雪球] 已点击 tab: {tab_text} (JS, tag={result.get('tag')}, text={result.get('text')})")
                return True
            else:
                # 诊断：收集页面上所有候选 tab 文本
                try:
                    tabs_info = page.evaluate(
                        """() => {
                            const tabs = Array.from(document.querySelectorAll('a, button, span, div, li, [role="tab"]'));
                            return tabs
                                .filter(el => el.offsetParent !== null && el.textContent.trim().length > 0)
                                .slice(0, 30)
                                .map(el => ({
                                    tag: el.tagName,
                                    text: el.textContent.trim().substring(0, 40),
                                    className: el.className || '',
                                }));
                        }"""
                    )
                    logger.warning(f"[雪球] 未找到 tab: {tab_text}")
                    logger.warning(f"[雪球] 页面上可见的候选元素: {tabs_info}")
                    self._debug_screenshot(page, f"tab_not_found_{tab_text}")
                except Exception:
                    pass
                return False
        except Exception as e:
            logger.warning(f"[雪球] 点击 tab 失败 [{tab_text}]: {e}")
            return False

    def _human_like_scroll(self, page):
        """模拟人类随机滚动页面"""
        try:
            for _ in range(random.randint(2, 5)):
                scroll_px = random.randint(200, 800)
                page.evaluate(f"window.scrollBy(0, {scroll_px})")
                time.sleep(random.uniform(0.5, 1.5))
        except Exception:
            pass

    def _extract_interaction(self, text: str) -> tuple[int, int, int]:
        """
        从 article 文本中提取互动数据（赞/评论/转发）。

        雪球列表页操作栏使用 Unicode PUA 图标，正则无法直接匹配中文标签。
        策略：从文本末尾提取数字，排除股票代码和年份，按顺序分配。
        """
        if not text:
            return 0, 0, 0

        # 只看最后 100 个字符（操作栏通常在末尾）
        tail = text[-100:]

        # 排除股票代码模式
        cleaned = tail
        cleaned = re.sub(r'\$\d+\$', '', cleaned)           # $02533$
        cleaned = re.sub(r'\([SHZHK]{2}\d+\)', '', cleaned)  # (SZ000661)
        cleaned = re.sub(r'\d{4}-\d{2}-\d{2}', '', cleaned)  # 日期 2025-05-26

        # 提取所有数字
        all_nums = [int(n) for n in re.findall(r'\d+', cleaned)]

        # 过滤：排除年份和过大的数字（股价、市值等）
        filtered = [n for n in all_nums
                    if n < 10000 and n not in (2024, 2025, 2026, 2027)]

        if not filtered:
            return 0, 0, 0

        # 取最后 1-3 个数字，按雪球常见顺序分配：
        # 从后往前：赞（最后一个）、评论（倒数第二个）、转发（倒数第三个）
        nums = filtered[-3:] if len(filtered) >= 3 else filtered

        like_count = nums[-1] if len(nums) >= 1 else 0
        comment_count = nums[-2] if len(nums) >= 2 else 0
        repost_count = nums[-3] if len(nums) >= 3 else 0

        return like_count, comment_count, repost_count

    def _is_valid_post_url(self, url: str, stock_code: str) -> bool:
        """验证帖子 URL 是否属于目标股票讨论区"""
        if not url:
            return False
        # 排除非帖子链接
        invalid_patterns = [
            "/qa", "/fund", "/etf", "/bond", "/of",
            "xueqiu.com/S/",  # 股票主页
            "xueqiu.com/hq",  # 行情页
            "xueqiu.com/today",  # 今日话题
        ]
        url_lower = url.lower()
        for pat in invalid_patterns:
            if pat in url_lower:
                return False
        # 有效模式：用户文章页
        valid_patterns = [
            "/",
        ]
        # 只要包含 xueqiu.com 且不是上面排除的，就接受
        return "xueqiu.com" in url_lower or url.startswith("/")

    def _go_to_next_page(self, page) -> bool:
        """
        点击分页导航中的"下一页"按钮。

        雪球讨论区使用传统数字分页：上一页 1 2 3 4 5 ... 100 下一页
        点击 .pagination__next 进入下一页。

        Args:
            page: Playwright page

        Returns:
            True if navigated to next page, False if no more pages.
        """
        try:
            # 先滚动到底部，确保分页器可见
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(random.uniform(1, 2))

            # 策略1: Playwright locator 点击 .pagination__next
            next_btn = page.locator(".pagination__next").first
            if next_btn.count() > 0 and next_btn.is_visible(timeout=3000):
                # 检查是否已禁用（最后一页）
                is_disabled = next_btn.evaluate("el => el.classList.contains('disabled') || el.getAttribute('disabled')")
                if is_disabled:
                    logger.info("[雪球] 已到最后一页")
                    return False
                next_btn.click()
                logger.info("[雪球] 已点击'下一页'")
                time.sleep(random.uniform(3, 5))
                return True

            # 策略2: JS 查找并点击
            clicked = page.evaluate(
                """() => {
                    const next = document.querySelector('.pagination__next');
                    if (!next || next.offsetParent === null) return false;
                    if (next.classList.contains('disabled') || next.getAttribute('disabled')) return false;
                    next.click();
                    return true;
                }"""
            )
            if clicked:
                logger.info("[雪球] 已点击'下一页' (JS)")
                time.sleep(random.uniform(3, 5))
                return True

            logger.info("[雪球] 未找到'下一页'按钮，可能已到末尾")
            return False

        except Exception as e:
            logger.warning(f"[雪球] 翻页失败: {e}")
            return False

    def _extract_posts_from_page(self, page, max_posts: int, stock_code: str) -> List[Dict]:
        """从当前页面提取帖子列表（Playwright Locator API 版本，更易调试）"""
        posts = []
        try:
            articles = page.locator("article").all()
            logger.info(f"[雪球] 找到 {len(articles)} 个 article 元素")
        except Exception as e:
            logger.warning(f"[雪球] 查找 article 失败: {e}")
            return posts

        for i, article in enumerate(articles[:max_posts]):
            try:
                # 1. 提取 URL: 找第一个 href 匹配 /数字/数字 的链接
                links = article.locator("a").all()
                post_url = ""
                for link in links:
                    try:
                        href = link.get_attribute("href") or ""
                        if href and href.startswith("/") and len(href.split("/")) == 3 and href.split("/")[1].isdigit() and href.split("/")[2].isdigit():
                            post_url = href
                            break
                    except Exception:
                        continue
                if not post_url:
                    continue
                full_url = "https://xueqiu.com" + post_url

                # 2. 提取作者
                author = ""
                try:
                    user_link = article.locator('a[href^="/u/"]').first
                    if user_link.count() > 0:
                        author = user_link.inner_text(timeout=1000).strip()
                except Exception:
                    pass
                if not author:
                    try:
                        author = article.locator('a').first.inner_text(timeout=1000).strip()[:20]
                    except Exception:
                        pass

                # 3. 提取时间
                time_str = ""
                try:
                    time_str = article.locator("time").first.inner_text(timeout=1000).strip()
                except Exception:
                    pass

                # 4. 提取内容文本（inner_text）
                content = ""
                try:
                    content = article.inner_text().strip()
                    # 简单清理：把多个空白合并
                    content = " ".join(content.split())
                except Exception:
                    pass

                # 5. 提取互动数据——从 content 末尾提取，更 robust
                like_count, comment_count, repost_count = self._extract_interaction(content)

                posts.append({
                    "title": content[:80] + "..." if len(content) > 80 else content,
                    "content": content,
                    "url": full_url,
                    "author": author,
                    "time": time_str,
                    "like_count": like_count,
                    "comment_count": comment_count,
                    "repost_count": repost_count,
                    "is_repost": False,
                    "source": "xueqiu",
                })
            except Exception as e:
                logger.warning(f"[雪球] 提取第 {i} 条帖子失败: {e}")
                continue

        logger.info(f"[雪球] 成功提取 {len(posts)} 条帖子")
        return posts

    def _fetch_post_detail(self, page, post_url: str) -> Optional[Dict]:
        """抓取帖子详情页，提取正文和评论（使用多选择器 + inner_text）"""
        detail_page = None
        try:
            detail_page = page.context.new_page()

            # 尝试策略1: domcontentloaded
            try:
                detail_page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                logger.warning(f"[雪球] 详情页 domcontentloaded 超时，尝试 networkidle: {post_url}")
                detail_page.goto(post_url, wait_until="networkidle", timeout=60000)

            # 随机延迟模拟阅读
            time.sleep(random.uniform(2, 4))

            # 多选择器尝试提取正文
            selectors = [
                ".article__bd",
                ".article-content",
                "#app .article",
                ".detail-main .content",
                "article",
            ]

            content = ""
            for selector in selectors:
                try:
                    loc = detail_page.locator(selector).first
                    if loc.count() > 0 and loc.is_visible(timeout=3000):
                        text = loc.inner_text(timeout=5000)
                        if text and len(text.strip()) >= 50:
                            content = text.strip()
                            break
                except Exception:
                    continue

            # Fallback: 用 body
            if not content:
                try:
                    body_text = detail_page.locator("body").inner_text(timeout=5000)
                    if body_text:
                        content = body_text.strip()
                except Exception:
                    pass

            # 清理雪球 footer 垃圾内容
            garbage_patterns = [
                "tousu@xueqiu.com", "京ICP备", "违法和不良信息举报",
                "举报电话", "友情链接", "关于我们", "加入我们",
                "免责声明", "雪球邀你参加", "风险提示",
            ]
            for pat in garbage_patterns:
                content = content.replace(pat, "")

            # 提取评论（简化版）
            comments = []
            try:
                cmt_result = detail_page.evaluate(
                    """() => {
                        const comments = [];
                        const allDivs = document.querySelectorAll('div');
                        for (const div of allDivs) {
                            const authorLink = div.querySelector('a[href^="/"]');
                            const para = div.querySelector('p');
                            if (authorLink && para) {
                                const author = authorLink.textContent.trim();
                                const text = para.textContent.trim();
                                if (author && text && author.length < 20 && text.length > 5) {
                                    const divText = div.textContent;
                                    const likeMatch = divText.match(/赞\\s*(\\d+)/);
                                    comments.push({
                                        author: author,
                                        content: text,
                                        like_count: parseInt(likeMatch ? likeMatch[1] : '0'),
                                    });
                                }
                            }
                        }
                        // 去重
                        const seen = new Set();
                        return comments.filter(c => {
                            const key = c.author + ':' + c.content.substring(0, 50);
                            if (seen.has(key)) return false;
                            seen.add(key);
                            return true;
                        }).slice(0, 10);
                    }"""
                )
                if cmt_result:
                    comments = cmt_result
            except Exception:
                pass

            detail_page.close()
            return {"content": content, "comments": comments}

        except Exception as e:
            logger.error(f"[雪球] 详情页抓取失败 [{post_url}]: {e}")
            if detail_page:
                try:
                    detail_page.close()
                except Exception:
                    pass
            return None

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()


def fetch_all_stocks(
    stocks_config: List[Dict],
    use_xueqiu: bool = False,
    xueqiu_cdp_url: str = "http://localhost:9222"
) -> Dict[str, List[Dict]]:
    """
    抓取所有配置股票的数据

    Args:
        stocks_config: config/stocks.json 中的股票列表
        use_xueqiu: 是否优先尝试雪球（需要 Chrome 已登录）
        xueqiu_cdp_url: Chrome DevTools Protocol 地址

    Returns:
        {股票名称: 帖子列表}
    """
    results = {}

    # 雪球抓取器（如需）
    xq_fetcher = None
    if use_xueqiu:
        try:
            xq_fetcher = XueqiuFetcher(cdp_url=xueqiu_cdp_url)
        except Exception as e:
            logger.warning(f"雪球抓取器初始化失败，将使用东方财富: {e}")

    # 东方财富抓取器（保底）
    em_fetcher = EastmoneyFetcher()

    for stock in stocks_config:
        name = stock["name"]
        gid = stock.get("gid")
        xq_code = stock.get("xueqiu_code")

        posts = []

        # 先尝试雪球
        if xq_fetcher and xq_code:
            try:
                result = xq_fetcher.fetch_stock_posts(xq_code, name)
                # 合并 featured 和 sentiment 为统一列表，保留分类标记
                for p in result.get("featured", []):
                    p["_track"] = "featured"
                    posts.append(p)
                for p in result.get("sentiment", []):
                    p["_track"] = "sentiment"
                    posts.append(p)
            except Exception as e:
                logger.warning(f"[雪球] 抓取 [{name}] 失败，将回退到东方财富: {e}")
                posts = []

        # 雪球失败或无数据，回退到东方财富
        if not posts and gid:
            posts = em_fetcher.fetch_stock_posts(gid, name, max_posts=15)
            # 东财数据无分类，全部标记为 sentiment（不进入 Vault）
            for p in posts:
                p["_track"] = "sentiment"

        results[name] = posts

        # 股票间间隔
        if stock != stocks_config[-1]:
            time.sleep(random.uniform(3, 5))

    if xq_fetcher:
        xq_fetcher.close()

    return results
