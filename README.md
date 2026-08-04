# A股个股深度分析系统

> 原项目名：雪球股票舆情监控系统 v2。已从单一的舆情监控工具扩展为覆盖数据采集、技术分析、情绪分析、LLM 综合研判、报告渲染与导出的端到端个股深度分析系统。

---

## 项目概述

Mac 本地运行的 A 股个股深度分析系统，支持：

- **数据采集**：mootdx (TCP 7709) + akshare + 腾讯财经 + 百度股市通 + 东财研报 API
- **技术分析**：纯 pandas 实现的趋势状态机、健康度评分、形态识别、价格目标分析（zigzag + 斐波那契 + 置信度）
- **情绪分析**：雪球网/东财股吧/知乎多源社区情绪采集 + Kimi LLM 深度分析
- **LLM 综合研判**：跨数据源 FinancialAgent 生成结构化分析报告
- **报告渲染**：8 个 SectionRenderer 模块化组装 Markdown 报告
- **知识沉淀**：自动写入 Obsidian Vault 原子笔记
- **项目信息搜索**（新增）：Agent-Reach 多平台搜索（Twitter/X、Reddit、Bilibili、微信文章等），补充项目进展、产品动态、竞品情报

---

## 监控标的（原始6只）

| 股票名称 | 代码 | 雪球格式 | 东财 GID |
|---------|------|---------|---------|
| 黑芝麻智能 | 02533 | HK02533 | hk02533 |
| 长春高新 | 000661 | SZ000661 | 000661 |
| 三花智控 | 002050 | SZ002050 | 002050 |
| 中简科技 | 300777 | SZ300777 | 300777 |
| 圣邦股份 | 300661 | SZ300661 | 300661 |
| 乐鑫科技 | 688188 | SH688188 | 688188 |

> 技术分析模块已扩展支持任意 A 股代码（通过 `run_*技术分析_真实数据.py` 入口）。

---

## 架构概览

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  数据采集层   │────▶│ 技术分析引擎  │────▶│ 报告渲染层    │────▶│ 报告组装导出  │
│              │     │              │     │              │     │              │
│ mootdx      │     │ technical_   │     │ sections/    │     │ stock_reporter│
│ akshare     │────▶│ analyzer.py  │────▶│ *_renderer.py│────▶│ .py          │
│ 百度PAE     │     │ (orchestrator)│     │              │     │              │
│ 腾讯财经    │     │              │     │              │     │ PDF/Markdown │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
        │                                              ▲
        ▼                                              │
┌──────────────┐                              ┌──────────────┐
│ 内容处理层    │     ┌──────────────┐        │ Skill 流水线  │
│ (雪球/知乎/  │     │ Agent-Reach  │        │ skill_pipeline│
│  东财股吧/   │────▶│ 多平台搜索   │───────▶│ .py          │
│  Twitter)   │     └──────────────┘        └──────────────┘
└──────────────┘
```

---

## 目录结构

| 目录 | 说明 |
|---|---|
| `scripts/` | 入口脚本（单股分析、雪球监控、批量提取） |
| `scripts/utils/` | 核心工具（采集器、分析器、渲染器、导出器） |
| `scripts/utils/reporter/` | 技术分析引擎与报告生成 |
| `scripts/utils/reporter/sections/` | 报告分板块渲染器 |
| `scripts/utils/report_skills/` | Skill Pipeline 技能模块 |
| `tests/` | 测试套件 |
| `config/` | 配置文件（股票映射、市场指数映射） |
| `data/` | 原始数据采集目录 |
| `knowledge/` | Obsidian Vault 知识沉淀 |
| `reports/` | 生成的报告输出（Markdown + PDF） |
| `docs/` | 设计文档与实施计划（superpowers 规范） |

---

## 核心数据流

### 1. 舆情监控流程（原始）

```
xueqiu_monitor_v2.py
  ├── fetcher.py        ← 东财股吧 / 雪球网 采集
  ├── parser.py         ← HTML 解析
  ├── analyzer.py       ← Kimi LLM 情绪分析
  └── reporter.py       ← Markdown 报告保存
```

### 2. 技术分析流程（新增）

```
run_*技术分析_真实数据.py
  ├── data_collector.py
  │     ├── TechnicalCollector   ← mootdx K线 + stockstats 指标
  │     ├── ReportCollector      ← 东财研报
  │     └── _baidu_*()           ← 资金流向 + 概念板块（百度PAE）
  ├── technical_analyzer.py
  │     ├── technical_indicators.py   ← RSI/MACD/BOLL/BIAS/ADX
  │     ├── technical_patterns.py     ← 双顶/双底/K线形态
  │     ├── technical_structure.py    ← 趋势/通道/支撑阻力
  │     ├── technical_state_machine.py← 状态机 + 健康度
  │     ├── technical_resonance.py    ← 市场/板块共振
  │     └── price_target.py           ← zigzag/斐波那契/置信度
  └── sections/technical_renderer.py  ← Markdown 渲染
```

### 3. Skill Pipeline 流程（新架构）

```
skill_pipeline.py
  ├── data_skills.py           ← 加载 + 质量门槛 + 行情
  ├── agent_reach_skills.py    ← LLM生成关键词 + 多平台搜索（Twitter/Reddit/Bilibili/微信）
  ├── technical_skills.py      ← K线 + 指标 + 价格目标
  ├── analysis_skills.py       ← 跨源合并 + 五维评分
  ├── synthesis_skills.py      ← LLM 综合叙事（含项目进展主题）
  ├── chart_skills.py          ← 图表生成
  └── assembly_skills.py       ← 报告组装
```

### 4. 项目信息搜索流程（Agent-Reach）

```
query_generation_skill.py
  └── LLM 根据股票属性生成 6-8 个搜索关键词
        ↓
agent_reach_skill.py
  ├── xreach search "..."          ← Twitter/X
  ├── agent-reach reddit search    ← Reddit
  ├── yt-dlp "ytsearch:..."        ← Bilibili
  └── ... 其他平台
        ↓
SourceAdapter（Twitter/Reddit/Bilibili/微信）→ SynthesisItem
        ↓
ContentQualityGate + ZhihuCurator + ContentConsolidator
        ↓
KnowledgeSynthesizer（新增 "project_intelligence" 主题）
        ↓
DeepAnalysisRenderer（新增 "4.3 项目动态与产品进展"）
```

> Agent-Reach 未安装时自动降级，不影响报告生成。详见 `docs/superpowers/specs/2026-06-10-agent-reach-fundamental-research-design.md`。

---

## 文件详解

### `scripts/` — 入口脚本

| 文件 | 功能 | 实现方式 |
|---|---|---|
| `run_澜起科技技术分析_真实数据.py` | 澜起科技 (688008) Phase 2/3 技术形态分析入口 | 调用 `TechnicalCollector` 获取 qfq 真实日K，打印指标，生成 Markdown 报告 |
| `run_乐鑫科技技术分析_真实数据.py` | 乐鑫科技 (688018) 技术分析入口 | 同上 |
| `run_中简科技技术分析_真实数据.py` | 中简科技 技术分析入口 | 同上 |
| `run_黑芝麻智能.py` | 黑芝麻智能 (HK) 完整报告入口 | 调用 `stock_reporter` 生成带情绪分析的综合报告 |
| `run_圣邦股份.py` | 圣邦股份 (300661) 完整报告入口 | 调用 `data_collector` + `financial_agent` + `stock_reporter` |
| `demo_shengbang.py` | 圣邦股份演示脚本 | 演示全流程：采集→LLM分析→Obsidian写入→PDF生成 |
| `xueqiu_monitor_v2.py` | **雪球情绪监控主程序** | 每周手动运行，采集6只持仓股的社区情绪，调用 Kimi API 生成分析报告 |
| `high_risk/fetch_xueqiu.py` | 雪球列表页采集脚本 | 高风险 CLI，启动 Chrome 登录雪球后批量采集帖子 |
| `high_risk/batch_fetch_quality_posts.py` | 批量提取高质量帖子详情页 | 高风险入口，过滤互动数>=15的帖子，用 `DetailPageFetcher` 提取完整正文 |
| `high_risk/extract_detail.py` | 帖子详情页提取脚本 | 高风险入口，读取 raw JSON，提取 URL，调用 `DetailPageFetcher` 写入 knowledge |
| `high_risk/extract_detail_via_cdp.py` | CDP 模式提取详情页 | 已废弃 shim，保留安全提示 |
| `archive/legacy_maintenance/generate_periodic_report.py` | 旧定期报告生成器 | CLI 包装 `PeriodicReporter`，已归档；新流程优先使用年报缓存与 Source Intake |
| `periodic_report_cache.py` | 年报缓存入口 | A 股可通过巨潮发现并下载官方 PDF；港股/美股用官方 PDF URL 或本地 PDF/TXT 注册到 `data/raw/periodic_reports/` |
| `previews/broker_research_digest_preview.py` | 券商研报 digest 预览入口 | 从 `data/raw/broker_research_reports/<stock>_<code>/_downloads/` 读取 PDF，生成 `/tmp` preview，可选写入 `broker_research_digest` Knowledge notes |
| `archive/legacy_maintenance/sync_vault_from_raw.py` | 旧 raw 到 Obsidian 同步器 | 归档维护脚本；不作为当前报告主流程入口 |

### 年报缓存入口 usage

`scripts/periodic_report_cache.py` 只负责把年报 PDF/TXT 标准化缓存到 `data/raw/periodic_reports/`，不会写 `reports/` 或 `knowledge/`。生成的标准文件包括：

- `{股票名}_{年份}_{report_type}_jina.txt`
- `{股票名}_{年份}_{report_type}_meta.json`
- `_downloads/{股票名}_{年份}_{report_type}_source.pdf`（仅 URL 下载时）

A 股优先走巨潮发现链路。只看发现结果：

```bash
python3 scripts/periodic_report_cache.py \
  --discover-cninfo \
  --code 300661 \
  --year 2025
```

A 股发现后直接下载并缓存：

```bash
python3 scripts/periodic_report_cache.py \
  --discover-cninfo \
  --download-discovered \
  --stock 圣邦股份 \
  --code 300661 \
  --year 2025
```

港股可走 HKEX 披露易发现链路。只看发现结果：

```bash
python3 scripts/periodic_report_cache.py \
  --discover-hkex \
  --code 02533 \
  --year 2025
```

港股发现后直接下载并缓存：

```bash
python3 scripts/periodic_report_cache.py \
  --discover-hkex \
  --download-discovered \
  --stock 黑芝麻智能 \
  --code 02533 \
  --year 2025
```

也可以用官方 PDF URL 下载并缓存：

```bash
python3 scripts/periodic_report_cache.py \
  --download-url "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0328/example_c.pdf" \
  --stock 黑芝麻智能 \
  --code 02533 \
  --year 2025 \
  --market HK
```

用本地 PDF/TXT 注册：

```bash
python3 scripts/periodic_report_cache.py \
  --stock MiniMax \
  --code 06677 \
  --year 2025 \
  --market HK \
  --input minimax年报.pdf
```

如果 `config/stocks.json` 的单股配置中维护了官方年报 PDF URL，可用配置入口统一准备 cache：

```json
{
  "name": "黑芝麻智能",
  "code": "02533",
  "xueqiu_code": "HK02533",
  "annual_report_url": "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0328/example_c.pdf"
}
```

```bash
python3 scripts/periodic_report_cache.py \
  --from-config \
  --stock 黑芝麻智能 \
  --year 2025
```

配置入口规则：

- `annual_report_url` 存在时，直接下载该官方 PDF 并写入标准 cache。
- A 股没有 `annual_report_url` 时，会按股票代码走巨潮发现和下载链路。
- 港股没有 `annual_report_url` 时，会按股票代码走 HKEX 披露易发现和下载链路。

CLI 输出会包含 `text_path`、`meta_path`、`official_url`、`source_path`、`input_format`、`market`、`report_year` 和 `report_type`，后续 narrative cards preview 或报告入口可复用这些 cache 文件。

### `scripts/prepare_annual_report_materials.py` — 一键年报材料准备

把「cache + narrative cards preview + 可选 knowledge 写入」合成一条命令。

```bash
python3 scripts/prepare_annual_report_materials.py --stock 黑芝麻智能 --year 2025
```

默认只生成 cache 和 `/tmp` 下的 preview，不写入 `knowledge/`：

```bash
python3 scripts/prepare_annual_report_materials.py --stock 圣邦股份 --year 2025
```

当前 narrative cards v1 优先服务泛半导体/硬科技年报，例如芯片设计、光模块、电子材料、AI 芯片、智能硬件，以及产品/R&D 披露足够具体的高端制造公司。其他行业默认只做 preview 观察，不默认写入 Knowledge；长春高新、三花智控这类样本用于观察边界，不作为默认质量回归或默认沉淀目标。若要扩展医药、消费、地产等行业，应另开行业 v2 规则，不在当前泛半导体路径里堆特例。

需要沉淀 narrative cards 时再传入 `--write-knowledge`：

```bash
python3 scripts/prepare_annual_report_materials.py \
  --stock 黑芝麻智能 \
  --year 2025 \
  --write-knowledge \
  --base-dir knowledge
```

支持参数：

- `--stock`：股票名/代码（需在 `config/stocks.json` 中能找到）
- `--year`：报告年份
- `--config`：股票配置路径，默认 `config/stocks.json`
- `--cache-dir`：cache 目录，默认 `data/raw/periodic_reports`
- `--report-type`：报告类型，默认 `annual`
- `--preview-output`：覆盖默认 `/tmp/{safe_stock}_{year}_annual_narrative_cards_preview.md`
- `--write-knowledge`：写入 `knowledge/10-Stocks/<stock>/periodic_narrative_cards/`
- `--base-dir`：knowledge 根目录，默认 `knowledge`

CLI 输出 JSON：

```json
{
  "stock_name": "黑芝麻智能",
  "stock_code": "02533",
  "market": "HK",
  "report_year": 2025,
  "report_type": "annual",
  "text_path": "data/raw/periodic_reports/黑芝麻智能_2025_annual_jina.txt",
  "meta_path": "data/raw/periodic_reports/黑芝麻智能_2025_annual_meta.json",
  "preview_path": "/tmp/__________2025_annual_narrative_cards_preview.md",
  "evidence_blocks_count": 18,
  "cards_count": 12,
  "wrote_knowledge": false,
  "knowledge_written_count": 0
}
```

准备策略：

- 配置中有 `annual_report_url` 时直接下载该 URL。
- A 股无 URL 时走巨潮发现+下载。
- 港股无 URL 时走 HKEX 披露易发现+下载。
- 无法识别市场且无 URL 时非 0 退出。

### 券商研报 digest usage

券商研报 digest 是 Source Intake 的专业观察层，用来把东财研报 PDF 中较有信息量的段落提炼成可读卡片。它的边界和年报 narrative cards 不一样：

- `source_type`: `broker_research`
- `source_credit`: 72
- `claim_status`: `professional_analysis`
- 只能作为 display-only 材料进入深度分析展示
- 不进入 `confirmed_fact`、`fact_candidate`、综合评分、风险计分或核心事实基座
- 不直接读取 raw PDF 进入 synthesis；报告只读取已经人工/规则筛过的 `knowledge/10-Stocks/<stock>/broker_research_digest/*.md`

东财研报 PDF 由 Source Intake 下载并缓存到：

```text
data/raw/broker_research_reports/<股票名>_<代码>/_downloads/
```

生成本地 digest preview：

```bash
python3 scripts/previews/broker_research_digest_preview.py \
  --stock 圣邦股份 \
  --code 300661 \
  --output /tmp/圣邦股份_broker_research_digest_preview.md
```

人工确认 preview 后，再写入 Knowledge：

```bash
python3 scripts/previews/broker_research_digest_preview.py \
  --stock 圣邦股份 \
  --code 300661 \
  --write-knowledge \
  --base-dir knowledge
```

报告中启用 display-only 读取时，在单股 `source_intake` 配置中加入：

```json
{
  "broker_research_digest_synthesis_display": {
    "enabled": true,
    "max_display_items": 3
  }
}
```

已验证样例：圣邦股份。当前报告可在 §四深度分析中引用国元证券、东莞证券等券商研报 digest；核心事实、评分、风险仍保持隔离。

### `scripts/utils/` — 核心工具

| 文件 | 功能 | 实现方式 |
|---|---|---|
| `data_collector.py` | **多源数据采集器** | 封装 `TechnicalCollector`(mootdx K线+stockstats指标)、`ReportCollector`(东财研报)、`AnnouncementCollector`(巨潮公告)、`FundFlowCollector`(akshare资金流)、`NewsCollector`(东财新闻)、`ZhihuCollector`(知乎搜索)。新增百度PAE `_baidu_fund_flow_history()` 和 `_baidu_concept_blocks()` |
| `fetcher.py` | 东财股吧数据获取器 | `EastmoneyFetcher` / `XueqiuFetcher`，带 session 和随机延迟的 HTTP 抓取 |
| `detail_page_fetcher.py` | 雪球详情页提取器 | `DetailPageFetcher` 用 headed Playwright 打开 Chrome，提取完整帖子内容 |
| `analyzer.py` | Kimi API 分析器 | `KimiAnalyzer` 封装 OpenAI-compatible Kimi API，做情绪分析和报告生成 |
| `financial_agent.py` | 跨数据源深度分析 Agent | `FinancialAgent` 接收多源数据，构建结构化 prompt，调用 Kimi 做综合研判 |
| `stock_reporter.py` | **个股深度报告主生成器** | `PerStockReporter` 接收股票数据，委托各 `SectionRenderer` 组装最终 Markdown |
| `reporter.py` | 旧版报告管理器 | `ReportManager` 保存 Markdown 到磁盘，逐步淘汰中 |
| `pdf_exporter.py` | PDF 导出器 | `export_pdf()` 将 Markdown 转 HTML（自定义CSS），Playwright 打印为 PDF |
| `obsidian_writer.py` | Obsidian Vault 写入器 | `ObsidianWriter` 创建带 YAML frontmatter 的原子笔记 |
| `periodic_reporter.py` | 定期报告生成器 | `PeriodicReporter` 编排数据采集和 LLM 分析，生成季报/半年报 |
| `skill_pipeline.py` | **Skill Pipeline 框架核心** | `SkillContext`(共享上下文)、`BaseSkill`(基类)、`@skill` 装饰器、`SkillPipeline`(执行器)。函数式流水线，技能逐个转换上下文 |
| `source_adapter.py` | 多源数据适配器 | `SynthesisItem` 统一数据格式，`XueqiuAdapter`/`ZhihuAdapter`/`ReportAdapter` 转换原始 API 响应 |
| `content_quality.py` | 内容质量评分 | `classify_posts()` / `score_post()` 基于长度、数据密度、逻辑词数、互动数的硬规则分类器 |
| `content_quality_gate.py` | 内容质量门槛 | `ContentQualityGate` 两阶段过滤：硬指标 → LLM 质量评分(0-100) |
| `content_consolidator.py` | 跨源内容去重聚类 | `ContentConsolidator` 用 LLM 提取 topic tags，按主题聚类，每类保留最高分内容 |
| `knowledge_synthesizer.py` | 主题综合叙事生成 | `KnowledgeSynthesizer` 将 `SynthesisItem` 合成为行业逻辑/基本面/估值/资金/事件主题叙事，带 `[^n]` 引用 |
| `zhihu_curator.py` | 知乎内容精编器 | `ZhihuCurator` 三层漏斗：L1 时间截断(365天) → L2 DeepSeek 批量质量评估 → L3 有效性过滤 |
| `parser.py` | 东财股吧 HTML 解析 | `EastmoneyParser` 正则解析帖子列表、标题、作者、时间、阅读量 |

### `scripts/utils/reporter/` — 技术分析引擎

| 文件 | 功能 | 实现方式 |
|---|---|---|
| `technical_analyzer.py` | **技术分析主入口 (orchestrator)** | `analyze()` 函数编排所有子模块：指标计算→形态识别→结构分析→状态机→健康度→失效条件→共振分析。纯 pandas 实现，接收 DataFrame 输出完整分析结果字典 |
| `technical_indicators.py` | 基础指标计算 | `sma()`/`ema()`/`atr()`/`adx()`/`cci()`/`williams_r()`/`stoch_rsi()`/`obv()`/`macd()`/`bollinger()`/`rsi()`，全部用 pandas rolling/ewm 从零实现 |
| `technical_patterns.py` | 形态识别与预警 | `detect_double_top()`/`detect_double_bottom()`/`detect_boll_overextension()`/`evaluate_candle_at_key_levels()`，检测经典图表形态和 BOLL 超买超卖 |
| `technical_structure.py` | 结构分析模块 | `compute_bias()`/`compute_boll_state()`/`compute_candle_features()`/`compute_ma_direction()`/`resample_daily_to_weekly()`/`compute_weekly_trend()`/`find_support_resistance()`/`evaluate_sr_transformation()`，分析价格结构、周线趋势、支撑阻力 |
| `technical_state_machine.py` | **趋势状态机 + 健康度评分** | `classify_trend_state()` 按优先级判定趋势阶段（破坏期→转弱期→高位钝化→加速期→主升期→启动期→回撤观察→盘整期）；`compute_trend_health()` 动态评分（含成交量确认评分 `_score_volume_confirmation()`）；`compute_invalidation()` 失效条件；`evaluate_bias_extreme()`/`detect_false_rebound()`/`detect_false_breakout()`/`evaluate_sell_three_factors()` 策略信号 |
| `technical_resonance.py` | 市场/板块共振框架 | `evaluate_market_resonance()` 个股 vs 市场/行业/主题趋势共振；`load_market_index_map()` 加载映射；`analyze_index_trend()` 对指数复用状态机。支持主题指数代理行业 |
| `technical_strategy.py` | 策略信号模块 | `evaluate_dart_strategy()` 底部区域分批观察框架，不直接给出买入建议 |
| `price_target.py` | **价格目标核心引擎** | `zigzag()` 识别波段转折点 → `fib_targets_with_convergence()` 斐波那契扩展 → `pattern_target()` 形态测量 → `analyze_price_target()` 主入口：整合周线趋势、形态、zigzag、斐波那契、盈亏比过滤、六因子置信度评分、时间预期、止损条件 |
| `price_adjustment_validator.py` | 除权复权校验 | `detect_price_gaps()` 检测跳空>25%的除权缺口；`validate_adjustment()` 校验复权状态；`apply_qfq_adjustment()` 应用前复权修复 |
| `scoring_engine.py` | 评分引擎 | `classify_sentiment()` 关键词情绪分类；`compute_pillar_scores()` 五维评分（基本面/估值/情绪/技术/风险）；`ev_expectation()` EV 预期模型；`composite_score_section()`/`risk_score_section()` 综合/风险评分 |
| `data_fetcher.py` | 外部 API 数据获取 | `fetch_tencent_quote()` 腾讯实时行情；`fetch_consensus_eps()` 东财一致预期；`fetch_financial_abstract()` 财务摘要；`fetch_competitor_metrics()` 竞品指标；`industry_fwd_pe()` 行业前瞻PE |
| `chart_generator.py` | 图表生成 | `generate_decision_chain_chart()` 投资决策链；`generate_technical_panel()` 动态技术面板；`generate_bull_bear_chart()` 多空情绪图；`generate_radar_chart()` Dashboard 雷达图。Plotly + Kaleido 输出 PNG |
| `constants.py` | 共享常量 | `COMPETITOR_MAP`/`COMPETITOR_CODES`/`INDUSTRY_MAP` 竞品映射 |
| `technical_config.py` | 技术指标配置 | `load_technical_config()` 加载阈值参数（MA走平阈值、BOLL开口比例、BIAS窗口、RSI阈值），支持 JSON 覆盖 |

### `scripts/utils/reporter/sections/` — 报告板块渲染器

| 文件 | 功能 | 实现方式 |
|---|---|---|
| `__init__.py` | 包初始化 | 渲染器从各自 owner 模块直接导入，避免包级 eager import |
| `technical_renderer.py` | **技术面分析板块渲染** | `TechnicalRenderer` 支持 compact/full/legacy 三模式，渲染趋势状态、健康度评分、结构健康、通道/箱体、底部信号、市场共振、K线形态、谋士团、背离预警、价格目标、概念板块、资金流向 |
| `executive_summary_renderer.py` | 执行摘要渲染 | `ExecutiveSummaryRenderer` 调用 LLM 提取多空论点和一句话结论 |
| `composite_score_renderer.py` | 综合评分渲染 | `CompositeScoreRenderer` 渲染 G=B+M 评分、EV 预期、目标价区间、AI 建议 |
| `valuation_renderer.py` | 估值分析渲染 | `ValuationRenderer` 懒加载实时行情和一致预期，渲染 PE/PB/PS、前瞻估值、财务快照、同业对比 |
| `deep_analysis_renderer.py` | 深度分析渲染 | `DeepAnalysisRenderer` 渲染核心事实表和主题深度分析（行业逻辑/业绩路径/资金） |
| `risk_renderer.py` | 风险分析渲染 | `RiskRenderer` 渲染风险因子、关注点、行业特定风险表 |
| `html_dashboard_renderer.py` | HTML 仪表盘渲染 | `HTMLDashboardRenderer` 生成单页可视化快览仪表盘 |

### `scripts/utils/report_skills/` — Skill Pipeline 技能

| 文件 | 功能 | 实现方式 |
|---|---|---|
| `__init__.py` | 流水线组装 | `build_stock_report_pipeline()` 组装 11 个技能的完整流水线 |
| `data_skills.py` | 数据加载技能 | `data_loading_skill()` 加载原始数据；`quality_gate_skill()` 质量门槛；`quote_fetching_skill()` 实时行情；`competitor_fetching_skill()` 竞品数据 |
| `agent_reach_skills.py` | **项目信息搜索技能**（新增） | `query_generation_skill()` LLM生成搜索关键词；`agent_reach_fetching_skill()` 调用Agent-Reach CLI搜索Twitter/Reddit/Bilibili/微信 |
| `technical_skills.py` | 技术数据采集技能 | `technical_fetching_skill()` 包装 `TechnicalCollector`，获取日K/周K/指标/价格目标 |
| `analysis_skills.py` | 分析与评分技能 | `cross_source_consolidation_skill()` 跨源合并去重；`scoring_skill()` 五维评分+雷达图数据 |
| `synthesis_skills.py` | LLM 综合技能 | `SynthesisSkill` 调用 LLM 生成综合叙事，或模板降级 |
| `chart_skills.py` | 图表生成技能 | `ChartGenerationSkill` 生成技术面板/多空图/雷达图；`TechnicalAnalysisSkill` 技术分析图表 |
| `assembly_skills.py` | 报告组装技能 | `ReportAssemblySkill` 编排所有 section renderer 输出最终 Markdown + HTML |

### `tests/` — 测试套件

| 文件 | 功能 |
|---|---|
| `test_data_collector.py` | `data_collector` 集成测试（K线/研报采集） |
| `test_financial_agent.py` | `financial_agent` 单元测试（初始化/prompt构建） |
| `test_obsidian_writer.py` | `obsidian_writer` 单元测试（原子笔记写入） |
| `test_price_target_e2e.py` | `price_target` 端到端测试 |
| `test_skill_pipeline.py` | `skill_pipeline` 框架测试（上下文/子类/执行/错误处理） |
| `utils/test_detail_page_fetcher.py` | `detail_page_fetcher` 初始化测试 |
| `utils/test_knowledge_synthesizer.py` | `knowledge_synthesizer` 测试（引用解析/prompt构建） |
| `utils/test_source_adapter.py` | `source_adapter` 测试（字段映射/平台检测） |

### `tests/reporter/` — Reporter 模块测试（53个文件）

| 测试对象 | 测试文件 |
|---|---|
| **技术分析全流程** | `test_advanced_technical_e2e.py`, `test_phase3_integration.py`, `test_backward_compatibility.py`, `test_technical_imports.py`, `test_lanqi_phase3_report.py`, `test_lexin_phase3_report.py` |
| **指标计算** | `test_technical_indicators.py` (SMA/RSI/BOLL), `test_bias_computation.py`, `test_boll_state.py`, `test_boll_overextension.py` |
| **形态识别** | `test_technical_patterns.py` (双顶/双底/BOLL超买) |
| **结构分析** | `test_technical_structure.py` (BIAS/BOLL/支撑阻力), `test_daily_structure.py`, `test_phase3_structure.py`, `test_support_resistance.py`, `test_weekly_trend.py` |
| **状态机** | `test_technical_state_machine.py` (状态分类/健康度), `test_trend_health.py`, `test_trend_state_machine.py` |
| **共振分析** | `test_market_resonance.py`, `test_market_resonance_integration.py` |
| **价格目标** | `test_price_target.py` (zigzag/斐波那契/形态) |
| **除权校验** | `test_price_adjustment_validator.py`, `test_corporate_action_adjustment.py` |
| **策略信号** | `test_phase3_bottom_strategy.py` |
| **配置** | `test_technical_config.py` |
| **图表生成** | `test_chart_generator.py`, `test_stock_reporter_charts.py` |
| **渲染器** | `test_technical_renderer.py`, `test_composite_score_renderer.py`, `test_executive_summary_renderer.py`, `test_valuation_renderer.py`, `test_risk_renderer.py`, `test_deep_analysis_renderer.py`, `test_html_dashboard_renderer.py` |
| **Skill Pipeline** | `test_analysis_skills.py`, `test_assembly_skills.py`, `test_chart_skills.py`, `test_data_skills.py`, `test_synthesis_skills.py`, `test_pipeline_integration.py`, `test_skill_pipeline_observability.py` |

---

## 数据来源优先级

| 优先级 | 数据源 | 用途 | 可靠性 |
|--------|--------|------|--------|
| 1 | **mootdx** (TCP) | K线、五档盘口、逐笔成交、财务快照、F10 | 极稳定 |
| 2 | **腾讯财经 API** | 实时 PE/PB/市值/换手率/涨跌停 | 稳定 |
| 3 | **akshare** | 研报、一致预期、新闻、公告、龙虎榜、解禁、行业 | 稳定 |
| 4 | **百度股市通** | 概念板块归属、个股资金流向 | 稳定 |
| 5 | **东财 reportapi** | 研报列表 + PDF 下载 | 稳定 |
| 6 | **iwencai** (需 key) | NL 语义搜索研报 | 需 X-Claw Header |

---

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

### 1. 基础配置

编辑 `config/stocks.json` 修改监控股票列表。

### 2. Kimi API 密钥

在 `.env` 文件中添加：

```env
MOONSHOT_API_KEY=your_moonshot_api_key_here
MOONSHOT_MODEL=moonshot-v1-128k
```

### 3. 雪球增强（可选）

如需抓取雪球网数据，需保持 Chrome 已登录雪球：

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222
```

## 运行测试

```bash
# 全部 reporter 测试（264个）
pytest tests/reporter/ -v

# 单个模块
pytest tests/reporter/test_technical_state_machine.py -v

# 报告质量检查（可先跑内置最小样例）
python3 scripts/check_report_quality.py --sample
python3 scripts/check_report_quality.py reports/圣邦股份_20260604.md

# 端到端
python scripts/run_澜起科技技术分析_真实数据.py
```

## 反爬策略

- 单股票请求间隔 3-5 秒随机抖动
- 模拟 Mac Chrome User-Agent（东财）
- 复用已登录浏览器会话（雪球 CDP）
- 雪球限制：每只股票最多进 3 条详情页取评论
- 单只股票失败不中断整体流程

---

*最后更新: 2026-06-10*
