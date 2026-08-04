# Technical Analysis v2 Phase 2 Codex Notes

## Result

- Status: code implementation accepted.
- Claude review: explicitly waived by the user after three Codex self-review rounds.
- Task-start HEAD: `cb35b7b`.
- Formal reports: not generated in this code-only batch.

## Modified Runtime

- `scripts/utils/reporter/technical_state_machine.py`
  - adds deterministic `interpretation` projection to `technical_judgment.v1`;
  - validates producer status/reason pairs and additive interpretation shapes;
  - separates primary evidence, counter-evidence, confirmation/invalidation conditions, market context,
    priority observation, localized target message, and stage change;
  - upgrades core-only caches only when explicit structural inputs exist.
- `scripts/utils/reporter/sections/technical_renderer.py`
  - uses one shared judgment projection for compact/full modes;
  - removes `_build_conclusion`, `_pick_priority_signal`, insertion-based full assembly, raw reason codes,
    raw extrema diagnostics, unavailable market placeholders, and the independent sell recommendation;
  - keeps local structure/channel diagnostics explicitly labeled as auxiliary.

## TDD Evidence

- State-machine RED: 5 failed, 28 passed. Failures were missing interpretation, trusted target
  status/reason mismatch, and missing cache upgrade validation.
- State-machine GREEN: 33 passed.
- Renderer RED: 6 failed, 10 passed. Failures were old conclusion/ranking paths, unavailable market
  placeholder, raw reason wording, legacy core-cache routing, and duplicated judgment semantics.
- Renderer GREEN: 16 passed.
- Final self-review RED: 3 failed for invalid-trend target wording, malformed evidence-item acceptance,
  and removed auxiliary structure coverage; then GREEN: 3 passed.
- Independent sell recommendation RED: 1 failed; renderer block removed.
- Formal-report follow-up narrow-fix RED: 2 failed for an already-triggered condition rendered as a future
  invalidation and for raw `上升趋势结构健康` prose leaking into the bearish auxiliary block.
- Final focused after the narrow fix: 52 passed.

## Verification

- Downstream recommendation/dashboard/report-quality/technical-skill/scoring contracts: 151 passed.
- Non-network technical suite: 173 passed.
- Full suite after the final code change: 2493 passed, 16 skipped in 37.20s.
- `bash tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.
- Symbol/text audit: no `_build_conclusion`, `_pick_priority_signal`, `list.insert`, raw extrema prose,
  raw target reason-code prose, or independent sell recommendation remains in the advanced renderer.

## Runtime Budget

Relative to `cb35b7b`:

| Runtime file | Added | Removed | Net |
| --- | ---: | ---: | ---: |
| `technical_state_machine.py` | 222 | 3 | +219 |
| `technical_renderer.py` | 125 | 394 | -269 |
| Combined | 347 | 397 | -50 |

The combined result is net-negative and does not approach the `+120` hard stop.

## Scope Audit

- Runtime changes are limited to the two locked files.
- Test changes are limited to the three locked files.
- No indicator, target-price formula, score, risk, recommendation, collector, config, Chapter 4, citation,
  LLM prompt, data, knowledge, or report file was changed by this task.
- The pre-existing modification to
  `docs/agent_workflow/2026-07-15-knowledge-persistence-slimming-6a2-codex-notes.md` remains untouched.

## Blocker / Warning / Deviation

- Blocker: none.
- Warning: Chapter 4 prose checks retain pre-existing `long_sentence`, `theme_reexpanded_outside_owner`,
  `strong_assertion_wording`, and Zhongji-only `repeated_theme_across_sections` warnings. They are outside
  the Phase 2 technical scope.
- Deviation: Claude review was skipped by explicit user authorization; all locked code/test/runtime gates
  were retained.

## Formal Report Acceptance

- Fresh reports generated after the final narrow fix:
  - `reports/中际旭创_20260718.md`
  - `reports/复旦微电_20260718.md`
- Both reports passed `check_report_quality.py` and `check_report_source_boundary.py`; prose checks passed
  with only the pre-existing Chapter 4 warnings listed above.
- Both reports render the broken regime as `已触发的破坏条件`, keep the complete hard condition separate
  from primary evidence, and show no raw `上升趋势结构健康` auxiliary wording.
- Technical action, 0-5% position cap, risk level, executive summary, and final recommendation remain
  consistent. Citation alignment remains complete with no missing or unused references.
- Formal-report verdict: PASS. Technical Analysis Phase 2 is ready for branch integration.
