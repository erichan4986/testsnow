# DetailPageFetcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable DetailPageFetcher component that uses a headed Playwright browser with anti-detection measures to scrape full post content from Xueqiu detail pages, storing results in the Obsidian Vault for consumption by stock_reporter.py.

**Architecture:** Standalone fetcher component that plugs into the existing reporting pipeline without disrupting the current data collection flow. Reporter reads Vault first, falls back to truncated JSON content.

**Tech Stack:** Python 3.11+, Playwright, PyYAML (frontmatter), pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/utils/detail_page_fetcher.py` | Create | Core component: headed browser, anti-detection, page extraction, Vault write |
| `tests/utils/test_detail_page_fetcher.py` | Create | Unit tests with mocked Playwright |
| `scripts/utils/stock_reporter.py` | Modify | Add Vault read fallback in `_featured_posts()`, remove confusing Chinese numeral note |
| `scripts/utils/stock_reporter.py` | Modify | Enhance `_extract_excerpt()` to extract argument chains from full content |

---

### Task 1: DetailPageFetcher Core Component

**Files:**
- Create: `scripts/utils/detail_page_fetcher.py`
- Modify: `scripts/utils/stock_reporter.py:421` (remove Chinese numeral note later)

- [ ] **Step 1: Create `scripts/utils/detail_page_fetcher.py` with imports and class skeleton**

```python
"""
雪球帖子详情页抓取器

使用有头 Playwright 浏览器抓取雪球帖子详情页完整正文，
输出写入 Obsidian Vault（knowledge/10-Stocks/）。

反爬措施：
1. 有头浏览器（headless=False）
2. 挂载真实 Chrome profile（cookies、localStorage 完整）
3. 隐藏 navigator.webdriver 等自动化标志
4. 每次请求间隔 ≥ 5 秒，页面内随机滚动模拟阅读
"""

import json
import logging
import random
import time
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
            vault_base: Obsidian Vault 根目录，如 Path("knowledge/10-Stocks")
            user_data_dir: Chrome profile 目录，默认使用用户主 profile
            headless: 是否无头模式（默认 False，需手动登录）
            delay_range: 页面加载后随机停留秒数范围
            request_interval: 两次请求之间的最小间隔秒数
        """
        self.vault_base = Path(vault_base)
        self.user_data_dir = user_data_dir
        self.headless = headless
        self.delay_range = delay_range
        self.request_interval = request_interval

    def fetch_posts(self, stock_name: str, posts: List[Dict]) -> List[str]:
        """
        批量抓取帖子详情页完整正文。

        Args:
            stock_name: 股票名称，用于 Vault 子目录
            posts: 帖子列表，每项至少包含 url、title、author 等字段

        Returns:
            成功写入 Vault 的 URL 列表
        """
        raise NotImplementedError("待实现")

    def _extract_post_id(self, url: str) -> str:
        """从 URL 中提取帖子 ID"""
        return url.rstrip("/").split("/")[-1]

    def _write_to_vault(
        self,
        stock_name: str,
        post_id: str,
        metadata: Dict,
        full_content: str,
    ) -> Path:
        """将完整正文写入 Vault"""
        raise NotImplementedError("待实现")
```

- [ ] **Step 2: Implement `_write_to_vault()` method**

在 `DetailPageFetcher` 类中添加：

```python
    def _write_to_vault(
        self,
        stock_name: str,
        post_id: str,
        metadata: Dict,
        full_content: str,
    ) -> Path:
        """
        将帖子完整正文写入 Obsidian Vault。

        存储路径: knowledge/10-Stocks/<股票名>/posts/<帖子ID>.md
        """
        from datetime import datetime

        post_dir = self.vault_base / stock_name / "posts"
        post_dir.mkdir(parents=True, exist_ok=True)

        filepath = post_dir / f"{post_id}.md"

        # 构建 YAML frontmatter
        frontmatter = {
            "source_url": metadata.get("url", ""),
            "stock_name": stock_name,
            "author": metadata.get("author", ""),
            "title": metadata.get("title", ""),
            "date": metadata.get("time", ""),
            "interactions": {
                "likes": metadata.get("like_count", 0),
                "comments": metadata.get("comment_count", 0),
                "reposts": metadata.get("repost_count", 0),
            },
            "collected_at": datetime.now().isoformat(),
        }

        # 写入 markdown 文件
        lines = [
            "---",
            json.dumps(frontmatter, ensure_ascii=False, indent=2),
            "---",
            "",
            f"# {metadata.get('title', '')}",
            "",
            full_content,
        ]
        filepath.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"[Vault] 已写入: {filepath}")
        return filepath
```

- [ ] **Step 3: Implement `_init_browser()` with stealth and user data dir**

在 `DetailPageFetcher` 类中添加：

```python
    def _init_browser(self):
        """
        初始化有头 Playwright 浏览器，启用反检测措施。
        """
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()

        launch_args = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        }

        if self.user_data_dir and self.user_data_dir.exists():
            launch_args["user_data_dir"] = str(self.user_data_dir)
            logger.info(f"[Browser] 使用用户数据目录: {self.user_data_dir}")
        else:
            logger.warning("[Browser] 未指定用户数据目录，需手动登录雪球")

        self._browser = self._playwright.chromium.launch(**launch_args)
        context = self._browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )

        # 隐藏 webdriver 标志
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            delete window.__playwright;
        """)

        self._page = context.new_page()
        logger.info("[Browser] 浏览器已启动，请在窗口中手动登录雪球")
```

- [ ] **Step 4: Implement `_extract_content()` for Xueqiu detail pages**

在 `DetailPageFetcher` 类中添加：

```python
    def _extract_content(self, url: str) -> Optional[str]:
        """
        访问雪球帖子详情页并提取完整正文。

        Returns:
            完整正文文本，失败返回 None
        """
        if not hasattr(self, "_page"):
            self._init_browser()

        try:
            logger.info(f"[Fetch] 访问: {url}")
            self._page.goto(url, wait_until="networkidle", timeout=30000)

            # 随机停留，模拟阅读
            delay = random.randint(*self.delay_range)
            time.sleep(delay)

            # 检查是否需要登录
            if "login" in self._page.url or self._page.locator(".login-dialog").count() > 0:
                logger.error("[Fetch] 检测到登录页，请先在浏览器窗口中登录雪球")
                return None

            # 页面内随机滚动
            for _ in range(random.randint(2, 5)):
                scroll_y = random.randint(200, 800)
                self._page.evaluate(f"window.scrollBy(0, {scroll_y})")
                time.sleep(random.uniform(0.5, 1.5))

            # 提取正文：雪球详情页文章主体通常在 .article__bd 或 #app .article 中
            selectors = [
                ".article__bd",
                ".article-content",
                "#app .article",
                ".detail-main .content",
                "article",
            ]

            content = None
            for selector in selectors:
                try:
                    element = self._page.locator(selector).first
                    if element.count() > 0:
                        content = element.inner_text()
                        if content and len(content.strip()) > 100:
                            break
                except Exception:
                    continue

            if not content or len(content.strip()) < 100:
                logger.warning(f"[Fetch] 正文提取为空或过短，可能页面结构变化: {url}")
                # fallback：提取整个 body 文本
                content = self._page.locator("body").inner_text()

            return content.strip() if content else None

        except Exception as e:
            logger.error(f"[Fetch] 抓取失败 {url}: {e}")
            return None
```

- [ ] **Step 5: Implement `fetch_posts()` orchestration method**

在 `DetailPageFetcher` 类中添加：

```python
    def fetch_posts(self, stock_name: str, posts: List[Dict]) -> List[str]:
        """
        批量抓取帖子详情页完整正文。
        """
        success_urls = []

        for i, post in enumerate(posts, 1):
            url = post.get("url", "")
            if not url:
                continue

            post_id = self._extract_post_id(url)
            vault_path = self.vault_base / stock_name / "posts" / f"{post_id}.md"

            # 如果 Vault 中已存在且非强制覆盖，跳过
            if vault_path.exists():
                logger.info(f"[Skip] Vault 中已存在，跳过: {url}")
                success_urls.append(url)
                continue

            # 抓取详情页
            full_content = self._extract_content(url)
            if not full_content:
                continue

            # 写入 Vault
            self._write_to_vault(stock_name, post_id, post, full_content)
            success_urls.append(url)

            # 请求间隔（最后一条不需要）
            if i < len(posts):
                logger.info(f"[Wait] 间隔 {self.request_interval} 秒...")
                time.sleep(self.request_interval)

        # 关闭浏览器
        if hasattr(self, "_browser"):
            self._browser.close()
        if hasattr(self, "_playwright"):
            self._playwright.stop()

        logger.info(f"[Done] 共抓取 {len(success_urls)}/{len(posts)} 篇")
        return success_urls
```

- [ ] **Step 6: Commit Task 1**

```bash
git add scripts/utils/detail_page_fetcher.py
git commit -m "feat(detail-fetcher): add DetailPageFetcher with stealth browser and Vault output"
```

---

### Task 2: Unit Tests for DetailPageFetcher

**Files:**
- Create: `tests/utils/test_detail_page_fetcher.py`

- [ ] **Step 1: Write failing test for `_extract_post_id()`**

```python
# tests/utils/test_detail_page_fetcher.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from detail_page_fetcher import DetailPageFetcher


def test_extract_post_id():
    fetcher = DetailPageFetcher(vault_base=Path("/tmp/test-vault"))
    assert fetcher._extract_post_id("https://xueqiu.com/8025337289/389734910") == "389734910"
    assert fetcher._extract_post_id("https://xueqiu.com/8025337289/389734910/") == "389734910"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/utils/test_detail_page_fetcher.py::test_extract_post_id -v
```

Expected: PASS（因为 Step 1 已实现了该 method）

- [ ] **Step 3: Write test for `_write_to_vault()` with temp directory**

```python
def test_write_to_vault():
    import tempfile
    from datetime import datetime

    with tempfile.TemporaryDirectory() as tmpdir:
        fetcher = DetailPageFetcher(vault_base=Path(tmpdir))
        metadata = {
            "url": "https://xueqiu.com/8025337289/389734910",
            "title": "测试标题",
            "author": "测试作者",
            "time": "2026-05-20",
            "like_count": 10,
            "comment_count": 2,
            "repost_count": 1,
        }
        path = fetcher._write_to_vault(
            stock_name="测试股票",
            post_id="389734910",
            metadata=metadata,
            full_content="这是测试正文内容。",
        )
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "测试标题" in content
        assert "这是测试正文内容" in content
        assert "389734910" in content
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/utils/test_detail_page_fetcher.py -v
```

Expected: PASS

- [ ] **Step 5: Commit Task 2**

```bash
git add tests/utils/test_detail_page_fetcher.py
git commit -m "test(detail-fetcher): add unit tests for post ID extraction and Vault write"
```

---

### Task 3: Integrate Vault Read into stock_reporter.py

**Files:**
- Modify: `scripts/utils/stock_reporter.py`

- [ ] **Step 1: Add `_read_full_content_from_vault()` method**

在 `PerStockReporter` 类中（在 `_extract_excerpt()` 附近）添加：

```python
    def _read_full_content_from_vault(self, stock_name: str, url: str) -> Optional[str]:
        """
        从 Obsidian Vault 读取帖子的完整正文。

        Args:
            stock_name: 股票名称
            url: 帖子 URL

        Returns:
            完整正文文本，未找到返回 None
        """
        post_id = url.rstrip("/").split("/")[-1]
        vault_path = (
            Path(__file__).parent.parent.parent
            / "knowledge"
            / "10-Stocks"
            / stock_name
            / "posts"
            / f"{post_id}.md"
        )
        if not vault_path.exists():
            return None

        content = vault_path.read_text(encoding="utf-8")
        # 跳过 YAML frontmatter
        import re
        match = re.search(r"^---\n.*?\n---\n\n# .*\n\n(.+)", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
```

- [ ] **Step 2: Modify `_featured_posts()` to read Vault first**

在 `_featured_posts()` 方法中，找到这一段（约第436-440行）：

```python
            # 尽量保留原文核心内容
            excerpt = self._extract_excerpt(content, min_length=150, max_length=400)
            # 如果内容明显是截断的列表页摘要，标注提示
            if len(content) < 200:
                excerpt = f"【列表页摘要，详情见原文链接】{excerpt}"
```

替换为：

```python
            # 优先从 Vault 读取完整正文
            full_content = self._read_full_content_from_vault(stock_name, url)
            if full_content:
                excerpt = self._extract_excerpt(full_content, min_length=200, max_length=600)
            else:
                excerpt = self._extract_excerpt(content, min_length=150, max_length=400)
                # 如果内容明显是截断的列表页摘要，标注提示
                if len(content) < 200:
                    excerpt = f"【列表页摘要，详情见原文链接】{excerpt}"
```

- [ ] **Step 3: Remove confusing Chinese numeral note**

删除 `_featured_posts()` 中的这一行（第421行）：

```python
sections.append("*注：标题中的（一）（二）（三）等中文数字为作者原文自带的系列编号，非报告编号。*\n")
```

改为直接开始帖子列表，不再添加注释。

- [ ] **Step 4: Run reporter to verify no regression**

```bash
cd /Users/erichan/testsnow
python -c "
from scripts.utils.stock_reporter import PerStockReporter
import json

with open('data/raw/xueqiu_data_20260520.json') as f:
    data = json.load(f)

reporter = PerStockReporter(stocks_data=data, stock_codes={'圣邦股份': '300661'})
path = reporter.generate_stock_report('圣邦股份', 'reports')
print(f'Report: {path}')
"
```

Expected: 报告正常生成，没有报错

- [ ] **Step 5: Commit Task 3**

```bash
git add scripts/utils/stock_reporter.py
git commit -m "feat(reporter): read full content from Vault before falling back to truncated summary"
```

---

### Task 4: Enhance `_extract_excerpt()` for Argument Chains

**Files:**
- Modify: `scripts/utils/stock_reporter.py:1246`

- [ ] **Step 1: Rename and enhance extraction logic**

将 `_extract_excerpt()` 重命名为 `_extract_argument_chain()`，增强推导链提取：

```python
    def _extract_argument_chain(self, content: str, min_length: int = 200, max_length: int = 600) -> str:
        """
        从帖子正文中提取推导链（前提假设 → 论据/数据 → 推理过程 → 结论）。

        策略：
        1. 如果正文长度在范围内，直接返回
        2. 如果过长，优先保留包含"因为"、"所以"、"如果"、"那么"等逻辑词附近的段落
        3. 尽量保留包含数字、百分比、金额的句子
        """
        content = content.strip()
        if len(content) <= max_length:
            return content

        # 尝试提取包含逻辑连接词和数字的关键段落
        logic_keywords = ["因为", "所以", "如果", "那么", "因此", "意味着", "结论是",
                          "前提", "论据", "推导", "逻辑", "假设", "验证"]
        data_patterns = [r"\d+[%％]", r"\d+\.\d+", r"\d+亿", r"\d+万", r"\d+元"]

        import re

        # 按段落分割
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]

        # 给每个段落打分
        scored_paragraphs = []
        for p in paragraphs:
            score = 0
            # 逻辑词加分
            for kw in logic_keywords:
                if kw in p:
                    score += 2
            # 数字/数据加分
            for pattern in data_patterns:
                if re.search(pattern, p):
                    score += 3
            # 长度适中加分（太短的信息量低）
            if 30 <= len(p) <= 200:
                score += 1
            scored_paragraphs.append((score, p))

        # 按分数降序排序，优先保留高分段落
        scored_paragraphs.sort(key=lambda x: x[0], reverse=True)

        # 构建摘录：优先高分段落，直到接近 max_length
        selected = []
        total_len = 0
        for score, p in scored_paragraphs:
            if total_len + len(p) > max_length and total_len >= min_length:
                break
            selected.append(p)
            total_len += len(p) + 1  # +1 for newline

        # 按原文顺序重新排列选中的段落
        selected_set = set(selected)
        ordered = [p for p in paragraphs if p in selected_set]

        result = "\n".join(ordered)

        # 如果还是太短，fallback 到前 max_length 字符
        if len(result) < min_length:
            truncated = content[:max_length]
            last_period = max(truncated.rfind("。"), truncated.rfind("！"), truncated.rfind("？"))
            if last_period > min_length:
                return truncated[:last_period + 1]
            return truncated + "..."

        return result
```

- [ ] **Step 2: Update call sites to use new method name**

在 `_featured_posts()` 中，将所有调用 `_extract_excerpt` 的地方改为 `_extract_argument_chain`。

- [ ] **Step 3: Add backward-compatible alias**

为避免其他调用点报错，保留一个别名：

```python
    def _extract_excerpt(self, content: str, min_length: int = 150, max_length: int = 400) -> str:
        """Backward-compatible alias for _extract_argument_chain."""
        return self._extract_argument_chain(content, min_length, max_length)
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/erichan/testsnow
python -c "
from scripts.utils.stock_reporter import PerStockReporter
r = PerStockReporter(stocks_data={})
text = '这是前提。因为A公司业绩增长了50%，所以B公司的市场份额会下降。如果C公司进入该领域，那么竞争格局将发生根本性变化。因此，结论是投资D公司。'
print(r._extract_argument_chain(text, min_length=50, max_length=200))
"
```

Expected: 输出包含逻辑推导链的摘录

- [ ] **Step 5: Commit Task 4**

```bash
git add scripts/utils/stock_reporter.py
git commit -m "feat(reporter): enhance excerpt extraction to capture argument chains with logic keywords and data"
```

---

### Task 5: End-to-End Smoke Test

**Files:**
- None (verification only)

- [ ] **Step 1: Verify DetailPageFetcher can be imported**

```bash
cd /Users/erichan/testsnow
python -c "from scripts.utils.detail_page_fetcher import DetailPageFetcher; print('OK')"
```

Expected: `OK`

- [ ] **Step 2: Verify stock_reporter still generates reports without error**

```bash
cd /Users/erichan/testsnow
python -c "
import json
from scripts.utils.stock_reporter import PerStockReporter

with open('data/raw/xueqiu_data_20260520.json') as f:
    data = json.load(f)

for stock in ['圣邦股份', '黑芝麻智能']:
    reporter = PerStockReporter(
        stocks_data={stock: data.get(stock, [])},
        stock_codes={stock: '300661' if stock == '圣邦股份' else '02533'},
    )
    path = reporter.generate_stock_report(stock, 'reports')
    print(f'{stock}: {path}')
"
```

Expected: 两份报告正常生成，无异常

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/erichan/testsnow
python -m pytest tests/utils/test_detail_page_fetcher.py -v
```

Expected: All PASS

- [ ] **Step 4: Final commit**

```bash
git add docs/superpowers/plans/2026-05-25-detail-page-fetcher.md
git commit -m "docs(plan): add DetailPageFetcher implementation plan"
```

---

## Self-Review

### Spec Coverage Check

| Spec Section | Plan Task | Status |
|--------------|-----------|--------|
| 组件接口 (`DetailPageFetcher`) | Task 1 | ✅ |
| 有头浏览器 + stealth | Task 1, Step 3 | ✅ |
| 真实用户数据目录 | Task 1, Step 3 | ✅ |
| 行为模拟（随机停留/滚动） | Task 1, Step 4 | ✅ |
| Vault 存储格式 | Task 1, Step 2 | ✅ |
| reporter 对接（优先读 Vault） | Task 3 | ✅ |
| 反爬措施 | Task 1, Step 3-4 | ✅ |

### Placeholder Scan

- 无 TBD、TODO、"implement later"
- 所有步骤包含完整代码
- 所有测试包含具体断言

### Type Consistency

- `_extract_post_id()` → 返回 `str`，与 Vault 文件名生成一致
- `_write_to_vault()` → 返回 `Path`，测试中验证 `.exists()`
- `fetch_posts()` → 返回 `List[str]`（成功 URL 列表）
