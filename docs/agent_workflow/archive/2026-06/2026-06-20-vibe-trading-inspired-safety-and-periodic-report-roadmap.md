# Vibe-Trading-Inspired Safety And Periodic Report Roadmap

Date: 2026-06-20

## Context

This note records the agreed improvement plan after reviewing HKUDS/Vibe-Trading and the workflow-style suggestions around vibe-coding/agentic engineering.

The key takeaway is not to copy a full multi-agent trading platform. testsnow is a batch-oriented A/HK stock report generator, so the useful parts are:

- lightweight invariant guardrails;
- clearer workflow/runbook documentation;
- structured periodic-report facts and risk signals;
- eventually, a safer data-source registry and throttle model.

The near-term goal is to protect the recently implemented periodic-report fulltext material-layer path without adding more runtime artifacts or making future LLM/code review context harder to navigate.

## Current Fulltext Rule

Periodic report fulltext summaries are currently treated as high-quality material, not as auto-confirmed facts.

The fulltext summary item may support final report synthesis/display, but must not directly enter:

- core facts;
- Knowledge persistence;
- scoring;
- risk scoring;
- `confirmed_fact` / `fact_candidate`.

Reason: the annual-report source is high credibility, but the current fulltext item is a mixed LLM/rule-derived summary containing facts, derived metrics, backfills, and analysis judgments. It should not be persisted or scored as one undifferentiated fact object.

Future work should split annual-report content into structured fact layers before Knowledge/scoring use.

## Bucket 1: Safety Invariant Guardrails

Status: recommended next implementation bucket.

Purpose: add low-cost guardrails around the existing fulltext isolation design. This bucket should not change runtime behavior.

### Scope

Add:

- `tools/ci_grep_gates.sh`
- `tests/reporter/test_fulltext_material_isolation.py`
- `tests/tools/test_ci_grep_gates.py` or `tests/utils/test_ci_grep_gates.py`

### CI Grep Gate Requirements

The script should fail on obvious invariant violations:

- `periodic_report_fulltext` or `synthesis_display` appears in scoring, risk-rendering, or Knowledge-persistence files.
- `requests.get(...)` in source code lacks an explicit `timeout`; prefer a small AST-based check so multi-line calls are handled correctly.
- unsafe `yaml.load(` appears without `safe_load`.
- obvious secret literals appear in source code, e.g. `api_key="sk-..."`, `token="..."`, `password="..."`.

Do not scan docs for token/key words; docs contain legitimate design discussion and would create noise.

The gate must be deliberately narrow:

- Use a precise denylist for fulltext/display leakage checks, e.g. `scoring_engine.py`, `risk_renderer.py`, and `knowledge_skills.py`.
- Do not globally ban `synthesis_display`; display renderers are supposed to read it.
- Do not try to prove semantic invariants with grep. In particular, avoid a fragile text rule for "synthesis_text assigned from display/enhanced narrative"; keep that invariant in pytest.
- Add allowlists/exclusions for `tools/ci_grep_gates.sh` and the gate's own tests so secret-pattern examples do not make the gate flag itself.

### CI Grep Gate Test Requirements

`test_ci_grep_gates.py` must test both directions:

- the real repository passes the gate;
- a temporary fake file containing a known violation fails the gate.

Minimum negative fixtures:

- fake scoring/risk/Knowledge file containing `periodic_report_fulltext`;
- fake file with `requests.get(...)` missing `timeout`;
- fake file with unsafe `yaml.load(`;
- fake source file with an obvious secret literal.

The pytest test should run the script through `subprocess`, so the gate is executed as part of normal test runs without requiring separate CI wiring.

Also add a positive fixture or assertion showing display renderers may still use `synthesis_display`; this prevents future over-broad grep rules from breaking the legal display path.

### Invariant Test Requirements

The test file should be a readable red-line entrypoint, not a wholesale rewrite of existing tests. It should make the core invariants easy to find:

- canonical `ctx["synthesis"]` remains baseline;
- `ctx["synthesis_text"]` remains baseline and is what risk keyword scanning sees;
- Knowledge persistence would receive baseline synthesis, not fulltext-enhanced display synthesis;
- display renderers may use `ctx["synthesis_display"]` while canonical/Knowledge/scoring paths stay baseline.

Existing tests already cover parts of this behavior. This new file should consolidate or lightly wrap those assertions so maintainers have one obvious place to look.

Forward-compatibility requirement:

- The test must anchor its prohibition to the material-layer source type `periodic_report_fulltext_analysis`.
- It must not assert that all future annual-report content is barred from Knowledge/scoring.
- Bucket 3 will introduce a separate structured fact path; tests should allow that future `filing_facts` / `derived_facts` source types may enter Knowledge/scoring through explicit structured channels.

### Explicit Non-Scope

Do not add:

- report run cards;
- trace JSONL;
- manifest files;
- new runtime output artifacts;
- report rendering changes;
- Knowledge/scoring/risk logic changes;
- data-source registry or throttling changes.

### Redaction Decision

Do not implement `scripts/utils/redaction.py` in Bucket 1.

Reason: Bucket 1 intentionally creates no new runtime artifacts. A redaction helper is useful only when notes/manifest/audit output is introduced. Implement it later alongside the first output path that needs it.

## Bucket 2: Workflow Hygiene

Status: documentation-only bucket after Bucket 1.

Purpose: reduce "conversation as state" without creating a large new framework.

Recommended files:

- `docs/agent_workflow/context_index.md`
- `docs/agent_workflow/runbooks/run_local_report_validation.md`
- `docs/agent_workflow/runbooks/add_periodic_report_metric.md`
- `docs/agent_workflow/runbooks/review_generated_report_quality.md`

`context_index.md` should answer:

- current mainline;
- core entry files;
- files/modules not to touch casually;
- periodic-report fulltext current status;
- common validation commands;
- where to look for active design/status docs.

Runbooks should stay short and operational. Do not introduce a second workflow framework; AGENTS.md and `docs/agent_workflow/README.md` remain authoritative.

Drift guard:

- Add a small path-existence test for `context_index.md`.
- The test should parse documented local file paths and assert they still exist, similar in spirit to Vibe-Trading's guide-path tests.
- Keep it lightweight; the goal is to prevent the index from becoming a stale map.

## Bucket 3: Periodic Report Fact Extractor Design

Status: design-review bucket.

Purpose: annual-report content should eventually become a high-credit structured fact source, not just a display material item.

Important distinction:

- the current fulltext summary item should not be persisted/scored wholesale;
- structured annual-report facts derived from exact evidence can be persisted and scored.

### Proposed Output Layers

`periodic_report_fact_extractor` should produce three distinct layers.

#### 1. `filing_facts`

Original, verifiable facts from the report.

Examples:

- revenue;
- net profit;
- non-GAAP/deducted net profit where applicable;
- operating cash flow;
- gross margin;
- segment revenue/gross margin;
- production/sales/inventory;
- customer/supplier concentration;
- R&D expense and R&D ratio;
- audit opinion;
- key audit matters;
- unprofitable/listed-while-unprofitable status.

Policy:

- may enter Knowledge;
- may support high-credit factual context;
- must bind to source evidence or deterministic required-metrics extraction.
- must distinguish as-reported values from restated/retrospectively adjusted values when the report discloses both.

#### 2. `derived_facts`

Computed facts derived from extracted report values.

Examples:

- operating cash flow / net profit;
- receivables / revenue;
- inventory growth vs revenue growth;
- R&D expense / revenue;
- top customer concentration deltas;
- capex / cash.

Policy:

- may enter Knowledge if calculation inputs are preserved;
- must be marked as `derived`;
- should not masquerade as company-stated text.
- must include `schema_version` and `input_refs` pointing back to the source `filing_facts`.
- should be recomputable or invalidatable when extractor/calculation logic changes.

#### 3. `filing_risk_signals`

Typed signals derived from facts and report disclosures.

Examples:

- `customer_concentration_high`;
- `supplier_concentration_high`;
- `inventory_pressure`;
- `cashflow_quality_weak`;
- `low_margin_pressure`;
- `capex_pressure`;
- `governance_signal`;
- `unprofitable_status`;
- `financial_asset_income_dependency`;
- `related_party_or_litigation_signal`.

Policy:

- may participate in scoring/risk scoring only as structured typed signals;
- must not be introduced by scanning prose fulltext summaries;
- must carry source facts and calculation rationale.

### Scoring Bridge Principle

Annual-report material can influence scoring only through typed factual signals, not through LLM narrative text.

Good:

```text
inventory_growth = 150.95%
sales_volume_growth = 4.44%
signal = inventory_pressure
```

Avoid:

```text
Scan annual-report fulltext summary prose for "毛利率承压" and add risk score.
```

Implementation advice:

- Start with a thin spike before broad extraction.
- Suggested first slice: revenue and net profit filing facts end-to-end, including evidence binding, Knowledge persistence, and one scoring/risk consumer.
- Use the spike to validate the structured fact channel before adding the full metric/signal surface.

### HK Evidence-Pack Support Gap

Status: recorded follow-up, not part of the A-share Phase A helper.

The structured-facts preview on 黑芝麻智能 02533.HK showed that the Phase A helper itself behaves conservatively, but the upstream `build_periodic_report_evidence_pack` does not yet extract HK-style financial summary / income statement / cash-flow blocks from the local Chinese HK annual-report cache. As a result, HK `revenue`, `net_profit`, and `operating_cash_flow` cannot be anchored and no filing facts are emitted.

This should be a separate task before claiming HK structured facts support:

- detect HK annual-report financial statement headings and summary tables;
- preserve real evidence-pack block ids and bounded excerpts;
- handle simplified/traditional Chinese labels such as 收入/來自客戶合同的收入、毛利、經營虧損、年內虧損、經營活動所用現金淨額;
- avoid anchoring to five-year summaries when a current-year income statement is available;
- add HK fixtures using 黑芝麻-style tables.

Until that task lands, HK structured facts should be treated as unsupported / best-effort and should fail closed by emitting diagnostics rather than facts with placeholder evidence refs.

## Bucket 4: Data Source Registry And HostThrottle Design

Status: later Level 3 design.

Purpose: convert current source-priority and anti-scraping rules into explicit code contracts.

Design requirements:

- source availability checks, e.g. cached data exists, cookie/login present, endpoint available;
- per-host request throttle with jitter;
- explicit fallback chains for A-share/HK/annual-report/social sources;
- "manual only" source types such as Xueqiu detail pages must fail loudly when not authorized/logged in;
- never silently downgrade an explicitly requested risky/manual source to a different source.

Hard rule to preserve from AGENTS/CLAUDE constraints:

- `xueqiu_detail_manual` without login/authorization must fail loudly and must not silently fall back to Eastmoney.

For a batch report generator, "fail loudly" should mean:

- return a typed `source_unavailable` / `requires_login` result;
- isolate the failure to the current stock/source;
- surface the reason in source diagnostics or report evidence context;
- do not raise a naked exception that stops unrelated stocks in a batch run.

## Deferred Or Rejected Ideas

Deferred:

- lightweight report manifest / run card: useful, but not in Bucket 1 because it creates runtime artifacts;
- minimal redaction helper: implement when manifest/audit output exists;
- output contract classifier for LLM synthesis: useful, but touches synthesis behavior and needs design;
- source registry / HostThrottle: useful, but high-risk data-collection area.

Rejected for current project stage:

- multi-agent DAG/swarm runtime;
- five-layer conversational context compression;
- full session/attempt service;
- full Signal Zoo rewrite now;
- full Pydantic config migration now;
- prediction accuracy tracker / hypothesis registry as near-term infrastructure.

## Recommended Order

1. Bucket 1: safety invariant guardrails.
2. Bucket 2: workflow hygiene docs and runbooks.
3. Bucket 3: periodic-report fact extractor design.
4. Bucket 3A: HK evidence-pack support for structured facts.
5. Bucket 4: data-source registry / HostThrottle design.
6. Later: report manifest + redaction helper when a concrete runtime-output need exists.

## Bucket 1 Implementation Notes

Status: implemented on 2026-06-20.

Files added:

- `tools/ci_grep_gates.sh`
- `tests/utils/test_ci_grep_gates.py`
- `tests/reporter/test_fulltext_material_isolation.py`

What landed:

- A narrow gate for obvious fulltext material-layer leakage into scoring/risk/Knowledge files.
- AST checks for `requests.get(...)` without `timeout`, unsafe `yaml.load(...)`, and obvious secret literals in source code.
- Positive and negative gate fixtures, including a positive case that display renderers may still use `synthesis_display`.
- A readable material-layer isolation test covering baseline synthesis, baseline risk scan input, baseline Knowledge input, and enhanced display rendering.

Verification commands used:

```bash
python3 -m pytest tests/utils/test_ci_grep_gates.py tests/reporter/test_fulltext_material_isolation.py -q
python3 -m pytest tests/reporter/test_synthesis_skills.py tests/reporter/test_scoring_engine_risk.py tests/reporter/test_executive_summary_renderer.py tests/reporter/test_deep_analysis_renderer.py tests/reporter/test_html_dashboard_renderer.py -q
bash tools/ci_grep_gates.sh
git diff --check
```
