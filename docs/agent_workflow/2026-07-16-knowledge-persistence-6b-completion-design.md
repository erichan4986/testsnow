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

The writer must first call `load_validated_periodic_narrative_pack_set()` and select exactly
one envelope with the requested `(report_year, report_type)`. It must not accept a raw
`cards_pack`, raw text, or arbitrary card list. Missing/duplicate periods and invalid packs
raise a stable projection error; a corrupted pack cannot be rendered into a reassuring view.

The module exposes two functions, both of which load the same persisted validated pack set:

```python
build_periodic_report_narrative_view(
    *, stock_name: str, stock_code: str, report_year: int,
    report_type: str, base_dir: str | Path,
) -> PeriodicNarrativeViewProjection

write_periodic_report_narrative_view(
    *, stock_name: str, stock_code: str, report_year: int,
    report_type: str, base_dir: str | Path,
) -> PeriodicNarrativeViewWriteResult
```

`build_*` is pure with respect to the filesystem: it reads and validates the pack set and
returns rendered Markdown plus metadata, but writes nothing. Acceptance uses this function.
`write_*` calls `build_*`, then performs the atomic write. Neither function accepts raw cards.

`load_validated_periodic_narrative_pack_set()` is extended additively to return validated
manifest `entries`, aligned by index with `packs`. Existing `packs` and `cards` outputs remain
unchanged. The view uses the matched entry's `pack_path`; it must not reconstruct that path
from year/type.

`PeriodicNarrativeViewProjection` contains `markdown`, `view_path`, `pack_relative_path`,
`cards_sha256`, `total_cards`, `displayed_cards` and family count metadata.
`PeriodicNarrativeViewWriteResult` contains the same non-Markdown metadata plus `state`, whose
only values are `created`, `updated`, and `unchanged`.

Create `PeriodicNarrativeViewError(code)` with stable codes:

- `view_period_not_found`
- `view_period_ambiguous`
- `view_write_failed`

`PeriodicNarrativePackStorageError` propagates unchanged from `build_*`; the view layer must not
wrap or translate machine-storage failures. `view_write_failed` retains the original `OSError`
as its exception cause.

`periodic_report_narrative_pack_store.py` must expose a public
`periodic_narrative_stock_root(base_dir, stock_name)` helper, replacing internal use of
`_root`, so pack and view paths share sanitisation. No second manifest parser, period
normalizer, stock-name sanitizer or card validator may be introduced.

### 4.2 Path And Atomicity

Path:

```text
knowledge/10-Stocks/<stock>/periodic_narrative_views/<year>-<report-type>.md
```

Write via same-directory temporary file plus `Path.replace()`. A failed render/write leaves
the prior view untouched and removes the temporary file. The machine pack is never rolled back
or altered by view writing.

### 4.3 Content

The view contains deterministic YAML frontmatter with these exact scalar keys:

- `generated_projection: true`
- `stock_name`, `stock_code`, `report_year`, `report_type`
- `pack_path` (relative to the stock root)
- `cards_sha256`
- `total_cards`, `displayed_cards`
- `family_<canonical-family>_total` and
  `family_<canonical-family>_displayed` for every canonical family

Strings are JSON-quoted scalars, integers remain integers and booleans remain booleans. No
general YAML dependency or second frontmatter helper is introduced.

It imports `CANONICAL_FAMILIES` and `FAMILY_LABELS` from
`annual_argument_schema.py` and emits those five families in schema order:

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

Deduplicate only matching `normalized_source_excerpt_hash()` values within the same family.
That shared hash intentionally treats whitespace-only variants as the same excerpt; this exact
normalization behavior is covered by a test. Keep the earlier sorted card. Never
semantic-deduplicate, rewrite, compress, or truncate an excerpt. Each rendered item includes
title, `card_id`, `source_block_id`, `source_unit_ids`, the full exact `source_excerpt`, and no
producer diagnostics/source-unit JSON/guardrail template. The excerpt is rendered as a
Markdown blockquote by prefixing each existing line; no source character is removed and
existing line boundaries are preserved.

An empty but valid pack produces a valid view with all five `0 / 0` family sections and matching
zero counts; it is not a projection error.

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

The exact successful shape is:

```python
{
    "knowledge_written_count": 0,
    "knowledge_outputs": {
        "legacy_note_count": 0,
        "periodic_narrative_pack": {
            "state": "bootstrap|upsert",
            "pack_path": "...",
            "manifest_path": "...",
        },
        "periodic_narrative_view": {
            "state": "created|updated|unchanged",
            "view_path": "...",
            "total_cards": 0,
            "displayed_cards": 0,
            "cards_sha256": "...",
        },
    },
}
```

When `write_knowledge=False`, both `knowledge_outputs` and the legacy count retain their current
empty/zero shape.

The CLI help changes from “write narrative card notes” to “write validated pack and human
projection.”

### 5.2 `periodic_report_narrative_cards_preview.py`

The preview remains a local producer inspection tool. `write_knowledge=False` never loads or
writes knowledge artifacts, even when `knowledge_base_dir` is supplied; it renders producer
cards and a `knowledge_write_mode: disabled` line only. `write_knowledge=True` requires
`knowledge_base_dir`, then writes pack and view with the same contract as preparation. Missing
base dir raises `knowledge_base_dir_required` before any write.

The existing `--refresh-existing`, `--refresh-frontmatter-only`, and `--existing-only` options
are legacy-card-note options. Keep them temporarily only to produce a stable
`legacy_note_options_removed` error when non-default; do not silently ignore them and do not
add a normal CLI switch that regenerates N card notes. The Python function raises
`ValueError("legacy_note_options_removed")`; the CLI converts it to argparse exit code `2`
without a traceback. Explicit migration code can still call the retained writer directly.

### 5.3 Acceptance CLI

`periodic_report_narrative_cards_acceptance.py` replaces `analyze_pack_shadow()` and its old
active-v2 Markdown parity fields with `analyze_pack_projection()`:

- it validates persisted packs and verifies the selected period equals the producer envelope;
- it calls pure `build_periodic_report_narrative_view()` twice and verifies byte identity;
- it snapshots pack and manifest bytes before/after the pure build and verifies no change;
- it reports legacy v1 recovery diagnostics from
  `build_annual_report_material_pack(..., stock_code=stock_code)` separately;
- it no longer requires active v2 Markdown card-note parity.

The new result has exact booleans/values:

- `producer_pack_parity`
- `projection_deterministic`
- `pack_bytes_unchanged`
- `manifest_bytes_unchanged`
- `projection_cards_sha256_matches`
- `projection_total_cards`
- `projection_displayed_cards`
- `v1_actionable_needs_recovery_count`
- `v1_adapter_use_count`

Delete acceptance output/tests for `active_v2_parity`, `selected_material_parity`,
`synthesis_items_parity`, v2 note classifications, and note-maintenance counts. Their migration
purpose ended with the approved pack-first reset; retaining them would require recreating the
deleted projections.

Keep the existing `--pack-shadow` CLI option as a deprecated compatibility alias for running
the new pack-projection analysis. It must not restore the old fields or write notes. Acceptance
Markdown labels the section `pack projection`, while a new `--pack-projection` option is the
preferred spelling; passing either or both is equivalent.

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
- narrow-export the shared stock-root/path helper from
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
| Acceptance renders a view | pure build performs zero writes | before/after tree and byte fixture |
| View tries raw producer input | no public raw-card write API | writer API and call-site tests |
| Same pack rerun changes Markdown | byte-identical view | idempotence fixture |
| Matching normalized excerpt hash | only one display row in that family | hash-dedup fixture |
| Whitespace-only excerpt variant | treated as the same shared normalized hash | normalization fixture |
| Similar but non-identical excerpts | both may display | no semantic-dedup fixture |
| Long/high-value excerpt | full exact text remains visible | exact-excerpt fixture |
| One family dominates | at most four displayed there; other family slots remain available | family cap fixture |
| Normal `--write-knowledge` recreates cards dir | must not occur | fresh temporary base-dir integration fixture |
| Legacy refresh flags ignored | stable explicit error | preview CLI/function fixture |
| `write_knowledge=True` lacks base dir | fail before any write | preview function/CLI fixture |
| View is accidentally loader input | material pack remains unchanged with sentinel view Markdown | loader regression |
| View write fails mid-write | prior view bytes remain | atomic-write failure fixture |
| View write leaves a temp file | cleanup before raising typed write error | temp-cleanup fixture |
| Valid empty pack | write five empty family sections with zero counts | empty-pack fixture |
| Manifest path spelling differs from a naive year/type join | use aligned validated entry path | aligned-entry fixture |

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

After code review approves 6B, perform a separate local backfill using the public writer for
every period in the 11 committed manifests. The backfill may add only
`periodic_narrative_views/*.md`; it must not modify pack/manifest bytes or create v2 card notes.
Record per-stock period/view counts and `git status` in acceptance notes. This backfill is the
completion gate for existing knowledge, not part of the implementation-model task.

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
7. runtime delta across the allowed runtime files exceeds target `+40` or hard stop `+100`
   net lines relative to commit `c20af7f`, excluding tests/docs. Deleting obsolete note-plan and
   pack-shadow acceptance code counts toward the net budget; layering new code without deleting
   those paths is a stop condition.

## 11. Review Questions

The Round 1 reviewer should specifically challenge:

1. Whether selecting a persisted validated envelope avoids a second machine truth;
2. Whether the output compatibility contract is explicit enough for current CLI tests;
3. Whether retaining legacy CLI flags as explicit errors is safer than silently accepting them;
4. Whether the re-baselined gate proves safety without resurrecting deleted v2 projections;
5. Whether any formal-thin citation/report path is accidentally touched (it must not be).

## 12. Self-Review Round 1 Delta

Accepted and fixed:

- split pure `build_*` from atomic `write_*`, so acceptance stays genuinely read-only;
- defined result objects, states and stable projection error codes;
- replaced optional path reuse with one required pack-store stock-root owner;
- required schema-owned family order/labels instead of a copied taxonomy;
- made frontmatter, blockquote preservation and `knowledge_outputs` exact;
- made preview no-write behavior and legacy flag failure explicit;
- replaced obsolete v2-note parity outputs with pack/projection integrity outputs;
- anchored the runtime budget to `c20af7f` and required deletion of superseded paths.

## 13. Self-Review Round 2 Delta

Accepted and fixed:

- made pack-store manifest entries an additive loader result, preventing a second path builder;
- preserved pack storage errors unchanged; defined valid-empty-pack behavior and
  whitespace-normalized dedup semantics;
- retained `--pack-shadow` only as a deprecated alias to the new read-only projection audit;
- added a post-review backfill gate for all 11 current manifests, so 6B covers existing as well
  as future knowledge;
- tightened the runtime target to `+40` and hard stop to `+100`, relying on deletion of obsolete
  preview maintenance and acceptance parity code rather than permanent parallel paths.

Replacement ledger used for budget review:

| Area | Expected runtime delta |
| --- | ---: |
| New view writer | `+110` to `+150` |
| Pack-store aligned entries/root export | `+5` to `+15` |
| Prepare integration | `-5` to `+10` |
| Delete preview card-note plan/maintenance; add pack/view status | `-80` to `-130` |
| Replace old acceptance note parity with projection integrity | `-50` to `-100` |
| Expected net | `-120` to `+25` |
