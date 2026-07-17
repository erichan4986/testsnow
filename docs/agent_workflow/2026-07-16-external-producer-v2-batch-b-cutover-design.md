# External Producer v2 Batch B: Canonical Pack Cutover

日期：2026-07-16
分支：`codex/pipeline-stabilization`
前置提交：`62be6bf feat: add canonical external argument projection`
状态：待 Round 1 只读设计审查

## 1. Goal

Batch B 将外部材料生产链收口为唯一正式路径：

```text
本地全文 / source packets
  -> LLM extractor 输出 argument candidates
  -> deterministic validator
  -> curated_external_argument_pack.v2
  -> Chapter 4 / freshness / display-only risk / evidence profile
```

最终态不再保留 narrative composer、paragraph/reasoning-card payload、v1 digest/narrative
正式缓存或 legacy fallback。正式报告只读取已持久化、可复现的 canonical v2 pack，
不会在运行时调用 LLM。

## 2. Locked Decisions

1. 正式 pipeline 使用 extractor-only；narrative composer 整体退出并删除。
2. 唯一正式缓存为持久化 `curated_external_argument_pack.v2`。
3. pack missing、stale 或 invalid 时 fail closed，不读取旧缓存、不实时调用 LLM。
4. 每个 argument 保留 1--3 个逐字 evidence units；总 card 数不设上限。
5. freshness、外部风险观察和 profile 全部迁移到 canonical v2 pack。
6. profile 使用 annual / broker / v2 pack 的明确来源层规则，不再读取 legacy card 数量。
7. 中际、复旦、黑芝麻样例只能先写 `/tmp`；用户确认无编造后才能覆盖正式 pack。
8. 外部材料继续保持 Preview / display-only，不进入 core facts、评分、风险分数、目标价、
   推荐或技术判断。

## 3. Non-goals

- 不修改外部网站采集、雪球详情页、Chrome/CDP 或 source packet 构造逻辑。
- 不修改 annual/broker producer、Chapter 4 source-layer ownership、评分、风险分数、
  目标价、技术分析或推荐阈值。
- 不加入股票名、股票代码或行业专用 admission 规则。
- 不让 LLM 输出绕过确定性 validator。
- 不在正式报告入口调用 LLM、访问全文或自动刷新 pack。

## 4. Target Schemas

### 4.1 LLM candidate

Extractor 返回：

```json
{
  "schema_version": "curated_external_argument_candidate.v2",
  "target_entity": "中际旭创",
  "entity_scope": "target",
  "claim": "外部材料提示上游物料供给仍可能约束交付节奏。",
  "evidence_units": [
    {
      "source_id": "source:abc",
      "source_quote": "部分原材料仍处于紧张状态。"
    }
  ],
  "topic_family": "capacity_delivery",
  "incremental_delta": "相对正式材料新增上游供给节奏变量。",
  "baseline_owner": "annual_or_broker",
  "baseline_overlap": "partial"
}
```

字段约束：

- `entity_scope`: `target | target_with_peer_context | peer_or_industry | ambiguous`。
- `evidence_units`: 1--3 条；每条必须带已存在的 `source_id` 和逐字 quote。
- `topic_family`: 使用现有 canonical family，不接受自由生成的新 taxonomy。
- `baseline_owner`: `annual | broker | annual_or_broker | none | unknown`。
- `baseline_overlap`: `none | partial | duplicate`。
- `claim` 必须是一条完整、谨慎、可由 evidence 支撑的论断；不得输出评级、目标价或建议。

这些字段都是 candidate，不是最终事实。LLM 给出的实体、topic、delta 和 owner 仅作为
hint；validator 和 MaterialSnapshot 仍是最终 owner。

### 4.2 Canonical pack

```json
{
  "schema_version": "curated_external_argument_pack.v2",
  "stock_name": "中际旭创",
  "status": "ready",
  "extractor_prompt_version": "external_argument_extractor.v2",
  "validator_version": "external_argument_validator.v2",
  "source_packet_fingerprints": [],
  "baseline_fingerprint": "sha256:...",
  "cards": [],
  "citations": {},
  "diagnostics": {
    "candidate_count": 0,
    "accepted_count": 0,
    "rejected_by_reason": {}
  }
}
```

Pack reader 必须验证：

- schema、stock identity、status；
- prompt/validator version 与当前代码要求一致；
- card schema、安全 flags、1--3 evidence units；
- quote hash、source identity、citation refs 和 source packet fingerprint 格式；
- cards 中不存在未被 citations 覆盖的 ref。

版本不匹配为 `stale`，结构或证据不合法为 `invalid`，文件不存在为 `missing`。
报告入口不会重新读取全文来比较 source fingerprints；fingerprints 用于审计和显式刷新。

`baseline_fingerprint` 是 refresh 时传入的 annual/broker baseline 文本经共享 whitespace
normalization 后的 SHA-256；它只证明 candidate 当时做过 duplicate baseline 校验，不是
报告时 freshness 日期，也不能替代 MaterialSnapshot 的当次 owner/novelty 判断。

### 4.3 Public API and context contract

`curated_external_full_body_viewpoint_claims.py` 是唯一 refresh-time producer owner，最终提供：

```text
build_curated_external_argument_pack(source_packets, baseline_text, extractor, stock_name)
write_curated_external_argument_pack(pack, path)
```

它执行 candidate normalization、确定性 validation、citation allocation 和 pack diagnostics。
删除 `build_viewpoint_digest()` 及其 digest schema/result。
`curated_external_argument_cards.py` 收缩为 pack candidate/card validation 的唯一 deterministic
owner，最终不再接受 `digest_claims` 或 `narrative_cards` 适配输入。

`curated_external_display.py` 是唯一 report-time reader owner，最终提供：

```text
build_curated_external_argument_display(pack_json, expected_stock_name)
```

它只读取 pack，返回固定 `status`（`missing_config | missing | stale | invalid | reader_error |
stock_identity_mismatch | empty | ok`）、`stats`、`citations` 和
`_curated_external_argument_cards_v2`。它不得打开 source packet、全文、digest 或 narrative
文件；报告时只校验 evidence 的 stored quote hash、citation ref、source identity 与 safety flags。
quote 是否为原文连续子串只能在 refresh-time validator 证明。

`SynthesisSkill._build_curated_external_deep_analysis_display()` 只接收
`include_curated_external_argument_pack_in_deep_analysis_display` 与
`curated_external_argument_pack_json`，并只写：

```text
curated_external_argument_pack_status
curated_external_argument_pack_stats
curated_external_argument_pack_lint
deep_analysis_display
deep_analysis_display_sources
```

不再写 digest/narrative status 或 `synthesis_text_with_curated_external_viewpoint_*`。状态非 `ok`
时不得以任何旧对象补充 `deep_analysis_display`。

保留的 `scripts/previews/curated_external_full_body_viewpoint_preview.py` 改为 pack refresh/sample
入口：必须显式接收 output path，样例阶段只写 `/tmp`，不得默认覆盖
`data/curated_external/`。它不再输出 digest/narrative JSON；正式 pack 的写入仅发生在用户确认
三股样例后的 Gate B2。

## 5. Deterministic Validation

Validator 复用并扩展 `curated_external_argument_cards.py`，保持唯一 owner：

1. `source_id` 必须存在于本轮 source packets。
2. quote 经共享 whitespace 归一化后必须是 source body 的连续子串。
3. evidence unit 保存 quote hash、source identity 和 citation ref。
4. claim 中全部数字、百分比、时间、型号必须出现在 evidence units 中。
5. target / peer / industry 实体归属由 source title、正文和 target identity 重算；
   `ambiguous` fail closed。
6. `duplicate` baseline 不准入；`incremental_delta` 不得引入 evidence 中不存在的数字或型号。
7. topic family 由 metadata + 通用词表重算；未知映射为 `other`，不创建新 family。
8. 同一 argument identity 只保留证据更完整者；同 URL 的不同 argument 继续保留。
9. 不设总 card cap；输入顺序与 source identity 可审计。
10. 最终 cards 强制写入现有 Preview/display-only/scoring/risk safety flags。

MaterialSnapshot 继续根据当次 visible annual/broker rows 重算 `owner_relation` 和 display
novelty。Pack 中的 `baseline_owner`/`incremental_delta` 不能覆盖 snapshot 的判断。

Citation allocation 在 refresh-time writer 按 accepted cards 的稳定 source identity 首次出现顺序
完成；同一 identity 复用同一 ref。每个 citation meta 必须保留 `source_id`、`source_quote_hash`、
`source_block_hash`、source type/credit/verification status、title、author、URL/source_ref 和可用的
publish date。report-time reader 只重建这些稳定 refs，不能根据 rendered text 再编号。

## 6. Prompt Upgrade

修改 full-body extractor 默认 prompt：

- 输出 candidate v2 schema，不再输出 v1 claim schema；
- 每个 candidate 只写一个核心 claim；
- 为每个 claim 选择 1--3 条逐字 quote，并逐条复制 source_id；
- 明确 target / peer / industry，不得把同业事实写成目标公司事实；
- 指出相对 baseline 的新增机制、事件、分歧或待验证变量；
- 没有高质量增量时返回空 candidates，不凑数；
- 不计算、推导或补写数字，不输出评级、目标价、评分和投资建议。

Parser 只负责 JSON/schema normalization。任何缺字段、自由 taxonomy、quote 不对齐或实体
不明的 candidate 交给 validator 拒绝，不做修写或 second-pass recovery。

Extractor 只保留一个通用 candidate 生产入口。若 source packets 因上下文长度需要分批，
只能按稳定输入顺序或 canonical topic-family 表做确定性 transport chunking；所有 chunk 仍输出
同一 candidate schema，并汇入同一个 validator。删除当前股票/主题专用的
`THEME_PROFILES`、固定 `DEFAULT_MULTIPASS_SPECS`、`_NEAR_DUPLICATE_BUCKETS` 及其专用
coverage gate。不得为中际、复旦、黑芝麻或某个行业保留独立 prompt/pass。

逐字 quote 不允许 fuzzy repair。删除 `repair_quote()`、相似度/LCS 窗口修补及相应 fallback；
LLM quote 不能经共享 whitespace normalization 后成为原文连续子串时，candidate 直接拒绝。

## 7. Runtime Consumers

### 7.1 Report configuration

`config/stocks.json` 最终只保留：

```json
"curated_external_argument_pack_display": {
  "enabled": true,
  "pack_json": "data/curated_external/argument_packs/<stock>.json"
}
```

`stock_reporter.py` 和 `report_skills/__init__.py` 只传播 pack 开关与路径。

### 7.2 Display

`curated_external_display.py` 只读取和验证 pack，输出：

- `_curated_external_argument_cards_v2`
- canonical citations、sources、stats/status

不再组装 paragraphs、reasoning cards、topic groups 或 v1 digest display。

`deep_analysis_material_snapshot._external_rows()` 仍是 external `MaterialRow` 的唯一 adapter：
它只消费上述 cards/citations，并保持 `section_hint`、owner relation 和 allocator 行为。
formal-thin 的 citation offset 继续从完整 `MaterialSnapshot` 的 annual + broker + external citation
序列计算；renderer 不得直接打开 pack 或重新计算 ref。formal-medium 4.4 也只消费 snapshot 的
canonical external rows，禁止保留现有 `curated_display` 直读 addendum。

### 7.3 Freshness

`evidence_freshness.py` 从 v2 cards/citations 提取 display-only 新近变量。日期只来自 citation
metadata；缺日期不伪造 freshness。去重使用 argument/source identity。

### 7.4 External risk observation

`assembly_skills.py` 从 v2 cards 生成外部人工跟踪项，只读取 claim/topic/citation。
保持 `scoring_eligible=False`、`risk_score_eligible=False`，不得修改风险分数。

本任务只替换由 `deep_analysis_display` 派生的 curated-viewpoint 风险行：删除 paragraphs、
reasoning cards 与 topic groups 的扫描，改为读取 v2 cards。`display_only_external_risks` 与
`curated_external_analysis_items` 是调用方显式传入的独立风险输入，不是 viewpoint composer
payload，本批不删除或改变其语义；测试必须证明它们不会成为 v2/legacy fallback，也不改变风险分数。

### 7.5 Profile routing

Profile 顺序固定：

```text
if current formal-rich condition:
    formal_rich
elif annual ready and broker usable_card_count > 0:
    formal_medium
elif annual ready and formal_insight_facts < 5 and external_v2_rich:
    formal_thin_external_rich
elif any formal material:
    formal_medium
else:
    thin_all
```

其中 `annual_ready` = `annual_report_memo.status == "ready"` 且 annual citations 非空；
`broker_usable_card_count` 只取 broker memo diagnostics；`any formal material` 只包括 annual/broker
memo 或 canonical official/broker source，不得把 external display、external citation 或泛
`synthesis item` 计入。`current formal-rich condition` 保持现有
`formal_insight_facts >= 5 && industry_support >= 2 && fundamentals_support >= 2`，并同样要求
`annual_ready`。这组 predicates 必须抽成一个可直接 fixture 的 helper，不能通过 status 字符串
或 legacy field 旁路。

`external_v2_rich` 继续使用现有 richness 口径：canonical topic families >= 3 或 accepted
cards >= 6。判断只读 pack diagnostics/cards，不依赖 legacy payload。该顺序保持中际
`formal_medium`、复旦 `formal_thin_external_rich`；黑芝麻没有足够正式材料时不得仅靠
外部 pack 升级为正式 profile。

## 8. Deletion Ledger

在用户确认三股样例后，最终实现删除：

- `scripts/utils/curated_external_viewpoint_narrative.py`
- `scripts/previews/curated_external_viewpoint_narrative_preview.py`
- `scripts/previews/social_viewpoint_digest_preview.py`
- `tests/utils/test_curated_external_viewpoint_narrative.py`
- `tests/reporter/test_curated_external_viewpoint_narrative_preview.py`
- `data/curated_external/viewpoint_narratives/*.json`
- `data/curated_external/viewpoint_digests/*.json`
- `config/stocks.json` 的 digest/narrative display 配置
- `stock_reporter.py`、`report_skills/__init__.py`、`synthesis_skills.py` 中旧开关与路径
- `_curated_external_narrative_paragraphs`、`_curated_external_reasoning_cards`、
  `_curated_external_topic_groups` runtime payload
- display/snapshot/renderer 中 legacy external adapters/fallback
- freshness/risk/profile 中 legacy card consumers
- v1 extractor prompt/schema normalization 与无调用 helper
- 股票/主题专用 extractor profile、固定 multipass specs、near-duplicate buckets
- fuzzy quote repair、相似度/LCS 修补及其 fallback

同时删除或改写所有引用这些已删模块/脚本/fixtures 的测试注册和文档：
`tests/conftest.py`、`tests/test_scripts_layout.py`、`tests/README.md`，以及
`test_synthesis_skills.py`、`test_stock_reporter_source_intake_config.py`、
`test_run_stock_report_entry.py`、`test_curated_external_display.py`、
`test_evidence_freshness.py`、`test_deep_analysis_material_snapshot.py`、
`test_deep_analysis_renderer.py`、`test_recommendation_decision.py`、
`test_pytest_marker_contract.py` 中的 digest/narrative fixture 和 compatibility assertions。
`tests/utils/test_curated_external_full_body_viewpoint_claims.py` 与
`tests/reporter/test_curated_external_full_body_viewpoint_preview.py` 保留但改写为 v2 pack contract；
不得继续导入 `THEME_PROFILES`、`repair_quote` 或 `build_viewpoint_digest`。

保留：本地全文、source packet 构造、preview extractor 入口、canonical pack writer/reader、
确定性 validator、Chapter 4 canonical renderer。

## 9. Implementation Gates

### Gate B1: Code and offline fixtures

1. 先新增 candidate/pack schema 与 validator tests；RED 后实现。
2. 更新 extractor prompt/parser，使用 fake client 测试输出和拒绝路径。
3. 新增 pack writer/reader 与 stale/missing/invalid tests。
4. 新增 v2 display/freshness/risk/profile consumer，并通过显式 v2 fixture 验证；v2 reader
   本身不得读取或 fallback 到 legacy 文件。
5. 列出并测试最终 deletion ledger，但在三股样例确认前暂不切换生产 config，也不删除仍被
   当前生产 config 使用的 legacy runtime/cache。该短暂并存只用于迁移，不是正式兼容层。
6. 运行 focused、affected、full offline、CI grep gates、`git diff --check`。

Gate B1 期间不覆盖 `data/curated_external` 正式缓存，不提交、不推送。

### Gate B2: Three-stock sample confirmation

使用本地材料和已配置 LLM，在 `/tmp` 生成：

- 中际旭创 canonical v2 sample pack
- 复旦微电 canonical v2 sample pack
- 黑芝麻智能 canonical v2 sample pack

向用户展示每股：accepted cards、每张卡 claim、全部逐字 evidence、entity scope、topic、
rejection diagnostics，以及 quote/numeric/model alignment 结果。用户确认无编造后才：

1. 写入 `data/curated_external/argument_packs/`；
2. 在同一 cutover 中切换 config 和 pipeline plumbing；
3. 删除全部 legacy runtime、tests、config 与 v1 digest/narrative 缓存；
4. 运行 repo grep，证明正式 runtime 只有 v2 pack 路径；
5. 生成三股报告并跑质量/source/prose gates；
6. 提交或合并。

步骤 1--4 是同一个最终切换批次：任一删除项仍有真实调用、任一新 pack 不可读，或 full
offline tests 未通过，都停止，不提交一个“新 config + 旧 runtime”或“旧 config + 已删
runtime”的半切换状态。

## 10. Required Tests

### Candidate and validator

1. 1、2、3 evidence units 均可准入，4 条拒绝。
2. 无 source_id、quote 非连续子串、quote hash 不匹配拒绝。
3. claim 新增数字、百分比、时间或型号拒绝。
4. target、target-with-peer、peer/industry 正确；ambiguous/foreign-only 拒绝。
5. duplicate baseline 拒绝，partial/none 仍交给 snapshot 做最终 novelty。
6. 同 argument 跨来源合并证据；同 URL 不同 argument 保留。
7. 无总 card 上限：超过旧显示数量的高质量 fixture 全部保留。
8. quote 只有 fuzzy/LCS 近似匹配时拒绝，不得自动改写成原文片段。
9. extractor 不存在股票/行业专用 theme profile、pass spec 或 admission 分支。

### Pack

10. pack round-trip 保留 cards、citations、source fingerprints 和 diagnostics。
11. missing/stale/invalid fail closed，绝不读取 v1 文件。
12. stock mismatch、版本 mismatch、dangling refs、unsafe flags 拒绝。
13. writer 对相同 citation identity 分配稳定单一 ref；reader 不触碰 source packet/full body。

### Consumers

14. display 只输出 v2 cards，无 legacy payload keys。
15. freshness 只读 v2，缺日期不伪造。
16. external risk observation 只读 v2，风险分数 identity test 不变。
17. 中际/复旦/黑芝麻 profile fixtures 符合 §7.5。
18. formal-thin citation offset 仍基于 full snapshot。
19. formal-medium 4.4 只复用 canonical rows。
20. external cards 不进入 core facts/scoring/risk score/target/recommendation。
21. snapshot 是唯一 external `MaterialRow` adapter；formal-thin offset 和 formal-medium 4.4
    都不直接读取 pack/display。
22. deep-display 派生的风险行只读 v2；两个显式非-viewpoint risk 输入保持原语义且不改变
    risk-score identity。
23. full-body preview 在未指定正式路径时只写 `/tmp` pack，绝不产生 digest/narrative JSON。

### Deletion and integration

24. repo grep 不存在正式 runtime 对 narrative/digest config、paragraphs/reasoning/topic groups
    的读取。
25. composer module/preview/tests/caches 已删除，test registry/layout/README 无死引用。
26. repo grep 不存在股票/行业专用 external extractor profile、fuzzy quote repair、
    `social_viewpoint_digest_preview.py` 或 `build_viewpoint_digest` import。
27. focused、full offline、CI 和 whitespace 全绿。
28. 三股 fresh reports 无 missing/unused/malformed/unknown citation。

## 11. Failure Modes

| Failure | Safe outcome | Gate |
|---|---|---|
| LLM 返回漂亮但无逐字 quote 的 claim | validator 拒绝 | quote fixture |
| 同业事实写成目标事实 | ambiguous/peer 或拒绝 | entity fixture |
| Pack 版本旧 | `stale`，4.3 空状态 | pack reader test |
| Pack 损坏或 refs 悬空 | `invalid`，不渲染 | pack reader test |
| Pack 缺失 | `missing`，其他章节继续 | integration test |
| 外部材料进入风险分数 | identity test 失败并停止 | risk integration |
| v2 richness 把中际降成 formal-thin | profile fixture 失败 | routing test |
| external-only 输入把黑芝麻升为 formal-medium | profile fixture 失败 | routing test |
| 删除 composer 后 freshness/risk 为空 | consumer fixture 失败 | downstream tests |
| 遗留 social preview 重新生产 digest | grep/test layout 失败 | deletion integration |
| 三股样例出现 evidence 外数字/型号 | 不写正式 pack | sample audit |

## 12. Scope and Budget

这是 Level 3 任务。允许修改 extractor、argument validator/pack、display、report plumbing、
freshness、assembly display-only risk、profile routing、配置和对应测试；删除 §8 文件。

不允许修改评分、风险分数、目标价、技术算法、推荐、KnowledgeSynthesizer prompt、
annual/broker producer、雪球/Chrome/CDP 或外部采集逻辑。

目标是 runtime 净减。Gate B1 因明确保留当前生产链用于样例确认，允许临时 runtime 净增
不超过 `+450`；该数字按 Gate B1 实测后的等价压缩结果校准，只用于迁移中间态，B1 不提交/合并。Gate B2 新增 pack/schema/reader
必须由 narrative composer、legacy display 和 compatibility code 的删除抵消；若最终 runtime
相对 `62be6bf` 净增超过 `+120`，停止并返回设计。若最终仍存在第二个 external card
producer/selector，也停止。

当前替换账本（仅 runtime，不含 tests）是 B1/B2 的逐步核对基线：

| File | Current lines | Final action |
|---|---:|---|
| `curated_external_full_body_viewpoint_claims.py` | 1565 | rewrite v1 extractor/digest API to v2 pack producer |
| `curated_external_argument_cards.py` | 290 | replace legacy adapters with v2 validator/card owner |
| `curated_external_display.py` | 505 | replace narrative/digest readers with one pack reader |
| `curated_external_viewpoint_narrative.py` | 913 | delete |
| `curated_external_viewpoint_narrative_preview.py` | 139 | delete |
| `social_viewpoint_digest_preview.py` | 191 | delete |

这不是允许按行数删校验。每个删除必须由 §10 contract test 和 repo grep 证明不再有调用；若新
pack API 使上述三份保留模块无法在 +120 内替换旧逻辑，停止并回到设计。

## 13. Stop Conditions

立即停止并返回设计，如果：

1. source packets 无法在本地重建三股样例；
2. 必须保留 narrative composer 才能维持 freshness/risk/profile；
3. validator 需要 fuzzy quote 接受或 LLM second-pass repair；
4. 需要股票/行业专用 hardcode；
5. external 内容进入任何决策路径；
6. 用户尚未确认样例却需要覆盖正式缓存；
7. B1 临时 runtime 超过 +450，或 B2 最终 runtime 超过 +120；
8. formal-thin offset 或中际/复旦 profile 无法保持。
