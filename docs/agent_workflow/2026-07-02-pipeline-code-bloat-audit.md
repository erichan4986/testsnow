# Pipeline Code Bloat Audit

Date: 2026-07-02

## Verdict

`needs_slimming_before_commit`

这一轮 pipeline 修复方向是对的：问题确实来自生产链路，而不是单份复旦微电报告。但当前 diff 已经进入“质量修复推动代码膨胀”的危险区。建议暂停新增功能，先做收口、拆包和删减决策，再继续复旦报告 trial。

## Current Diff Size

Tracked diff:

```text
23 files changed, 2491 insertions(+), 108 deletions(-)
```

Untracked new code/tests:

```text
scripts/utils/fundflow_material.py                         134 lines
scripts/utils/periodic_report_explanation_pack.py          272 lines
scripts/utils/source_direct_relevance.py                   183 lines
tests/utils/test_fundflow_material.py                       53 lines
tests/utils/test_periodic_report_explanation_pack.py        79 lines
tests/utils/test_source_direct_relevance.py                 83 lines
tests/reporter/test_periodic_report_fulltext_intake_skill.py 39 lines
```

Workflow docs currently add roughly 3,100 lines. These are not runtime bloat, but they do increase review noise and should be curated before final commit.

## Hotspots

### 1. `scripts/utils/report_skills/synthesis_skills.py`

Risk: `high`

Current symptom:

- `SynthesisSkill` is now doing orchestration, curated external narrative reading, citation hydration, reasoning card normalization, deterministic viewpoint digest, financial fact pack sanitation, indirect industry citation cleanup, source metadata enrichment, and legacy synthesis.
- This is becoming the central dumping ground for every report-quality fix.

Recommendation:

- Do not add more logic here.
- Move curated external display construction into a helper module, for example:
  - `scripts/utils/curated_external_display.py`
- Leave `SynthesisSkill` as a caller:
  - read ctx
  - call helper
  - set ctx outputs

Keep now:

- The current behavior is tested and useful.

Must slim before or immediately after commit:

- Extract `_build_viewpoint_narrative_deep_analysis_display` plus citation/card helpers out of `SynthesisSkill`.

### 2. `scripts/utils/report_quality.py`

Risk: `high`

Current symptom:

- New warnings and gates are useful, but all rules are being added to one growing file.
- Peer gates, industry chain gates, fundflow gates, evidence-depth warnings, citation footnote checks and scoring contradictions now live together.

Recommendation:

- Keep `report_quality.py` as the public API:
  - `check_report_file`
  - `check_report_text`
  - `QualityIssue`
  - `QualityResult`
- Move rule families into small helpers later:
  - `report_quality_deep_analysis.py`
  - `report_quality_peer.py`
  - `report_quality_fundflow.py`
  - `report_quality_citations.py`

Keep now:

- Warning-only gates are appropriate; they prevent “安全但空泛”的报告。

Must adjust before commit:

- `section_too_generic` currently treats any citation as “specific content”. This may under-detect cited but empty prose. Acceptable as warning, but should be documented as low-sensitivity.
- `external_viewpoint_overcompressed` will warn on old paragraph-only 4.4. That is intended, but should remain warning-only.

### 3. `scripts/utils/reporter/sections/deep_analysis_renderer.py`

Risk: `medium-high`

Current symptom:

- Renderer now contains substantial curated external remap/dedupe/grouping/reasoning-card logic.
- The renderer is no longer only rendering; it is doing display policy and citation identity handling.

Recommendation:

- Keep the behavior for now because 4.4 footnote correctness is critical.
- Later extract curated external rendering to:
  - `scripts/utils/reporter/sections/curated_external_renderer.py`

Do not add more 4.4-specific helpers to `DeepAnalysisRenderer`.

### 4. `scripts/utils/periodic_report_explanation_pack.py`

Risk: `medium`

Current symptom:

- New module is 272 lines.
- It solves a real issue: 4.2 needs management explanation, not repeated finance figures.

Recommendation:

- Keep as a standalone module.
- This is healthier than embedding the extractor inside `periodic_report_fulltext_intake_skill.py`.

Slimming opportunity:

- `_TOPIC_PATTERNS`, `_REASON_TOPIC_RULES`, and heading parsing can be made smaller later.
- No urgent rewrite needed.

### 5. `scripts/utils/fundflow_material.py`

Risk: `low`

Current symptom:

- Small deterministic pack, 134 lines.
- Clear purpose: summarize资金流向 for 4.3.

Recommendation:

- Keep.
- Good example of the style we want: deterministic, isolated, testable.

### 6. `scripts/utils/source_direct_relevance.py`

Risk: `medium`

Current symptom:

- Necessary response to the MLCC failure: LLM cannot safely invent multi-hop chains.
- But the rules are still blunt and config-sensitive.

Recommendation:

- Keep only as a conservative filter.
- It should not become a full chain-reasoning engine.
- If `product_exposure_terms` are missing, fallback to keywords must remain conservative.

Future guard:

- Multi-hop industry logic should stay out of canonical 4.1-4.3 until a deterministic chain validator exists.

## Keep / Refactor / Defer Matrix

| Area | Decision | Reason |
| --- | --- | --- |
| Fundflow material pack | Keep | Small, deterministic, reusable across A-share stocks |
| Annual-report explanation pack | Keep | Directly addresses 4.2 emptiness; reusable |
| Direct relevance filter | Keep cautiously | Prevents MLCC-style hallucinated chain |
| 4.4 reasoning cards | Keep, but incomplete until composer emits cards | Needed to preserve good social/知乎 logic |
| Evidence-depth warnings | Keep as warning-only | Good quality tripwires, not hard gates |
| SynthesisSkill curated external helpers | Refactor | Too much display/citation logic inside skill |
| DeepAnalysisRenderer curated external helpers | Refactor later | Renderer owns too much 4.4 policy |
| report_quality rule families | Refactor later | File is becoming rule landfill |
| Workflow docs | Curate before final commit | Keep design/final notes; reduce intermediate noise if possible |
| Batch B peer business comparison | Defer | Important, but should not be added before slimming current diff |

## Suggested Commit Strategy

Do not commit this as one large “fix report quality” commit.

Recommended split:

1. `fix: tighten direct source relevance and renderer fallback`
   - source direct relevance
   - industry/news filtering
   - renderer fallback
   - related quality gates

2. `feat: add deterministic fundflow material pack`
   - `fundflow_material.py`
   - fundflow sidecar/quality integration
   - tests

3. `feat: add annual report explanation pack`
   - `periodic_report_explanation_pack.py`
   - intake/synthesis prompt integration
   - tests

4. `feat: preserve external viewpoint reasoning cards`
   - narrative schema
   - synthesis display bridge
   - renderer
   - tests

5. `test: add evidence-depth warning coverage`
   - warning-only quality checks
   - tests

6. `docs: record fudan pipeline quality audit`
   - only final design/notes needed for traceability

## Pre-Commit Slimming Checklist

- [ ] Decide whether to extract curated external display helpers out of `synthesis_skills.py` now or immediately after commit.
- [ ] Decide whether to split `report_quality.py` now or accept one more commit with a follow-up refactor task.
- [ ] Keep `reports/` out of commit; current `reports/复旦微电_20260702.md` was overwritten by a sandbox run with network/API failures and is not a valid review artifact.
- [ ] Avoid starting Batch B until current diff is split or slimmed.
- [ ] Re-run focused tests and gates after any slimming:
  - `python3 -m pytest ...`
  - `bash tools/ci_grep_gates.sh`
  - `git diff --check`

## Recommended Next Step

Before continuing feature work, do one of these:

Option A: Minimal-risk path

- Keep code as-is.
- Split into small commits.
- Create follow-up refactor ticket for `synthesis_skills.py`, `report_quality.py`, and `deep_analysis_renderer.py`.

Option B: Cleaner path

- First extract curated external display/card hydration from `SynthesisSkill`.
- Then split commits.
- Leave `report_quality.py` split for a later commit.

Option C: Aggressive cleanup

- Extract curated external display helper.
- Split `report_quality.py` rule families now.
- Then rerun full focused suite.

Recommendation: Option B. It reduces the worst hotspot without turning cleanup itself into another large refactor.

## Option B Execution Note

Status: `done`

Implemented after this audit:

- Added `scripts/utils/curated_external_display.py`
- Moved curated external narrative JSON reading, citation hydration, reasoning card normalization, source excerpt truncation, and paragraph flattening out of `SynthesisSkill`
- Kept `SynthesisSkill` as the ctx-level caller
- Kept legacy curated external digest path unchanged

Important nuance:

- This is a boundary cleanup, not a net line-count reduction.
- `curated_external_display.py` is about 250 lines, but it prevents `synthesis_skills.py` from continuing to absorb 4.4-specific display/citation policy.
- Next slimming target remains `report_quality.py`; do not split it until current functional diff is committed or otherwise stabilized.

Verification after extraction:

```text
python3 -m pytest tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py tests/utils/test_curated_external_viewpoint_narrative.py -q
# 134 passed

python3 -m pytest tests/utils/test_periodic_report_explanation_pack.py tests/reporter/test_periodic_report_fulltext_intake_skill.py tests/utils/test_curated_external_viewpoint_narrative.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_report_quality.py tests/utils/test_fundflow_material.py tests/reporter/test_technical_skills_contract.py tests/utils/test_source_adapter.py -q
# 238 passed

bash tools/ci_grep_gates.sh
# all gates passed

git diff --check
# clean
```

## Duplicate Helper Slimming Note

Status: `done`

After Option B, a second pass found two safe duplicate clusters and merged them:

1. Curated external text helpers

- Shared `attach_refs_to_sentence()` now handles citation de-duplication.
- `curated_external_viewpoint_narrative.py` reuses shared citation attachment and source-excerpt truncation.
- `DeepAnalysisRenderer` reuses shared citation attachment and source-excerpt truncation.
- Removed local duplicate helper methods/constants from renderer/narrative code.

2. Fund-flow normalization

- `fundflow_material.py` now exposes `normalize_fundflow_row()`.
- `SourceAdapter.FundFlowAdapter` reuses the same normalization instead of reparsing `main_inflow` / `main_in` / `super_net_in` / `large_net_in` / `small_net_in` / `change_pct` itself.
- Legacy `main_inflow - main_outflow` and Baidu PAE `main_in` fields are both covered by tests.

Verification after duplicate merge:

```text
python3 -m pytest tests/utils/test_curated_external_viewpoint_narrative.py tests/reporter/test_deep_analysis_renderer.py tests/reporter/test_synthesis_skills.py tests/utils/test_source_adapter.py tests/utils/test_fundflow_material.py -q
# 149 passed

python3 -m pytest tests/utils/test_periodic_report_explanation_pack.py tests/reporter/test_periodic_report_fulltext_intake_skill.py tests/utils/test_curated_external_viewpoint_narrative.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_report_quality.py tests/utils/test_fundflow_material.py tests/reporter/test_technical_skills_contract.py tests/utils/test_source_adapter.py -q
# 238 passed

bash tools/ci_grep_gates.sh
# all gates passed

git diff --check
# clean
```
