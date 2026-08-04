# Knowledge Persistence 6B Completion Notes

日期：2026-07-16
实现基线：`c20af7f`
实现分支：`codex/annual-producer-v2`

## Outcome

- 6B runtime implementation: accepted
- existing-view backfill: completed
- persisted-pack/current-producer parity gate: needs follow-up
- formal report generation: not run, per design

正常 preparation/preview 入口现在只写 validated JSON pack、stock-local manifest 和单一
human Markdown view，不再导入或调用逐卡 note writer。Human view 仅从 validated persisted pack
构建，material loader 不读取该目录。Acceptance 已从 v2 note-shadow parity 改为只读 pack
projection audit。

## Modified Files

Runtime:

- `scripts/utils/periodic_report_narrative_view_writer.py` (new)
- `scripts/utils/periodic_report_narrative_pack_store.py`
- `scripts/prepare_annual_report_materials.py`
- `scripts/previews/periodic_report_narrative_cards_preview.py`
- `scripts/previews/periodic_report_narrative_cards_acceptance.py`

Tests:

- `tests/utils/test_periodic_report_narrative_view_writer.py` (new)
- `tests/utils/test_periodic_report_narrative_pack_store.py`
- `tests/utils/test_annual_report_material_pack.py`
- `tests/reporter/test_prepare_annual_report_materials.py`
- `tests/reporter/test_periodic_report_narrative_cards_preview_script.py`
- `tests/reporter/test_periodic_report_narrative_cards_acceptance_script.py`

Knowledge backfill:

- 11 new `periodic_narrative_views/2025-annual.md` files
- no pack, manifest, or retained v1 card-note modification

## RED / GREEN

1. Pack loader entries/public stock root: import and contract tests RED, then GREEN.
2. Validated-pack human view writer: missing module RED, then ranking/cap/dedup/full excerpt,
   empty pack, deterministic write, typed failure and atomicity tests GREEN.
3. Preparation/preview transition: 11 old dual-write expectations RED, then pack+view-only
   behavior GREEN.
4. Acceptance transition: obsolete preview-maintenance import and missing projection API RED,
   then pack/projection read-only audit GREEN.
5. Self-review fixes: envelope parity and filesystem-error tests RED, then GREEN.

## Verification

- Focused/downstream: `209 passed`
- `tools/ci_grep_gates.sh`: PASS
- `git diff --check`: PASS
- Python compile check for all five runtime files: PASS
- Normal entrypoint references to card-note writer: `0`
- Runtime delta vs `c20af7f`: `-95` net lines
  - prepare: `+2`
  - acceptance: `-101`
  - preview: `-195`
  - pack store: `+6`
  - new view writer: `+193`
- Full suite was stopped after an unrelated existing top-level import failure in
  `test_output_structured_risk_signals_passes_to_risk_section`:
  `224 passed, 6 skipped, 1 failed`; failure is `scoring_engine.py` relative-importing
  `recommendation_decision` when imported as a top-level module. No 6B file is involved.

## Requirement-Test Matrix

| Requirement | Implementation | Proof |
| --- | --- | --- |
| Validated pack is machine truth | view writer accepts only stock/period/base dir and calls validated loader | pack/view writer tests |
| One human view, no card-note dual write | preparation and preview call pack writer then view writer | prepare/preview integration tests |
| View is display-only | loader continues pack-first and ignores sentinel view | `test_pack_first_loader_ignores_human_projection_view` |
| Deterministic bounded display | schema family order, rank, normalized hash dedup, four per family | view ranking/idempotence tests |
| Full excerpts remain intact | multiline blockquote without compression/truncation | exact multiline fixture |
| Invalid pack fails closed | pack storage errors propagate | malformed manifest fixture |
| Atomic view update | same-directory temp + replace; typed failures preserve prior bytes | write/mkdir/read failure fixtures |
| Acceptance performs zero writes | pure build called twice; pack/manifest bytes compared | projection function and CLI tests |
| Deprecated `--pack-shadow` remains compatible | alias runs new projection only | alias/preferred/both fixture |

## Backfill Evidence

- Manifests/periods: 11 stocks, one `2025 annual` period each
- First run: 11 views `created`
- Second run: 11 views `unchanged`
- Views: 11 files, 1,739 lines total
- Retained v1 card notes: 48 before and after
- Temp files: 0
- SHA-256 snapshot: all 70 pack/manifest/v1-note files byte-identical before and after
- Displayed/total cards range: 14-18 displayed from 38-83 persisted per stock

## Remaining Finding

The only local cache available in this worktree is Black Sesame Intelligence. The new real
acceptance correctly reports `producer_pack_parity: False` while all projection-integrity and
v1 recovery fields pass:

- persisted cards: 56
- current producer cards from the tracked local cache: 57
- schema, selection version, stock identity, and period: equal
- card payload drift: 7 old-only IDs, 8 new-only IDs, 2 shared IDs changed
- projection deterministic/read-only/hash match: all true
- v1 actionable recovery / adapter use: both zero

This drift predates 6B: both the committed pack and producer code came from `c20af7f`, and this
batch did not modify producer or pack bytes. The design explicitly permits backfill to add only
views, so the implementation did not silently refresh machine truth. A separate local-cache
pack refresh/acceptance task should regenerate and review all 11 packs before claiming global
producer-pack parity or running formal reports.

## Blocker / Warning / Deviation

- Blocker for 6B code: none
- Blocker for global producer-pack parity completion: persisted packs need a separately scoped
  deterministic refresh and review
- Warning: the human view faithfully exposes some pre-existing producer family/ranking noise;
  view writer must not hide it by dropping source material
- Deviation: full pytest did not complete because an unrelated existing import failure was
  followed by slow data tests; focused/downstream/CI gates completed
