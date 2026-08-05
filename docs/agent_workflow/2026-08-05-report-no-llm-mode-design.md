# Report `--no-llm` Mode Design

## Goal

Add an explicit report-run flag that disables every LLM request owned by the
single-stock report pipeline while preserving local materials, market data,
technical analysis, charts, and normal report output.

Recommended engineering invocation:

```bash
python3 scripts/run_stock_report.py --stock <name> --fast-test --no-llm --no-pdf
```

This is separate from `--offline-smoke`, which also disables market data,
technical collection, charts, PDF output, and writes to temporary directories.

## Current Behavior And Root Cause

`--fast-test` currently skips network Zhihu collection and ZhihuCurator only.
It intentionally continues through the normal report pipeline. With API keys in
the environment, six report-owned paths may initialize or call an LLM:

1. non-fast Zhihu collection through `ContentQualityGate` and ZhihuCurator;
2. pipeline `ContentQualityGate` second-stage post assessment;
3. `ContentConsolidator` topic extraction;
4. `SynthesisSkill` / `KnowledgeSynthesizer` baseline and display synthesis;
5. the legacy executive-summary thesis extractor when no view model is present.
6. the HTML Dashboard thesis cards, which call the same extractor directly.

The acceptance run observed 46 successful DeepSeek requests because the CLI
had no context-level way to disable those owners. This is not an H1/H2 defect;
it is an ambiguous engineering-run contract.

## CLI Contract

- `--fast-test`: unchanged; skips Zhihu collection/curator and reuses local
  cached inputs, but may use the normal synthesis LLM.
- `--no-llm`: disables report-pipeline LLM requests only. It does not imply
  `--fast-test`, `--no-pdf`, or offline market-data behavior.
- `--offline-smoke`: behavior unchanged. It explicitly sets `no_llm=True` in
  addition to its existing implied `--fast-test` / `--no-pdf` flags and broader
  offline patches, so diagnostics describe its actual contract.
- API-key environment variables must not be deleted or mutated by
  `--no-llm`; the policy is carried explicitly in report context.

## Data Flow And Ownership

The flag has one propagation path:

```text
run_stock_report --no-llm
  -> ZhihuCollector(..., use_curator=False) when collection is requested
  -> PerStockReporter(report_llm_enabled=False)
  -> pipeline input: report_llm_enabled=False
  -> each report-owned LLM boundary chooses its deterministic fallback
```

`report_llm_enabled` defaults to `True`, preserving all production and existing
callers.

Entry helpers that are directly exercised with lightweight test namespaces read
the new option through `getattr(args, "no_llm", False)`. Adding the flag must not
break old direct helper callers that do not yet carry the parsed attribute.

### Zhihu intake

`--fast-test` continues to skip Zhihu collection. On a normal run with only
`--no-llm`, the collector may still perform its existing Zhihu API searches,
but it receives `use_curator=False`. That existing branch uses deterministic
keyword classification and bypasses both ContentQualityGate LLM assessment and
ZhihuCurator. Network collection and its request limits are otherwise unchanged.
This is the only Zhihu behavior changed by explicitly selecting `--no-llm`.

### Quality gate

`quality_gate_skill` passes the policy into
`ContentQualityGate.process_xueqiu_posts(..., use_llm=...)`. The existing
rule-based assessment remains the fallback. The wrapper gains only the optional
argument needed to forward the existing `process(..., use_llm=...)` contract.

### Cross-source consolidation

`cross_source_consolidation_skill` constructs
`ContentConsolidator(use_llm_topics=...)`. The existing keyword topic extractor
remains the fallback. No clustering or similarity rule changes.

### Synthesis

When `report_llm_enabled` is false, `SynthesisSkill._synthesize` must not:

- call an injected legacy LLM client;
- instantiate an environment-backed `KnowledgeSynthesizer`;
- call baseline or display synthesis LLMs.

It still builds canonical `SynthesisItem` inputs and returns the existing
deterministic `_template_synthesize` envelope with item/source diagnostics.
Formal annual, broker, and curated external Chapter 4 projections continue to
come from their canonical packs and `MaterialSnapshot`; they are not discarded.

### Executive-summary fallback

The view-model path remains unchanged. The legacy fallback passes the context
policy into thesis extraction. With LLM disabled it enters the existing
heuristic bullish/bearish extraction directly instead of calling
`_llm_extract_thesis` and relying on an exception.

The HTML Dashboard uses the same helper and must pass the same context policy.
It is a separate renderer call site even though it shares the request owner.

The optional periodic-report fulltext intake skill is not another owner: its
active pipeline call already omits `enable_llm` and `llm_client`, and the skill
documents and tests its deterministic no-LLM path. H2 does not change it.

### Explicitly out of scope

- No prompt edits.
- No change to `--fast-test` semantics.
- No changes to scoring, recommendation, risk, technical algorithms, market
  providers, external producer CLIs, or canonical packs.
- No annual OCR or `Timestamp` chart fix in this batch.
- No changes to Xueqiu/Chrome/CDP behavior or Zhihu network request limits.

## Failure Modes And Tests

| Failure mode | Observable result | Required test |
|---|---|---|
| CLI flag is not propagated | DeepSeek requests still occur | entry test asserts reporter receives `report_llm_enabled=False` |
| default behavior changes | production callers unexpectedly lose synthesis | default-constructor and no-flag tests assert `True` |
| non-fast intake still invokes curator | `--no-llm` makes Zhihu LLM calls before the pipeline | collector spy asserts `use_curator=False` |
| quality gate ignores policy | post assessment calls LLM | strict assessor spy with context false |
| consolidator ignores policy | topic extraction calls LLM | strict consolidator spy asserts `use_llm_topics=False` |
| synthesis constructs/calls LLM | baseline/display calls remain | strict injected client/synthesizer spies must remain unused |
| executive fallback calls LLM | one or two hidden calls remain | fallback renderer test patches `_llm_extract_thesis` to fail |
| HTML Dashboard uses the helper default | two hidden requests remain after Markdown assembly | dashboard test patches `_llm_extract_thesis` to fail |
| no-LLM accidentally becomes offline | market/technical/chart behavior disappears | entry test asserts offline patches are not installed and fast/no-pdf are not implied |
| offline smoke reports an inconsistent policy | diagnostics say LLM enabled despite broad patches | offline-smoke test asserts `no_llm=True` |
| API keys are mutated | later production run loses credentials | environment-preservation test |
| Chapter 4 loses canonical material | annual/broker/external sections thin out | focused H1/H2 snapshot and renderer suites remain green |

Entry propagation and each owner must have strict request no-call tests. Client
object construction alone is not an LLM request, but no `.chat`,
`chat.completions.create`, or equivalent request boundary may execute. A local
acceptance harness may additionally install request spies across all six owners
before running `--fast-test --no-llm --no-pdf`; it must not make a real LLM
request. The non-fast collector contract is verified separately without making
network requests.

## Scope And Budget

Allowed runtime files:

- `scripts/run_stock_report.py`
- `scripts/utils/stock_reporter.py`
- `scripts/utils/content_quality_gate.py`
- `scripts/utils/report_skills/data_skills.py`
- `scripts/utils/report_skills/analysis_skills.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/reporter/sections/executive_summary_renderer.py`
- `scripts/utils/reporter/sections/html_dashboard_renderer.py`

Allowed tests are the directly corresponding reporter/unit test files. Workflow
notes may be added under `docs/agent_workflow/`.

Expected focused test owners:

- `tests/reporter/test_run_stock_report_entry.py`
- `tests/reporter/test_stock_reporter_run_plan.py`
- `tests/reporter/test_data_skills.py`
- `tests/reporter/test_analysis_skills.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_executive_summary_renderer.py`
- `tests/reporter/test_html_dashboard_renderer.py`
- existing H1/H2 snapshot and renderer suites

Runtime target: net `+40` lines. Hard stop: net `+80` lines. Prefer forwarding
one boolean through existing constructors/functions; do not add a policy class,
registry, environment mutation layer, or second report pipeline.

## Verification

1. TDD CLI/intake and owner tests, RED before GREEN.
2. Focused entry, reporter, quality, consolidation, synthesis, executive-summary,
   H1/H2 snapshot, and renderer tests.
3. Full `pytest`.
4. `bash tools/ci_grep_gates.sh`.
5. `git diff --check`.
6. Local acceptance with an API key present and strict request accounting:
   `--fast-test --no-llm --no-pdf` must produce zero LLM requests while retaining
   market/technical execution. Do not use a live request merely to prove zero.

## Design Self-Review Delta

Accepted and incorporated:

- added non-fast Zhihu quality/curator as the fifth owner;
- made `offline-smoke` explicitly carry the no-LLM policy without changing its
  broader behavior;
- preserved direct-helper compatibility through `getattr` defaults;
- distinguished zero requests from harmless SDK client construction;
- confirmed periodic fulltext intake is already deterministic and outside the
  required runtime edits.

Rejected:

- redefining `--fast-test` as no-LLM, because it would silently change an
  established report-quality workflow;
- reusing process-wide environment deletion or offline monkeypatches, because
  that would make a composable report option disable unrelated capabilities;
- adding a policy class or second pipeline for one boolean.

Remaining ambiguity: none. Round 1 read-only review is still required because
the change crosses the report entry, pipeline, synthesis, and renderer boundary.

## Stop Conditions

Stop and return to design if:

- any report-owned LLM request remains without expanding the allowed runtime
  scope;
- disabling LLM requires modifying prompts or canonical pack generation;
- deterministic fallback changes scoring, technical, risk, target, or
  recommendation behavior;
- runtime net growth exceeds `+80` lines;
- unrelated dirty-worktree changes would need to be reverted or overwritten.
