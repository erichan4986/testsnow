# DetailPageFetcher 设计规格

> 日期：2026-05-25
> 目标：为雪球帖子详情页提供可复用的有头浏览器抓取组件，输出写入 Obsidian Vault

---

## 背景与动机

现有 `data/raw/xueqiu_data_*.json` 中的 `content` 字段是列表页截断摘要，导致：
- 同一作者多篇帖子内容重复（开头模板相同）
- 摘录长度不足（<200字），无法提取推导链
- 精品帖子深度解读板块质量受限

本组件独立于现有采集管道，负责补全详情页完整正文。

---

## 架构定位

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Xueqiu列表页    │────▶│ DetailPageFetcher │────▶│ Obsidian Vault  │
│  (截断摘要)      │     │ (有头浏览器)       │     │ (完整正文)       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌──────────────────┐
                        │  stock_reporter   │
                        │ (优先读Vault全文) │
                        └──────────────────┘
```

- 和现有 `data_collector.py` 解耦，不阻塞列表页采集
- 输出格式与 roadmap 阶段2 的 `ContentMerger` 兼容

---

## 组件接口

```python
class DetailPageFetcher:
    def __init__(
        self,
        vault_base: Path,
        user_data_dir: Optional[Path] = None,  # Chrome profile 目录
        headless: bool = False,
        delay_range: tuple = (3, 8),  # 页面加载后停留秒数
    ):
        ...

    def fetch_posts(
        self,
        stock_name: str,
        posts: List[Dict],  # 含 url, title, author, 等字段
    ) -> List[str]:
        """
        逐页抓取详情页正文，写入 Vault。

        Returns:
            成功写入 Vault 的 URL 列表
        """
```

---

## Vault 存储格式

每篇帖子一个 markdown 文件：

```
knowledge/10-Stocks/<股票名>/posts/<帖子ID>.md
```

内容格式：

```markdown
---
source_url: "https://xueqiu.com/8025337289/389734910"
stock_name: "黑芝麻智能"
author: "郭小松驾道"
title: "黑芝麻智能（三）：平替英伟达..."
date: "2026-05-20"
interactions:
  likes: 59
  comments: 3
  reposts: 14
collected_at: "2026-05-25T14:30:00"
---

# 黑芝麻智能（三）：平替英伟达，高阶智驾明年大规模量产

[完整正文内容，保留段落结构]
```

---

## 反爬措施

1. **有头浏览器**（`headless=False`），由用户手动登录雪球
2. **Stealth 模式**：隐藏 `navigator.webdriver`、`__playwright` 等自动化标志
3. **真实用户数据目录**：挂载用户现有 Chrome profile（cookies、localStorage 完整）
4. **行为模拟**：
   - 每次页面加载后随机停留 3–8 秒
   - 页面内随机滚动，模拟阅读行为
   - 请求间隔 ≥ 5 秒

---

## reporter 对接

`stock_reporter.py` 的 `_featured_posts()` 中，在 `_extract_excerpt()` 之前增加一步：

```python
def _read_full_content_from_vault(stock_name: str, url: str) -> Optional[str]:
    """优先从 Vault 读取完整正文"""
```

优先级：Vault `full_content` → JSON `content` → fallback 标注"列表页摘要"

---

## 使用流程

```python
from scripts.utils.detail_page_fetcher import DetailPageFetcher

fetcher = DetailPageFetcher(
    vault_base=Path("knowledge/10-Stocks"),
    user_data_dir=Path("~/Library/Application Support/Google/Chrome"),
)

# 用户在有头窗口中手动登录雪球
# 登录完成后，程序接管

success_urls = fetcher.fetch_posts("黑芝麻智能", posts_list)
print(f"成功抓取 {len(success_urls)} 篇")
```

---

## 边界情况

- **登录态过期**：抓取过程中若出现登录页，立即报错退出，不继续
- **内容为空/JS未渲染**：重试一次，仍失败则跳过该 URL，记录日志
- **Vault 中已存在**：默认跳过（增量更新），可选强制覆盖
- **用户 Chrome 正在运行**：报错提示关闭 Chrome 后再启动
