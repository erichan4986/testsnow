# Report Run Plan Deduplication Implementation Notes

## Result

Implementation completed in the current worktree. The report runtime now compiles
Agent-Reach and Source Intake options once per stock, and the legacy monitor owns
batch iteration. The hard-coded `xueqiu_summary_*.md` path is gone.

## Files changed for this task

- Added `scripts/utils/report_run_plan.py`.
- Modified `scripts/utils/stock_reporter.py`.
- Modified `scripts/xueqiu_monitor_v2.py`.
- Added `tests/reporter/test_report_run_plan.py`.
- Added `tests/reporter/test_stock_reporter_run_plan.py`.
- Added `tests/reporter/test_xueqiu_monitor_report_batch.py`.
- Deleted `tests/reporter/test_stock_reporter_agent_reach_config.py`.
- Deleted `tests/reporter/test_stock_reporter_source_intake_config.py`.

Other dirty files shown by `git status` predated this task or belong to the
earlier runtime/test dedup and Chapter 2 work; they were preserved.

## TDD / test results

### Batch A: compiler

- RED: `ModuleNotFoundError: No module named 'utils.report_run_plan'`.
- GREEN: `23 passed`.
- Coverage includes global/per-stock gates, nested fulltext precedence, display
  parent gates, relative/absolute pack paths, URL alias precedence, evidence
  payload precedence, claim verification precedence, malformed nested config,
  and production canonical-pack/config assertions.

### Batch B: facade

- RED: patch target `utils.stock_reporter.compile_report_run_plan` was absent.
- GREEN: compiler + facade focused tests passed (`27 passed`); existing
  configuration, pipeline and chart tests passed (`73 passed`) before removal
  of the superseded configuration modules.
- The facade now builds invariant input once, updates it with the compiled
  context, and passes the compiled pipeline kwargs unchanged.

### Batch C: batch ownership

- RED: `xueqiu_monitor_v2._generate_deep_reports` was absent.
- GREEN: batch helper test passed (`1 passed`). It verifies source order, one
  `generate_stock_report` call per stock, path accumulation, and no summary
  output. The legacy monitor keeps its existing constructor inputs and does not
  newly enable Source Intake.

### Acceptance narrow fixes

- Added a RED/GREEN regression for explicit `pack_json: null`, `0`, and empty
  string values. Non-path values now stay empty instead of becoming repository
  paths such as `/repo/None`.
- Restored the Fudan Source Intake, `formal_first`, A-stock, iWencai, and
  periodic-fulltext production assertions.
- Restored the canonical external-config single-key assertion.
- Added direct Agent-Reach evidence-parent and claim-verification contracts.
- Expanded the compiler's long expressions; it has no line over 119 characters.

### Final verification

- Focused compiler/facade/batch/pipeline/chart suite: `68 passed`.
- Full suite: `2805 passed, 10 skipped in 51.70s`.
- `bash tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.
- `python3 scripts/run_黑芝麻智能.py --offline-smoke`: exit `0`; outputs were
  confined to `/tmp/testsnow_offline_smoke`.
- No formal report was generated and no network, Chrome/CDP, Xueqiu detail
  page, LLM refresh, or report/data/knowledge mutation was performed.

## Legacy configuration test mapping

| Removed test | New owner |
|---|---|
| `test_default_reporter_does_not_enable_claim_risk_signals` | `test_compile_report_run_plan_core_gates` |
| `test_claim_risk_signals_enabled_passes_through` | `test_claim_precedence_and_risk_signal_independence` |
| `test_claim_risk_signals_independent_of_claim_verification_enabled` | `test_claim_precedence_and_risk_signal_independence` |
| `test_other_stocks_unaffected_by_claim_risk_signals_config` | `test_compile_report_run_plan_core_gates` |
| `test_per_stock_claim_verification_enabled_without_agent_reach` | `test_agent_claim_verification_does_not_require_active_agent_source` |
| `test_claim_verification_and_risk_signals_enable_independent_flags` | `test_claim_precedence_and_risk_signal_independence` plus `test_agent_claim_verification_does_not_require_active_agent_source` |
| `test_per_stock_claim_verification_disabled_does_not_pass` | `test_claim_precedence_and_risk_signal_independence` |
| `test_per_stock_agent_reach_official_domains_passed` | `test_agent_reach_context_preserves_urls_alias_and_optional_lists` |
| `test_default_reporter_does_not_enable_agent_reach` | `test_compile_report_run_plan_core_gates` |
| `test_per_stock_config_enables_agent_reach_and_passes_url` | `test_agent_reach_context_preserves_urls_alias_and_optional_lists` |
| `test_disabled_per_stock_config_does_not_enable_agent_reach` | `test_compile_report_run_plan_core_gates` |
| `test_global_enable_overrides_per_stock` | `test_compile_report_run_plan_core_gates` |
| `test_rss_config_mapping_when_enabled` | `test_agent_reach_context_preserves_urls_alias_and_optional_lists` |
| `test_urls_alias_backward_compatible` | `test_agent_reach_context_preserves_urls_alias_and_optional_lists` |
| `test_no_evidence_notes_config_does_not_enable_evidence_notes` | `test_compile_report_run_plan_core_gates` |
| `test_evidence_notes_enabled_with_agent_reach` | `test_agent_evidence_notes_require_active_agent_parent` |
| `test_evidence_notes_dry_run_and_base_dir_passed` | `test_agent_evidence_notes_require_active_agent_parent` |
| `test_evidence_notes_enabled_without_agent_reach_does_not_enable` | `test_agent_evidence_notes_require_active_agent_parent` |
| `test_default_reporter_does_not_enable_source_intake` | `test_compile_report_run_plan_core_gates` |
| `test_source_intake_enabled_passes_flag` | `test_compile_report_run_plan_core_gates` |
| `test_source_intake_formal_first_policy_passes_context_and_pipeline_kwarg` | `test_only_formal_first_policy_is_emitted` |
| `test_stock_config_passes_to_pipeline_input` | `test_reporter_forwards_one_compiled_plan_to_builder_and_context` |
| `test_pilot_stocks_enable_formal_first_source_policy_in_config` | `test_production_pilot_configs_use_formal_first_source_policy` |
| `test_annual_review_stocks_enable_local_fulltext_intake` | `test_production_annual_review_configs_enable_annual_fulltext` |
| `test_zhongji_config_enables_broker_digest_display` | `test_production_zhongji_config_enables_broker_digest_display` |
| `test_fudan_microelectronics_config_present_and_wired` | `test_production_fudan_config_keeps_direct_relevance_fields` plus `test_production_annual_review_configs_enable_annual_fulltext` |
| `test_pilot_stocks_have_direct_relevance_config` | `test_production_peer_and_product_exposure_fields_are_present` |
| `test_source_intake_enabled_allows_empty_community_posts` | `test_reporter_runs_empty_posts_when_plan_has_active_source` |
| `test_source_intake_periodic_fulltext_enabled_passes_pipeline_flag` | `test_periodic_fulltext_nested_value_overrides_global` plus `test_fulltext_cache_and_report_type_emit_only_when_enabled` |
| `test_global_periodic_fulltext_flag_enables_source_intake_fulltext` | `test_periodic_fulltext_nested_value_overrides_global` |
| `test_periodic_fulltext_stock_config_can_disable_global_flag` | `test_periodic_fulltext_nested_value_overrides_global` |
| `test_periodic_narrative_cards_display_default_off` | `test_compile_report_run_plan_core_gates` |
| `test_source_intake_periodic_narrative_cards_display_enabled_passes_context` | `test_child_displays_require_active_source_intake_and_keep_limits` |
| `test_periodic_narrative_cards_display_requires_source_intake_enabled` | `test_disabled_source_parent_suppresses_all_child_displays` |
| `test_source_intake_evidence_notes_enabled_without_agent_reach` | `test_source_intake_evidence_payload_is_used_without_agent_block` |
| `test_source_intake_config_separate_from_agent_reach` | `test_compile_report_run_plan_core_gates` |
| `test_source_intake_disabled_per_stock` | `test_compile_report_run_plan_core_gates` |
| `test_source_intake_with_dry_run_false` | `test_source_intake_evidence_payload_is_used_without_agent_block` |
| `test_source_intake_claim_verification_enabled_passes_context` | `test_source_claim_config_is_fallback_when_agent_claim_block_is_empty` |
| `test_broker_research_digest_display_default_off` | `test_compile_report_run_plan_core_gates` |
| `test_source_intake_broker_research_digest_display_enabled_passes_context` | `test_child_displays_require_active_source_intake_and_keep_limits` |
| `test_broker_research_digest_display_requires_source_intake_enabled` | `test_disabled_source_parent_suppresses_all_child_displays` |
| `test_source_intake_curated_external_display_default_off` | `test_compile_report_run_plan_core_gates` |
| `test_source_intake_curated_external_argument_pack_enabled_passes_context` | `test_child_displays_require_active_source_intake_and_keep_limits` plus `test_absolute_pack_path_is_not_rebased` |
| `test_production_external_configs_use_only_readable_canonical_v4_packs` | `test_production_external_configs_point_to_readable_canonical_v4_packs` |

## Ownership and dead-path audit

- `compile_report_run_plan` is the only compiler owner and is called once by
  `PerStockReporter.generate_stock_report`.
- `build_stock_report_pipeline(**plan.pipeline_kwargs)` remains unchanged in
  skill ordering and is still covered by the existing integration tests.
- Batch iteration is owned by `xueqiu_monitor_v2._generate_deep_reports`.
- `PerStockReporter.generate_all_reports`, `_generate_summary_report`, the
  module CLI, `data_path`, and the old summary filename have been removed.
- Runtime search finds no active references to the removed methods or
  constructor argument. The only `xueqiu_summary_` match is the negative test
  assertion.

## Line accounting

Post-clean totals:

- Runtime: `67,052` lines, versus the locked pre-task baseline `67,156`;
  net `-104`, under the `67,056` target.
- Tests: `62,300` lines, versus the locked pre-task baseline `63,045`;
  net `-745`, under the `62,645` target.

The reduction comes from deleting duplicated reporter configuration plumbing,
the legacy summary/batch/CLI code, and two 1,327-line configuration test
modules. Their active configuration contracts were moved to the compiler matrix
and facade/batch tests before deletion.

## Scope audit

- No changes to scoring, target price, risk, technical algorithms, citation
  generation, report structure, synthesis prompts, source collection, or
  pipeline skill order.
- No unrelated dirty-worktree changes were reverted or formatted.
- No blocker remains.

## Warning / deviation

- The worktree remains dirty because it contains pre-existing and earlier-task
  changes. No commit was made.
- The compiler intentionally preserves the existing unusual evidence payload
  precedence and claim-verification fallback semantics, even where they are
  not the most intuitive configuration design.
