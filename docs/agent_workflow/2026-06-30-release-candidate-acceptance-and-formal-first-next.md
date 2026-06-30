# Release Candidate Acceptance And Formal-First Next Step

Date: 2026-06-30

Branch: `codex-report-quality-upgrade`

## 1. Scope

This release-candidate pass closes the current report-quality line before
starting the next `formal_first` source-boundary work.

Included in this RC:

- curated external flat `4.4` narrative rendering;
- curated external display-only isolation gates;
- social viewpoint digest preview utility, still `/tmp` preview-only;
- scripts layout cleanup / archive / high-risk grouping;
- source-boundary design notes and Claude review record.

Not included in this RC:

- making `formal_first` the default source policy;
- running social viewpoint extraction inside ordinary report runtime;
- changing scoring, technical analysis, risk scoring, EV, target price, or
  final recommendation logic;
- live LLM benchmark reruns or report regeneration during this RC check.

## 2. Verification Run

Focused pytest suite:

```text
python3 -m pytest \
  tests/utils/test_curated_external_display_lint.py \
  tests/utils/test_curated_external_viewpoint_narrative.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_stock_reporter_source_intake_config.py \
  tests/reporter/test_synthesis_skills.py \
  tests/reporter/test_social_viewpoint_digest_preview.py \
  tests/utils/test_social_viewpoint_source_packets.py \
  tests/reporter/test_curated_external_full_body_viewpoint_preview.py \
  tests/utils/test_curated_external_full_body_viewpoint_claims.py \
  tests/test_scripts_layout.py \
  tests/utils/test_extract_detail_cli.py \
  tests/reporter/test_broker_research_digest_preview.py \
  tests/reporter/test_curated_external_viewpoint_narrative_preview.py \
  tests/reporter/test_periodic_report_fulltext_preview_script.py \
  tests/reporter/test_periodic_report_narrative_cards_preview_script.py \
  tests/reporter/test_periodic_report_narrative_cards_acceptance_script.py \
  tests/reporter/test_wechat_candidate_selector_preview.py \
  tests/reporter/test_wechat_targeted_discovery_preview.py \
  tests/reporter/test_iwencai_industry_research_preview.py \
  tests/test_pytest_marker_contract.py -q
```

Result:

```text
257 passed in 6.33s
```

Compile check:

```text
python3 -m compileall scripts/previews scripts/smoke scripts/high_risk \
  scripts/archive scripts/utils/curated_external_display_lint.py \
  scripts/utils/curated_external_full_body_viewpoint_claims.py \
  scripts/utils/curated_external_viewpoint_narrative.py \
  scripts/utils/social_viewpoint_source_packets.py \
  scripts/utils/report_skills \
  scripts/utils/reporter/sections/deep_analysis_renderer.py \
  scripts/utils/stock_reporter.py scripts/run_stock_report.py
```

Result: exit code 0.

CI grep gates:

```text
bash tools/ci_grep_gates.sh
```

Result:

```text
[gate a] ok
[gate c] ok
[gate b] ok
ci_grep_gates: all gates passed
```

Diff hygiene:

```text
git diff --check
```

Result: clean.

Git status before writing this note: clean.

## 3. Acceptance Decision

Status: `rc_accepted_for_current_scope`.

Reason:

- flat `4.4` narrative rendering is implemented and covered by renderer tests;
- claim-ref repair, model-token guard, quantity guard, and per-paragraph
  overclaim drop are covered by narrative tests;
- curated external display-only isolation still passes `gate c`;
- social viewpoint extraction remains preview-only and does not connect to the
  report runtime;
- scripts layout cleanup has focused tests for moved preview / smoke /
  high-risk entrypoints;
- no LLM/API/report-generation cost was incurred during this RC check.

## 4. Known Residual Risks

- Full `tests/reporter -q` is still too broad / slow and previously reached
  historical TDX parser paths.  Keep using focused suites until legacy test
  taxonomy is fully cleaned.
- 中际旭创 still has a known quality warning:
  `contradiction_blocked_entry_strong_recommendation`.  This is a scoring /
  recommendation consistency issue, not a curated external issue.
- `formal_first` is opt-in only.  It must not become default until low-formal
  coverage stocks are tested.
- Social / Xueqiu / Zhihu viewpoint extraction is not a live report-runtime
  path.  It should stay as cached-preview infrastructure until stability is
  proven.

## 5. Next Work: Formal-First Preview

Recommended next phase: `formal_first_preview`.

Goal:

Verify whether `4.1-4.3` can rely mainly on formal / medium-high-credit
sources while social and external viewpoints stay in `4.4`.

Initial constraints:

- Do not make `formal_first` default.
- Enable only by per-stock opt-in config or direct test context.
- Do not let LLM synthesis see raw social text when writing `4.1-4.3`.
- Do not change scoring, technical analysis, risk scoring, target price, or
  final recommendation logic.
- Do not run Xueqiu detail scraping or logged-in Chrome/CDP.

Suggested first tests:

1. Unit-test source policy classification:
   announcements / reports / broker research kept; Xueqiu / Zhihu / WeChat
   excluded from canonical synthesis under `formal_first`.
2. Add a degradation contract:
   when formal items are insufficient, `4.1-4.3` should show a clear formal
   source insufficiency note rather than silently reverting to social-only
   synthesis.
3. Run no-LLM fixture tests for:
   - 中际旭创: enough formal material;
   - 圣邦股份: enough formal material and no `4.4`;
   - 黑芝麻智能: likely lower formal coverage, requiring graceful behavior.

Stop conditions:

- formal-first would require changing scoring / recommendation logic;
- HK stock coverage requires a new data source rather than source filtering;
- report quality drops to template-only `4.1-4.3` without a clear degradation
  message.
