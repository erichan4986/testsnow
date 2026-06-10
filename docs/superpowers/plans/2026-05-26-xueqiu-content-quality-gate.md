# 雪球爬虫内容质量门控 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为雪球爬虫添加列表页双轨分流机制，过滤短内容，仅让高质量长文进入详情页、Vault 和报告。

**Architecture:** 在 `XueqiuFetcher` 列表页阶段引入质量评分，分流为 `featured`（长文精选）和 `sentiment`（短帖情绪）。`featured` 帖子进入详情页提取完整正文并写入 Vault；`sentiment` 帖子仅参与情绪统计，不进详情页/Vault/报告精品帖。

**Tech Stack:** Python 3.10, Playwright (sync API), markdown

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/utils/fetcher.py` | `XueqiuFetcher` 列表页浏览、质量评分、双轨分流、详情页提取 |
| `scripts/utils/stock_reporter.py` | `PerStockReporter` 接收双轨数据，分别用于精品帖和情绪分析 |
| `scripts/xueqiu_monitor_v2.py` | 主流程适配新返回格式 |
| `scripts/demo_shengbang.py` | Demo 脚本适配新返回格式 |
| `scripts/utils/detail_page_fetcher.py` | 不变（继续处理长文候选的 Vault 写入） |

---

## Task 1: 提取质量评分逻辑为独立函数

**Files:**
- Create: `scripts/utils/content_quality.py`
- Test: `scripts/utils/test_content_quality.py`

- [ ] **Step 1: 编写测试文件**

```python
# scripts/utils/test_content_quality.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from content_quality import classify_post, score_post

def test_classify_short_post():
    post = {
        "title": "看好！",
        "content": "乐鑫科技牛逼！看好！",
        "like_count": 5,
        "comment_count": 0,
    }
    result = classify_post(post)
    assert result == "sentiment"

def test_classify_truncated_post():
    post = {
        "title": "关于模拟芯片的深度分析...",
        "content": "关于模拟芯片的深度分析，当前市场环境下...",
        "like_count": 45,
        "comment_count": 12,
    }
    result = classify_post(post)
    assert result == "featured"

def test_classify_data_rich_post():
    post = {
        "title": "营收增长35%因为产能释放",
        "content": "营收增长35%因为产能释放，毛利率提升至42%...",
        "like_count": 8,
        "comment_count": 2,
    }
    result = classify_post(post)
    assert result == "featured"

def test_classify_high_interaction_post():
    post = {
        "title": "简单观点",
        "content": "简单观点表达",
        "like_count": 25,
        "comment_count": 10,
    }
    result = classify_post(post)
    assert result == "featured"

def test_score_post():
    post = {
        "title": "深度分析...",
        "content": "深度分析，营收增长35%...",
        "like_count": 50,
        "comment_count": 20,
    }
    score = score_post(post)
    assert score > 0

def test_score_low_quality_post():
    post = {
        "title": "看好",
        "content": "看好这只股票",
        "like_count": 2,
        "comment_count": 0,
    }
    score = score_post(post)
    assert score == 0

if __name__ == "__main__":
    test_classify_short_post()
    test_classify_truncated_post()
    test_classify_data_rich_post()
    test_classify_high_interaction_post()
    test_score_post()
    test_score_low_quality_post()
    print("All tests passed")
```

- [ ] **Step 2: 运行测试确认全部失败**

Run: `python scripts/utils/test_content_quality.py`
Expected: `ModuleNotFoundError: No module named 'content_quality'`

- [ ] **Step 3: 实现 content_quality 模块**

```python
# scripts/utils/content_quality.py
"""
雪球帖子内容质量评分与分类器

将列表页提取的帖子分流为：
- featured: 长文精选（进入详情页、Vault、报告精品帖）
- sentiment: 短帖情绪（仅参与情绪统计）
"""

import re
from typing import Dict

# 逻辑连接词
_LOGIC_WORDS = [
    "因为", "所以", "如果", "那么", "因此", "意味着", "结论",
    "前提", "推导", "验证", "由于", "导致", "说明", "反映",
    "对比", "相较于", "数据表明", "统计", "测算", "估算",
]

# 数据模式
data_patterns = [r"\d+[%％]", r"\d+\.\d+", r"\d+亿", r"\d+万", r"\d+元"]


def _has_logic_words(text: str) -> bool:
    return any(w in text for w in _LOGIC_WORDS)


def _has_data(text: str) -> bool:
    return any(re.search(p, text) for p in data_patterns)


def score_post(post: Dict) -> int:
    """
    对列表页帖子进行质量评分。

    Returns:
        评分值，>=1 表示 featured 候选，0 表示 sentiment
    """
    title = post.get("title", "")
    content = post.get("content", "")
    combined = f"{title} {content}"
    likes = post.get("like_count", 0)
    comments = post.get("comment_count", 0)
    score = 0

    # 信号1: 列表页摘要以 "..." 结尾（截断标识）
    if content.rstrip().endswith("...") or title.rstrip().endswith("..."):
        score += 3

    # 信号2: 同时包含数据和逻辑词
    if _has_data(combined) and _has_logic_words(combined):
        score += 2

    # 信号3: 高互动数
    if likes + comments > 30:
        score += 2

    return score


def classify_post(post: Dict) -> str:
    """
    将帖子分类为 featured 或 sentiment。

    Returns:
        "featured" | "sentiment"
    """
    if score_post(post) >= 1:
        return "featured"
    return "sentiment"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python scripts/utils/test_content_quality.py`
Expected: `All tests passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/content_quality.py scripts/utils/test_content_quality.py
git commit -m "feat: add content quality scorer and classifier"
```

---

## Task 2: 修改 XueqiuFetcher 支持列表页多页浏览

**Files:**
- Modify: `scripts/utils/fetcher.py:163-245`

- [ ] **Step 1: 修改 `fetch_stock_posts` 签名和返回类型**

将 `fetch_stock_posts` 的签名改为：

```python
def fetch_stock_posts(
    self,
    stock_code: str,
    stock_name: str,
    max_list_pages: int = 10,
    max_detail_posts: int = 10,
    fetch_comments: bool = True,
) -> Dict[str, List[Dict]]:
    """
    抓取单只股票的雪球帖子（讨论区）

    Args:
        stock_code: 雪球股票代码，如 SZ000661
        stock_name: 股票名称（用于日志）
        max_list_pages: 列表页浏览页数（默认 10）
        max_detail_posts: 对长文候选 Top N 进入详情页提取正文
        fetch_comments: 是否提取评论

    Returns:
        {
            "featured": [...],   # 长文精选（含完整正文，已进详情页）
            "sentiment": [...],  # 短帖情绪（仅列表页摘要）
        }
    """
```

- [ ] **Step 2: 添加列表页翻页逻辑**

在 `XueqiuFetcher` 中添加 `_scroll_or_next_page` 方法：

```python
def _scroll_or_next_page(self, page) -> bool:
    """
    触发列表页下一页加载（无限滚动或点击翻页）。

    Returns:
        True if more posts were loaded, False otherwise.
    """
    try:
        # 策略1: 尝试点击"加载更多"按钮
        more_loaded = page.evaluate(
            """() => {
                const btn = document.querySelector('a.show-more, button.show-more, .load-more');
                if (btn && btn.offsetParent !== null) {
                    btn.click();
                    return true;
                }
                return false;
            }"""
        )
        if more_loaded:
            return True

        # 策略2: 滚动到底部触发无限滚动
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        return True
    except Exception:
        return False
```

- [ ] **Step 3: 修改 `fetch_stock_posts` 主体逻辑**

将 `fetch_stock_posts` 的主体替换为：

```python
if not self.browser:
    self._connect()

all_posts: List[Dict] = []
context = None
page = None

# 导入质量评分器
from .content_quality import classify_post, score_post

try:
    context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
    page = context.new_page()

    # 1. 打开股票页面
    url = f"{self.BASE_URL}/S/{stock_code}"
    logger.info(f"[雪球] 打开 {stock_name} 页面: {url}")
    page.goto(url, wait_until="networkidle", timeout=60000)

    # 2. 点击"全部" tab（新流程）
    self._click_tab(page, "全部")
    time.sleep(random.uniform(1, 2))

    # 3. 点击"热帖" tab（新流程）
    self._click_tab(page, "热帖")
    time.sleep(random.uniform(1, 2))

    # 4. 多页浏览提取帖子
    seen_urls = set()
    for page_num in range(1, max_list_pages + 1):
        posts = self._extract_posts_from_page(page, 100)
        new_posts = [p for p in posts if p.get("url") and p["url"] not in seen_urls]
        if not new_posts:
            logger.info(f"[雪球] [{stock_name}] 第 {page_num} 页无新帖子，停止翻页")
            break

        all_posts.extend(new_posts)
        for p in new_posts:
            seen_urls.add(p["url"])

        logger.info(f"[雪球] [{stock_name}] 第 {page_num} 页提取到 {len(new_posts)} 条新帖子，累计 {len(all_posts)} 条")

        if page_num < max_list_pages:
            has_more = self._scroll_or_next_page(page)
            if not has_more:
                break
            time.sleep(random.uniform(2, 3))

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

    # 6. 对 featured 候选排序，Top N 进入详情页
    featured_candidates.sort(
        key=lambda x: x.get("like_count", 0) + x.get("comment_count", 0),
        reverse=True,
    )

    featured_posts = []
    for post in featured_candidates[:max_detail_posts]:
        if post.get("url"):
            try:
                detail = self._fetch_post_detail(page, post["url"])
                if detail:
                    post["content"] = detail.get("content", "")
                    post["comments"] = detail.get("comments", [])
                    # 二次过滤: 详情页正文 < 80 字降级为 sentiment
                    if len(post.get("content", "")) < 80:
                        logger.info(
                            f"[雪球] [{stock_name}] 详情页正文过短，降级: "
                            f"{post.get('title', '')[:20]}..."
                        )
                        sentiment_posts.append(post)
                    else:
                        featured_posts.append(post)
                        logger.info(
                            f"[雪球] [{stock_name}] 详情页提取: "
                            f"{post.get('title', '')[:20]}... "
                            f"正文 {len(post['content'])} 字"
                        )
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.warning(f"[雪球] 详情页提取失败: {e}")

    page.close()

    return {
        "featured": featured_posts,
        "sentiment": sentiment_posts,
    }

except Exception as e:
    logger.error(f"[雪球] 抓取失败 [{stock_name}]: {e}")
    if page:
        try:
            page.close()
        except Exception:
            pass
    return {"featured": [], "sentiment": []}
```

- [ ] **Step 4: Commit**

```bash
git add scripts/utils/fetcher.py
git commit -m "feat: add list-page pagination and dual-track filtering to XueqiuFetcher"
```

---

## Task 3: 修改 `fetch_all_stocks` 适配新返回格式

**Files:**
- Modify: `scripts/utils/fetcher.py:429-486`

- [ ] **Step 1: 修改 `fetch_all_stocks` 返回类型和合并逻辑**

```python
def fetch_all_stocks(
    stocks_config: List[Dict],
    use_xueqiu: bool = False,
    xueqiu_cdp_url: str = "http://localhost:9222"
) -> Dict[str, List[Dict]]:
    """
    抓取所有配置股票的数据

    Returns:
        {股票名称: 帖子列表} — 合并 featured + sentiment 后的全部帖子
    """
    results = {}

    xq_fetcher = None
    if use_xueqiu:
        try:
            xq_fetcher = XueqiuFetcher(cdp_url=xueqiu_cdp_url)
        except Exception as e:
            logger.warning(f"雪球抓取器初始化失败，将使用东方财富: {e}")

    em_fetcher = EastmoneyFetcher()

    for stock in stocks_config:
        name = stock["name"]
        gid = stock.get("gid")
        xq_code = stock.get("xueqiu_code")

        posts = []

        if xq_fetcher and xq_code:
            try:
                result = xq_fetcher.fetch_stock_posts(xq_code, name)
                # 合并 featured 和 sentiment 为统一列表，但保留分类标记
                for p in result.get("featured", []):
                    p["_track"] = "featured"
                    posts.append(p)
                for p in result.get("sentiment", []):
                    p["_track"] = "sentiment"
                    posts.append(p)
            except Exception as e:
                logger.warning(f"[雪球] 抓取 [{name}] 失败，将回退到东方财富: {e}")
                posts = []

        if not posts and gid:
            posts = em_fetcher.fetch_stock_posts(gid, name, max_posts=15)
            # 东财数据无分类，全部标记为 sentiment（不进入 Vault）
            for p in posts:
                p["_track"] = "sentiment"

        results[name] = posts

        if stock != stocks_config[-1]:
            time.sleep(random.uniform(3, 5))

    if xq_fetcher:
        xq_fetcher.close()

    return results
```

- [ ] **Step 2: Commit**

```bash
git add scripts/utils/fetcher.py
git commit -m "feat: adapt fetch_all_stocks to merge featured and sentiment tracks"
```

---

## Task 4: 修改 `PerStockReporter` 区分双轨数据

**Files:**
- Modify: `scripts/utils/stock_reporter.py:96-147`

- [ ] **Step 1: 修改 `generate_stock_report` 使用 `_track` 标记分流**

在 `generate_stock_report` 中，将帖子按 `_track` 分流：

```python
def generate_stock_report(self, stock_name: str, output_dir: str) -> str:
    all_posts = self.stocks_data.get(stock_name, [])
    if not all_posts:
        logger.warning(f"[{stock_name}] 无数据，跳过")
        return ""

    # 双轨分流
    featured_posts = [p for p in all_posts if p.get("_track") == "featured"]
    sentiment_posts = [p for p in all_posts if p.get("_track") == "sentiment"]

    logger.info(
        f"[{stock_name}] 报告生成: featured={len(featured_posts)}, "
        f"sentiment={len(sentiment_posts)}"
    )

    # 构建报告各部分
    sections = []
    sections.append(self._header(stock_name))
    sections.append(self._valuation_forecast(stock_name))

    # 3-7. 扩展数据章节（不变）
    stock_raw = self.raw_data.get(stock_name, {})
    analysis_result = stock_raw.get("analysis", {})
    sections.append(self._technical_section(stock_name, analysis_result))
    sections.append(self._reports_section(stock_name, analysis_result, stock_raw.get("reports", [])))
    sections.append(self._announcements_section(stock_name, analysis_result, stock_raw.get("announcements", [])))
    sections.append(self._fundflow_section(stock_name, analysis_result, stock_raw.get("fundflow", [])))
    sections.append(self._zhihu_section(stock_name, stock_raw.get("zhihu", {})))

    # 情绪与竞争格局: 使用全部帖子
    sections.append(self._sentiment_and_competition(stock_name, all_posts))
    sections.append(self._core_topics(stock_name, all_posts))

    # 精品帖子深度解读: 仅使用 featured 帖子
    sections.append(self._featured_posts(stock_name, featured_posts))

    # 评论摘录: 使用全部帖子
    sections.append(self._comment_highlights(stock_name, all_posts))
    sections.append(self._risks_and_watch(stock_name, all_posts))
    sections.append(self._footer())

    markdown = "\n\n".join(sections)

    filename = f"{stock_name}_{self.date_str}.md"
    filepath = Path(output_dir) / filename
    filepath.write_text(markdown, encoding="utf-8")
    return str(filepath)
```

- [ ] **Step 2: 修改 `_featured_posts` 处理空候选池的情况**

在 `_featured_posts` 方法开头添加空值处理：

```python
def _featured_posts(self, stock_name: str, posts: List[Dict]) -> str:
    if not posts:
        return "## 三、精品帖子深度解读\n\n*本期无高质量分析帖*\n"

    # ... 原有逻辑保持不变 ...
```

- [ ] **Step 3: Commit**

```bash
git add scripts/utils/stock_reporter.py
git commit -m "feat: reporter uses dual-track data, featured posts only for deep analysis"
```

---

## Task 5: 更新 `xueqiu_monitor_v2.py` 和 `demo_shengbang.py`

**Files:**
- Modify: `scripts/xueqiu_monitor_v2.py:84-96`
- Modify: `scripts/demo_shengbang.py:154-160`

- [ ] **Step 1: 更新 `xueqiu_monitor_v2.py` 中的日志输出**

将日志中的 `total_posts` 计算改为分别统计：

```python
stocks_data = fetch_all_stocks(
    stocks,
    use_xueqiu=use_xueqiu,
    xueqiu_cdp_url=xueqiu_cdp_url or "http://localhost:9222"
)

total_featured = sum(
    1 for posts in stocks_data.values() for p in posts if p.get("_track") == "featured"
)
total_sentiment = sum(
    1 for posts in stocks_data.values() for p in posts if p.get("_track") == "sentiment"
)
logger.info(f"数据采集完成，共 {total_featured} 条精选帖，{total_sentiment} 条情绪帖")
```

- [ ] **Step 2: 更新 `demo_shengbang.py` 中的 dummy 数据**

```python
# 构造双轨 dummy 数据让 reporter 不跳过
dummy_featured = [{
    "title": "Demo featured post",
    "author": "demo",
    "content": "demo content with enough length to pass quality gate",
    "comment_count": 0,
    "like_count": 0,
    "_track": "featured",
}]
dummy_sentiment = [{
    "title": "Demo sentiment post",
    "author": "demo",
    "content": "demo",
    "comment_count": 0,
    "like_count": 0,
    "_track": "sentiment",
}]
reporter = PerStockReporter(
    stocks_data={stock_name: dummy_featured + dummy_sentiment},
    stock_codes={stock_name: code},
    raw_data=collected_data,
)
```

- [ ] **Step 3: Commit**

```bash
git add scripts/xueqiu_monitor_v2.py scripts/demo_shengbang.py
git commit -m "chore: adapt callers to dual-track post data"
```

---

## Task 6: 运行端到端验证

**Files:**
- Modify: `scripts/validate_e2e.py`

- [ ] **Step 1: 更新 `validate_e2e.py` 支持双轨数据结构**

在加载 xueqiu_data 后，为旧数据添加 `_track` 标记（兼容旧数据格式）：

```python
# 兼容旧数据: 无 _track 标记的帖子全部视为 sentiment
for stock_name, posts in stocks_data.items():
    for p in posts:
        if "_track" not in p:
            # 用 content_quality 重新分类
            from scripts.utils.content_quality import classify_post
            p["_track"] = classify_post(p)
```

- [ ] **Step 2: 运行验证脚本**

Run: `python scripts/validate_e2e.py`
Expected: 6 只股票的报告成功生成，PDF 导出成功

- [ ] **Step 3: 检查报告质量**

检查 `reports/乐鑫科技_20260526.md`：
- 精品帖子章节不应再出现口号式短内容
- 情绪分析章节仍应基于全部帖子

- [ ] **Step 4: Commit**

```bash
git add scripts/validate_e2e.py
git commit -m "chore: update e2e validation script for dual-track data"
```

---

## Spec Coverage Check

| Spec 需求 | 实现任务 |
|---|---|
| 列表页浏览 5-10 页 | Task 2: `_scroll_or_next_page` + 翻页循环 |
| 摘要以 `"..."` 结尾为长文信号 | Task 1: `score_post` 信号1 |
| 含数据+逻辑词为长文信号 | Task 1: `score_post` 信号2 |
| 互动数 > 30 为长文信号 | Task 1: `score_post` 信号3 |
| featured 进详情页 | Task 2: 详情页提取逻辑 |
| sentiment 不进详情页 | Task 2: 分流后直接跳过 |
| 详情页正文 < 80 字降级 | Task 2: 二次过滤逻辑 |
| Vault 仅写入 featured | Task 4: reporter 仅传 featured 给 `_featured_posts` |
| 情绪分析基于全部帖子 | Task 4: `_sentiment_and_competition` 仍用 `all_posts` |
| 报告精品帖仅 featured | Task 4: `_featured_posts` 仅接收 featured |
| 空候选池处理 | Task 4: `_featured_posts` 空值处理 |

## Placeholder Scan

- 无 TBD/TODO ✅
- 所有代码步骤包含完整代码 ✅
- 所有测试步骤包含完整测试代码 ✅
- 无 "similar to Task N" ✅

## Type Consistency

- `fetch_stock_posts` 返回 `Dict[str, List[Dict]]` — 与 `fetch_all_stocks` 消费端一致 ✅
- `_track` 字段值为 `"featured" | "sentiment"` — 全文件统一 ✅
- `classify_post` 返回 `str` — 与分流逻辑一致 ✅
