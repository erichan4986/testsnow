# AGENTS.md — Codex 项目规则

## 1. 项目目标

本项目是一个 A股/港股中文股票深度分析报告生成系统。核心目标：

- **基本面分析**：整合雪球社区讨论、知乎深度文章、券商研报、公司公告、资金流向、新闻资讯，通过 LLM 生成主题化综合叙事（产业逻辑、业绩路径、估值争议、资金面、事件催化）。
- **技术面分析**：基于 OHLCV 数据自主计算全部技术指标（MA/MACD/RSI/BOLL/ATR/ADX/BIAS），识别趋势结构、支撑/压力区、K线形态、价格目标、背离信号。
- **综合报告输出**：Markdown + HTML Dashboard + PDF，包含评分雷达图、牛熊观点图、估值对比图。

## 2. 报告质量目标

- **逻辑一致**：技术面结论与评分引擎输出需相互印证，不能出现"趋势走弱但评分10分"的冲突。
- **风险明确**：风险评分必须标注触发因子和加分依据，亏损股（如黑芝麻智能）需展示专项风险因子表。
- **不编造数据**：所有数据必须来自实际 API 或采集结果。LLM 合成叙事时，prompt 中明确要求"不要编造数据，只能基于以下信息"。
- **引用可追溯**：深度分析板块的 `[^n]` 引用标记需与来源列表对应。

## 3. 运行命令

```bash
# 主流程（每周手动运行，生成全部6只股票报告）
cd scripts && python xueqiu_monitor_v2.py

# 带雪球社区采集（需 Chrome 已登录并开启 CDP 远程调试）
cd scripts && python xueqiu_monitor_v2.py --xueqiu

# 单股快速测试（以黑芝麻智能为例）
cd scripts && python run_黑芝麻智能.py

# 纯技术形态分析（独立流程，不走主 pipeline）
cd scripts && python run_technical_analysis.py <股票名称> <代码> <市场(0=深圳/1=上海)>

# 测试
pytest

# 运行特定模块测试
pytest tests/reporter/test_pipeline_integration.py -v
pytest tests/reporter/test_technical_*.py -v
```

## 4. 主要目录说明

```
scripts/
  xueqiu_monitor_v2.py          # 主入口：采集 → 分析 → 报告 → PDF
  run_*.py                      # 单股入口（6只股票各一个）
  run_technical_analysis.py     # 纯技术分析入口
  utils/
    skill_pipeline.py           # Pipeline 框架（SkillContext + BaseSkill）
    stock_reporter.py           # PerStockReporter 外观类
    fetcher.py                  # 雪球列表页采集（Playwright）
    data_collector.py           # 技术指标/研报/公告/资金流向/新闻采集
    content_quality_gate.py     # 内容质量门（硬指标 + LLM 评估）
    source_adapter.py           # 多源数据统一适配为 SynthesisItem
    knowledge_synthesizer.py    # 5主题 LLM 合成叙事 + 核心事实提取
    reporter/
      data_fetcher.py           # 外部 API：行情/财务/估值/竞争对比
      scoring_engine.py         # 五维度评分 + EV 期望模型 + 风险评分
      chart_generator.py        # Plotly 图表生成
      technical_*.py            # 技术形态计算（8个模块文件）
      price_target.py           # 目标价计算
      price_adjustment_validator.py  # 除权复权校验
      sections/                 # 8个 SectionRenderer（渲染器）
    report_skills/
      __init__.py               # Pipeline 组装（11 个 skill 顺序）
      data_skills.py            # 数据加载 skills
      synthesis_skills.py       # LLM 合成 skill
      chart_skills.py           # 图表生成 skills
      assembly_skills.py        # 报告组装 skill
data/
  raw/                          # 原始采集数据（JSON）
  processed/                    # 处理后数据
config/
  stocks.json                   # 6 只股票配置（代码、行业、竞争对手映射）
knowledge/10-Stocks/            # Obsidian 知识库输出
reports/                        # Markdown/HTML/PDF 报告输出
```

## 5. 禁止事项

- **不要重写整个仓库**：当前代码已运行稳定，修改应聚焦在特定 skill 或 renderer 上。
- **不要随意更换数据源**：行情用腾讯财经、财务用 akshare/东财、研报用东财 reportapi。更换数据源需充分验证字段兼容性。
- **不要引入大型框架**：当前依赖仅 11 个（requests/python-dotenv/openai/playwright/mardown/mootdx/stockstats/akshare/plotly/kaleido）。不要引入 Django/FastAPI/Flask 等 Web 框架。
- **不要删除现有入口**：`xueqiu_monitor_v2.py`、`run_*.py`、`run_technical_analysis.py` 是用户的使用入口，不能删除或改名。
- **不要修改核心业务代码 unless 明确 requested**：如 scoring_engine.py 的阈值、technical_*.py 的算法，修改前需写测试验证。

## 6. 完成标准

任何修改完成后，必须满足：

- [ ] **测试通过**：`pytest` 无失败（现有测试覆盖技术形态模块和 pipeline 集成）。
- [ ] **样例报告可生成**：能成功运行至少一只股票的报告生成（如 `python run_黑芝麻智能.py`），输出 Markdown 文件到 `reports/`。
- [ ] **技术面报告完整性**：包含趋势背景、日线结构、周线结构、价格位置、成交量确认、波动率条件、综合评分、背离预警、关键观察位（支撑/压力）、趋势失效条件、趋势结构、谋士团指标状态。
- [ ] **基本面报告完整性**：包含执行摘要、核心事实基座、产业逻辑、业绩路径、估值多空分歧、资金面与催化剂、引用来源。
- [ ] **风险提示完整**：风险评分因子表、行业特有风险（如亏损芯片企业专项风险表）、关注要点。
- [ ] **基本面 LLM 合成内容需用户确认**：如果修改了 `KnowledgeSynthesizer` 的 prompt 或合成逻辑，必须向用户展示样例输出，确认无编造数据后再提交。

## 7. 环境约束与数据来源规则（来自 CLAUDE.md）

### 雪球网 (Xueqiu) 采集限制

**极度重要**: 雪球网反爬机制非常强，频繁或自动化的 Playwright/浏览器请求可能导致账号被封禁。

- **禁止自动抓取详情页**: 不要在没有用户手动登录的情况下，使用 Playwright 批量访问雪球帖子详情页。
- **触发预警**: 过高的请求频率会触发雪球的反爬预警系统。
- **正确做法**: 如需提取详情页完整内容，应：
  1. 由用户先手动登录雪球账号
  2. 使用已登录的 Chrome 远程调试模式（CDP）
  3. 控制请求频率，每次请求间隔至少 3-5 秒
  4. 优先使用列表页已获取的摘要内容，避免不必要的详情页访问

### GitHub 代码访问限制

在这个运行环境中，直接访问 GitHub 及其 raw 内容会被网络/安全策略阻止：

- **WebFetch 访问 GitHub**: 安全策略直接拒绝（"Unable to verify if domain is safe"）
- **curl 访问 raw.githubusercontent.com**: 无输出/超时
- **gh CLI**: 未安装
- **常见代理（ghproxy.com 等）**: 同样被限制

**可用方案 — gitclone.com 镜像**:

```bash
git clone --depth=1 https://gitclone.com/github.com/OWNER/REPO.git /tmp/REPO
```

**使用注意事项**:
1. 读取完代码后及时清理：`rm -rf /tmp/REPO`
2. 不要 clone 到项目仓库内，避免误提交
3. 优先使用 `--depth=1` 减少传输量
4. 如果 gitclone 也失效，最后的备选是让用户手动复制代码内容

### 数据来源优先级

1. 雪球列表页摘要（已通过 Playwright 获取，存储在 data/raw/）
2. 东方财富网（备用来源，限制较少）
3. 雪球详情页（仅限用户明确授权且已登录时使用）

---

## 8. Codex Skill 使用规则

Codex may use repository skills under `.agents/skills` when relevant.
