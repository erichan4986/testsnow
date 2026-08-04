# Knowledge Persistence Slimming Design

日期：2026-07-15
分支：`codex/annual-producer-v2`
路线图批次：Batch 6

## 1. Goal

把 Annual Producer v2 的机器材料从“一张 argument card 一份 Markdown”迁移为
pack-first 持久化，同时保留全部 card、SourceUnit、选择诊断和 v1 coverage 证明。

本批不改善 producer 选材，也不改变报告内容。它只重划持久化职责：

- 完整结构化 pack 是报告机器输入；
- Obsidian Markdown 是少量、只读友好的高价值投影；
- 旧 v1/v2 card notes 在迁移证明完成前保留，不自动删除。

## 2. Current State

当前本地 `knowledge/10-Stocks/*/periodic_narrative_cards/` 包含：

- 11 只股票；
- 1,029 张 Markdown notes；
- 其中 881 张是 v2 notes，148 张是 legacy v1 notes；
- 合计约 75,774 行、4.2 MB。

膨胀主要来自每张 v2 note 重复保存 frontmatter、Narrative Evidence、Source
Units JSON、Selection Diagnostics、Source 和 Guardrails。更重要的是，当前
`annual_report_material_pack.py` 仍需逐张解析这些 Markdown 才能在内存中重建
material pack；所谓 pack 尚不是持久化真源。

当前生产链路是：

```text
annual cache
  -> evidence pack
  -> periodic_report_narrative_evidence_cards envelope
  -> N Markdown card notes
  -> annual_report_material_pack parses N notes
  -> SynthesisItem / annual memo / MaterialSnapshot / report
```

目标链路是：

```text
annual cache
  -> evidence pack
  -> periodic_report_narrative_evidence_cards envelope
  -> one validated JSON pack per stock / period
  -> annual_report_material_pack reads JSON cards directly
  -> SynthesisItem / annual memo / MaterialSnapshot / report

same JSON pack
  -> one bounded human-readable Markdown projection per stock / period
```

## 3. Fixed Invariants

1. Producer envelope 中的所有 v2 cards 必须进入机器 pack；不得增加 card 上限、
   family 上限或新的 selector。
2. 每张 card 的 `source_units`、`source_unit_ids`、`source_excerpt`、
   `score_parts`、`quality_score`、`selection_reason`、family 和 source identity
   必须逐值保留。
3. 不修改 Annual Producer v2 admission、48-block evidence-pack 预算、annual memo、
   Chapter4ViewModel、formal-thin citation offset、profile、评分、目标价、风险、
   技术分析、推荐或 LLM prompt。
4. 报告只消费机器 pack。人类 Markdown 投影不得成为 report、memo、coverage 或
   scoring 的输入。
5. v1 adapter 的当前语义和诊断 key 保持不变。迁移不得把
   `v1_actionable_needs_recovery_count` 静默归零。
6. pack 缺失或损坏时，迁移期可回退到现有 card notes；不得混用部分有效 pack
   和部分 v2 Markdown 形成不可审计的混合真源。
7. 不自动删除或覆盖当前 1,029 张 notes。归档是兼容 gate 之后的独立、显式动作。

## 4. Alternatives

### A. Recommended: stock-local JSON pack plus one human projection

在现有 Knowledge stock 目录下持久化机器 pack，并生成一张按五个 canonical
family 分节的 Markdown 阅读投影。优点是复用 `knowledge_base_dir`、可在干净 clone
中版本化、文件数从每 card 一张降为每期两个文件，并且机器与人类职责清晰。

### B. `data/processed` machine pack

分层更纯粹，但 `data/processed/` 当前被 `.gitignore` 忽略。干净 clone 无法复现
完整 v2 material，报告还需新增第二个根目录配置。暂不采用。

### C. One large Markdown note or SQLite

大 Markdown 仍需要脆弱的 frontmatter/section parser；SQLite 引入不必要的迁移和
运维边界。两者都不如已有 JSON producer envelope 直接。暂不采用。

## 5. Persisted Pack Contract

### 5.1 Path

每个股票、报告期、报告类型保存一份：

```text
knowledge/10-Stocks/<stock>/periodic_narrative_packs/<year>-<report-type>.json
```

目录和文件名使用现有安全 path-segment 规则。pack 不加入 `.gitignore`；它是替代
881 张 v2 Markdown 的可版本化机器材料。

每只股票另保存一份独立于 pack 目录的期次清单：

```text
knowledge/10-Stocks/<stock>/periodic_narrative_pack_manifest.json
```

manifest 是完整性边界，不是第二份 card 真源。它记录 stock identity，以及所有预期
pack 的 `report_year`、`report_type`、相对路径、`cards_sha256` 和 `payload_sha256`。
把 manifest 放在 pack 目录之外，可以在整个 pack 目录缺失时仍检测出材料丢失。
loader 只读取 manifest 声明的 pack；存在未登记 pack、manifest 声明文件缺失或 hash
不匹配时，整组存储无效。

manifest schema 固定为：

```json
{
  "schema_version": "periodic_report_narrative_pack_manifest.v1",
  "stock_code": "300308",
  "stock_name": "中际旭创",
  "periods": [
    {
      "report_year": 2025,
      "report_type": "annual",
      "pack_path": "periodic_narrative_packs/2025-annual.json",
      "cards_sha256": "...",
      "payload_sha256": "..."
    }
  ],
  "periods_sha256": "..."
}
```

`periods` 按 year/type/path 稳定排序，`periods_sha256` 使用相同 canonical JSON 规则。
写入一个期次时必须在已验证 manifest 上按 `(year, report_type)` upsert，保留其他期次；
不得用本次单期结果覆盖整份 periods 清单。

`pack_path` 只能是相对于股票根目录的
`periodic_narrative_packs/<year>-<report-type>.json`：不得为绝对路径、不得包含
`..`、解析后不得离开固定 pack 目录，且文件名必须与 entry/envelope 的 year/type
完全一致。路径校验属于 manifest validator，不允许调用方自行拼接后绕过。

manifest writer 只有三种状态：

1. `bootstrap`：manifest 不存在且 pack 目录不存在或为空，允许用本次已验证 pack
   建立首个 manifest；
2. `upsert`：manifest 已存在且完整验证通过，按 `(year, report_type)` 原子更新一个
   entry 并保留全部其他 entry；
3. `repair_required`：manifest 损坏，或 manifest 不存在但 pack 目录已有 JSON。普通
   preparation/preview writer 不写任何 pack 或 manifest，返回稳定错误码和 dry-run
   repair 建议。只有 acceptance 能根据已验证的 pack/v2 notes 输出 repair plan；实际
   repair 与 archive 一样需要用户单独确认，不能由正常报告入口自动执行。

repair 只可在 legacy v2 Markdown 尚完整存在时，用其完整期次 inventory 建立新的
manifest；不得仅根据残留 JSON packs 推断“全部期次”。一旦 v2 notes 已归档，manifest
缺失或损坏必须 fail closed，由显式恢复流程提供完整期次清单，而不是自动 rebuild。

### 5.2 Schema

新增 envelope schema：

```json
{
  "schema_version": "periodic_report_narrative_material_pack.v1",
  "producer_schema_version": "periodic_report_narrative_evidence_cards.v2",
  "selection_version": "annual_argument_selection.v2",
  "stock_code": "300308",
  "stock_name": "中际旭创",
  "report_year": 2025,
  "report_type": "annual",
  "cards": [],
  "producer_diagnostics": {},
  "integrity": {
    "card_count": 0,
    "source_unit_count": 0,
    "cards_sha256": "...",
    "producer_diagnostics_sha256": "...",
    "payload_sha256": "..."
  }
}
```

`cards` 是 producer `cards` 的深拷贝，保持原顺序。`producer_diagnostics` 是
producer `diagnostics` 的深拷贝。producer 当前的 `candidate_cards` 与 `cards`
完全相同，持久化时不重复写第二份；writer 必须先证明二者逐值相同。若未来二者
不同，写入直接失败并返回设计，而不是丢 candidate 数据。

`cards_sha256` 对 `cards` 使用 UTF-8、`ensure_ascii=False`、`sort_keys=True`、
紧凑 separators 的 canonical JSON 计算。文件本身使用 `indent=2` 和稳定 key 顺序，
便于 review。`producer_diagnostics_sha256` 对 diagnostics 使用相同规则；
`payload_sha256` 覆盖 schema/version、stock identity、report period、cards 和
producer diagnostics，但不递归包含 integrity 本身。pack 不保存生成时间或文件
mtime，保证同输入字节稳定。

### 5.3 Validation

pack writer 和 reader 共用唯一 validator，至少验证：

- envelope / producer / selection schema 精确匹配；
- stock identity 与路径目录一致；文件名解析出的 report year/type 与 envelope
  一致；当调用方提供 `stock_code` 时，envelope 的 code 也必须与调用参数一致；
- `cards` 与 `producer_diagnostics` 类型正确；
- 每张 card 通过现有 `validate_card_v2()`；
- card id 全局唯一；
- source unit id 在 pack 内单一归属；
- cards、producer diagnostics、完整 payload 的 integrity counts/hash 与正文一致；
- 空 pack 只有在 producer 明确输出零 cards 且无 invariant violation 时合法。

写入使用同目录临时文件加 `Path.replace()` 原子替换。先原子写入并验证 pack，再原子
更新 manifest；若进程在两步之间中断，旧 manifest 与新 pack hash 不匹配，loader
必须 fallback/fail closed，重跑后恢复一致。验证失败不得触碰已有 manifest。

## 6. Loader and Compatibility Contract

以下规则描述 6B 切换后的默认行为。6A-1 只写入 pack/manifest 并保留 legacy
Markdown loader；6A-2 才在独立 acceptance 路径构建 shadow material pack。正常报告
调用始终走 legacy，直到 parity gate 通过，不给生产 loader 增加可泄漏的部分/调试模式。

`build_annual_report_material_pack()` 最终成为 pack-first loader，接口保留向后兼容的
可选身份参数：

```python
build_annual_report_material_pack(
    *, stock_name, base_dir, stock_code=None,
)
```

loader 始终读取 manifest 声明的全部 period，不提供部分期次过滤模式。每个 pack
都用其文件名和 manifest 的 year/type 做 envelope 校验；`stock_code` 由主报告的
`ctx["stock_codes"]` 传入。缺少 code 的历史/预览调用仍可读取，但不能把“未提供
expected code”当成身份校验通过的证据。对应的
`load_periodic_narrative_card_synthesis_items()` 也接收并透传 `stock_code`。

`build_annual_report_material_pack()` 的读取规则：

1. 读取并验证 stock-local manifest，按 manifest 中的 year/type/path 稳定顺序加载；
2. manifest 声明的 pack 必须全部存在且有效，pack 目录不得含未登记 JSON；
3. 若完整 pack set 有效，直接把 pack cards 构造成 v2 `_CardRecord`；
4. 此模式忽略 `periodic_narrative_cards/` 中的 v2 Markdown，避免双真源；
5. 仍读取 legacy v1 Markdown，仅用于现有 exact-shadow、SourceUnit coverage、
   actionable recovery 和 adapter 逻辑；
6. 若没有 manifest 且仍有 v2 Markdown，完整走当前 Markdown loader；
7. 若任一 pack 缺失、损坏、未登记或身份冲突，整组 pack 不参与本次构建，迁移期完整回退到
   Markdown，并在 diagnostics 写入 `storage_mode=legacy_fallback` 和稳定错误码；
8. 不允许“有效 pack A + 损坏 pack B + B 的 v2 notes”这种部分混合；
9. 若 manifest 存在但 pack set 不完整或损坏，且已没有完整 v2 Markdown 可供回退，loader 抛出专用
   `AnnualMaterialPackStorageError`。该异常必须穿过所有 `use_pack=True` 调用路径：
   `periodic_report_narrative_card_synthesis_items.py` 不得吞掉，
   `SynthesisSkill._eligible_periodic_narrative_card_items()` 也不得吞掉；
   `SynthesisSkill` 构建 annual material pack 的宽泛异常分支同样必须显式重抛该类型。
   只有“没有发现 pack”这一正常迁移状态允许走 legacy fallback 或返回空；不得把
   损坏 pack 降级成空 annual memo。

manifest 缺失且 pack 目录非空属于损坏状态，不是“没有发现 pack”；manifest 存在但
整个 pack 目录缺失同样必须被检测。只有 manifest、pack 和 v2 Markdown 都从未存在的
股票才允许 `storage_mode=empty`。

pack-first 与 legacy-fallback 必须产生相同的 v2 card id、excerpt、SourceUnit、family
和 report ordering。`selected_cards_to_synthesis_items()`、SynthesisSkill、annual memo、
MaterialSnapshot 和 renderer 不感知底层存储变化。

迁移期 diagnostics 新增而不重定义旧 key：

- `storage_mode`: `pack_shadow | pack_first | legacy_fallback | empty`
- `manifest_seen`
- `manifest_valid`
- `packs_seen`
- `packs_loaded`
- `pack_validation_errors`
- `v2_markdown_ignored_count`

### 6.1 Existing v2 Note Classification

现有 v2 Markdown 不能直接视为 producer 的 canonical 集合。当前本地 8 只股票有
197 个重复 `card_id`，涉及 459 个 v2 文件；旧 writer 会刷新目标路径，但不会移除
重新分类或重新编号留下的文件。

6A-2 acceptance 必须以本次 producer envelope 为准，把 v2 notes 确定性分类：

- `active_v2`：card id 和 `v2_note_card_fingerprint` 与 producer card 一致；每个 producer
  card 只能有一个 active note。若多个 note 匹配，优先选择当前 writer 的预期路径；若该
  路径不存在，选择字典序最小路径。writer path 只是确定 canonical representative 的
  tie-breaker，不是 active 的必要条件；
- `stale_duplicate`：与 active card payload 相同但未被选为 canonical representative；
- `stale_reindexed`：card id 仍存在，但 family 或 payload 已变化；
- `stale_orphan`：card id 已不在当前 producer envelope。
- `stale_invalid`：缺少可解析 frontmatter、Source Units 或 Selection Diagnostics，无法
  构成合法 v2 card projection。

`v2_note_card_fingerprint` 是专用于 note/card 对齐的 canonical JSON，不比较 note 的
`stock`、`code`、`collected_at`、knowledge flags、Markdown 标题或 Guardrails，也不尝试
从 note 重建 envelope-level `producer_diagnostics`。它逐值包含：

```text
schema_version, selection_version, card_id, argument_family, argument_complete,
title, report_year, report_type, source_type, source_credit, source_block_id,
source_unit_ids, source_units, source_excerpt_hash, fact_anchors,
secondary_signals, score_parts, quality_score, selection_reason
```

其中 `source_excerpt_hash` 强制使用新 pack store 唯一公开的
`normalized_source_excerpt_hash()`：语义必须与当前 note writer 的 `_source_text_hash()`
一致（空白压缩为单空格后 SHA-256）。6A-1 将 note writer 改为复用该 helper，并用
兼容测试锁定新旧 hash 相同；producer `source_excerpt` 和 note 可见 excerpt 分别计算。
`source_units` 保留原列表顺序并以 stable-key JSON 比较。pack 与 producer envelope
仍比较完整 cards 和全局 `producer_diagnostics`，而 active-v2 对齐只比较上述 card-level
fingerprint。

pack roundtrip 必须与 producer envelope 和 `active_v2` 完全一致，不要求复制 stale
notes。stale 分类只进入 dry-run archive manifest，普通入口不得移动或删除它们。

6A-1 为 dual-write：正常报告继续使用 legacy loader，只写 pack/manifest 与既有 notes。
6A-2 单独构建 `pack_shadow`，比较 active cards、v1 diagnostics、annual memo、
MaterialSnapshot、formal-medium/formal-thin 输出和引用。只有 6A-2 全部门通过，6B 才切换
默认 report read path 到 `pack_first`。若 legacy report 因 stale v2 notes 与 pack report
不同，停止并输出差异，不得通过把 stale notes 复制进 pack 来追求表面一致。

## 7. Human Markdown Projection

每个 stock/period 生成一张：

```text
knowledge/10-Stocks/<stock>/periodic_narrative_views/<year>-<report-type>.md
```

它只用于 Obsidian 阅读，不被任何 loader 扫描。正文按五个 canonical family 分节，
每节最多展示 4 条高价值 excerpt，最多 20 条。该预算只限制人类投影，不限制 pack、
material loader 或报告输入。每节标题必须显示 `展示 x/y 条`，frontmatter 记录完整
`total_cards`；当 x < y 时同时给出机器 pack 相对路径，明确其余 card 仍被保留在
机器材料中。

family 内排序固定为：

1. `argument_complete=True` 优先；
2. `quality_score` 降序；
3. source unit 数量降序；
4. producer 原顺序；
5. card id 稳定兜底。

仅做 exact `source_excerpt` hash 去重，不做语义相似、embedding、改写或摘要。每条
展示完整原始 excerpt，并紧凑附带 `card_id`、`source_block_id`、
`source_unit_ids`，不重复嵌入 Source Units JSON、Selection Diagnostics 或 Guardrails。

投影 frontmatter 记录 pack 相对路径、`cards_sha256`、总 card 数、各 family 数和
`generated_projection: true`。文件由生成器完整覆盖；人工补充应写在独立 note，
避免生成内容和人工内容形成第三种状态。

## 8. Delivery Batches

### Batch 6A-1: Pack store and dual-write

- 新增纯 pack/manifest store 和共用 validator；
- `prepare_annual_report_materials.py` 和 preview 在 `--write-knowledge` 时 dual-write
  JSON pack 与原 per-card notes；
- report material loader 仍使用 legacy notes；
- 不生成 human view，不停止旧 note writer，不归档任何文件；

### Batch 6A-2: Migration shadow audit

- acceptance 显式执行 `pack_shadow` loader，输出 active/stale v2 分类和
  pack/legacy/report parity；
- 完成逐卡、逐 SourceUnit、逐 diagnostics parity gate；
- 不改变报告默认 loader，不归档任何文件。

### Batch 6B: Human projection and pack-first switch

- 新增一文件式 human projection writer；
- 只有 6A-2 的 active-v2、v1 diagnostics、memo/snapshot/report/citation gates 全绿后，
  才把默认 report loader 切到 manifest-backed `pack_first`；
- 切换同时接通 stock-code identity 和所有 typed-error fail-closed 调用链；
- `--write-knowledge` 默认写 JSON pack + human projection，不再新写或刷新 v2
  per-card Markdown；
- legacy note writer 保留为显式 migration-only helper；
- preview/CLI 输出分别报告 machine pack 和 human projection，不再把二者混成
  `knowledge_written_count`。6A 期间保留该字段的既有语义（仅统计逐卡 Markdown
  的 written/refreshed 数量），并新增结构化 `knowledge_outputs`：
  `machine_pack={path,written,refreshed}`、`human_projection=null`、
  `legacy_card_notes={written,refreshed}`。6B 后新字段成为唯一权威；旧字段保留为
  deprecated compatibility field，不再用于 CLI 展示或验收计数，且 6B 测试必须
  明确其不会把 pack/view 计入旧的 note 数量。

### Batch 6C: Migration audit and code slimming

- 将本地 acceptance 入口的 active/stale 分类扩展为最终 pack/note parity、完整
  card/source-unit parity 和可归档清单；
- 只有所有本地 stock/period gate 通过后，才允许显式归档 v2 notes；
- v1 notes 只有在所有配置股票同时满足
  `v1_actionable_needs_recovery_count == 0` 和 `v1_adapter_use_count == 0` 后才可归档；
- 归档不得由普通 report/preparation 入口自动执行；
- pack-first 稳定后删除 v2 Markdown render/parser 分支和重复 YAML/JSON section helpers，
  保留最小 v1 migration reader，最终 runtime 应较 Batch 6 前净减少。
- 验证 6B 已接通的 no-fallback typed error 在删除 v2 parser 后仍 fail closed；这只是
  存储完整性边界，不改变 memo、profile 或报告选择逻辑。

每个 batch 独立 TDD、验收并可回滚。6A-1 不通过不得开始 6A-2；6A-2 不通过不得开始
6B；6B 不通过不得开始 6C。

## 9. Migration and Archive Gate

归档 v2 notes 前，每个现存 stock/period 必须同时证明：

1. producer envelope 与 persisted pack 的 card count、card ids、card order、
   source excerpts、source unit ids/objects、selection fields 和 diagnostics 完全一致；
2. pack-first 与 producer envelope、`active_v2` record 集合完全一致；stale duplicate、
   reindexed 和 orphan notes 均进入 dry-run manifest，不进入 pack；
3. pack-first 前后 v1 diagnostics 和 adapted legacy excerpts 完全一致；
4. selected material cards 与 synthesis items 完全一致；
5. historical 八股 fixture 全绿；本地当前 11 个 notes 目录全部纳入迁移审计；
6. legacy report 与 pack-shadow/pack-first 的 annual memo、MaterialSnapshot、
   formal-medium/formal-thin rendered output 和 citations 无变化；若 stale notes 导致
   差异则停止并人工审查，不把 stale 内容补进 pack；
7. citation missing/unused/unknown/malformed 仍为零；
8. 至少中际旭创和复旦微电新报告复跑通过质量/source/prose gates。

归档动作只产生 dry-run archive manifest。实际移动/删除需用户单独确认，且不得与 runtime
实现提交混在一起。

## 10. Failure Modes and Required Tests

| Failure mode | Safe behavior | Required test |
|---|---|---|
| Writer 丢一个 card 或 SourceUnit | 拒绝写入，旧 pack 不变 | Producer envelope roundtrip exact equality |
| `candidate_cards` 与 `cards` 分叉 | 停止，不省略 candidate | Divergent candidate fixture |
| cards/diagnostics/payload hash 或 count 被篡改 | 整组回退 legacy notes并记录错误 | Malformed integrity fixtures |
| pack 损坏且 v2 notes 已归档 | 报告构建显式失败，不生成空 annual memo | No-fallback typed-error integration fixture |
| manifest 声明 pack 缺失或 pack 未登记 | 整组 fallback；无 v2 fallback 时 typed error | Manifest completeness fixtures |
| manifest 缺失但 pack 目录非空 | 视为损坏，不把发现的 pack 当完整集合 | Orphan pack-set fixture |
| manifest 损坏时执行单期刷新 | normal writer 拒绝写入，只输出 repair-required | Manifest write-state fixtures |
| v2 notes 已归档后 manifest 缺失/损坏 | fail closed，不根据残留 pack 自动 rebuild | Post-archive repair fixture |
| 首次无 manifest、无 pack 写入 | 建立单期 manifest，不依赖旧 notes | Manifest bootstrap fixture |
| manifest pack_path 逃逸固定目录或 filename 与 period 不符 | validation fail，不读取目录外文件 | Manifest path confinement fixtures |
| 两张 card 复用同一 SourceUnit | pack validation fail | Cross-card ownership fixture |
| pack identity 与路径 stock/period 不符 | validation fail，不跨股读取 | Identity mismatch fixture |
| `stock_code` 与 pack identity 不符 | validation fail，不跨代码读取 | Expected stock-code mismatch fixture |
| pack 与 v2 Markdown 同时存在 | 只读 pack；v2 notes 不叠加 | Poisoned v2 note ignored fixture |
| pack 缺失 | 旧 Markdown 路径输出不变 | Legacy fallback fixture |
| 一个 period pack 坏、另一个有效 | 不部分混用，整组 fallback | Multi-period all-or-nothing fixture |
| v2 notes 有重复/reindexed/orphan 文件 | 分类为 stale，pack 仍与 producer/active-v2 一致 | Local duplicate-card-id fixtures |
| v2 note 的投影字段与 producer card 不同 | fingerprint 不匹配，不能误标 active | Note-card fingerprint fixtures |
| v2 note 无法解析 | 分类为 stale_invalid，不参与 active parity | Invalid-v2-note fixture |
| note writer 与 pack store 对空白的 hash 规则漂移 | active 分类拒绝并阻止切换 | Shared excerpt-hash compatibility fixture |
| v1 有未覆盖事实 | adapter 和 diagnostics 保持 | v1 actionable recovery parity fixture |
| human projection 省略 card | 只影响阅读 view，机器 pack仍完整 | Pack count unchanged + bounded view fixture |
| projection 改写/截断 excerpt | test fail | Visible excerpt exact-substring fixture |
| 重跑相同输入 | pack/view 字节相同 | Deterministic idempotence fixture |
| 写入中断 | 旧 pack 保持可读 | Atomic replace failure fixture |
| typed storage error 被宽泛异常吞掉 | 报告构建 fail closed，不生成空 annual memo | All pack-first callers re-raise typed-error fixture |
| 6A/6B 输出计数混淆 | 新旧字段含义稳定，pack/view 不计入 legacy note count | `knowledge_outputs` compatibility fixture |
| report 因存储切换变化 | acceptance fail | Memo/snapshot/formal-thin citation regression |

## 11. Planned Scope

Batch 6A runtime scope，subject to review：

- Create `scripts/utils/periodic_report_narrative_pack_store.py`
- Modify `scripts/utils/annual_report_material_pack.py`
- Modify `scripts/prepare_annual_report_materials.py`
- Modify `scripts/previews/periodic_report_narrative_cards_preview.py`
- Modify `scripts/previews/periodic_report_narrative_cards_acceptance.py` and
  `tests/reporter/test_periodic_report_narrative_cards_acceptance_script.py` for the
  migration audit owner and its gate tests
- Modify `scripts/utils/periodic_report_narrative_card_note_writer.py` only to reuse
  pack store's `normalized_source_excerpt_hash()` and, where useful, a shared validation
  helper that replaces duplicate code

Batch 6B runtime scope：

- Create `scripts/utils/periodic_report_narrative_view_writer.py`
- Modify the preparation/preview/acceptance callers above
- Modify `scripts/utils/periodic_report_narrative_card_synthesis_items.py` and its
  tests so `use_pack=True` preserves typed storage errors and passes identity params
- Modify `scripts/utils/report_skills/synthesis_skills.py` only to pass stock identity
  and re-raise the typed no-fallback storage error instead of swallowing it
- Keep annual memo, snapshot, renderers and all report-selection logic unchanged

Batch 6C may delete or shrink：

- `scripts/utils/periodic_report_narrative_card_synthesis_items.py` direct-note branch
- v2 render/parse portions of `periodic_report_narrative_card_note_writer.py`
- v2 Markdown parse portions of `annual_report_material_pack.py`

Corresponding tests may change under `tests/utils/` and `tests/reporter/`. Config, data,
reports, scoring, target, risk, technical, profile, collection and prompts are prohibited.

由于当前 worktree 已有其他未提交批次，开始 6A 前必须记录 Batch 6 allowed runtime
文件的逐文件 SHA256、行数和副本；预算只比较这些文件与后续新增文件，不使用整个
worktree 的混合 `git diff` 作为基线。

Budget is measured against that locked pre-Batch-6 runtime baseline:

- 6A target `+220`, hard stop `+300` runtime lines；
- 6B cumulative target `+320`, hard stop `+420`；
- 6C final cumulative target `<= 0`；hard stop `+80`。若未能通过删除旧 v2
  render/parser/writer 回到账本上限，Batch 6 不得宣告完成。

Tests and workflow notes are excluded. Implementation must replace parsers/writers in 6C,
not leave permanent parallel paths.

## 12. Stop Conditions

Stop and return to design if：

1. pack cannot preserve exact cards, SourceUnits or diagnostics without changing producer；
2. report needs to read human projection Markdown；
3. compatibility requires combining partial packs with v2 Markdown；
4. v1 diagnostics or adapted excerpts differ between storage modes；
5. pack corruption can still be swallowed into an empty annual memo after v2 notes archive；
6. any report profile, memo, snapshot, citation offset, score, target, risk, technical,
   recommendation, collection or prompt must change；
7. a stock/industry-specific rule is proposed；
8. a batch exceeds its runtime hard stop；
9. manifest cannot prove the complete expected period set without a second machine truth；
10. stale v2 notes cause memo/snapshot/report differences that cannot be explained and
    accepted without changing report logic；
11. normal writer would overwrite a damaged/nonempty manifest state instead of returning
    `repair_required`；
12. any file archive/delete is attempted before the migration gate and explicit user approval。

## 13. Acceptance

Batch 6 is complete only when：

- every persisted pack is a validated exact projection of its producer envelope；
- report machine input is pack-first and human view independent；
- normal material preparation writes one pack and one readable projection per period，
  not N v2 Markdown card notes；
- pack-first and legacy paths are report-equivalent during migration；
- current v2 notes have a reviewed dry-run archive manifest；
- v1 notes remain until their independent zero-recovery gate passes；
- final runtime is slimmer than the temporary migration checkpoint；
- fresh formal-medium and formal-thin reports retain citation and quality hygiene。

## 14. Design Delta After Self-Review

Accepted：

- 6A 改为 pack/manifest shadow-write，不在 parity 证明前切换报告机器真源；
- 新增 stock-level expected-period manifest，检测缺失、未登记和部分 pack set；
- integrity 扩展为 cards、producer diagnostics 和完整 payload 三层 hash；
- 现有 v2 notes 明确分类 active/stale_duplicate/stale_reindexed/stale_orphan；
- active-v2 采用固定 card-level fingerprint，不把 note projection 与 envelope-level
  diagnostics 混为同一比较；
- manifest 写入限定为 bootstrap/upsert/repair_required 三态，损坏状态不会被单期刷新覆盖；
- 旧 note 的 writer filename 不作为 active-v2 身份；它仅用于多个同 fingerprint note 的
  canonical representative 选择，避免 reindex 留存被误判为未覆盖；
- manifest repair 只能由完整 legacy v2 inventory 支撑；archive 后的 manifest 故障必须
  fail closed，不能从残留 pack 自动重建；
- typed-error 与 stock identity plumbing 移到 6B 真正切换 pack-first 的同一批次；
- 删除 loader 的 report-year/type 部分过滤模式，保持全期 all-or-nothing。

Rejected：none。

Deferred：实际 archive/move/delete 仍等待 6C dry-run archive manifest 和用户单独确认。

R2 required：yes。manifest 完整性和 shadow-to-pack-first 切换改变了高风险迁移边界，
需要独立 reviewer 核对后才能写 6A implementation task。
