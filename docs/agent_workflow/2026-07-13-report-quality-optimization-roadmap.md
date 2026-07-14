# Report Quality Optimization Roadmap

日期：2026-07-13
分支：`codex/annual-producer-v2`

## 1. Current Assessment

Annual Producer v2 与 Chapter 4 annual display selector 已把主要问题从“材料缺失”推进到“成品编辑质量”。当前两份验收报告的引用边界和材料保全基本稳定，但还存在五类独立问题：

1. 执行摘要可能只剩标题、评分和图表，没有可读正文。
2. 技术分析的 `primary_state`、`stage`、健康度、失效条件和价格目标可出现语义冲突。
3. Chapter 4 虽有足够 annual / broker / external 材料，但成品仍存在轻重排序、共识归纳和分歧表达不足。
4. 正式材料出版较久且缺少券商研报时，动态基本面主题可能过时或过薄。
5. 正文仍有重复来源表、调试信息、项目符号墙和章节编号不一致等版式负担。

这些问题不得再通过 producer 丢弃原始材料解决。后续优化发生在成品契约、技术判断、确定性 editorial projection、freshness policy 和排版层；另以独立基础设施批次处理 Knowledge 持久化膨胀。

## 2. Shared Invariants

1. 不编造数据；任何数字、公司事实和外部观点必须来自已有材料。
2. 正式材料、机构分析和外部观点继续保持独立信用层。
3. 外部材料可以补充近期基本面变量，但不得升级为官方确认、评分、风险评分或目标价依据。
4. Producer、annual memo 和 MaterialSnapshot 继续保留完整材料。
5. 每一批独立设计、测试和验收；不得把五类问题合成一次大改。
6. 技术算法、评分、目标价和 LLM prompt 只有在对应专项设计批准后才能修改。
7. 正式报告必须由修改后的源码重新生成，不验收 stale 样本。

## 3. Delivery Order

当前状态：

- Batch 1 已完成，checkpoint：`3ae8c86`；
- Batch 2 已完成，checkpoint：`4f84fd2`；
- 当前进入 Batch 3；
- Batch 4–6 必须按顺序独立设计、实现和复跑，不得合并成一次大改。

### Batch 1: Executive Summary Completeness

目标：每份报告稳定输出基本面、估值预期、交易状态与风险、一句话结论；LLM 提取为空时也不产生空壳摘要。

边界：只使用现有结构化输入和 RecommendationDecision；不改技术算法、评分、目标价、Chapter 4 或 LLM prompt。

验收：中际旭创与复旦微电执行摘要均有实质正文；真正空摘要触发 quality error。

### Batch 2: Technical Analysis v2

目标：统一趋势主状态、阶段、健康度、失效条件、目标展示和交易触发语义。

重点问题：

- 上升趋势、主升期、低健康度与“趋势结构转弱”的冲突；
- 站上 MA60 却显示“略低于/无法收回”；
- 支撑压力识别失败或目标置信度极低时仍突出精确价格目标；
- 已越过历史颈线却仍显示为未满足价格触发；
- 市场共振数据缺失时输出占位分析；
- 时间预期精度超过当前证据能力。

边界：单独走 Level 3 设计，不在 Batch 1 做临时文案补丁。

### Batch 3: Deterministic Chapter 4 Editorial Projection

目标：在完整 MaterialSnapshot 之上，以确定性 read-model 把材料编辑成投研叙事，而不是逐 row 展示。

建议输出：

- 业务画像与竞争位置；
- 经营驱动与财务质量；
- 机构共识、差异和反方约束；
- 外部近期变量及其验证状态；
- 观点升级与降级条件。

本批不上 LLM memo，不修改 prompt。formal-medium 的 `Chapter4ViewModel` 负责 display rows 的排序、分组和预算；formal-thin 复用同一个 annual selector，同时保留既有 broker/external adapters 与 full-snapshot citation offset。renderer 只负责排版，不再持有第二套 annual selector 或 external hard slice。输出引用必须是输入引用的子集。

本批同时做窄版式清理：

- 4.1–4.4 从 bullet wall 改为短段落；
- 新版 formal-medium / formal-thin 路径只保留 inline footnotes 和全局引用表；
- Source Intake 正文诊断默认隐藏，但 ingestion/material context 保持启用，并可用显式 debug 开关恢复；
- formal-rich legacy body 不变。

LLM editorial memo 延后评估。只有确定性投影仍无法达到可读性目标时，才另开 Level 3 设计，不作为本批隐含 fallback。

### Batch 4: Evidence Freshness Adaptation

目标：避免年报或半年报出版较久、且缺少券商研报时，动态基本面内容过时或过薄。

采用按主题判断新鲜度：

- 业务模式、长期产品线和稳定竞争位置可继续使用较早正式材料；
- 订单、客户、产能、毛利率、需求和产品验证等动态主题在正式材料超过约 120 天后需要近期补充；
- 来源优先级为最新季报/业绩预告/公告/调研记录，其次券商或行业材料，最后精选外部材料；
- 外部材料扩充 4.3，并最多有一条进入执行摘要的“待验证变量”；不得进入 4.1 官方确认。

不设置外部观点死板条数上限，只使用相关性、来源完整性、同源去重和信用边界控制。

### Batch 5: Report Layout Cleanup

目标：减少工具输出感，形成可连续阅读的投研成稿。

候选改动：

- Source Intake 诊断移入附录或 debug 模式；
- 减少“本节引用来源”和全局引用表的重复展示；
- 把连续卡片式 bullet 改成“判断 + 证据 + 含义”的短段落；
- 统一章节编号；
- 清理绝对图片路径、OCR 空格和非必要装饰符号；
- 保留 Markdown、HTML 和 PDF 的可追溯引用与可移植资源路径。

Batch 3 已完成的窄版式项不在本批重复实现。Batch 5 只处理剩余的全局问题，例如章节编号、资源相对路径、Markdown/HTML/PDF 一致性和非 Chapter 4 的工具输出感。

### Batch 6: Knowledge Persistence Slimming

目标：保留 Annual Producer v2 的全部 SourceUnit、选择诊断和 coverage 证明，同时停止为每个原子 argument 写一张冗长 Markdown note。

当前本地刷新结果为 8 只股票、881 张 v2 notes、约 69,708 行。膨胀来自两个因素：

- 一个 evidence block 可以拆成多张 argument card，48-block 不是 card 上限；
- 每张 note 重复写 frontmatter、Narrative Evidence、Source Units JSON、Selection Diagnostics、Source 和 Guardrails。

采用 pack-first + human-note projection：

- 每只股票每期保存一个完整、结构化的 annual material pack，作为 material loader 的机器输入；
- Obsidian Markdown 只投影少量高价值、可阅读的主题 notes；
- 不通过 producer 丢 card，不降低八股 coverage，不删除 SourceUnit；
- v1 notes 的归档/删除必须等 pack migration 与兼容 gate 独立通过。

本批必须单独走 Level 3。当前 881 张本地 notes 保留但不提交，直到持久化契约锁定。

## 4. Dependency Rules

1. Batch 1 可独立实施。
2. Batch 2 完成后，Batch 1 的交易状态摘要才能接入更丰富技术判断；Batch 1 当前只复用 RecommendationDecision 的保守结论。
3. Batch 3 必须复用完整 MaterialSnapshot，不得回退到 producer 过滤。
4. Batch 4 在 Batch 3 已稳定的 Chapter 4 display contract 上增加 freshness metadata 和近期补充规则，不改变 4.1 的官方材料边界，也不把 freshness selection 放回 renderer。
5. Batch 5 在 Batch 4 后处理剩余全局版式，避免先改章节编号和资源路径后因 freshness 结构变化返工。
6. Batch 6 在报告成品结构稳定后进行，避免同时改 material storage 与 renderer；它不得反向改变 Batch 3 的 display contract。

## 5. Global Stop Conditions

- 需要修改当前批次范围之外的高风险模块；
- 引用无法保持完整、出现 missing / unused / malformed；
- 需要把低信用来源升级为确认事实；
- 需要新增股票名、股票代码或行业专用 hardcode；
- focused tests 或既有质量门出现无法解释的跨模块回归；
- 正式报告无法证明为修改后的新产物。
