# Credit-Aware Synthesis Layer Design

日期：2026-06-15

## Status

Revised after Round 1 feedback. Ready for Round 2 review.

## 背景

当前报告已经具备三类证据链路：

- 高信用来源：巨潮公告、公司公告、公司官网、交易所披露等。
- 中信用来源：券商研报摘要、东方财富新闻、同花顺新闻、行业政策、产业链新闻等。
- 低信用来源：雪球、股吧、微博/B站等社区讨论。

现有 `KnowledgeSynthesizer` 主要把 `SynthesisItem` 编号后交给 LLM 合成，并通过 `claim_verification_context` 提供 verified/supported/unverified 的社区 claim 状态。当前约束已经能避免 unverified claim 进入核心事实，但还没有系统表达：

- 中信用来源可以参与分析判断，但不能写成“公司确认”。
- verified / supported discussion 可以作为“被验证的市场线索”参与分析观点生成。
- 由证据推导出的收入、利润、估值判断必须标成 inference，而不是事实。

因此需要增加一层 **Credit-Aware Synthesis Layer**：让 LLM 根据证据信用与验证状态决定材料的写法、位置和推理边界。

## 目标

1. 保持核心事实基座干净：只允许高信用 confirmed facts 或明确高信用引用支持的客观事实进入。
2. 允许中信用专业来源参与产业逻辑、业绩路径、估值分歧和风险观察，但必须保留来源属性。
3. 允许 verified / supported 社区 discussion 进入“带证据等级的分析观点”，但不能伪装成官方事实。
4. 明确区分：
   - 已确认事实
   - 专业观察
   - 已验证讨论线索
   - 部分支持讨论线索
   - 社区共振线索
   - 未验证市场讨论
   - 分析推论
5. 不改变 scoring、technical、EV、position advice、report assembly 顺序。

## Non-Goals

- 不新增外部数据源。
- 不重新设计 claim verification 匹配算法。
- 不让中信用新闻/研报直接验证为官方事实。
- 不让 unverified social claim 进入核心事实、风险因子表、最终推荐或编号引用。
- 不在本阶段修改 `check_report_quality.py`，污染质量门可作为下一阶段。
- 不改变现有 citation 编号系统，不引入 `^verified` 这类可能和 `[^n]` 混淆的新引用语法。

## 术语

### confirmed_fact

来自高信用来源，或正文中有高信用编号引用支持的客观事实。

写法：

- “公司公告披露……”
- “业绩预告显示……”

允许：

- 进入核心事实基座。
- 支撑正文结论。
- 参与风险和关注点。

### professional_observation

来自中信用来源，例如券商研报、新闻、政策或产业链报道。

写法：

- “券商研报关注……”
- “媒体报道显示……”
- “政策文件指向……”

限制：

- 不得写成“公司确认”。
- 不得单独进入核心事实基座。
- 可作为背景和专业判断材料。

### verified_discussion

低信用社区讨论中的 claim 被高信用来源验证。

写法：

- “社区讨论中关于 X 的线索，已与公告/业绩预告相互印证……”

允许：

- 进入“多来源验证观察”。
- 可参与主题分析和风险观察。
- 如果正文使用，必须同时引用上方高信用编号来源，而不是引用 claim verification appendix。

限制：

- 不能把“社区讨论”本身写成核心事实。
- 只能把被高信用来源确认的前提视为可用，后续推论仍需标注 inference。

### supported_discussion

低信用社区 claim 被中信用来源支持，但没有高信用来源确认。

写法：

- “该线索获得新闻/研报支持，但仍非官方确认……”

允许：

- 进入“多来源验证观察”。
- 可参与市场分歧、估值争议、关注点。

限制：

- 不进入核心事实基座。
- 不得写成公司已确认。
- 不得作为强结论唯一依据。

### unverified_discussion

低信用社区 claim 未被高/中信用来源匹配。

写法：

- “社区讨论中出现……，但当前缺少高信用证据支持。”

限制：

- 不进入核心事实。
- 不进入风险因子表。
- 不进入最终建议。
- 只可在待验证线索或 audit 中出现。

### corroborated_discussion

多个低信用来源出现相似 claim，但没有中/高信用来源支持。

中文报告中建议写作：

- “社区共振线索”
- “多源市场讨论”
- “多个社区来源共同关注……”

含义：

- 它表示市场关注度或讨论热度提高。
- 它不表示事实确认等级提高。
- 多个低信用来源互相重复，不能升级为 `supported_discussion` 或 `verified_discussion`。

写法：

- “雪球、股吧等多个社区来源都关注 X，但当前缺少公告、研报或新闻支持。”
- “该议题已形成社区讨论焦点，仍需官方公告、订单、产能、价格或财务数据验证。”

允许：

- 进入市场分歧、情绪跟踪、待验证关注点。
- 作为后续验证清单的优先项。

限制：

- 不进入核心事实基座。
- 不直接进入风险因子表或风险加分。
- 不进入最终建议。
- 不得写成“已验证”或“公司确认”。
- 只有后续被中信用来源支持，才可升级为 `supported_discussion`；被高信用来源验证，才可升级为 `verified_discussion`。

Phase 1 约束：

- 当前 `claim_verification.py` 只输出 `verified / supported / needs_review / unverified`。
- Phase 1 不新增 `corroborated` action，不在 claim verification appendix 中渲染 corroborated row。
- Phase 1 只在 prompt 规则中说明：多个低信用来源重复出现不得被 LLM 视为 fact verification。
- 真正的低信用-低信用相似度检测和 `corroborated` schema 扩展放到 Phase 2。

### analyst_inference

基于 confirmed/professional/verified/supported 前提出发的分析判断。

写法：

- “在该前提下，可能意味着……”
- “若后续订单/产能利用率兑现，可能带来……”

限制：

- 不得编造数值。
- 收入、利润、估值影响必须说明缺失变量，例如订单、ASP、产能利用率、毛利率。
- 不得被核心事实提取器抽为事实。

## 当前系统入口

### `SynthesisItem`

`scripts/utils/source_adapter.py` 的 `SynthesisItem.extra` 已可携带：

- `source_credit`
- `verification_status`
- `source_type`
- `source_domain`
- `knowledge_eligible`

当前非 Agent-Reach 的 adapter 不一定都填这些字段，但 Source Intake / evidence notes / source credit helper 已有能力提供类似 metadata。

### `claim_verification_context`

`KnowledgeSynthesizer._format_claim_verification_context()` 已把 verified/supported/unverified/needs_review 作为非引用 appendix 加入 prompt。

现有约束：

- appendix 不是新的引用来源。
- verified 只有当同一事实也出现在编号信息来源中时才可使用。
- supported 不能写成确认事实。
- unverified 不得进入核心事实。

本设计将增强该 appendix 的“可用方式”说明，而不是改变其引用属性。

### `core_facts`

`extract_core_facts()` 当前要求只提取客观事实和数据，并要求 `source_refs` 来自正文 `[^n]`。

本设计要求进一步明确：

- professional_observation / supported_discussion / analyst_inference 不应被抽入核心事实。
- verified_discussion 中只有被高信用来源确认的客观前提可以进入核心事实，且必须指向高信用编号来源。

## 设计方案

### 1. 增加 prompt 内的 Credit Usage Rules

在每个主题 prompt 中追加统一规则：

```text
证据信用与写法规则：
- 高信用/官方/公告/交易所来源：可写为“公司公告披露/业绩预告显示”，可作为事实。
- 中信用/研报/新闻/政策来源：只能写为“券商研报关注/媒体报道显示/政策文件指向”，不得写成公司确认。
- verified discussion：可写为“社区讨论中的 X 已与公告相互印证”，但必须引用上方编号的高信用来源。
- supported discussion：可写为“该线索获得新闻/研报支持，但仍非官方确认”。
- 多个低信用来源重复出现时，只能理解为“社区共振/市场关注”，不得写成事实确认；Phase 1 不会从 claim verification appendix 中提供 `corroborated` bucket。
- unverified discussion：只能作为待验证市场观点，不得进入结论、核心事实或风险加分。
- 推论必须显式标注为“可能/若/需要验证”，不得把推论写成事实。
```

该规则只影响 LLM 写法，不改变输入数据和 pipeline 顺序。

### 2. 增加可读的 Source Credit Label

在 `_build_prompt()` 的 source line 中增加保守标签，来源于 `item.extra` 和 `source_platform`。

示例：

```text
[3] 标题: 2026年第一季度业绩预告 | 来源: 公告 | 信用层: 高信用/confirmed_fact | 可用方式: core_fact_allowed | ...
[8] 标题: 东财新闻... | 来源: 新闻 | 信用层: 中信用/professional_observation | 可用方式: background_only | ...
[12] 标题: 雪球帖子... | 来源: 雪球 | 信用层: 低信用/market_discussion | 可用方式: discussion_only | ...
```

建议通过一个纯 helper 推导：

```python
derive_synthesis_usage(item) -> {
  "credit_tier": "high" | "medium" | "low" | "unknown",
  "usage": "core_fact_allowed" | "professional_observation" | "discussion_only",
  "display_label": "...",
}
```

第一版不需要修改 `SynthesisItem` dataclass，避免大范围适配器改动。

### 3. 增强 Claim Verification Appendix

当前 appendix 已列出 verified/supported/unverified。新增写法边界：

- verified row：
  - `证据等级：已验证讨论线索`
  - `可用方式：可参与分析；如写入正文，必须引用上方编号来源中与其匹配的高信用来源`
- supported row：
  - `证据等级：部分支持讨论线索`
  - `可用方式：可参与市场分歧/关注点；不得写成官方确认`
- unverified row：
  - `证据等级：未验证市场讨论`
  - `可用方式：仅保留为待验证线索；不得进入核心事实/结论`

Phase 1 不渲染 corroborated row，因为当前 summary schema 不存在该 bucket。若后续 Phase 2 扩展 schema，再新增：

- corroborated row：
  - `证据等级：社区共振线索`
  - `可用方式：可描述市场关注度；不得作为事实确认、风险加分或最终建议依据`

仍然保持：

- appendix 不是引用来源。
- 不产生新的 citation。
- 不写入 `source_index`。

### 4. 新增“多来源验证观察”作为可选合成产物

不建议第一版直接新增独立 renderer。Phase 2 可在 synthesis 结果里增加一个可选键：

```python
multi_source_observations: [
  {
    "claim": "...",
    "status": "verified" | "supported" | "corroborated" | "unverified",
    "analysis_use": "risk_observation" | "valuation_debate" | "watch_item",
    "verified_by_titles": [...],
    "inference_boundary": "..."
  }
]
```

Phase 2 可由 deterministic helper 从扩展后的 `claim_verification_summary` 生成，不让 LLM 生成结构化 JSON。

报告展示可以暂缓，先用于 prompt context 和 notes；如果要展示，后续放在 DeepAnalysis 之后、Source Intake 之前。

### 5. 核心事实提取约束增强

`extract_core_facts()` prompt 增加：

```text
不要提取以下内容为核心事实：
- 券商/媒体观点本身
- 社区讨论观点本身
- supported/unverified discussion
- 任何“可能、预计、推测、若...则...”形式的分析推论

只有当事实由公告/官方/交易所/编号高信用来源支持时，才可进入核心事实。
```

同时保留现有 `source_refs` 清洗与 provenance enrichment。

### 6. 核心事实 provenance hard filter

Round 1 review 指出：现有 `_enrich_core_fact_provenance()` 会把 `新闻`、`研报`、`雪球`、`知乎` 等 source family 标记为 `provenance_status: supported`，这会违背 professional_observation 不得进入核心事实的目标。

Phase 1 必须增加 deterministic hard filter：

```python
is_core_fact_supporting_source(source_family, meta) -> bool
```

第一版允许支撑核心事实的来源家族：

- `公告`
- `官方`
- `交易所`
- `巨潮`
- 后续明确标注为 `confirmed_fact` 且 `source_credit >= 80` 的来源

第一版不得作为核心事实支撑的来源家族：

- `研报`
- `新闻`
- `雪球`
- `知乎`
- `AgentReach(...)`
- `资金流向`
- unknown

实现选择：

- 推荐在 `_enrich_core_fact_provenance()` 中过滤 accepted labels：只有 high-credit fact-supporting source 才进入 `accepted_labels`。
- 如果 refs 全部来自中/低信用来源，则该 core fact 标记为 `invalid_ref`，并在 renderer 中显示“未绑定有效高信用引用”。
- 不在本阶段直接 drop fact，保留 invalid status 便于审计；后续质量门可选择 warning。

该 hard filter 是 Phase 1 的必做项，不是 Phase 2。

### 7. Source usage fallback mapping

`SynthesisItem.extra` 不稳定，非 Agent-Reach adapter 可能没有 `source_credit`。Phase 1 必须提供显式 fallback 映射：

| source_platform | credit_tier | usage |
|---|---|---|
| 公告 | high | core_fact_allowed |
| 巨潮 / 交易所 / 官方 | high | core_fact_allowed |
| 研报 | medium | professional_observation |
| 新闻 | medium | professional_observation |
| 东方财富新闻 / 同花顺新闻 | medium | professional_observation |
| 资金流向 | medium | quantitative_observation |
| 雪球 | low | discussion_only |
| 知乎 | low | discussion_only |
| AgentReach(...) | from extra if present, otherwise low/limited |
| unknown | unknown | background_limited |

`derive_synthesis_usage(item)` 优先级：

1. 如果 `item.extra.source_credit` / `verification_status` 存在，优先使用结构化 metadata。
2. 否则使用 `source_platform` fallback。
3. unknown 默认最保守，不允许 core fact。

### 8. Legacy prompt path 同步

`SynthesisSkill._legacy_llm_synthesize()` 使用 `_build_prompt()`，该路径必须同步同样的信用规则。

Phase 1 要求：

- credit usage rules 抽成共享文本 helper。
- source usage label helper 可被 `KnowledgeSynthesizer._build_prompt()` 和 legacy `_build_prompt()` 复用。
- legacy claim verification appendix 同步 verified/supported/unverified 的写法边界。

### 9. Verified discussion 显式标签

Phase 1 关闭 Open Question 4：

- 正文使用 verified discussion 时，必须出现“社区讨论线索已与……相互印证”或“已验证讨论线索”等显式字样。
- 不能把 verified discussion 直接改写成无来源属性的事实句。

### 10. 中信用风险文字边界

Phase 1 关闭 Open Question 5：

- 中信用新闻/研报可以进入“风险观察/关注点”文字。
- 中信用来源不得直接生成结构化风险信号。
- 风险评分表只接受 claim verification 输出的 verified/supported structured risk signals。
- `professional_observation` 不能单独影响风险分。

## 数据流

```text
Source Intake / Xueqiu / Zhihu / Reports / News
  -> SynthesisItem + extra metadata
  -> SynthesisSkill builds items
  -> Claim Verification summary built separately
  -> KnowledgeSynthesizer prompt:
       numbered sources with credit usage labels
       claim verification appendix with usage rules
       previous narratives
  -> LLM thematic synthesis
  -> parse citations
  -> extract_core_facts with stricter rules
  -> deterministic provenance enrichment
       hard filter: only high-credit official/announcement/exchange sources support core facts
```

## 报告写法示例

### verified discussion + inference

```text
社区讨论中关于一季度收入阶段性承压的线索，已与公司业绩预告中“客户需求阶段性减少导致发货暂时减少”的表述相互印证[^3]。这说明短期收入压力更可能来自交付节奏和需求阶段波动，而不是单纯的价格因素；但是否延续到全年，仍需后续订单与产能利用率数据验证。
```

说明：

- `已相互印证` 对应 verified discussion。
- `[^3]` 必须是公告/高信用编号来源。
- 后半句是 analyst_inference，使用“更可能”“仍需验证”。

### supported discussion

```text
市场讨论中关于行业竞争压力加大的观点，获得部分媒体和研报关注，但当前缺少公司公告层面的直接确认，因此更适合作为估值分歧变量，而不是已确认风险。
```

### unverified discussion

```text
关于榆林基地满产后营收翻倍的讨论仍缺少订单、ASP 和产能利用率证据，本报告仅将其列为待验证线索，不纳入核心结论。
```

### corroborated discussion

```text
雪球与股吧等多个社区来源都关注榆林基地满产后的收入弹性，说明该议题已形成市场讨论焦点；但当前缺少公告、订单、ASP 和产能利用率数据支撑，因此仍属于社区共振线索，不纳入核心事实或收入预测。
```

## 测试计划

### KnowledgeSynthesizer prompt tests

- numbered source line includes credit usage label for announcement / report / news / social.
- prompt contains credit usage rules.
- claim verification appendix labels verified/supported/unverified with usage boundaries.
- prompt states repeated low-credit-only discussion is market attention only, not fact verification.
- appendix still says it is not a citation source.
- previous narratives remain after claim verification appendix.
- legacy chat prompt includes the same credit usage rules.

### Core facts tests

- core facts extraction prompt excludes professional observations and analyst inference.
- source refs normalization remains unchanged.
- supported/unverified discussion wording in narratives should not become core facts if no high-credit refs.
- corroborated discussion wording should not become core facts if only low-credit refs exist.
- core fact provenance rejects refs that only point to news/report/community/AgentReach/fundflow sources.
- core fact provenance accepts announcement/official/exchange/high-credit confirmed sources.

### SynthesisSkill tests

- existing `claim_verification_summary` still reaches `KnowledgeSynthesizer`.
- source metadata labels do not mutate `SynthesisItem`.
- legacy `.chat(prompt)` path receives the same credit usage constraints.
- `derive_synthesis_usage()` fallback maps legacy adapters without `extra.source_credit`.

### Regression tests

- existing `tests/utils/test_knowledge_synthesizer.py`.
- existing `tests/reporter/test_synthesis_skills.py`.
- one sample prompt snapshot for 中简科技 should show:
  - 公告 as high/core_fact_allowed
  - 新闻/研报 as medium/professional_observation
  - verified claims as verified_discussion
  - repeated low-credit-only claims described only as community attention, not fact verification
  - unverified claims blocked from core facts

## 风险与防护

### 风险：LLM 仍把 supported 写成 confirmed

防护：

- prompt 明确 forbidden wording。
- core fact extraction 二次过滤。
- 后续可加 report quality guard 检查“媒体报道/研报观点”是否被写成“公司确认”。

### 风险：多个低信用来源被误当成事实确认

防护：

- 明确 `corroborated_discussion` 只表示社区关注度。
- prompt 禁止把低信用多源重复写成 confirmed/verified。
- 风险评分仍只接受 verified/supported 的结构化风险信号。
- 后续质量门检查“社区共振线索”是否进入核心事实或最终建议。

### 风险：引用混淆

防护：

- 不使用 `^verified`。
- claim verification appendix 不产生 citation。
- 正文如使用 verified discussion，必须引用上方编号来源。

### 风险：推论变成事实

防护：

- 要求推论使用“可能/若/需要验证”。
- core facts prompt 排除预测和推论。

### 风险：信息源 metadata 不完整

防护：

- `derive_synthesis_usage()` 对缺失 metadata 使用 source_platform fallback。
- unknown 来源默认 `discussion_or_background_limited`，不得进入核心事实。

## 分阶段实施建议

### Phase 1：Prompt + deterministic hard-filter safety upgrade

- 增加 credit usage rules。
- source lines 增加信用/可用方式标签。
- claim verification appendix 增强 verified/supported/unverified 写法约束。
- core facts extraction prompt 增强排除规则。
- 增加 `derive_synthesis_usage()` fallback mapping。
- 增加 core fact provenance hard filter：只有公告/官方/交易所/巨潮/high-credit confirmed 来源可支撑核心事实。
- legacy `.chat(prompt)` 路径同步同样信用规则。

不新增 renderer，不新增 pipeline skill。

### Phase 2：Multi-source observation structure

- Deterministic helper 从 claim verification summary 生成 `multi_source_observations`。
- 可选扩展 claim verification schema，增加 `corroborated` action 或 separate bucket，用于低信用-低信用相似 claim 的社区共振检测。
- 可选择在报告中展示“多来源验证观察”小节。

### Phase 3：Quality guard

- `check_report_quality.py` 检查中信用/低信用污染：
  - unverified social claim 不得出现在核心事实/风险因子/最终建议。
  - “媒体报道/券商研报”不得被写成“公司确认”。

## 建议本次实现范围

先做 Phase 1。

理由：

- 改动集中在 `KnowledgeSynthesizer` 和 `SynthesisSkill` 测试。
- 不改变报告结构和评分路径。
- 可以立刻提升 synthesis 对不同信用来源的处理质量。
- deterministic hard filter 直接修复新闻/研报/社区来源进入核心事实的污染风险。
- 风险可控，便于用 prompt snapshot 和 provenance unit tests 验收。

## 禁止修改范围

本阶段不得修改：

- `scoring_engine.py`
- 技术分析算法
- EV / position advice
- Source Intake fetcher
- Agent-Reach fetcher
- Xueqiu / CDP / Playwright 采集逻辑
- `config/stocks.json`
- `knowledge/` 真实笔记
- `reports/` runtime 输出

## Closed Design Decisions After Round 1

1. Phase 1 不新增 `multi_source_observations` 结构；只做 prompt/usage label/appendix/hard filter。
2. `derive_synthesis_usage()` 建议先放在 `knowledge_synthesizer.py` 或相邻小 helper 中；若 `check_report_quality.py` 后续复用，再抽到独立模块。
3. 核心事实必须增加 provenance hard filter，不能只靠 prompt。
4. verified discussion 正文必须出现“相互印证/已验证线索”等显式字样。
5. 中信用研报/新闻允许进入风险观察文字，但不进入结构化风险信号，不影响风险评分。

## Acceptance Criteria

- Prompt 中明确区分高/中/低信用与 verified/supported/unverified discussion 的使用方式。
- Prompt 中明确 `corroborated_discussion` 只代表多源低信用共振，不代表事实确认。
- 中信用来源在 prompt 中标注为 professional observation，不可写成公司确认。
- Claim verification appendix 不成为 citation source。
- Core facts extraction prompt 明确排除专业观察、社区观点和分析推论。
- Core fact provenance hard filter 阻止新闻/研报/社区/AgentReach/资金流向支撑核心事实。
- Legacy `.chat(prompt)` 路径包含相同信用规则。
- Existing synthesis and core fact tests pass.
- No report runtime required unless implementation touches LLM output behavior and user explicitly要求样例输出。

## Round 1 Design Delta

Round 1 review 结论为 `Must-fix before task`，本版采纳以下修正：

1. **Phase 1 不再是 prompt-only。**
   - 必须增加 deterministic core fact provenance hard filter。
   - 只有公告/官方/交易所/巨潮/high-credit confirmed 来源可支撑核心事实。
   - 新闻、研报、社区、Agent-Reach、资金流向、unknown 不可支撑核心事实。

2. **`corroborated_discussion` 暂不进入 Phase 1 schema。**
   - 当前 claim verification action 只有 `verified / supported / needs_review / unverified`。
   - Phase 1 只在 prompt 中禁止“多个低信用来源互相验证”的误用。
   - 低信用-低信用相似度检测和 `corroborated` bucket 放入 Phase 2。

3. **`derive_synthesis_usage()` 必须有 source_platform fallback。**
   - 多数 legacy adapter 不填 `extra.source_credit`。
   - 映射表必须覆盖公告、研报、新闻、雪球、知乎、资金流向、AgentReach、unknown。

4. **legacy `.chat(prompt)` 路径必须同步。**
   - credit usage rules 和 claim verification appendix 约束不能只存在于 `KnowledgeSynthesizer._build_prompt()`。

5. **verified discussion 必须显式标注。**
   - 正文使用 verified discussion 时，必须出现“社区讨论线索已与……相互印证”或“已验证讨论线索”等字样。

6. **中信用风险文字边界已关闭。**
   - 中信用新闻/研报可进入风险观察文字。
   - 不可直接生成结构化风险信号。
   - 不可直接影响风险分。

## Round 1 Feedback

- **Status**: Must-fix before task
- **R2 Needed**: Yes

### Findings

#### blocker: 当前 `_enrich_core_fact_provenance` 会把新闻/研报来源标记为 `supported`，与设计目标直接冲突

`scripts/utils/report_skills/synthesis_skills.py:274-304` 的 `_derive_evidence_type()` / `_derive_provenance_status()` 会把 `source_platform` 为 `研报`、`新闻` 的引用标记为 `evidence_type: research_report|news` 和 `provenance_status: supported`。设计目标要求 `professional_observation` 不得进入核心事实基座，但现有 provenance enrichment 会让 LLM 一旦从新闻/研报提取出 core fact 并通过 `[^n]` 引用，就被渲染成带 `supported` 标签的核心事实。这会直接造成“研报/新闻观点被写成事实”的污染。

设计文档只在 Phase 1 提出“prompt 排除规则”，未提出 deterministic guard。仅靠 LLM prompt 无法确保新闻/研报事实不被抽入 core facts，且即使 LLM 没抽， enrichment 逻辑本身也在鼓励中信用来源进入核心事实。

**Required delta**: 必须在 provenance enrichment 层增加 hard filter，只把 `公告/官方/交易所/高信用证据` 视为可支撑 core fact 的有效来源；`研报`、`新闻`、社区来源对应的 core fact 必须被标记为 `invalid_ref` 或被过滤掉。

#### blocker: `corroborated_discussion` 在当前 claim verification summary 中不存在，Phase 1 无法安全使用

`scripts/utils/claim_verification.py:822-903` 的 `_verify_claim()` 只对比低信用 claim 与高信用/中信用证据，输出 `verified / supported / needs_review / unverified` 四种 action。两个或多个低信用来源重复出现但没有高/中信用支持时，每个都会独立得到 `unverified`，summary 里不会生成 `corroborated` bucket。

设计文档 Phase 1 却要求在 prompt 中标注 `corroborated row`，并测试 “claim verification appendix labels corroborated discussion as market-attention only if such rows are present”。当前 schema 无法产生这样的行，因此 Phase 1 实施时会落空，或者工程师被迫在低信用来源之间做二次匹配，这就已经不是 prompt-only 了。

**Required delta**: Phase 1 要么删除对 `corroborated_discussion` 的展示（仅保留术语定义，提示未来实现），要么先在 `claim_verification.py` 中增加 `corroborated` 检测逻辑并同步扩展 `summarize_claim_verification_plan()`。若选择后者，必须更新 claim verification 的测试并确认不会影响现有 `verified/supported/unverified` 计数。

#### medium: `derive_synthesis_usage()` 的 fallback 策略对非 Agent-Reach 适配器不够安全

`scripts/utils/source_adapter.py` 里只有 `AgentReachAdapter` 填充了 `source_credit`、`source_type` 等字段；`ReportAdapter`、`NewsAdapter`、`AnnouncementAdapter`、`XueqiuAdapter` 等的 `extra` 是空的或只有业务字段。Phase 1 若通过 `item.extra` 推导信用层，大量 source 会落到 `unknown`。

设计文档提到“对缺失 metadata 使用 source_platform fallback”，但未给出映射表。如果 `unknown` 默认 `discussion_or_background_limited`，那么公告类来源（`source_platform: 公告`）没有 `source_credit` 时也会被降级，这虽然安全（不会把中信用写成高信用），但会导致高信用事实无法被正确标注为 `core_fact_allowed`。

**Required delta**: 在 `derive_synthesis_usage()` 中显式维护 `source_platform -> credit_tier / usage` 的 fallback 映射，覆盖 `公告`、`研报`、`新闻`、`雪球`、`知乎`、`AgentReach(...)`、`资金流向` 等已知平台；unknown 默认 `discussion_or_background_limited` 并记录 warning。

#### medium: legacy `.chat(prompt)` 路径未同步信用规则

`scripts/utils/report_skills/synthesis_skills.py:311-379` 的 `_build_prompt()` 和 `_format_claim_verification_appendix()` 是 legacy chat 路径专用的 prompt，其中没有“证据信用与写法规则”、没有 source credit label、也没有 core fact 排除规则。测试计划要求 “legacy `.chat(prompt)` path receives the same credit usage constraints”，但设计文档的 Phase 1 改动范围只字未提同步 legacy path。

如果 legacy path 被真实调用（例如某些调用方传入 `llm_client`），它会绕过 KnowledgeSynthesizer 的 prompt 约束，导致中信用/低信用污染。

**Required delta**: 把 credit usage rules 和 source credit label 逻辑抽到可复用函数，同时注入 `_build_prompt()` 和 KnowledgeSynthesizer 的 `_build_prompt()`；同步更新 `_format_claim_verification_appendix()` 的约束描述。

#### medium: verified discussion 的显式写法未作为强制要求

Open Question 4 提出“verified discussion 正文是否必须出现‘相互印证/已验证线索’等显式字样”，但设计文档未给出结论。若不强制，LLM 很可能把 verified claim 直接写成事实，仅在末尾引用高信用来源，读者无法区分这是“社区线索被验证”还是“官方事实”。

**Required delta**: 在 prompt 中强制要求 verified discussion 必须出现“社区讨论线索已与…相互印证”或类似显式标签，并在 report quality / test snapshot 中检查该字样。

#### low: 中信用来源进入“风险提示文字但不进入风险评分”的边界未明确

Open Question 5 提出该问题但未回答。当前 `scoring_engine.py` 默认 `score_llm_keyword_risks=False`，风险评分只接受 `structured_risk_signals` 中的 `verified/supported` 信号，因此中信用新闻/研报不会直接影响分数。但在深度分析文字中，LLM 可能把“媒体报道的竞争加剧”写成风险描述。这是允许的，但必须与评分表中的风险因子区分。

**Required delta**: 在 prompt 中说明中信用来源可以出现在“风险观察/关注点”文字中，但不得生成 `verified/supported` 结构化风险信号；风险评分表只允许 claim_verification 输出的 verified/supported 信号。

### Required design deltas

1. **增加 core fact provenance hard filter**
   - 修改 `SynthesisSkill._derive_provenance_status()` 或新增 `_is_core_fact_supporting_source()`：只有 source family 为 `公告`（以及未来可能的 `交易所`、`巨潮`、`官方`）时才视为有效支持；`研报`、`新闻`、`雪球`、`知乎`、`AgentReach` 均视为无效/排除。
   - 或者直接在 `extract_core_facts()` 之后增加 post-filter：drop 任何 `source_labels` 不包含高信用来源的 core fact。
   - 同步更新 `tests/reporter/test_synthesis_skills.py` 中关于 `evidence_type: news/research_report/community` 的测试预期。

2. **处理 corroborated_discussion 的来源问题**
   - 选项 A（推荐）：Phase 1 只在术语章节保留 `corroborated_discussion` 定义，prompt 和 appendix 中先不展示 corroborated row；等 Phase 2 扩展 claim verification schema 后再启用。
   - 选项 B：在 `claim_verification.py` 增加低信用-低信用相似度检测，输出 `corroborated` action，并同步更新 summarize/test/report。

3. **统一 source credit 推导与 fallback 映射**
   - 定义 `derive_synthesis_usage(item)`，输入 `SynthesisItem`，输出 `{credit_tier, usage, display_label}`。
   - 优先读取 `item.extra` 中的 `source_credit` / `source_type`；缺失时按 `source_platform` fallback。
   - fallback 映射必须覆盖现有 adapter 产出的所有 `source_platform` 值。

4. **同步 legacy chat path**
   - 把 credit usage rules、source line label、claim verification appendix 约束抽到共享 helper。
   - `_build_prompt()`（legacy）和 `KnowledgeSynthesizer._build_prompt()` 都调用同一 helper。
   - 增加测试：legacy chat path prompt 包含 credit usage rules 和 source credit label。

5. **明确 verified discussion 显式标签要求**
   - prompt 中强制 verified discussion 使用“社区讨论中的…已与…相互印证”句式。
   - 测试 snapshot 中检查该标签。

6. **回答并关闭 Open Questions 4、5**
   - Q4 答案：是，必须出现显式字样。
   - Q5 答案：允许进入“风险观察/关注点”文字，但不允许生成结构化风险信号，也不允许直接影响风险评分。

### Missing tests

- `test_derive_synthesis_usage_fallback_for_legacy_adapters`: 验证 ReportAdapter / NewsAdapter / AnnouncementAdapter 等未填充 `extra` 的 item 能正确映射到 `professional_observation` / `core_fact_allowed`。
- `test_derive_synthesis_usage_agent_reach_uses_extra`: 验证 AgentReach 来源优先使用 `source_credit` 而不是 `source_platform` fallback。
- `test_core_fact_provenance_rejects_news_report_community`: 验证 core fact 的 source refs 只有新闻/研报/社区时，`provenance_status` 为 `invalid_ref` 且该 fact 被过滤。
- `test_legacy_chat_prompt_includes_credit_rules`: 验证 `_build_prompt()` 输出包含 credit usage rules 和 source credit label。
- `test_prompt_order_credit_rules_before_sources`: 验证信用规则出现在 source lines 之前，符合“先给约束再给材料”的 prompt engineering 最佳实践。
- `test_verified_discussion_requires_explicit_wording`: 验证 prompt 要求 verified discussion 正文出现“相互印证/已验证线索”等字样。
- `test_corroborated_not_generated_by_current_schema`（若选项 A）: 验证当前 summary 不会产生 corroborated bucket。
- `test_corroborated_detection_in_claim_verification`（若选项 B）: 验证两个低信用相似 claim 无高/中支持时生成 corroborated action。

### Open questions

1. 对于 core fact provenance hard filter，是选择“直接过滤掉中信用来源支撑的 fact”还是“保留但标记为 invalid_ref/partially_supported 以便审计”？前者更干净，后者便于调试。
2. 如果采用选项 A 处理 corroborated，是否需要在设计文档中把 Phase 2 的 claim verification schema 扩展也一并设计，还是留到 R2？
3. `derive_synthesis_usage()` 是否也需要被 `DeepAnalysisRenderer` 或 `check_report_quality.py` 复用？如果未来会复用，建议现在抽到 `scripts/utils/source_credit.py` 或独立 helper。

## Round 2 Feedback

- **Status**: Ready to implement
- **R3 Needed**: No

### Blockers resolved

1. **Core fact provenance hard filter added.** Section 6 now requires a deterministic `is_core_fact_supporting_source()` guard that only accepts `公告/官方/交易所/巨潮` or sources explicitly tagged as `confirmed_fact` with `source_credit >= 80`, and explicitly rejects `研报/新闻/雪球/知乎/AgentReach/资金流向/unknown`. This directly fixes the Round 1 blocker that news/research-report sources could be marked as `supported` core facts.

2. **`corroborated_discussion` deferred to Phase 2.** Section 3 and the `corroborated_discussion` definition now explicitly state that Phase 1 does not add a `corroborated` action to `claim_verification.py`, does not render corroborated rows in the claim verification appendix, and only keeps the term as a prompt-level rule. This resolves the Round 1 blocker that Phase 1 could not safely produce `corroborated` rows.

### Remaining concerns / required task adjustments

1. **Hard filter needs source metadata, not just normalized labels.** The current `_enrich_core_fact_provenance()` only receives normalized source labels. The design allows otherwise-labeled sources to support core facts when `source_credit >= 80` and tagged `confirmed_fact`. Ensure the hard-filter helper receives `item.extra` / `source_credit` / `source_type` so this credit-threshold rule is enforceable; otherwise the exception is unreachable.

2. **Clarify `invalid_ref` core-fact handling.** The design says invalid_ref facts should not be dropped but displayed as “未绑定有效高信用引用”. Decide and document which renderer owns this display, and add a test proving `invalid_ref` facts do not flow into scoring, position advice, recommendations, or numbered citations.

3. **Add `微信公众号` to the fallback mapping.** `source_adapter.py` defines `WechatAdapter` with `source_platform: 微信公众号`, but Section 7's fallback table does not list it. Map it explicitly to `medium/professional_observation` or `low/discussion_only` so it does not silently fall through to `unknown/background_limited`.

4. **Legacy path sync needs an explicit shared helper location.** Section 8 requires the legacy `.chat(prompt)` path to use the same rules, but the design does not name the shared module. Specify that `credit usage rules` and `derive_synthesis_usage()` live in a module importable by both `knowledge_synthesizer.py` and `synthesis_skills.py` (e.g. `scripts/utils/source_credit.py` or a new `scripts/utils/synthesis_credit.py`).

### Missing tests

In addition to the tests already listed in the Round 1 design delta, add:

- `test_core_fact_hard_filter_uses_source_credit`: verify that a source with a non-announcement label but `source_credit >= 80` and `confirmed_fact` can support a core fact, while `研报/新闻/雪球/知乎/AgentReach/资金流向` cannot.
- `test_invalid_ref_core_fact_does_not_affect_output`: verify that core facts marked `invalid_ref` are omitted from report synthesis output or rendered only in an audit section, and never enter scoring/recommendations.
- `test_wechat_source_fallback_mapping`: verify `微信公众号` maps to the intended credit tier/usage.
- `test_legacy_chat_prompt_credit_rules_and_labels`: verify the legacy `_build_prompt()` output contains credit usage rules and per-source usage labels.

### Final recommendation

Approve Phase 1 implementation. The two Round 1 blockers are resolved at the design level. The remaining items are minor implementation clarifications and test-coverage gaps that should be addressed during implementation, not as additional design rounds.
