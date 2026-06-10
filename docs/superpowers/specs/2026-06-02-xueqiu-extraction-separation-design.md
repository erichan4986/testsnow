# 雪球抓取与报告生成分离设计

## 目标

将雪球 CDP 抓取从报告生成流程中完全分离，实现：
1. 独立交互式抓取脚本（`fetch_xueqiu.py`）：启动 Chrome → 用户登录 → 抓取 → 保存数据
2. 报告脚本（`run_*`）只读取已抓取的数据，不再启动浏览器
3. 雪球数据经 `SourceAdapter` 混入 `KnowledgeSynthesizer`，与知乎共同生成报告三~七模块

## 架构

```
┌─────────────────┐     ┌─────────────────┐
│  fetch_xueqiu   │────▶│   run_*         │
│  （交互式抓取）  │     │  （报告生成）    │
└─────────────────┘     └─────────────────┘
         │                       │
         ▼                       ▼
   data/raw/xueqiu_data_{date}_{stock}.json
         │
         ▼
┌──────────────────────────────────────┐
│  SourceAdapter (XueqiuAdapter +      │
│   ZhihuAdapter) → List[SynthesisItem]│
└──────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  KnowledgeSynthesizer                │
│  混合多源 → 产业逻辑/基本面/估值争议/  │
│  资金面/催化剂（报告三~七模块）        │
└──────────────────────────────────────┘
```

## 组件

### 1. `scripts/fetch_xueqiu.py`（新建）

独立抓取脚本，职责单一：
- 参数：`--stock 黑芝麻智能` 或 `--all`（抓配置文件中全部6只）
- 交互流程：
  1. 启动 Chrome CDP（`scripts/start_chrome_cdp.sh` 的 Python 等价实现）
  2. 提示用户在浏览器中登录雪球
  3. 用户按回车确认后，连接 CDP 开始抓取
  4. 调用 `XueqiuFetcher.fetch_stock_posts()` 获取列表页
  5. 对 featured 候选进入详情页提取完整正文（双轨分流）
  6. 应用内容质量门（粗筛：长度/数据/逻辑/互动）
  7. 保存到 `data/raw/xueqiu_data_{date}_{stock_name}.json`
  8. 精品帖子全文写入 `knowledge/10-Stocks/{stock}/posts/{post_id}.md`（Obsidian Vault）

输出格式（与现有 `fetch_all_stocks` 返回的结构一致）：
```json
{
  "date": "20260602",
  "stock_name": "黑芝麻智能",
  "stock_code": "HK02533",
  "posts": [
    {
      "title": "...",
      "content": "完整正文...",
      "url": "https://xueqiu.com/...",
      "author": "...",
      "time": "...",
      "like_count": 10,
      "comment_count": 5,
      "repost_count": 2,
      "source": "xueqiu",
      "_track": "featured",
      "is_repost": false
    }
  ],
  "gate_stats": {"keep": 3, "demote": 5, "discard": 12},
  "fetched_at": "2026-06-02T12:00:00"
}
```

### 2. `scripts/run_黑芝麻智能.py`（修改）

去掉所有 CDP 启动和 `input()` 交互逻辑：
- 步骤1：加载雪球数据
  - 尝试读取 `data/raw/xueqiu_data_{date}_黑芝麻智能.json`
  - 存在则使用，不存在则回退到 `fetch_all_stocks(use_xueqiu=False)`（东财）
  - 不再启动 Chrome
- 步骤2~5：知乎采集 → 保存 → 报告生成 → PDF（保持现有逻辑）

### 3. `scripts/utils/fetcher.py`（不变，复用）

`XueqiuFetcher`、`EastmoneyFetcher`、`fetch_all_stocks` 保持不变。`fetch_xueqiu.py` 直接导入使用。

### 4. `scripts/utils/stock_reporter.py`（不变，复用）

`KnowledgeSynthesizer` 已支持多源输入，`XueqiuAdapter` 和 `ZhihuAdapter` 并存。雪球数据经 `SourceAdapter.to_synthesis_item()` 统一为 `SynthesisItem`，与知乎数据一起按主题聚类合成报告三~七模块。

### 5. `knowledge/10-Stocks/`（Obsidian Vault）

精品帖子的详情页全文以 Markdown + YAML frontmatter 格式写入，供报告模块引用或二次精读。

## 数据流

```
fetch_xueqiu.py:
  XueqiuFetcher.fetch_stock_posts() → featured/sentiment 双轨
  → ContentQualityGate（粗筛）
  → json dump → data/raw/xueqiu_data_{date}_{stock}.json
  → featured 详情页正文 → knowledge/10-Stocks/{stock}/posts/*.md

run_*.py:
  load json → stocks_data
  → ZhihuCollector.collect() → zhihu_data
  → PerStockReporter(stocks_data=stocks_data, raw_data={stock: {zhihu: zhihu_data}})
  → SourceAdapter 统一转换（雪球 + 知乎 → SynthesisItem 列表）
  → KnowledgeSynthesizer → 报告三~七模块
```

## 关键不变点

- `KnowledgeSynthesizer` 的输入始终是 `List[SynthesisItem]`，不关心来源
- 报告结构（一~九模块）不变
- 东财保底机制保留：无雪球数据时仍可用东财生成报告

## 边界情况

| 场景 | 行为 |
|------|------|
| 雪球数据文件不存在 | 回退到东财抓取 |
| 雪球抓取 0 条 | 回退到东财 |
| 雪球 featured 为空 | sentiment 仍可用于情绪分析 |
| 用户未登录雪球 | `fetch_xueqiu.py` 提示后退出，不写入数据 |
| 报告脚本反复运行 | 直接读缓存的 json，不重新抓取 |

## 文件清单

| 操作 | 文件 |
|------|------|
| 新建 | `scripts/fetch_xueqiu.py` |
| 修改 | `scripts/run_黑芝麻智能.py`（去掉CDP交互） |
| 复用（不变） | `scripts/utils/fetcher.py` |
| 复用（不变） | `scripts/utils/stock_reporter.py` |
| 复用（不变） | `scripts/utils/source_adapter.py` |
| 复用（不变） | `scripts/utils/content_quality.py` |
