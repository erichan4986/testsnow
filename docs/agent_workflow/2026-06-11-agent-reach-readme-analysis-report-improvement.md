# Agent-Reach README 解读与报告改进方案

## 背景

Agent-Reach 实际能力远超当前 repo 中的配置。根据官方 README，它支持 **15+ 平台**，且多个平台（微信公众号、微博、雪球、YouTube、RSS、全网搜索）是**无需配置、装好即用**的。当前 `_AGENT_REACH_COMMANDS` 只配置了 5 个平台，严重浪费了其能力。

---

## Agent-Reach 完整平台能力速览

| 平台 | 状态 | 配置需求 | 核心能力 | 对股票研究的价值 |
|------|------|----------|----------|-----------------|
| **微信公众号** | 无需配置 | 零配置 | 搜索+阅读全文（Markdown） | **极高** — A 股/港股深度分析核心信源 |
| **雪球** | 需配置 | 告诉 Agent「帮我配雪球」 | 股票行情、搜索股票、热门帖子、热门排行 | **极高** — 现有 CDP 方案的替代或补充 |
| **微博** | 无需配置 | 零配置 | 热搜、搜索内容/用户/话题、用户动态、评论 | **中高** — 情绪面监测、热点追踪 |
| **YouTube** | 无需配置 | 零配置 | 视频搜索 + 字幕提取（yt-dlp） | **中高** — 海外机构分析、行业会议、竞品动态 |
| **全网搜索(Exa)** | 自动配置 | MCP 接入，免费免 Key | AI 语义搜索，跨平台聚合 | **中高** — 补充信息缺口，发现非 obvious 来源 |
| **RSS** | 无需配置 | 零配置 | 订阅任意 RSS/Atom 源 | **中** — 行业媒体、券商 RSS 自动化 |
| **Bilibili** | 本地可用 | 服务器需代理 | 字幕提取 + 搜索 + 热门排行 | **中** — 行业科普、产品评测、技术解析 |
| **Twitter/X** | 需配置 | Cookie（建议小号） | 搜索推文、读时间线、读长文 | **中** — 港股/美股海外讨论、机构观点 |
| **GitHub** | 公开仓库可用 | 私有需 gh auth | 仓库搜索、读 issue/PR、趋势追踪 | **中低** — 技术公司代码动态、开源项目进展 |
| **Reddit** | 需登录 | `rdt login` Cookie | 搜索帖子、读评论 | **低** — 中文股票讨论极少 |
| **小红书** | 需配置 | Cookie（建议小号） | 搜索笔记、读详情、评论 | **低** — 股票讨论内容质量差 |
| **抖音** | 需配置 | 告诉 Agent「帮我配抖音」 | 视频解析、无水印下载 | **低** — 股票相关内容极少 |
| **LinkedIn** | 公开页可用 | Profile 需配置 | 读公开页面、公司动态 | **低** — 港股公司页面信息有限 |
| **V2EX** | 无需配置 | 零配置 | 热门帖子、节点帖子、详情+回复 | **低** — 技术社区，股票讨论少 |
| **网页读取** | 无需配置 | 零配置 | Jina Reader 读任意 URL | **中** — 解析研报链接、公告原文 |

> 来源：[Agent-Reach README — 支持的平台](https://github.com/Panniantong/Agent-Reach)

---

## 当前代码与 Agent-Reach 能力的差距

### 1. 平台配置严重不足

`agent_reach_skill.py:25-31` 当前只映射了 5 个平台：

```python
_AGENT_REACH_COMMANDS = {
    "twitter": ["agent-reach", "search", "twitter"],
    "reddit": ["agent-reach", "search", "reddit"],
    "bilibili": ["agent-reach", "search", "bilibili"],
    "wechat": ["agent-reach", "search", "wechat"],
    "xiaohongshu": ["agent-reach", "search", "xiaohongshu"],
}
```

**缺失的关键平台**：
- **雪球** — README 明确支持，但代码中完全未配置
- **微博** — 无需配置，零成本接入
- **YouTube** — 无需配置，字幕提取对行业研究极有价值
- **RSS** — 可以订阅预设的行业 RSS 源
- **全网搜索(Exa)** — 免 Key AI 语义搜索，可替代部分手动信息搜集
- **GitHub** — 技术公司（如黑芝麻）的开源代码动态
- **网页读取** — Jina Reader 可以解析任意 URL，补充现有 fetcher

### 2. 查询策略过于单一

`agent_reach_query_skill.py:32-38` 的 5 个基础查询对所有平台一视同仁：

```python
base_queries = [
    ("{stock_name} 产品进展", "产品/技术进展"),
    ("{stock_name} 量产", "量产/商业化"),
    ("{stock_name} 客户 定点", "客户定点/订单"),
    ("{stock_name} 竞争对手", "竞争格局"),
    ("{stock_name} 财报 业绩", "财报/业绩"),
]
```

**问题**：
- Twitter/Reddit 应该用英文搜索（`Black Sesame Technologies` 而非 `黑芝麻智能`）
- YouTube 应该搜索行业关键词而非个股名称
- 雪球/微博/微信公众号的搜索策略应该差异化
- 没有利用 Exa 的全网语义搜索能力

### 3. 适配器字段覆盖不全

`AgentReachAdapter` 只处理了通用字段（`title, content, summary, text, author`），但 Agent-Reach 不同上游工具的返回结构差异很大：

- **YouTube**: 可能返回 `subtitles`（字幕文本）、`duration`、`channel`、`upload_date`
- **RSS**: 可能返回 `description`、`categories`、`enclosures`
- **雪球**: 可能返回 `stock_code`、`view_count`、`like_count`
- **GitHub**: 可能返回 `stars`、`language`、`updated_at`
- **网页**: Jina Reader 返回的是清洗后的 Markdown 全文

当前适配器把 YouTube 字幕和雪球帖子当成同一种内容处理，会丢失关键元数据。

### 4. 缺少平台级诊断和降级

README 提供了 `agent-reach doctor` 来检查各渠道状态，但当前代码中没有调用它。如果某个平台（如 Twitter）因为 Cookie 过期而不可用，当前代码会静默失败或返回 `error`，但没有区分是"平台本身不可用"还是"搜索无结果"。

---

## 报告改进方案

### 方案一：扩展平台配置（高优先级）

在 `agent_reach_skill.py` 的 `_AGENT_REACH_COMMANDS` 中补充 Agent-Reach 支持的所有平台：

```python
_AGENT_REACH_COMMANDS: Dict[str, List[str]] = {
    # 现有 5 个
    "twitter": ["agent-reach", "search", "twitter"],
    "reddit": ["agent-reach", "search", "reddit"],
    "bilibili": ["agent-reach", "search", "bilibili"],
    "wechat": ["agent-reach", "search", "wechat"],  # 微信公众号
    "xiaohongshu": ["agent-reach", "search", "xiaohongshu"],
    # 新增 — 无需配置/低配置平台
    "weibo": ["agent-reach", "search", "weibo"],     # 微博
    "xueqiu": ["agent-reach", "search", "xueqiu"],   # 雪球
    "youtube": ["agent-reach", "search", "youtube"], # YouTube
    "github": ["agent-reach", "search", "github"],   # GitHub
    "rss": ["agent-reach", "search", "rss"],         # RSS
    "web": ["agent-reach", "read"],                  # 网页读取
    # 全网搜索通过 Exa MCP，可作为通用 channel
    "exa_search": ["agent-reach", "search"],         # 全网语义搜索
}
```

**注意**：新增平台需要先在本地运行 `agent-reach doctor` 验证可用性，再实际接入 pipeline。

### 方案二：按平台差异化查询（高优先级）

重写 `generate_agent_reach_queries`，按平台生成不同的搜索策略：

| 平台组 | 搜索策略 | 示例查询 |
|--------|----------|----------|
| **中文社交平台**（雪球、微博、微信公众号、B站） | 中文个股名称 + 业务关键词 | `黑芝麻智能 量产`、`黑芝麻 客户定点` |
| **海外社交平台**（Twitter、Reddit） | 英文公司名/股票代码 + 行业关键词 | `Black Sesame Technologies autonomous driving`、`02533 HK stock` |
| **视频平台**（YouTube、Bilibili） | 行业关键词 + 公司名 | `黑芝麻智能 智驾芯片`、`Black Sesame auto chip analysis` |
| **全网搜索**（Exa） | 语义搜索，更开放的问题 | `黑芝麻智能 2026 量产进展 客户定点`、`地平线 vs 黑芝麻 市场份额` |
| **GitHub** | 技术关键词 + 公司/产品名 | `Black Sesame chip driver`、`华山芯片` |
| **RSS** | 不搜索，直接订阅预设源 | 订阅行业媒体 RSS（如 36氪、半导体行业观察） |

具体实现：把 `target_platforms` 从统一列表改为按查询类型分配：

```python
# 中文社区查询 — 面向雪球、微博、微信公众号、B站
{
    "query": f"{stock_name} 量产 交付",
    "target_platforms": ["xueqiu", "weibo", "wechat", "bilibili"],
    "rationale": "中文社区产品/量产讨论",
}

# 海外查询 — 面向 Twitter、Reddit
{
    "query": f"Black Sesame Technologies {code} autonomous chip",
    "target_platforms": ["twitter", "reddit"],
    "rationale": "海外社区技术/投资讨论",
}

# 视频分析 — 面向 YouTube、Bilibili
{
    "query": f"{stock_name} 智驾芯片 分析",
    "target_platforms": ["youtube", "bilibili"],
    "rationale": "视频平台行业分析",
}

# 全网语义搜索
{
    "query": f"{stock_name} 2026 最新进展 客户 竞争",
    "target_platforms": ["exa_search"],
    "rationale": "全网语义搜索补充",
}
```

### 方案三：增强 AgentReachAdapter（中优先级）

按平台类型扩展适配器，保留关键元数据：

```python
class AgentReachAdapter:
    @staticmethod
    def to_synthesis_item(raw: Dict) -> SynthesisItem:
        platform = raw.get("_platform", "") or raw.get("platform", "")
        source_platform = f"AgentReach({platform})"

        # 平台特定内容提取
        content = _extract_content_by_platform(raw, platform)

        # 平台特定互动分计算
        interaction_score = _extract_interaction_by_platform(raw, platform)

        # 平台特定元数据
        extra = {"raw": raw, "platform": platform}
        if platform == "youtube":
            extra["duration"] = raw.get("duration", "")
            extra["channel"] = raw.get("channel", "")
            extra["subtitles_language"] = raw.get("language", "")
        elif platform == "xueqiu":
            extra["stock_code"] = raw.get("stock_code", "")
            extra["view_count"] = raw.get("view_count", 0)
        elif platform == "github":
            extra["stars"] = raw.get("stars", 0)
            extra["language"] = raw.get("language", "")

        return SynthesisItem(...)
```

### 方案四：接入 YouTube 字幕提取（中优先级）

对港股/半导体研究，YouTube 字幕的价值被严重低估：

- **海外机构分析师观点**：如 Morgan Stanley、Goldman Sachs 的半导体行业报告视频
- **财报电话会议**：港股公司财报会常有 YouTube 直播/录播
- **行业会议**：CES、Auto Shanghai 等展会的技术演讲
- **竞品动态**：Mobileye、NVIDIA 的产品发布会

实现方式：Agent-Reach 内部使用 `yt-dlp --write-sub --skip-download` 提取字幕，返回纯文本。适配器把字幕内容放入 `content` 字段，视频标题放入 `title`，频道名放入 `author`。

### 方案五：RSS 订阅行业媒体（中优先级）

在 `agent_reach_query_skill.py` 中增加 RSS 源配置：

```python
_RSS_SOURCES: Dict[str, List[str]] = {
    "半导体": [
        "https://www.36kr.com/feed",
        "https://www.cls.cn/rss",
    ],
    "智能驾驶": [
        "https://www.autonews.com/feed",
    ],
}
```

Agent-Reach 的 RSS channel 使用 `feedparser` 解析，返回结构化数据。可以在报告中增加"行业 RSS 动态"板块。

### 方案六：雪球双轨采集（需谨慎）

Agent-Reach 支持雪球，但当前项目已有 `fetcher.py` + CDP 的成熟方案。**不建议直接替换**，建议：

1. **对比测试**：同一时间段，用 Agent-Reach 抓雪球 vs 现有 CDP 方案，对比数据质量和稳定性
2. **如果 Agent-Reach 更稳定**：逐步迁移，复用现有缓存逻辑
3. **如果 CDP 更好**：保持现有方案，Agent-Reach 的雪球 channel 作为备用/补充
4. **关键约束**：无论用哪种方案，都必须遵守 AGENTS.md 的雪球限制（用户登录、3-5 秒间隔、优先列表页）

---

## 接入优先级路线图

| 阶段 | 平台 | 理由 | 预计工作量 |
|------|------|------|-----------|
| **Phase 1** | 微信公众号、微博 | 无需配置，零成本，高价值 | 2-3 天 |
| **Phase 2** | YouTube 字幕、全网搜索(Exa) | 无需配置，补充海外/跨平台信息 | 3-4 天 |
| **Phase 3** | RSS 订阅、Bilibili | 增强行业媒体覆盖 | 2-3 天 |
| **Phase 4** | Twitter/X（小号）、GitHub | 需要配置 Cookie/gh auth | 3-4 天 |
| **Phase 5** | 雪球（对比评估） | 与现有 CDP 方案对比后再决定 | 2-3 天 |
| **Do not** | 小红书、抖音、LinkedIn、V2EX | 股票内容质量低，不值得投入 | — |

---

## 风险与约束

### Cookie 安全
- 需要 Cookie 的平台（Twitter、小红书、雪球），README 明确建议**使用专用小号**
- Cookie 存储在本地 `~/.agent-reach/config.yaml`，权限 600，不上传

### 封号风险
- Twitter/X：小号 + 低频控制（与现有 60s 预算兼容）
- 小红书：内容质量低，建议不接
- 雪球：如果 Agent-Reach 内部也是 Playwright/CDP，封号风险与现有方案相当

### 速率限制
- 保持现有 `PER_STOCK_BUDGET=60s`、`PER_COMMAND_TIMEOUT=30s`、`PER_QUERY_CAP=10` 的防御策略
- Agent-Reach 内部的上游工具（yt-dlp、twitter-cli 等）可能有自己的节流，需要实测

### 数据质量
- YouTube 字幕：需要过滤掉无关视频（音乐、娱乐），可以通过 `channel` 元数据过滤
- RSS：需要按行业分类，避免噪音
- Exa 搜索：AI 语义搜索可能返回相关性不高的结果，需要通过 quality gate 过滤

---

## 立即行动建议

1. **安装 Agent-Reach CLI**：
   ```bash
   pip install agent-reach
   agent-reach install
   agent-reach doctor
   ```

2. **跑 doctor 确认平台可用性**，特别关注：
   - 微信公众号、微博是否"无需配置"即可工作
   - YouTube 字幕提取是否正常
   - Exa 搜索（MCP）是否免 Key 可用
   - 雪球 channel 需要什么配置

3. **小规模测试**：对每个候选平台跑 10-20 次搜索，记录：
   - 返回数据格式（与当前 `_parse_records()` 是否兼容）
   - 平均响应时间
   - 失败率
   - 数据质量（随机抽样 10 条评估相关性）

4. **按 Phase 1 开始接入**：先接微信公众号和微博（零配置），验证端到端 pipeline。

---

## 来源

- [Agent-Reach GitHub README](https://github.com/Panniantong/Agent-Reach)
- [Agent-Reach English README](https://github.com/Panniantong/Agent-Reach/blob/main/docs/README_en.md)
- [Agent-Reach Skill Documentation](https://github.com/Panniantong/Agent-Reach/blob/main/agent_reach/skill/SKILL.md)
