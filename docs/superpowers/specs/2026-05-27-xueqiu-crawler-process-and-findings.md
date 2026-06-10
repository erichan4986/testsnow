# 雪球网爬虫流程复盘与问题分析

> 日期：2026-05-27
> 相关股票案例：乐鑫科技、圣邦股份

---

## 一、当前爬虫完整流程

### Stage 1: 列表页采集

Playwright 连接用户已登录的 Chrome CDP，执行以下步骤：

1. 打开 `https://xueqiu.com/S/{stock_code}`
2. 点击「讨论」tab
3. 点击「热门排序」tab
4. 翻页浏览，最多 15 页，每页最多提取 100 条帖子
5. 从 DOM 中解析每篇帖子的：
   - 作者名（`a.user-name`）
   - 发布时间（`a.date-and-source`）
   - **标题 + 摘要**（`article` 文本内容，通常是 truncated）
   - 互动数（赞/评论/转发，从 Unicode PUA 图标字体中提取数字）
   - 帖子 URL
   - 是否转发（检测 `blockquote` 元素）

**关键注意点**：
- 雪球列表页只显示帖子的 **truncated 摘要**（以 `...` 结尾）
- 部分帖子开头使用模板话术，导致不同帖子的列表页摘要看起来完全一样
- 互动数通过 JavaScript 从页面文本中反向提取数字，需要排除股票代码（`$688018$`、`(SH688018)` 等模式）

### Stage 2: 双轨分流（质量门）

`content_quality.py` 实现准入制：

**featured 候选池准入**（满足任一条件即可）：
- **条件 A**：内容以 `...` 结尾（暗示长文被截断） + 含数据（`\d+%`、金额、数量等） + 含逻辑词（因为、所以、如果、因此等）
- **条件 B**：正文长度 >= 100 字 + 互动数 > 10

**sentiment 池**：不满足上述条件的帖子，仅参与情绪统计，**不进 Vault，不进报告精品帖板块**。

候选池内按 `content_score` 质量分排序（6 个维度：截断标识 +3、数据 +2、逻辑词 +2、关键词 +1、互动分级、长度/100 最高 +3）。

### Stage 3: 详情页提取

对 featured 候选中质量分 Top N（默认 10 条）的帖子：

1. 在新标签页打开帖子 URL
2. 尝试 `domcontentloaded` 策略（30s 超时），失败则回退到 `networkidle`（60s 超时）
3. 等待 `article` 元素出现（最多 10s）
4. 提取：完整正文（所有 `<p>` 段落拼接）+ 评论（最多 10 条）
5. **二次过滤**：详情页正文 < 60 字 → 降级为 sentiment

提取成功的帖子保存到 Obsidian Vault：`knowledge/10-Stocks/{stock_name}/posts/{post_id}.md`

### Stage 4: 报告生成时的三次过滤

`stock_reporter.py` 在生成「精品帖子深度解读」板块时执行额外过滤：

1. **Vault 读取**：尝试从 Vault 读取完整正文，正文 < 80 字或包含雪球 footer 垃圾内容（`tousu@xueqiu.com`、`京ICP备` 等）→ 丢弃
2. **口号检测** (`_detect_slogan_content`)：
   - < 120 字且无数据无逻辑 → 标记为口号
   - 感叹号/问号密度 > 3% 且无数据无逻辑 → 标记为口号
   - 包含 3 个以上极端断言词（绝对、必然、暴涨等）且无数据 → 标记为口号
3. **LLM 负面过滤**：调用 JudgmentGenerator 自动生成判断，如果 LLM 判定「论据扎实程度极低」「不具备分析价值」等 → 跳过该帖子不进入报告

---

## 二、乐鑫科技案例分析

### 2.1 实际爬取数据（2026-05-27）

共 10 条帖子，4 条进入 featured，6 条 sentiment：

| 作者 | 互动 | 列表页内容长度 | 详情页状态 | 问题 |
|------|------|----------------|------------|------|
| 股市小白703 | 295 | 62 字 | featured | 列表页摘要极短，即使进详情页大概率仍是短内容 |
| 分析仪 | 32 | 609 字 | featured + Vault | ✅ 真正的高质量分析帖 |
| Miravoss | 59 | 337 字 | featured + Vault | ✅ 有观点有逻辑 |
| 乐鑫科技(官方) | 64 | 756 字 | featured + Vault | ✅ 官方内容，偏 PR |
| 分析仪 | 6024 | 64 字 | sentiment | cardputer 预售快讯，纯消息播报 |
| 和颜的基金小观测员 | 46 | 79 字 | sentiment | 量化控盘吐槽，情绪发泄 |
| 分析仪 | 401 | 74 字 | sentiment | 众筹数据播报 |
| 猫头鹰学徒 | 61 | 84 字 | sentiment | 量化抱怨 |
| 沙漠 1988 | 29 | 47 字 | sentiment | 口号式看多（"欠一个 20cm 涨停"） |
| 沙迦 | 60 | 57 字 | sentiment | 口号式看多 |

### 2.2 Vault 存量

乐鑫 Vault 中仅 **1 篇**帖子（`387639520.md`），且内容存在断行问题（每句话被拆成多行，标点单独成行）。

圣邦 Vault 中有 **5 篇**帖子，质量参差不齐（包含大量口号式看多帖）。

### 2.3 报告输出效果

乐鑫报告中的「精品帖子深度解读」板块：
- 3.1 分析仪：609 字长文，LLM 判断「论据扎实程度中等」，保留
- 3.2 Miravoss：337 字，LLM 判断「论据扎实程度较低」，但仍保留（因为没有触发负面关键词过滤）

**问题**：Miravoss 的帖子被 LLM 判定为「论据扎实程度较低」，但仍然进入了报告。这说明三次过滤中的 LLM 负面过滤是**关键词匹配**而非**置信度阈值**。

---

## 三、根因分析

### 问题 1：列表页摘要 = 正文（短内容无法区分）

雪球列表页对短帖直接显示全文，对长帖显示 truncated 摘要（以 `...` 结尾）。当前代码中：

- `title` = `content.substring(0, 80) + '...'`（强制截断到 80 字）
- `content` = 列表页提取的文本

这意味着：**即使帖子原文只有 50 字，它的 `title` 也会以 `...` 结尾**，可能被条件 A 误识别为「看起来像长文」。

### 问题 2：股票级社区质量未被评估

当前流程是「帖子级」过滤，没有「股票级」评估。如果某只股票的社区本身就没有深度讨论（如乐鑫），过滤后仍然会产出「精品帖子深度解读」板块，只是内容质量不高。

### 问题 3：Vault 污染

详情页提取的帖子即使后来被报告生成阶段过滤掉（如 LLM 判定低质量），它们仍然保存在 Vault 中，造成知识库污染。

### 问题 4：断行内容未正确处理

Vault 中部分帖子（如 `387639520.md`）存在严重的断行问题——每句话被拆成多行，标点符号单独成行。当前 `_extract_argument_chain` 虽有断行检测逻辑（平均行长度 < 15 时重建段落），但 Vault 读取后的正文未经过该处理。

---

## 四、改进方案

### 方案 A：提高准入门槛（快速修复）

调整 `content_quality.py`：
- 条件 B：正文长度从 >= 100 字 → >= **200** 字，互动数 > 10
- 增加条件 C：内容以 `...` 结尾时，必须同时满足正文长度 >= **150** 字（防止短帖被 `title` 的强制 `...` 误触发条件 A）

调整 `fetcher.py`：
- 二次过滤：详情页正文 < 60 字 → < **150** 字才降级

### 方案 B：股票级质量评估（推荐）

在 `fetch_stock_posts` 返回前增加股票级评估：

```python
# 伪代码
featured_posts = result["featured"]
avg_content_len = sum(len(p["content"]) for p in featured_posts) / len(featured_posts)

if len(featured_posts) < 3 or avg_content_len < 150:
    logger.warning(f"[{stock_name}] 社区讨论质量不足，清空 featured，全部降为 sentiment")
    result["sentiment"].extend(featured_posts)
    result["featured"] = []
```

**效果**：如果整只股票都没什么好内容，直接跳过，报告中显示「*本期无高质量分析帖*」，Vault 中不保存任何帖子。

### 方案 C：列表页摘要识别（从源头过滤）

在 `_extract_posts_from_page` 阶段识别「这明显是 truncated 摘要」：

```python
# 伪代码
# 如果 content 以 "..." 结尾且长度 < 150，说明列表页只展示了摘要
# 此时不应仅凭条件 A 的 has_truncation 就放入 featured
# 需要额外满足：has_data + has_logic_words + (content_len >= 80)
```

### 方案 D：Vault 写入前过滤

在 `ObsidianWriter` 或 `fetcher.py` 中，详情页提取成功后、写入 Vault 前，增加过滤：

```python
# 伪代码
if len(detail_content) < 150 or is_slogan_content(detail_content):
    logger.info(f"详情页内容质量不足，不写入 Vault: {title}")
    # 降级为 sentiment，不保存到 Vault
```

### 方案 E：LLM 负面过滤升级

当前 LLM 过滤是关键词匹配（"论据扎实程度极低"等）。建议改为置信度评分：

```python
# 伪代码
# 在 _get_llm_judgment 返回的判断文本中，要求 LLM 给出一个 1-5 分的论据质量评分
# 评分 < 2 分的帖子不进入报告
```

---

## 五、待验证假设

1. **乐鑫科技是否为个例？** 其他股票（黑芝麻智能、长春高新、三花智控、中简科技）的社区讨论质量是否也面临同样问题？
2. **详情页超时失败的根因？** 乐鑫 Vault 中只有 1 篇帖子，大量详情页提取可能超时失败，需要增加重试机制或排查超时原因。
3. **LLM 过滤的召回率？** 当前 LLM 负面过滤是否能有效拦截低质量帖子，还是存在漏报/误报？

---

---

## 六、知乎与全网搜索优化方向（待实现）

### 方向 1：补齐 ZhihuCurator（优先实现）

设计文档：`docs/superpowers/specs/2026-05-24-zhihu-content-curation-design.md`

目标：将当前「简单列表展示」升级为「AI 质量评估 + 深度摘要 + 逻辑链呈现」。

核心改动：
1. 新增 `scripts/utils/zhihu_curator.py` — DeepSeek 批量质量评估（5条/批次）
2. 修改 `scripts/utils/data_collector.py` — `ZhihuCollector.collect()` 返回前调用 curator
3. 修改 `scripts/utils/stock_reporter.py` — `_zhihu_section()` 渲染摘要+逻辑链+判断

### 方向 2：接入全网搜索（扩大数据源）

当前知乎 API 日限额 1000 次，内容池有限。可考虑接入：
- **Tavily / SerpAPI / Bing Web Search API** — 通用网页搜索
- **微信公众号文章搜索** — 国内深度分析的重要来源
- **雪球专栏搜索** — 与现有雪球帖子形成互补（专栏是长文）

待评估：API 成本、内容解析复杂度、与现有 Vault 的整合方式。

### 方向 3：股票级搜索策略（个性化）

不同股票应搜索不同的关键词组合和关注博主：
- 圣邦股份 → 「模拟芯片」「国产替代」「杰华特」
- 乐鑫科技 → 「端侧 AI」「RISC-V」「ESP32」「物理 AI」
- 长春高新 → 「生长激素」「集采」「特宝生物」

当前 `demo_shengbang.py` 中手动传 `keywords=[