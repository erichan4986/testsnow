# Agent-Reach 基本面项目信息搜索集成设计

> **目标**：将 Agent-Reach 的多平台搜索能力（Twitter/X、Reddit、Bilibili、微信文章等）集成到现有股票深度分析 Pipeline 中，补充基本面分析中缺失的**项目进展、产品动态、竞品情报**维度。

**架构思路**：复用现有基础设施（`SynthesisItem`、`ContentQualityGate`、`ZhihuCurator`、`ContentConsolidator`、`KnowledgeSynthesizer`），在 Pipeline 中插入两个新 Skill（Query Generation + Agent-Reach Fetching），最小侵入现有代码。

---

## 1. 现有基础设施复用清单

| 现有组件 | 复用方式 | 改动点 |
|---------|---------|--------|
| `SynthesisItem` (source_adapter.py) | Agent-Reach 各平台原始数据 → `SynthesisItem` | 新增 `TwitterAdapter`、`RedditAdapter`、`BilibiliAdapter`、`WechatAdapter` |
| `ContentQualityGate` | 扩展 `process_xueqiu_posts()` 为通用 `process_items()` | 硬指标规则增加平台权重（研报 > Twitter > Reddit） |
| `ZhihuCurator` | 直接复用三层漏斗处理 Agent-Reach 内容 | 无改动，输入格式已是 `SynthesisItem` |
| `ContentConsolidator` | 跨源聚类自动包含 Agent-Reach 内容 | 无改动，LLM topic extraction 自动识别新主题 |
| `KnowledgeSynthesizer` | 现有 5 主题 + 新增第 6 主题 "project_intelligence" | 新增主题 prompt，或复用 "事件" 主题 |
| `DeepAnalysisRenderer` | 新增 "项目动态与产品进展" 子板块 | 读取 `stock_raw["project_intelligence"]` |

---

## 2. 新增模块

### 2.1 QueryGenerationSkill

**职责**：调用 LLM，根据股票属性生成 6-8 个精准搜索关键词。

**输入**（来自 `SkillContext`）：
- `stock_name`: str
- `code`: str
- `industry`: str（来自 `quote` 或 `INDUSTRY_MAP`）
- `competitors`: list[str]（来自 `COMPETITOR_MAP`）
- `market`: str（"A股"/"港股"）

**输出**：写入 `SkillContext`
- `search_queries`: list[dict]，每项含 `query`, `target_platforms`, `rationale`

**缓存策略**：
- 缓存路径：`knowledge/10-Stocks/{stock_name}/search_queries.json`
- 缓存键：`{stock_name}_{code}_{date}`
- 有效期：7 天
- 过期后重新生成，未过期直接读取缓存

**LLM Prompt 核心要求**：
- 覆盖 4 个维度：产品/R&D 进展、竞争对手动态、行业趋势、公司官方动态
- 关键词具体化，避免过于宽泛
- 按优先级排序
- 输出严格 JSON 数组格式

**降级策略**：
- LLM 调用失败 → 使用预定义默认关键词模板（基于行业类型匹配）
- 无行业信息 → 只生成 "{stock_name} 最新动态"、"{stock_name} 产品" 等通用关键词

### 2.2 AgentReachFetchingSkill

**职责**：调用 Agent-Reach CLI，执行搜索，将原始结果适配为 `SynthesisItem`。

**输入**：
- `search_queries`: list[dict]（来自 QueryGenerationSkill）
- `code`: str

**输出**：写入 `SkillContext`
- `agent_reach_items`: list[SynthesisItem]

**Agent-Reach CLI 调用映射**：

| 平台 | CLI 命令 | 输入参数 | 输出格式 |
|------|---------|---------|---------|
| Twitter/X | `xreach search "{query}" --limit 10` | 搜索词 | JSON lines |
| Reddit | `agent-reach reddit search "{query}" --limit 10` | 搜索词 | JSON lines |
| Bilibili | `yt-dlp "ytsearch10:{query}" --dump-json` | 搜索词 | JSON array |
| 微信文章 | `agent-reach wechat search "{query}" --limit 5` | 搜索词 | JSON lines |
| 小红书 | `mcporter search "{query}" --limit 5` | 搜索词 | JSON lines |

**搜索执行策略**：
1. 每个关键词在所有目标平台执行搜索
2. 单平台单关键词最多取 10 条结果
3. 同一只股票所有关键词的搜索结果去重（URL 维度）
4. 总结果数上限：100 条（防止数据爆炸）

**适配层**：各平台原始 JSON → `SynthesisItem`

```python
@dataclass
class SynthesisItem:
    source: str           # "twitter" / "reddit" / "bilibili" / "wechat" / "xiaohongshu"
    author: str
    title: str
    content: str          # 完整文本内容
    url: str
    publish_time: datetime
    extra: dict           # 平台特有字段（likes, comments, retweets, video_duration 等）
```

**超时与并发**：
- 单 CLI 调用超时：30 秒
- 单只股票总搜索时间上限：3 分钟
- 并发：同一关键词的不同平台搜索可并发（最多 3 个并行）

**降级策略**：
- Agent-Reach 未安装（`agent-reach doctor` 检测失败）→ 记录 warning，返回空列表
- 单个平台 CLI 调用失败 → 跳过该平台，继续其他平台
- 所有平台均失败 → 返回空列表，报告继续生成
- 报告头部标注："项目信息搜索未启用/失败"

---

## 3. Pipeline 集成

### 3.1 Skill 插入位置

```python
def build_stock_report_pipeline(llm_client=None) -> SkillPipeline:
    return SkillPipeline([
        data_loading_skill,
        query_generation_skill,        # ← 新增
        agent_reach_fetching_skill,    # ← 新增
        quality_gate_skill,            # ← 扩展（见 3.2）
        cross_source_consolidation_skill,  # ← 扩展（见 3.3）
        quote_fetching_skill,
        competitor_fetching_skill,
        technical_fetching_skill,
        TechnicalAnalysisSkill(),
        SynthesisSkill(llm_client=llm_client),
        scoring_skill,
        ChartGenerationSkill(),
        ReportAssemblySkill(),
    ])
```

### 3.2 QualityGateSkill 扩展

现有逻辑只处理雪球帖子：
```python
gate = ContentQualityGate()
results = gate.process_xueqiu_posts(all_posts)
```

扩展为通用入口：
```python
gate = ContentQualityGate()
all_items = xueqiu_items + zhihu_items + agent_reach_items
results = gate.process_items(all_items)
```

质量评分调整：
- 研报/深度分析：基础分 +20
- Twitter 官方账号：基础分 +10
- Twitter 普通用户：基础分 0
- Reddit 讨论：基础分 -5（噪音高）
- Bilibili 评测：基础分 +5

### 3.3 CrossSourceConsolidationSkill 扩展

无需代码改动。`ContentConsolidator.cluster()` 接收所有 `SynthesisItem`，LLM 自动提取 topic tags。

预期新增聚类主题示例（黑芝麻智能）：
- `"芯片量产进展"`：雪球研报 + Twitter 官方 + Bilibili 评测
- `"地平线竞争"`：知乎分析 + Reddit 讨论
- `"车企定点"`：微信文章 + Twitter 行业 KOL
- `"财报与经营"`：研报 + Reddit 讨论

---

## 4. 渲染层扩展

### 4.1 KnowledgeSynthesizer 第 6 主题

新增 `"project_intelligence"` 主题，prompt 设计：

```markdown
基于以下项目动态与产品进展信息，生成结构化分析：

要求：
1. 按时间线梳理最近的重要项目进展
2. 识别关键里程碑（量产、定点、合作、技术突破）
3. 评估项目进展对基本面的影响（正面/负面/待观察）
4. 标注信息来源平台（Twitter/Reddit/Bilibili/微信）
5. 指出信息矛盾点或待验证的传闻

输出格式：
- 项目进展时间线（最近 3 个月）
- 关键里程碑评估
- 对基本面的影响判断
- 风险提示（传闻/未证实信息）
```

### 4.2 DeepAnalysisRenderer 新增子板块

在 "4.2 业绩路径与多空分歧" 后新增 "4.3 项目动态与产品进展"：

```markdown
### 4.3 项目动态与产品进展

**项目进展时间线**：
- [日期] [事件描述]（来源：Twitter/Reddit/...）
- ...

**关键里程碑评估**：
| 里程碑 | 状态 | 可信度 | 影响 |
|--------|------|--------|------|
| ... | ... | ... | ... |

**对基本面的影响**：
[LLM 综合判断]

**风险提示**：
- [未证实传闻/信息矛盾点]
```

### 4.3 报告头部标注

如果 Agent-Reach 未启用或搜索失败，在报告头部添加：

```markdown
> **数据提醒**：项目信息搜索模块未启用（Agent-Reach 未安装或配置），本报告不包含社交媒体动态分析。
```

---

## 5. 数据流完整图示

```
┌─────────────────────────────────────────────────────────────────┐
│ Stock Name + Code                                               │
│   ↓                                                             │
│ QueryGenerationSkill (LLM / Cache)                              │
│   ↓                                                             │
│ search_queries: [{query, platforms, rationale}]                 │
│   ↓                                                             │
│ AgentReachFetchingSkill (subprocess CLI)                        │
│   ├── xreach search "..." → raw_tweets                          │
│   ├── agent-reach reddit search "..." → raw_posts               │
│   ├── yt-dlp "ytsearch:..." → raw_videos                        │
│   └── ...                                                       │
│   ↓                                                             │
│ PlatformAdapters (TwitterAdapter, RedditAdapter, ...)           │
│   ↓                                                             │
│ agent_reach_items: [SynthesisItem, ...]                         │
│   ↓                                                             │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │  merge with xueqiu_items + zhihu_items + report_items    │  │
│ │   ↓                                                       │  │
│ │ ContentQualityGate.process_items() → 过滤低质量          │  │
│ │   ↓                                                       │  │
│ │ ZhihuCurator (三层漏斗) → 精编                           │  │
│ │   ↓                                                       │  │
│ │ ContentConsolidator.cluster() → 跨源聚类                 │  │
│ │   ↓                                                       │  │
│ │ KnowledgeSynthesizer (6 主题) → 综合叙事                 │  │
│ └───────────────────────────────────────────────────────────┘  │
│   ↓                                                             │
│ DeepAnalysisRenderer → "4.3 项目动态与产品进展"                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. 错误处理与降级策略矩阵

| 场景 | 处理方式 | 报告表现 |
|------|---------|---------|
| Agent-Reach 未安装 | 跳过搜索，记录 warning | 报告头部提示 "项目信息搜索未启用" |
| 单个平台 CLI 失败 | 跳过该平台，其他平台继续 | 该平台内容缺失，不影响整体 |
| 所有平台 CLI 失败 | 返回空列表 | 同 "未安装" |
| LLM 生成关键词失败 | 使用默认关键词模板 | 搜索质量可能下降，但不中断 |
| 搜索超时（>3分钟） | 中断搜索，返回已获取结果 | 部分内容缺失 |
| 质量门过滤后无内容 | 继续 Pipeline，该维度为空 | 报告中 "项目动态" 板块显示 "暂无相关动态" |

---

## 7. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `scripts/utils/report_skills/query_generation_skill.py` | 新建 | LLM 关键词生成 + 缓存 |
| `scripts/utils/report_skills/agent_reach_skill.py` | 新建 | CLI 调用 + 适配 + 搜索编排 |
| `scripts/utils/source_adapter.py` | 修改 | 新增 TwitterAdapter、RedditAdapter、BilibiliAdapter、WechatAdapter |
| `scripts/utils/content_quality_gate.py` | 修改 | 扩展 `process_items()` 通用入口，调整平台权重 |
| `scripts/utils/report_skills/data_skills.py` | 修改 | `quality_gate_skill` 调用 `process_items()` |
| `scripts/utils/report_skills/__init__.py` | 修改 | Pipeline 插入两个新 skill |
| `scripts/utils/knowledge_synthesizer.py` | 修改 | 新增 "project_intelligence" 主题 |
| `scripts/utils/reporter/sections/deep_analysis_renderer.py` | 修改 | 新增 "4.3 项目动态与产品进展" 子板块 |
| `docs/superpowers/specs/2026-06-10-agent-reach-fundamental-research-design.md` | 新建 | 本文档 |

---

## 8. 性能与成本预估

| 项目 | 预估 |
|------|------|
| LLM 关键词生成 | 每次报告 1 次调用，~500 tokens，缓存后 7 天内 0 次 |
| Agent-Reach CLI 调用 | 6-8 关键词 × 3-4 平台 = 20-30 次 CLI 调用 |
| 单只股票总搜索时间 | 30-90 秒（并发） |
| 新增 SynthesisItem 数量 | 20-50 条（去重后） |
| 对报告生成总时长影响 | +30-90 秒 |
| 对 Pipeline 其他阶段影响 | 无，数据格式完全兼容 |

---

## 9. 验收标准

- [ ] Agent-Reach 未安装时，报告生成不失败，头部有提示
- [ ] 安装 Agent-Reach 后，Twitter/Reddit/Bilibili/微信内容出现在 "4.3 项目动态" 板块
- [ ] 同一项目进展（如芯片量产）在多个平台出现时，聚类去重后只出现一次
- [ ] 质量门正确过滤掉低质量社交噪音（纯表情、广告、无关内容）
- [ ] 关键词生成缓存生效，7 天内重复运行不重新调 LLM
- [ ] 港股/A股关键词生成策略一致（无需中英文双关键词）
