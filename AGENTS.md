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
# 首选样例报告 / runtime 验证入口（以黑芝麻智能为例）
cd scripts && python run_黑芝麻智能.py --fast-test

# 正式刷新知乎/LLM材料时才运行完整单股报告
cd scripts && python run_黑芝麻智能.py

# 批量轻量报告入口（旧主流程；不要作为默认测试入口）
cd scripts && python xueqiu_monitor_v2.py

# 带雪球社区采集（高风险；需 Chrome 已登录并开启 CDP 远程调试）
cd scripts && python xueqiu_monitor_v2.py --xueqiu

# 纯技术形态分析（独立流程，不走主 pipeline；当前为股票专用入口）
cd scripts && python run_澜起科技技术分析_真实数据.py

# 测试
pytest

# 运行特定模块测试
pytest tests/reporter/test_pipeline_integration.py -v
pytest tests/reporter/test_technical_*.py -v
```

## 4. 主要目录说明

```
scripts/
  run_*.py                      # 单股深度报告入口；测试/试跑优先使用，黑芝麻智能为默认样例
  xueqiu_monitor_v2.py          # 批量轻量报告/采集调度入口；不作为默认测试入口
  run_*技术分析_真实数据.py      # 纯技术分析股票专用入口；当前无统一通用 CLI
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
- **不要删除现有入口**：`xueqiu_monitor_v2.py`、`run_*.py`、`run_*技术分析_真实数据.py` 是用户的使用入口，不能删除或改名。
- **不要修改核心业务代码 unless 明确 requested**：如 scoring_engine.py 的阈值、technical_*.py 的算法，修改前需写测试验证。
- **不要把 `xueqiu_monitor_v2.py` 当默认验证入口**：报告试跑、runtime validation、样例报告验收应优先使用 `scripts/run_黑芝麻智能.py --fast-test` 或对应单股 `run_*.py` 的快速验证模式。只有验证批量调度/采集本身时才运行 `xueqiu_monitor_v2.py`。
- **不要在普通工程验证中消耗知乎/LLM token**：`run_黑芝麻智能.py --fast-test` 会跳过知乎采集和 ZhihuCurator，优先复用本地 `data/raw/report_input_*_黑芝麻智能.json` 中的知乎数据；只有任务明确要求刷新知乎内容质量或正式生成最新基本面材料时，才运行不带 `--fast-test` 的完整入口。

## 5.1 入口演进方向

- `run_*.py` / `PerStockReporter` / `report_skills` 是深度报告主路径。后续新功能、Agent-Reach、质量门、报告结构优化，应优先围绕单股深度报告 pipeline 设计和验证。
- `xueqiu_monitor_v2.py` 后续降级为批量轻量报告/采集调度器：负责批量枚举股票、保存轻量汇总、调用单股报告能力，但不继续承载深度报告核心逻辑。
- 新增或重构深度报告能力时，不要继续往 `xueqiu_monitor_v2.py` 里堆业务逻辑；应抽到可单股调用、可测试、可复用的模块或 skill。

## 6. 完成标准

任何修改完成后，必须满足：

- [ ] **测试通过**：`pytest` 无失败（现有测试覆盖技术形态模块和 pipeline 集成）。
- [ ] **样例报告可生成**：优先运行单股快速入口（默认 `cd scripts && python run_黑芝麻智能.py --fast-test`），输出 Markdown 文件到 `reports/`。除非任务明确涉及知乎刷新/正式基本面材料更新，不要默认消耗 ZhihuCurator/DeepSeek token；除非任务明确涉及批量调度，不要用 `xueqiu_monitor_v2.py` 作为完成标准。
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

### grill-me 自动触发规则

当用户提出尚未成形的方案、路线、架构或下一步选择，并且任务可能影响报告结构、pipeline、数据源、LLM 合成、质量门、采集策略或多文件实现时，Codex 应自动使用 `.agents/skills/grill-me` 做设计拷问，而不需要用户显式输入“grill-me”。

典型触发语义：

- “下一步做什么 / 要不要做 X / 重新设计 / 开新主题 / 这个方案靠谱不”
- “做一套流程 / 接入新 source / 改 synthesis / 改报告结构 / 改 pipeline”
- 用户表达不确定、权衡、担心信息质量或风险边界时

不自动触发：

- 用户给出明确小修、小测试、只读复验或报告试跑任务
- 紧急 bugfix、已锁定实现边界的 Level 0/1 小任务
- 用户明确要求“直接做 / 不要追问 / 给 prompt”

触发后行为：

1. 先读相关代码/配置；能从仓库回答的问题不要问用户。
2. 一次只问一个关键问题，并给出推荐答案。
3. 覆盖 failure modes、边界、测试门和停止条件。
4. 在用户确认“按这个做/推进”前，不进入实现；若确认后按最轻足够安全的 Level 继续。

---

## 9. Codex 编排、本地 Claude Code 执行协作规则

当任务属于 major plan/design 或高风险实现时，必须使用 `docs/agent_workflow/` 中定义的文件化协作流程。轻量任务可使用短 prompt handoff，不必为每个小改动创建 workflow 文件。

重要约束：Codex 在当前环境中不直接调用外部 Claude/Kimi 处理私有仓库上下文。Codex 负责写 design、review prompt、implementation task 和验收报告；用户在本地终端触发 Claude Code；Claude Code 将反馈、notes 或代码 diff 写回仓库；Codex 再读取文件和 diff 继续推进。

### Fast Quality Mode（默认协作策略）

当前默认目标是**效率和质量优先**，不再以最小化 Codex token 为第一目标。Codex 应更主动承担规划、实现、审查和窄范围修复，Claude Code 主要用于本地执行、第二视角 review、长时间/网络/浏览器/PDF 验证和较大实现任务。

默认分工：

- Codex 可以直接处理小文档、测试、局部 bugfix、窄范围脚本/renderer/skill 调整，并运行 focused tests。
- Claude Code 更适合本地网络访问、Jina/Agent-Reach 实跑、Chrome/PDF/Playwright、需要用户本机权限的验证、以及中等以上实现。
- Claude Code 完成后，如 Codex 验收发现窄范围 bug、测试缺口或任务契约偏差，Codex 可以直接补最小修复和测试，不必再开一轮 Claude handoff。
- 只有当修复会扩大允许文件、改变设计边界、涉及高风险模块，或需要本地权限/网络复验时，才重新交给 Claude Code。
- 设计和交接文档保持短而硬：目标、边界、失败模式、测试门、stop conditions；避免重复性 `codex-response.md` 和长篇复述。

仍然必须保留的硬门：

- 修改 `KnowledgeSynthesizer` prompt、LLM 合成逻辑、引用生成、评分/技术算法、风险规则、Xueqiu/CDP/Playwright/外部 API 采集逻辑，必须走 Level 3 或明确的 Level 2 task。
- 涉及 LLM 合成内容的改动，必须向用户展示样例输出并确认无编造数据。
- 涉及雪球详情页、登录态 Chrome/CDP、批量采集或账号安全时，必须明确授权并遵守 3-5 秒延迟规则。
- Codex 验收必须看真实 diff、关键文件和测试输出，不能只采信 Claude Code 摘要。

### 适用范围

协作强度分为四级，必须选择最轻但足够安全的流程：

- **Level 0: Direct Prompt Handoff** — 小型实现任务，边界清楚，通常 1-2 个文件：Codex 直接给一段可粘贴给 Claude Code 的短 prompt；Claude 实现后，Codex 只审 diff、notes/summary 和 focused tests。
- **Level 1: Codex Direct** — 小文档、错别字、窄范围测试、简单局部修改，或用户希望 Codex 直接改时，由 Codex 直接实现并验证。
- **Level 2: File Task Handoff** — 中等风险、需要较清晰审计边界的任务：Codex 写 `claude-task.md`，用户本地触发 Claude Code 实现，Codex 验收 diff 和测试。
- **Level 3: Full Design Review** — 高风险或设计不明确的任务：必须先做 Round 1 design review；Round 2 仅在 blocker、未解决 must-fix 或高风险设计变化时触发。

默认选择规则：

- 默认优先考虑 Codex Direct（Level 1）或紧凑 Level 2；只有风险或本地环境要求足够高时，才升级到文件化 review 或 Claude 本地执行。
- 用户说“交给 agent / Claude Code”且任务很小：默认 Level 0，给短 prompt，不创建 workflow 文件。
- 用户说“试跑报告 / 生成报告看看 / 跑一下报告入口”且不要求修改代码：默认 Level 0，给报告试跑短 prompt，由 Claude Code 本地执行，Codex 再验收生成物和质量门。默认试跑入口是 `scripts/run_黑芝麻智能.py --fast-test`；不要默认运行 `scripts/xueqiu_monitor_v2.py`，也不要默认刷新知乎/LLM curator。
- Codex 沙箱无法可靠执行的本地浏览器/GUI 验证（例如 Playwright/Chromium PDF 导出、需要 macOS 浏览器权限的截图/预览）默认交给用户本地 Claude Code 执行。Codex 应记录失败原因，给 Level 0 短 prompt，让 Claude Code 本地验证并回报结果；不要反复在沙箱里申请权限硬跑。
- 用户说“走 workflow / 写 task 文件 / 需要审计记录”：使用 Level 2 或 Level 3。
- Codex 判断涉及数据完整性、账号安全、LLM prompt、评分/技术算法、报告核心逻辑时，必须升级到 Level 2 或 Level 3，并说明原因。

以下任务必须走 Level 3：

- 修改架构、Pipeline 顺序、报告结构或多个 renderer/skill 的协作方式
- 修改 `KnowledgeSynthesizer` prompt、LLM 合成逻辑或引用生成逻辑
- 修改 `scoring_engine.py`、技术分析算法、风险评分、趋势/评分一致性规则
- 修改数据采集逻辑，尤其是雪球、Playwright、CDP 或外部 API 相关逻辑
- 预计改动超过 3 个文件，或需要多轮设计/验收的任务

### Level 3 设计互评规则

major task 在实现前必须至少完成 Round 1 设计审查；Round 2 条件触发：

1. Codex 起草 `docs/agent_workflow/YYYY-MM-DD-topic-design.md`
   - design 必须包含 failure modes：会坏在哪里、坏了怎么表现、哪个测试捕获。
2. Codex 写 `YYYY-MM-DD-topic-claude-review-round1.md`，并给出可直接交给本地 Claude Code 的 prompt。
3. 用户在本地终端运行 Claude Code 第一轮 review；Claude 只提风险、遗漏、测试缺口，不写代码；反馈必须标注 `blocker / must-fix / nice-to-have`。
4. Codex 读取 Claude 写回的 design/notes，修订 design，并只写 compact `Design Delta`：
   - accepted：采纳了什么，改了哪节
   - rejected：拒绝了什么，技术理由
   - deferred：延期什么，为什么不在本轮做
   - R2 required：yes/no 及原因
5. 若 Round 1 只有 nice-to-have，或 must-fix 已被 Codex 明确修正且不改变高风险边界，可跳过 Round 2，直接写 implementation task。
6. 只有存在 blocker、未解决 must-fix、高风险设计变化、或 Codex 拒绝了影响正确性的 must-fix 时，Codex 才写 `YYYY-MM-DD-topic-claude-review-round2.md` 并触发第二轮 review。
7. Codex 锁定 design 后，再写 `YYYY-MM-DD-topic-claude-task.md`，由用户本地触发 Claude Code 实现。
8. Claude notes 对非平凡任务必须包含 requirement-test matrix：设计要求、实现位置、测试/验证。

### Agent prompt 交付规则

- 当用户要求“交给 agent / Claude Code / 本地 agent 执行”时，Codex 必须提供一段可直接粘贴给 agent 的 prompt，而不是只给 bash 命令。
- Level 0 短 prompt 必须包含目标、允许修改范围、禁止事项、测试要求、完成后回报格式和停止条件；不要求写入 `docs/agent_workflow/`。
- Level 2/3 文件化 prompt 必须包含任务文件路径、目标、允许修改范围、禁止事项、测试要求、notes 输出路径和停止条件。
- 如已生成 `docs/agent_workflow/YYYY-MM-DD-topic-claude-task.md`，Codex 应先提示“把下面这段交给 Claude Code”，并在 prompt 中要求 agent 读取该 task 文件；bash 命令只能作为可选附注，不能作为主要交付物。
- 如果用户明确说“不要 bash 命令”，最终回复中不得以 bash 命令作为执行入口。

Level 0 短 prompt 模板：

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做一个小范围实现。

目标：
[一句话目标]

允许修改：
- [file_a]
- [test_file]

禁止修改：
- 入口脚本，除非明确列入允许修改
- scoring_engine.py、technical_analyzer.py、KnowledgeSynthesizer
- data/raw、reports、knowledge
- 与任务无关的重构或格式化

要求：
1. 先写失败测试，再实现最小代码。
2. 不要访问外部网站，不要启动 Chrome，不要抓雪球详情页。
3. 跑 focused tests：[列出测试]
4. 完成后回复：改了哪些文件、测试结果、偏离点、blocker。

停止条件：
- 需要改允许范围之外的文件
- 需要修改评分/技术算法/LLM prompt
- 测试暴露出无关大范围失败
```

报告试跑 Level 0 prompt 模板：

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做一次报告试跑，不要修改代码。

目标：
试跑 [股票名] 的现有报告生成入口，确认 Markdown/HTML/PDF 生成情况，并记录质量检查结果。

禁止事项：
- 不要修改任何代码。
- 不要抓雪球详情页，不要启动或控制已登录 Chrome/CDP。
- 不要改评分、技术分析、LLM prompt、报告模板。
- 不要改 data/raw、reports 里已有文件，除非报告入口自然生成新输出。
- 如果入口要求外部登录或危险采集，停止并汇报。

执行：
1. 运行对应单股入口：[脚本路径，默认 scripts/run_黑芝麻智能.py --fast-test]
2. 如果生成 Markdown，运行：python3 scripts/check_report_quality.py [生成的 Markdown 路径]
3. 记录 Markdown、HTML、PDF 是否生成以及路径/大小。
4. 简查报告是否包含趋势背景、日线结构、周线结构、成交量确认、波动率条件、综合评分、分析可信度、风险提示。
5. 不要修复问题，只记录。

完成后回复：
- 运行了哪个入口
- 生成了哪些文件
- 质量检查 PASS/FAIL/WARNING
- 主要 warning/error
- 是否有网络、LLM、Chrome/PDF 问题
- 是否发现明显报告矛盾
- git status 是否出现非报告输出以外的改动
```

本地浏览器/PDF 验证 Level 0 prompt 模板：

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做一次本地验证。

目标：
验证 [具体目标，例如重新导出 reports/黑芝麻智能_20260611.pdf，并确认 PDF 图片完整显示、不被裁切]。

允许修改：
- 如需修复，只允许修改与该问题直接相关的文件：[列出文件]
- 对应 focused test：[列出测试文件]

禁止事项：
- 不要抓雪球详情页，不要连接或控制已登录 Chrome/CDP。
- 不要修改评分、技术分析算法、LLM prompt、报告核心结构。
- 不要做无关重构或格式化。
- 不要删除已有报告/数据文件；报告入口或 PDF 导出自然覆盖目标输出可以接受。

要求：
1. 如果需要改代码，先写/保留失败测试，再做最小修复。
2. 在本地环境运行必要的 Playwright/Chromium/PDF 导出验证。
3. 检查生成 PDF 中图片是否等比缩放、完整显示、没有只露出局部的裁切问题。
4. 跑 focused tests：[列出命令]

完成后回复：
- 是否修改代码，改了哪些文件
- 本地验证了哪个 PDF/截图/浏览器输出
- focused tests 结果
- PDF 图片排版是否仍有裁切/溢出
- git status 中新增/修改了哪些报告或缓存文件
- blocker 或需要 Codex 继续审查的 diff
```

### 上下文与效率控制

- Level 0 可通过短 prompt 和 Claude 的简短结果摘要传递上下文，不创建 Markdown 交接文件。
- Level 2/3 通过 Markdown 文件传递上下文，不粘贴完整对话 transcript。
- 不再默认生成冗长 `codex-response.md`；用 design 内的 compact `Design Delta` 替代。
- 当 Codex 已经通过 diff 定位到窄范围问题时，优先直接补测试和最小修复；除非需要本地网络/浏览器/权限或会扩大设计边界，否则不再为小修重新派单。
- Codex 不尝试绕过沙箱/网络/数据外传限制来直接调用 Claude/Kimi。
- Claude Code 的执行结果写入 `YYYY-MM-DD-topic-claude-notes.md`，只记录改动、测试结果、偏离点和 blocker。
- Codex 验收必须看实际 diff 和测试结果，不能只依赖 Claude Code 总结。

### 验收责任

Codex 负责最终验收：

- 对照 design 和 `YYYY-MM-DD-topic-claude-task.md` 检查是否越界
- 运行必要测试和样例报告生成
- 检查是否违反雪球采集、数据来源、LLM 不编造、引用可追溯等项目规则
- 如涉及 LLM 合成 prompt 或合成逻辑，必须向用户展示样例输出并获得确认
