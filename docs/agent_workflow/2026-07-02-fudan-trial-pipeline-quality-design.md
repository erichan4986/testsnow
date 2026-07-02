# 复旦微电 Trial 暴露的报告 Pipeline 质量修复设计

## 背景

复旦微电正式 trial 已跑通信息采集、formal_first、4.4 external viewpoint narrative 与主报告入口，但成品报告暴露出几类问题。处理原则是：不手改 `reports/复旦微电_20260702.md`，只修导致问题的 pipeline 程序和质量门，保证下一只股票也被同样约束。

本设计吸收用户补充的三个边界：

1. 4.2 财务数字不必须来自年报全文截取。年报结构化事实、公告、东财/akshare 财务接口等正式财务数字都可作为正式源使用。
2. 行业新闻不能一刀切删除。若能形成明确链条：行业事件 -> 公司产品/业务暴露 -> 可能影响变量，则可保留为行业相关线索；若只是泛行业热闹，则不能进入公司催化剂。
3. 竞争对手不是 header 装饰。后续需要形成可复用的同行材料层，支持“优于/劣于同行/产业平均表现”和“产业红利期下个股机会”的闭环。

## 目标

- 让 4.1-4.4、估值、推荐、风险、引用、竞争对手这几条链路各有确定 owner。
- 将可确定的问题变成 deterministic check 或 focused tests。
- 修 pipeline，不修单份报告。
- 保持 formal_first source boundary：4.1-4.3 使用正式/专业源；社媒/知乎/雪球/微信仍主要在 4.4 display-only。

## 非目标

- 不重新设计整份报告结构。
- 不把社媒材料接入评分、EV、风险评分或最终建议。
- 不在本轮做全自动同行深度研究 Agent；本轮只把配置、材料层和质量边界打通。
- 不为复旦微电单独硬编码结论。

## 发现与程序归因

### P0. 4.4 正文脚注缺失

**现象**：复旦 4.4 有引用来源列表，但段落正文没有 `[^n]`。

**根因**：

- `data/curated_external/viewpoint_narratives/fudan_20260702.json` 的 paragraph 只有 `claim_refs`，没有 `citation_refs`。
- `DeepAnalysisRenderer._curated_external_narrative_addendum()` 已经会把 `citation_refs` 接到正文，但输入缺字段，因此无法渲染脚注。
- `SynthesisSkill._normalize_viewpoint_narrative_citations()` 还会过滤 `source_type != curated_external_analysis_evidence` 的 citation；如果 narrative JSON 使用 `xueqiu_column_observation`、`xueqiu_comment_observation`、`zhihu_selected_observation` 等细分类型，即使补齐 `citation_refs`，citations 也可能先被过滤为空。

**修复方向**：

- 在 narrative ingest 阶段建立 `claim_id -> citation_ref` 映射；如果 paragraph 有 `claim_refs` 且 citations metadata 带 `claim_id`，自动补齐 `citation_refs`。
- citation normalization 接受两类输入：
  - 标准化类型：`source_type == curated_external_analysis_evidence`；
  - 已验证的 display-only 细分类型：雪球专栏观察、雪球评论观察、知乎精选观察、微信公众号精选观察等，但统一输出到 renderer 前仍保留 display-only metadata，不参与 scoring/risk。
- hydration 先做精确 `claim_id` 匹配；如果历史数据使用 `curated-viewpoint:股票名:hash` 这类前缀格式，可用末段 hash/短 ID 做后备匹配。
- 同时加质量门：4.4 narrative 有 citations 且 paragraph 有 claim_refs，但正文渲染后没有 footnote，应 fail。

**测试**：

- `test_synthesis_skills.py`: narrative JSON 缺 `citation_refs` 但 citations 含 `claim_id` 时，deep_analysis_display 自动补齐。
- `test_synthesis_skills.py`: `xueqiu_column_observation`、`xueqiu_comment_observation`、`zhihu_selected_observation` 不被 normalizer 丢弃。
- `test_deep_analysis_renderer.py`: 4.4 narrative 正文必须带 deduped footnote。
- `test_report_quality.py`: 4.4 引用来源存在但正文无脚注时报错。

### P0. 估值行情口径异常

**现象**：估值区可能渲染出“流通市值 > 总市值”的不可能组合。

**根因**：

- `data_fetcher.py` 从不同行情字段/市场路径组合出 `mcap_yi` 和 `float_mcap_yi`。
- `valuation_renderer.py` 直接渲染这两个字段，没有 sanity check。

**修复方向**：

- 采用方案 A：在 `data_fetcher.py` quote 归一化层增加 `_normalize_market_cap_fields()`，renderer 只消费归一化后的结果。
- quote 增加 `market_cap_quality`：
  - total/float 都可信：正常渲染；
  - float > total * 1.05：标记 `market_cap_inconsistent`，流通市值渲染为 `N/A（口径冲突）`；
  - A/H 或多市场公司必须记录来源市场和币种。
- 港股当前 `float_mcap_yi = mcap_yi` 的兼容逻辑也走同一个 normalization。
- 美股或缺少 float market cap 的场景不渲染 `0.0 亿`，统一显示 `N/A`。
- `valuation_renderer.py` 只渲染通过 sanity 的字段，不能把明显冲突数字展示成事实。

**测试**：

- `test_data_fetcher_quote_normalization.py` 或现有 data_fetcher focused test：float market cap 大于 total 时标记异常。
- `test_valuation_renderer.py`: 异常口径不渲染“流通市值 xxx 亿”。

### P0. 趋势转弱时推荐标签过硬

**现象**：趋势/仓位已经降级，但摘要和综合评分仍可能显示裸“看多”。

**根因**：

- `recommendation_decision._apply_entry_constraint()` 对 `wait_for_entry`、`overheated`、`severe_technical` 做了 label 降级，但 `weak_trend` 只影响仓位，不影响正向推荐标签。

**修复方向**：

- 正向 raw label 遇到 `weak_trend` 时，display label 降级为“谨慎看多”或“看多但控制仓位”。
- 摘要、综合评分、风险仓位建议继续统一读取 `RecommendationDecision`。

**测试**：

- `test_recommendation_decision.py`: raw “看多” + weak_trend -> 不允许输出裸“看多”。
- `test_report_quality.py`: 技术趋势转弱时，摘要/综合评分裸“看多”给 warning 或 error。

### P1. 4.2 正式财务数字缺失

**现象**：报告 4.2 仍出现“具体数字未在给定信息中列出”，即使 formal source preflight 已显示年报、公告和财务接口可用。

**根因候选**：

- 年报全文/公告/财务接口的结构化数字未稳定进入 `KnowledgeSynthesizer` 的 4.2 输入。
- 当前 synthesis 更依赖文本材料，未先构建“正式财务指标事实包”。

**修复方向**：

- 新增或强化 `formal_financial_metrics_pack`，来源优先级：
  1. 年报/季报结构化事实；
  2. CNINFO 公告摘要中的财务指标；
  3. 东财/akshare 财务接口；
  4. 其他正式 API。
- 4.2 prompt/输入中显式注入：
  - 营收、归母净利、扣非净利、毛利率、费用率、现金流、存货/应收等。
- 若 pack 中已有核心指标，4.2 不允许说“具体数字未列出”。

**测试**：

- 使用 fixture 构造 formal metrics pack，验证 4.2 synthesis input 包含关键数字。
- `check_report_quality.py`: 若正式财务指标存在且 4.2 出现“具体数字未列出”，触发 warning/error。

### P1. 行业新闻进入 4.3 的边界太粗

**现象**：泛行业新闻可能被写成公司催化剂时间线。

**用户边界**：

- 行业新闻不是全部删除。像“AI 芯片扩销 -> 存储供不应求 -> 公司产品处于存储上游”这种有明确链条的内容，应可留作行业相关变量。
- 但不能把“半导体板块热”“IPO 同日受理”这类泛新闻直接写成公司催化剂。

**修复方向**：

- 采用 hybrid 分类，不引入本轮额外 LLM 调用：
  - intake 层用确定性规则打初始 `relevance_class`；
  - synthesis/后处理层要求 LLM 只把可解释链路的新闻写进 4.3，且输出时必须写明“行业事件 -> 公司暴露 -> 待验证变量”；
  - 无法形成链路的新闻即便输入给 LLM，也只能作为 4.1 背景或被忽略，不能渲染成公司催化剂。
- source intake 为行业新闻增加 relevance class：
  - `company_event`: 公司公告、订单、财报、调研、分红、股权等；
  - `industry_chain_relevant`: 行业事件能映射到公司业务线/产品线；
  - `sector_background`: 泛行业背景；
  - `noise`: 无关。
- 4.3 催化剂时间线只允许：
  - `company_event`;
  - 少量 `industry_chain_relevant`，且必须写明“行业事件 -> 公司暴露 -> 待验证变量”。
- `sector_background` 可以进入 4.1 产业背景，不能进入 4.3 时间线。

**测试**：

- `test_a_stock_source_intake.py`: 泛半导体新闻分类为 `sector_background`。
- 同样 fixture 中，带公司产品链路的行业新闻分类为 `industry_chain_relevant`。
- `test_knowledge_synthesizer.py`: 4.3 不展开 sector_background 为公司催化剂。

### P1. 赛道/可比公司配置与同行闭环不足

**现象**：新增股票 header 可能显示 `所属赛道: —`、`可比公司: —`；估值对比也缺少同行。

**根因**：

- `assembly_skills.py` 读硬编码 `INDUSTRY_MAP / COMPETITOR_MAP`。
- 新增股票主要写 `config/stocks.json`，但 header/估值/同行分析未完全由 config 驱动。

**修复方向**：

- 将 stock config 作为主来源：
  - `industry` / `sector`;
  - `competitors`;
  - `peer_keywords`;
  - `industry_relevance_keywords`;
- 若 config 缺同行，报告允许显示 `—`，但质量检查给 warning。
- 后续同行材料层：
  - iwencai 行业/公司对比；
  - 知乎/雪球/微信只作为 display-only 或外部观点；
  - 正式研报/年报/公告优先；
  - 输出“业务重叠、估值、盈利质量、产业红利暴露”的对比材料。

**测试**：

- `test_stock_reporter_source_intake_config.py`: 新增股票必须带 industry/competitors 或明确 `needs_peer_review`。
- `test_assembly_skills.py`: header 从 config 派生赛道和可比公司。
- `test_data_fetcher.py`: competitor list 优先来自 config。

## 实施切分

### Batch 1: 硬一致性与可见错误

范围：

- 4.4 citation hydration + gate。
- market cap sanity。
- weak_trend 推荐标签降级。

原因：这三项可测试、影响大、风险相对可控。

推荐实现顺序：

1. `weak_trend` 推荐标签降级：边界最小，先补测试再改 `_apply_entry_constraint()`。
2. 4.4 citation hydration：同时修 citation source_type normalizer 和 claim_refs -> citation_refs 补齐。
3. market cap sanity：在 data_fetcher 归一化层落地，renderer 只处理展示。

### Batch 2: 正式财务事实包与行业相关性分类

范围：

- Batch 2a: formal financial metrics pack + 4.2 数字缺失门禁。
  - metrics 来源包含年报/季报结构化事实、公告、东财/akshare 财务接口。
  - `fetch_financial_abstract()` 可作为非年报全文场景的后备来源。
- Batch 2b: industry news relevance class + 4.3 catalyst ownership。
  - 先落 deterministic relevance class，再让 synthesis/后处理保留可解释链路。

原因：涉及 source intake 和 synthesis，需要更谨慎。

### Batch 3: 竞争对手/同行材料层

范围：

- config-driven industry/competitors。
- 同行对比事实包。

原因：这是增强分析深度，不应和 P0 修复混在一个 PR。

本批不引入 `peer_source_queries`。先做 config migration、header/估值同行读取、缺失 warning；等同行研究 Agent 设计明确后再增加查询配置。

## 验收标准

- 不手改任何 `reports/*.md`。
- 复旦微电重新跑主入口后：
  - 4.4 段落正文有脚注；
  - 不出现流通市值大于总市值的渲染；
  - 趋势转弱时不显示裸“看多”；
  - 4.2 不在已有正式财务指标时声称数字缺失；
  - 4.3 不把泛行业新闻写成公司催化剂；
  - header 有赛道/可比公司，或质量检查解释缺失。
- 中际旭创或圣邦股份至少选一支做回归，确认没有破坏 formal_first、4.4 display-only 和已有推荐一致性。

## Stop Conditions

- 需要修改 LLM prompt 的核心输出结构时，先展示样例输出再继续。
- 需要扩大到雪球/CDP/详情页采集时，停止并单独授权。
- 任何修复导致 4.1-4.3 混入社媒/知乎/雪球/微信原文，必须回滚该方向。
- 如果 Batch 2 发现正式财务数据源字段不稳定，应先加 source manifest/audit 输出，不直接让 LLM 猜。
