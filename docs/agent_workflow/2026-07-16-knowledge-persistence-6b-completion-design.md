# Knowledge Persistence 6B Completion Design

日期：2026-07-16  
分支：`codex/annual-producer-v2`  
状态：等待 Round 1 只读审查

## 1. Decision

Batch 6A 已经完成机器侧收口：定期报告 narrative cards 的持久化真源是已验证的
`periodic_narrative_packs/<year>-<report-type>.json` 与 stock-local manifest；报告 loader
已 pack-first，v2 单卡 Markdown 不再是机器输入。

本批不恢复逐卡 Markdown，也不重建旧的 note-to-pack parity gate。旧 note 曾重复保存同一
source excerpt、frontmatter 和模板，造成约 69,708 行投影冗余；现已清理的 v2 note 不能再
作为验收基准。原始本地缓存、producer cards 与 JSON pack 均仍保留。

6B 的目标是补齐剩余闭环：

1. 正常 `--write-knowledge` 只写一个 machine pack 和一个可读的 Markdown view；
2. human view 只从已验证的 persisted pack 读取，永远不是 loader 输入；
3. 现有 preparation/preview 入口不再隐式调用逐卡 note writer；
4. 验收改为验证 pack integrity、projection determinism 和 machine/human 边界。

这是一项持久化与可浏览性修复，不修改 producer、annual memo、MaterialSnapshot、Chapter 4
renderer、引用、profile、评分、目标价、风险、技术面、推荐、采集或 LLM prompt。

## 2. Approaches Considered

### A. 恢复 card notes 并重做旧 parity gate

不采用。它会重新制造 N 张重复文件，把历史投影误当成真源，并使清理工作失效。

### B. 维持 pack-first，增加单一 human projection

采用。JSON pack 保持完整机器材料；一个 period 对应一个 Markdown view，方便人工浏览而不
影响报告输入。每个 family 的 view 上限只限制展示，不限制 producer 或 pack 保留内容。

### C. 不写 human projection

不采用。机器链路可运行，但知识库对人工审阅不友好，也无法替代被清掉的 card notes。

## 3. Target Layout And Ownership

```text
local annual cache
  -> evidence pack -> producer cards
  -> periodic_narrative_packs/<year>-<report-type>.json  [machine truth]
  -> periodic_narrative_pack_manifest.json               [machine inventory]
  -> periodic_narrative_views/<year>-<report-type>.md    [human projection]

annual_report_material_pack / synthesis / memo / report
  -> read validated pack + retained v1 compatibility only
  -> never parse periodic_narrative_views
```

The retained `periodic_report_narrative_card_note_writer.py` is migration-only. It may be
called explicitly by a future migration tool, but normal preparation and preview entrypoints
must neither import nor invoke it.

## 4. Human Projection Contract

### 4.1 Writer

Create `scripts/utils/periodic_report_narrative_view_writer.py`.

Public entrypoint:

```python
write_periodic_report_narrative_view(
    *, stock_name: str, stock_code: str, report_year: int,
    report_type: str, base_dir: str | Path,
) -> PeriodicNarrativeViewWriteResult
```

The writer must first call `load_validated_periodic_narrative_pack_set()` and select exactly
one envelope with the requested `(report_year, report_type)`. It must not accept a raw
`cards_pack`, raw text, or arbitrary card list. Missing/duplicate periods and invalid packs
raise a stable projection error; a corrupted pack cannot be rendered into a reassuring view.

`periodic_report_narrative_pack_store.py` may expose one small public stock-root/path helper
so pack and view paths share sanitisation. No second manifest parser or card validator may be
introduced.

### 4.2 Path And Atomicity

Path:

```text
knowledge/10-Stocks/<stock>/periodic_narrative_views/<year>-<report-type>.md
```

Write via same-directory temporary file plus `Path.replace()`. A failed render/write leaves
the prior view untouched. The machine pack is never rolled back or altered by view writing.

### 4.3 Content

The view contains YAML frontmatter with at least:

- `generated_projection: true`
- stock identity, report year/type
- pack-relative path
- pack `cards_sha256`
- `total_cards`
- `displayed_cards`
- per-family total/displayed counts

It then emits the five canonical families, in schema order:

1. 业务结构
2. 经营变化
3. 管理层判断与行业展望
4. 技术与产品进展
5. 财务质量与变化原因

For each family, display at most four cards and at most twenty cards overall. This is an
editorial browse limit only: all pack cards remain persisted and report-eligible. The heading
must show `displayed / total`, including `0 / 0` sections, so absence is observable rather
than silently dropped.

Within a family, sort deterministically by:

1. `argument_complete=True` first;
2. `quality_score` descending;
3. number of `source_unit_ids` descending;
4. original pack card order;
5. `card_id` lexicographically.

Deduplicate only exact `normalized_source_excerpt_hash()` matches within the same family.
Keep the earlier sorted card. Never semantic-deduplicate, rewrite, compress, or truncate an
excerpt. Each rendered item includes title, `card_id`, `source_block_id`, `source_unit_ids`,
the full exact `source_excerpt`, and no producer diagnostics/source-unit JSON/guardrail
template.

### 4.4 Determinism

The view must be byte-identical for the same validated pack. It must not include wall-clock
time, mtime, random IDs, absolute paths, or a reserialised copy of the complete pack.

## 5. Normal Writer Entry Points

### 5.1 `prepare_annual_report_materials.py`

Under `write_knowledge=True`:

1. write/upsert the validated pack;
2. write the one corresponding view from that persisted pack;
3. return structured output for `periodic_narrative_pack` and
   `periodic_narrative_view`.

`knowledge_written_count` remains for compatibility but is always `0` and documented as the
deprecated count of legacy card notes, not a count of all knowledge artifacts. Add a separate
structured `knowledge_outputs` entry for the pack and view; do not overload the old count.

The CLI help changes from “write narrative card notes” to “write validated pack and human
projection.”

### 5.2 `periodic_report_narrative_cards_preview.py`

The preview remains a local producer inspection tool. With `knowledge_base_dir` it may show
pack/view status, but it must not compute a card-note maintenance plan or invoke the legacy
note writer. With `write_knowledge=True`, it writes pack then view with the same contract as
preparation.

The existing `--refresh-existing`, `--refresh-frontmatter-only`, and `--existing-only` options
are legacy-card-note options. Keep them temporarily only to produce a stable
`legacy_note_options_removed` error when non-default; do not silently ignore them and do not
add a normal CLI switch that regenerates N card notes. Explicit migration code can still call
the retained writer directly.

### 5.3 Acceptance CLI

`periodic_report_narrative_cards_acceptance.py` is re-baselined for pack-first:

- it validates persisted packs and verifies the selected period equals the producer envelope;
- it verifies a generated view derives from the validated pack, is deterministic, and does not
  change pack bytes/hashes;
- it reports legacy v1 recovery diagnostics separately;
- it no longer requires active v2 Markdown card-note parity.

It must not import a human view as a report/material-loader input. Existing pack-first loader
tests add a sentinel view file and prove it is ignored.

## 6. Migration And Compatibility

- Retained legacy **v1** notes are still read for existing exact-shadow/actionable-recovery
  logic. This batch does not archive or delete them.
- Removed legacy **v2** card projections are neither recreated nor treated as missing source
  data.
- A malformed/missing manifest with existing packs remains fail-closed under the existing pack
  store contract. 6B adds no repair/rebuild path.
- 6C, not this batch, may remove v2 Markdown parsing and direct-note compatibility branches
  after a separate inventory/adapter gate.

## 7. Allowed Scope

Runtime files:

- create `scripts/utils/periodic_report_narrative_view_writer.py`
- optionally narrow-export a shared stock-root/path helper from
  `scripts/utils/periodic_report_narrative_pack_store.py`
- `scripts/prepare_annual_report_materials.py`
- `scripts/previews/periodic_report_narrative_cards_preview.py`
- `scripts/previews/periodic_report_narrative_cards_acceptance.py`

Tests:

- create `tests/utils/test_periodic_report_narrative_view_writer.py`
- `tests/utils/test_periodic_report_narrative_pack_store.py`
- `tests/reporter/test_prepare_annual_report_materials.py`
- `tests/reporter/test_periodic_report_narrative_cards_preview_script.py`
- `tests/reporter/test_periodic_report_narrative_cards_acceptance_script.py`
- `tests/utils/test_annual_report_material_pack.py` only for a view-is-ignored regression.

Workflow documents under `docs/agent_workflow/` are allowed. Everything else is prohibited.

## 8. Failure Modes And Required Tests

| Failure mode | Required behavior | Test |
| --- | --- | --- |
| Invalid/missing target pack | typed projection failure; existing view untouched | malformed/missing period fixtures |
| View tries raw producer input | no public raw-card write API | writer API and call-site tests |
| Same pack rerun changes Markdown | byte-identical view | idempotence fixture |
| Exact duplicate excerpt | only one display row in that family | hash-dedup fixture |
| Similar but non-identical excerpts | both may display | no semantic-dedup fixture |
| Long/high-value excerpt | full exact text remains visible | exact-excerpt fixture |
| One family dominates | at most four displayed there; other family slots remain available | family cap fixture |
| Normal `--write-knowledge` recreates cards dir | must not occur | fresh temporary base-dir integration fixture |
| Legacy refresh flags ignored | stable explicit error | preview CLI/function fixture |
| View is accidentally loader input | material pack remains unchanged with sentinel view Markdown | loader regression |
| View write fails mid-write | prior view bytes remain | atomic-write failure fixture |

## 9. Acceptance Gates

Before a formal report run:

1. focused writer/pack/prepare/preview/acceptance/material-loader tests pass;
2. `tools/ci_grep_gates.sh` and `git diff --check` pass;
3. on a temporary knowledge root, normal preparation creates exactly one pack JSON, one
   manifest and one view Markdown for the period, with no `periodic_narrative_cards/*.md`;
4. all committed stock packs validate and can each generate one deterministic view without
   network access;
5. pack bytes and integrity hashes are unchanged before/after view generation;
6. pack-first loader and its v1 recovery diagnostics remain unchanged when a view exists.

Only then may local report validation regenerate one formal-medium and one formal-thin sample
and check citation/source-boundary/report-quality gates. This implementation batch itself must
not generate reports.

## 10. Stop Conditions

Stop and return to design if any of the following becomes necessary:

1. report/material loader must read human projection Markdown;
2. full producer cards/source units/diagnostics need modification to render the view;
3. normal entrypoint needs to dual-write per-card notes for compatibility;
4. v1 recovery, profile, scoring, target, risk, technical, citation or LLM behavior changes;
5. pack corruption becomes repairable by silently scanning files;
6. a stock/industry-specific display rule is proposed;
7. runtime delta exceeds target `+110` or hard stop `+150` lines, excluding tests/docs.

## 11. Review Questions

The Round 1 reviewer should specifically challenge:

1. Whether selecting a persisted validated envelope avoids a second machine truth;
2. Whether the output compatibility contract is explicit enough for current CLI tests;
3. Whether retaining legacy CLI flags as explicit errors is safer than silently accepting them;
4. Whether the re-baselined gate proves safety without resurrecting deleted v2 projections;
5. Whether any formal-thin citation/report path is accidentally touched (it must not be).
