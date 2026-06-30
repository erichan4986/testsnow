# 股票报告生成仓库审计文档

> **审计日期**: 2026-06-10
> **审计范围**: /Users/erichan/testsnow（testsnow 股票舆情报告项目）
> **审计目的**: 为 Codex 接手后续开发提供全景上下文，不修改业务代码

---

## 1. 项目启动命令、测试命令、主要依赖

### 1.1 主要依赖

见 `requirements.txt`，共 11 个核心依赖：

| 依赖 | 用途 |
|------|------|
| `requests` | HTTP 请求（东财 API、腾讯财经、百度 PAE） |
| `python-dotenv` | 环境变量管理（API Key） |
| `openai` | LLM 调用（DeepSeek / Moonshot） |
| `playwright` | 雪球网浏览器采集（需手动登录） |
| `markdown` | Markdown 处理 |
| `mootdx` | A股 K线/财务/F10 数据（TCP 7709） |
| `stockstats` | 技术指标计算（RSI/MACD/BOLL/ATR/ADX/BIAS） |
| `akshare` | 研报/新闻/公告/资金流向/财务摘要 |
| `plotly` + `kaleido` | 图表生成（雷达图、牛熊图、估值对比图） |

### 1.2 项目启动命令

**主流程（每周手动运行）**：
```bash
cd scripts
python xueqiu_monitor_v2.py
# 带雪球采集（需 Chrome 已登录并开启 CDP）
python xueqiu_monitor_v2.py --xueqiu
```

**单股快速测试**：
```bash
cd scripts
python run_黑芝麻智能.py      # 或其他 run_*.py 文件
```

**单股技术形态分析（独立流程，不走主 pipeline）**：
```bash
cd scripts
python run_澜起科技技术分析_真实数据.py
```

### 1.3 测试命令

```bash
# 运行全部测试
pytest

# 或运行特定测试
pytest tests/reporter/test_pipeline_integration.py -v
pytest tests/reporter/test_technical_*.py -v
```

> 注意：当前测试覆盖度集中在技术形态模块（`tests/reporter/test_technical_*.py`），Pipeline 集成测试在 `tests/reporter/test_pipeline_integration.py`。

---

## 2. 入口文件在哪里

| 入口文件 | 用途 | 调用链路 |
|----------|------|----------|
| `scripts/xueqiu_monitor_v2.py` | **主入口**，每周运行一次 | 采集 → 分析 → 生成报告 → PDF导出 |
| `scripts/run_*.py`（6个文件） | 单股快速运行入口 | 直接构造 `PerStockReporter` 并生成报告 |
| `scripts/run_*技术分析_真实数据.py` | 纯技术形态分析股票专用入口（独立流程） | 不依赖主 pipeline；当前无统一通用 CLI |

**主流程调用链**（`xueqiu_monitor_v2.py`）：
```
main()
  ├── fetch_all_stocks()          # scripts/utils/fetcher.py
  ├── TechnicalCollector.collect() # scripts/utils/data_collector.py
  ├── ReportCollector.collect()    # scripts/utils/data_collector.py
  ├── AnnouncementCollector.collect()
  ├── FundFlowCollector.collect()
  ├── NewsCollector.collect()
  ├── FinancialAgent.analyze()     # scripts/utils/financial_agent.py
  ├── PerStockReporter.generate_all_reports()  # scripts/utils/stock_reporter.py
  │     └── build_stock_report_pipeline().run()  # scripts/utils/report_skills/__init__.py
  └── export_pdf()                 # scripts/utils/pdf_exporter.py
```

---

## 3. 核心逻辑分布在哪些文件

### 3.1 数据读取层

| 文件 | 职责 |
|------|------|
| `scripts/utils/fetcher.py` | 雪球帖子采集（列表页，Playwright） |
| `scripts/utils/data_collector.py` | 技术指标/研报/公告/资金流向/新闻采集（~1025行） |
| `scripts/utils/reporter/data_fetcher.py` | 实时行情/一致预期/财务摘要/竞争对手指标（~776行） |
| `scripts/utils/source_adapter.py` | 多源数据统一适配为 `SynthesisItem` |

### 3.2 指标计算层

| 文件 | 职责 |
|------|------|
| `scripts/utils/reporter/technical_indicators.py` | 基础指标计算（RSI/MACD/BOLL/ATR/ADX/BIAS等） |
| `scripts/utils/reporter/technical_structure.py` | 支撑/压力区、趋势结构、通道/箱体识别 |
| `scripts/utils/reporter/technical_patterns.py` | K线形态识别、蜡烛信号 |
| `scripts/utils/reporter/technical_state_machine.py` | 趋势状态机（健康度/失效条件） |
| `scripts/utils/reporter/technical_resonance.py` | 市场/板块共振分析 |
| `scripts/utils/reporter/price_target.py` | 目标价计算（zigzag + Fibonacci + 形态测量） |
| `scripts/utils/reporter/price_adjustment_validator.py` | 除权复权校验（raw/qfq/本地修复 三种状态） |

### 3.3 评分逻辑层

| 文件 | 职责 |
|------|------|
| `scripts/utils/reporter/scoring_engine.py` | 五维度评分（估值/技术/情绪/基本面/资金）+ EV期望模型 + 风险评分（~620行） |
| `scripts/utils/content_quality_gate.py` | 内容质量门（硬指标筛选 + LLM质量评估）（~645行） |

### 3.4 报告生成层

| 文件 | 职责 |
|------|------|
| `scripts/utils/skill_pipeline.py` | Pipeline 框架（SkillContext + BaseSkill + @skill 装饰器） |
| `scripts/utils/report_skills/__init__.py` | Pipeline 组装（11 个 skill 的顺序编排） |
| `scripts/utils/report_skills/data_skills.py` | 数据加载/质量门/行情获取/竞争对手获取 |
| `scripts/utils/report_skills/synthesis_skills.py` | LLM 综合叙事生成（5 主题） |
| `scripts/utils/report_skills/chart_skills.py` | 图表生成 skill（技术面/雷达/牛熊/估值对比） |
| `scripts/utils/report_skills/assembly_skills.py` | Markdown + HTML 报告组装 |
| `scripts/utils/stock_reporter.py` | `PerStockReporter` 外观类，协调 pipeline |

### 3.5 渲染层（SectionRenderers）

| 文件 | 职责 |
|------|------|
| `scripts/utils/reporter/sections/executive_summary_renderer.py` | 执行摘要 |
| `scripts/utils/reporter/sections/composite_score_renderer.py` | 综合评分与推荐 |
| `scripts/utils/reporter/sections/valuation_renderer.py` | 估值分析 |
| `scripts/utils/reporter/sections/technical_renderer.py` | 技术面分析（~748行，支持 compact/full/legacy 模式） |
| `scripts/utils/reporter/sections/price_target_renderer.py` | 价格目标分析 |
| `scripts/utils/reporter/sections/deep_analysis_renderer.py` | 深度分析（核心事实 + 3 个子板块） |
| `scripts/utils/reporter/sections/risk_renderer.py` | 风险评分 |
| `scripts/utils/reporter/sections/html_dashboard_renderer.py` | HTML Dashboard |

### 3.6 知识沉淀层

| 文件 | 职责 |
|------|------|
| `scripts/utils/knowledge_synthesizer.py` | 5 主题 LLM 合成 + 核心事实提取（~372行） |
| `scripts/utils/obsidian_writer.py` | 原子笔记写入 + MOC/周刊索引更新 |

---

## 4. 当前报告质量可能差的原因

### 4.1 数据层问题

1. **雪球帖子内容被截断**：列表页采集的 `content` 是摘要（以 "..." 结尾），详情页完整内容未系统接入。导致同一作者的多篇帖子开头模板相同，内容重复。
2. **港股数据通路不完整**：港股缺少 mootdx 技术支持（无 K线数据），技术形态分析只能依赖外部 Excel 导入，主流程 `xueqiu_monitor_v2.py` 对港股 `is_hk` 直接跳过技术/资金/新闻采集。
3. **板块共振数据缺失**：`technical_resonance.py` 中市场/行业共振目前大多返回 "未知（置信度：低）"，因为指数数据获取不稳定。

### 4.2 评分层问题

1. **情绪面评分过于粗糙**：`scoring_engine.py` 中 `sentiment_score` 仅基于看多/看空关键词计数，无 NLP 语义分析，容易被反讽、疑问句误导。
2. **基本面评分仅依赖 EPS 增速**：`fundamental_score` 只考虑一致预期 EPS 增速，不结合毛利率、ROE、现金流等维度。
3. **风险评分的定性信号提取脆弱**：从 LLM 合成文本中 `lower()` 匹配关键词，容易误触发（如 "没有资金流出" 会匹配到 "流出"）。

### 4.3 内容层问题

1. **LLM 合成叙事质量不稳定**：`KnowledgeSynthesizer` 的 prompt 对每只股票硬编码了竞争对手名单（如圣邦股份固定为思瑞浦/杰华特/纳芯微/艾为电子），若股票更换需同步修改 prompt。
2. **引用来源回填不完整**：`_parse_with_citations()` 提取 `[^n]` 标记后，citations 字典中的元数据是 placeholder（`{"_placeholder": True}`），未真正回填来源信息。
3. **核心事实基座无数据时不隐藏**：当 LLM 不可用或提取失败时，`core_facts` 为空列表，但渲染器仍输出空表头。

### 4.4 技术形态层问题

1. **部分指标在数据不足时静默跳过**：`technical_renderer.py` 有约 35 个条件 `if` 块，在数据缺失时直接不渲染该行/板块，导致报告出现 "缺行" 现象。
2. **RSI/BIAS 在下跌市中显示 "正常" 可能误导用户**：实际值（如 RSI=32.6, BIAS=-4.29%）确实未达极端阈值，但用户直觉上认为下跌市中不应是 "正常"。这是分类阈值设计问题，非 bug。
3. **价格目标与支撑/压力区完全独立计算**：两者无共享数据，可能出现目标价落在压力区之外的不一致情况。

---

## 5. 哪些文件最值得 Codex 优先阅读

**第一优先级（理解架构必读）**：

1. `scripts/utils/skill_pipeline.py` — Pipeline 框架，理解 `SkillContext` 数据传递机制
2. `scripts/utils/report_skills/__init__.py` — 11 个 skill 的组装顺序，是数据流的全景图
3. `scripts/utils/stock_reporter.py` — `PerStockReporter` 外观类，连接数据层和 pipeline
4. `scripts/utils/source_adapter.py` — `SynthesisItem` 统一数据格式，所有内容最终都转为此格式

**第二优先级（修改高频区）**：

5. `scripts/utils/reporter/scoring_engine.py` — 五维度评分 + EV 模型 + 风险评分，逻辑密集
6. `scripts/utils/knowledge_synthesizer.py` — LLM 合成叙事，prompt 工程集中地
7. `scripts/utils/content_quality_gate.py` — 质量门，硬指标 + LLM 评估双层筛选
8. `scripts/utils/reporter/data_fetcher.py` — 外部 API 调用，港股/A股/美股三市场兼容

**第三优先级（渲染扩展区）**：

9. `scripts/utils/reporter/sections/deep_analysis_renderer.py` — 深度分析板块，新增 "项目动态" 子板块需修改此处
10. `scripts/utils/report_skills/assembly_skills.py` — 报告组装，新增 renderer 需在此注册

---

## 6. 哪些地方不建议 Kimi 继续改，应该交给 Codex

### 6.1 技术形态计算模块（交给 Codex）

以下文件涉及复杂的数学计算和状态机逻辑，Kimi 曾多次出现边界条件判断错误：

- `scripts/utils/reporter/price_target.py` — zigzag  pivot 检测、Fibonacci 扩展、形态测量
- `scripts/utils/reporter/technical_structure.py` — ATR binning、有效触碰反向验证、支撑区位置校验
- `scripts/utils/reporter/technical_state_machine.py` — 趋势健康度计算、失效条件判定
- `scripts/utils/reporter/price_adjustment_validator.py` — 除权复权三种状态的 confidence 分级

**原因**：这些模块的 bug 往往隐藏在边界条件（如刚好等于阈值、空数据、单条数据）中，需要系统的单元测试覆盖。Codex 在 TDD 和边界条件处理上更可靠。

### 6.2 报告渲染器的条件分支逻辑（交给 Codex）

- `scripts/utils/reporter/sections/technical_renderer.py` — 约 748 行，大量 `if data: render else: skip` 分支
- `scripts/utils/reporter/sections/price_target_renderer.py` — 价格目标展示逻辑

**原因**：Kimi 修改渲染器时曾导致 "满足条件却不显示" 或 "不满足条件却显示" 的回归问题。这些需要逐个条件分支验证。

### 6.3 评分引擎的数值逻辑（交给 Codex）

- `scripts/utils/reporter/scoring_engine.py` 中的 `compute_pillar_scores()` 和 `ev_expectation()`

**原因**：评分阈值（如 `fwd_pe < 30` 得 9 分）是主观业务决策，但阈值之间的衔接和边界需要严密的数值验证。

### 6.4 Kimi 可以继续负责的区域

- **Pipeline 新增 Skill**：如 Agent-Reach 集成的 `query_generation_skill.py` 和 `agent_reach_skill.py`
- **Prompt 工程**：`KnowledgeSynthesizer` 的主题 prompt 优化
- **数据适配层**：新增 `TwitterAdapter`、`RedditAdapter` 等
- **文档和配置**：`config/stocks.json`、README、设计文档

---

## 7. 关键设计决策与约束

### 7.1 数据流格式

所有跨模块数据通过 `SkillContext` 传递，关键键名：

```python
# 输入键（由调用方设置）
ctx.input["stock_name"]      # 股票名称
ctx.input["stock_codes"]     # {name: code} 映射
ctx.input["stocks_data"]     # {name: [posts]} 雪球帖子
ctx.input["raw_data"]        # {name: {technical, reports, announcements, ...}}

# 中间产出键（由 skill 设置到 output）
ctx.output["keep_posts"]           # 质量门保留的帖子
ctx.output["synthesis"]            # LLM 合成叙事
ctx.output["quote"]                # 实时行情
ctx.output["consensus"]            # 一致预期 EPS
ctx.output["pillar_scores"]        # 五维度得分
ctx.output["total_score"]          # 综合得分
ctx.output["chart_paths"]          # 图表路径字典
```

### 7.2 港股特殊处理

- 港股代码：5 位数字且以 `0` 开头（如 `02533`）
- `xueqiu_monitor_v2.py` 中 `is_hk` 为 True 时跳过：技术指标、研报、公告、资金流向、新闻、FinancialAgent
- 港股行情走 `hk_stock_quote_tencent()`（`data_fetcher.py:45`）
- 港股财务走 `hk_key_indicators()`（东财 GMAININDICATOR）

### 7.3 LLM 调用点

仓库中共有 **4 处**直接调用 LLM：

1. `content_quality_gate.py:202` — LLMQualityAssessor 批量评估内容质量
2. `knowledge_synthesizer.py:269` — 主题化综合叙事生成
3. `knowledge_synthesizer.py:338` — 核心事实提取
4. `synthesis_skills.py:36` — SynthesisSkill（实际已被 KnowledgeSynthesizer 替代，此处为降级备份）

环境变量：`DEEPSEEK_API_KEY` 或 `MOONSHOT_API_KEY`，`DEEPSEEK_MODEL` 可选。

### 7.4 已知孤儿文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `scripts/high_risk/extract_detail_via_cdp.py` | 孤儿 | 未任何代码 import，`scripts/high_risk/extract_detail.py` 已覆盖同样功能。顶部有 deprecation note。保留作为独立 CLI 工具。 |

---

## 8. 目录结构速查

```
scripts/
  xueqiu_monitor_v2.py          # 主入口
  run_*.py                      # 单股入口（6个）
  run_*技术分析_真实数据.py      # 纯技术分析股票专用入口
  utils/
    skill_pipeline.py           # Pipeline 框架
    stock_reporter.py           # PerStockReporter 外观
    fetcher.py                  # 雪球采集
    data_collector.py           # 扩展数据采集
    content_quality_gate.py     # 质量门
    source_adapter.py           # SynthesisItem 适配器
    knowledge_synthesizer.py    # LLM 合成叙事
    financial_agent.py          # FinancialAgent
    obsidian_writer.py          # Obsidian 笔记写入
    pdf_exporter.py             # PDF 导出
    reporter/
      data_fetcher.py           # 外部 API（行情/财务/估值）
      scoring_engine.py         # 五维度评分引擎
      chart_generator.py        # Plotly 图表生成
      constants.py              # COMPETITOR_MAP, INDUSTRY_MAP 等
      technical_*.py            # 技术形态计算（8个文件）
      price_target.py           # 目标价计算
      price_adjustment_validator.py  # 除权复权校验
      sections/                 # 8 个 SectionRenderer
    report_skills/
      __init__.py               # Pipeline 组装
      data_skills.py            # 数据加载 skills
      synthesis_skills.py       # LLM 合成 skill
      chart_skills.py           # 图表生成 skills
      assembly_skills.py        # 报告组装 skill
data/
  raw/                          # 原始采集数据
  processed/                    # 处理后数据
config/
  stocks.json                   # 6 只股票配置
knowledge/10-Stocks/            # Obsidian 知识库输出
reports/                        # Markdown/HTML/PDF 报告输出
```

---

*本文档由 Claude 审计生成，供 Codex 接手参考。不修改业务代码。*
