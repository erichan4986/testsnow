# Agent-Reach Claim/Risk Bridge Design

Date: 2026-06-14

## Goal

Move Agent-Reach from display-only evidence toward a controlled verification loop:

```text
Agent-Reach source_credit
  -> evidence notes
  -> claim verification
  -> structured_risk_signals
  -> risk_score_section()
```

This should be one integrated implementation phase, not four separate micro-phases.

The first usable slice should let high-credit Agent-Reach evidence verify or support low-credit legacy/social claims, then derive deterministic `structured_risk_signals` for the risk section. This gives the risk model a real source-credit-backed qualitative input path without letting Agent-Reach directly rewrite synthesis, scoring, EV, technical analysis, or final recommendation.

## Why We Are Combining The Work

The repository already has the main building blocks:

- `source_credit.py` assigns deterministic source credibility.
- `AgentReachAdapter` attaches source-credit metadata to Agent-Reach `SynthesisItem.extra`.
- `evidence_note_writer.py` writes source-credit evidence notes with claims.
- `claim_verification.py` already implements high-credit-verifies-low-credit matching.
- `SynthesisSkill` can optionally build a prompt-safe claim-verification summary.
- `risk_score_section()` now accepts `structured_risk_signals`.

The missing piece is the bridge from claim verification output to risk signals, plus pipeline/config wiring.

Combining this is safe if we keep the implementation pure, gated, and narrow.

## Current State

### Agent-Reach

Black Sesame has configured official URLs:

```json
"agent_reach": {
  "enabled": true,
  "web_urls": [...],
  "official_domains": ["blacksesame.com"]
}
```

Current runtime:

- Fetches 6 official `blacksesame.com` URLs.
- Quality gate keeps them.
- Report renders `## Agent-Reach 外部证据观察`.
- Sidecar audit JSON is generated.
- Agent-Reach does not enter scoring, risk factors, LLM synthesis, or numbered citations.

### Evidence Notes

`evidence_note_writer_skill` exists but is only enabled by:

```json
"evidence_notes": {"enabled": true, "dry_run": ...}
```

Current Black Sesame config does not enable it, and `knowledge/10-Stocks/黑芝麻智能/evidence/` is not present.

### Claim Verification

`build_claim_verification_plan()` reads:

- high/medium-credit notes from `knowledge/10-Stocks/<stock>/evidence/*.md`
- low-credit social notes from `knowledge/10-Stocks/<stock>/*.md`

Trust direction is already correct:

- high credit (`>=80`) can verify
- medium credit (`55-79`) can support
- low/social cannot verify other claims

### Risk Model

`risk_score_section()` accepts:

```python
structured_risk_signals=[{
    "name": "竞争格局恶化",
    "score": 1.5,
    "confidence": 80,
    "source": "claim_verification",
    "evidence_text": "...",
    "matched_terms": ["..."],
    "status": "verified",
}]
```

Only `verified` or `supported` signals with confidence >= 60 and known names can score.

## Design Options

### Option A: Feed Agent-Reach items directly into `risk_score_section`

Rejected.

This would bypass claim verification and turn source quality into risk facts too directly. A company official article can verify a product milestone, but it should not automatically become a risk signal without deterministic interpretation.

### Option B: Feed Agent-Reach into LLM synthesis and let the LLM infer risks

Rejected for this phase.

This would undo the isolation and stability work. LLM wording would again influence risk indirectly, and Agent-Reach could leak into uncited conclusions.

### Option C: Add a deterministic claim-verification risk-signal bridge

Chosen.

Keep Agent-Reach out of synthesis/scoring by default, but use local evidence notes plus claim verification to derive explicit, auditable structured risk signals.

## Proposed Architecture

### New Pure Helper Module

Create:

```text
scripts/utils/claim_risk_signals.py
```

Public API:

```python
def derive_structured_risk_signals_from_claim_verification(summary: dict) -> list[dict]:
    ...
```

Input should be the prompt-safe summary shape already produced by `summarize_claim_verification_plan()`, not raw file paths or URLs.

Output should match `risk_score_section()`:

```python
{
    "name": "盈利压力",
    "score": 1.0,
    "confidence": 76,
    "source": "claim_verification",
    "evidence_text": "黑芝麻智能风险线索：毛利率承压...",
    "matched_terms": ["毛利率承压"],
    "status": "verified",
}
```

### New Pipeline Skill

Create:

```text
scripts/utils/report_skills/claim_risk_signal_skill.py
```

Skill behavior:

1. If `enable_claim_risk_signals` is false, set:

```python
structured_risk_signals = []
claim_risk_signal_status = "disabled"
```

2. If `claim_verification_summary` already exists on ctx, reuse it.

3. If no summary exists and `enable_claim_risk_signals=True`, build one using:

```python
build_claim_verification_plan(stock_name, base_dir, dry_run=True)
summarize_claim_verification_plan(...)
```

4. Convert summary to `structured_risk_signals`.

5. Set:

```python
ctx["structured_risk_signals"] = signals
ctx["claim_risk_signal_status"] = "ok" | "empty" | "error" | "disabled"
ctx["claim_risk_signal_summary"] = {"signal_count": ..., "source": ...}
ctx["claim_risk_signal_error"] = ""
```

Error handling:

- Catch all exceptions.
- Do not abort report generation.
- On error, set empty signals and status `error`.

### Pipeline Order

Current relevant order:

```text
agent_reach_query
agent_reach_fetch
agent_reach_quality
evidence_note_writer
cross_source_consolidation
quote_fetching
competitor_fetching
technical_fetching
TechnicalAnalysisSkill
SynthesisSkill
scoring_skill
ChartGenerationSkill
ReportAssemblySkill
```

New order when enabled:

```text
...
SynthesisSkill
claim_risk_signal_skill
scoring_skill
ChartGenerationSkill
ReportAssemblySkill
```

Rationale:

- If `SynthesisSkill` already built `claim_verification_summary`, reuse it.
- If synthesis claim verification is disabled but risk signals are enabled, the new skill can build the summary itself.
- `RiskRenderer` reads `structured_risk_signals` during `ReportAssemblySkill`, so setting the context before assembly is sufficient.

### Pipeline Builder

Extend:

```python
build_stock_report_pipeline(
    llm_client=None,
    enable_agent_reach=False,
    enable_evidence_notes=False,
    enable_claim_risk_signals=False,
)
```

Default remains false.

Only insert `claim_risk_signal_skill` when `enable_claim_risk_signals=True`.

### PerStockReporter Config

Support a nested config under `agent_reach.claim_verification`:

```json
"claim_verification": {
  "enabled": true,
  "risk_signals": true,
  "base_dir": "knowledge",
  "max_verified": 6,
  "max_supported": 4,
  "max_unverified": 4
}
```

Rules:

- `claim_verification.enabled` continues to control synthesis claim-verification context.
- `claim_verification.risk_signals` controls the new risk-signal bridge.
- Risk signals may be enabled even if synthesis context is disabled.
- Default is disabled.

For Black Sesame runtime validation, config can be updated explicitly:

```json
"evidence_notes": {"enabled": true, "dry_run": false},
"claim_verification": {
  "enabled": true,
  "risk_signals": true
}
```

This will create evidence notes under `knowledge/10-Stocks/黑芝麻智能/evidence/`. That is intentional for the runtime validation only if the user approves this config change.

## Risk Signal Derivation Rules

Use deterministic keyword mapping over `claim_text` and `reason`.

Allowed signal names must match `risk_score_section()`:

| Signal | Max Score | Keywords |
|--------|-----------|----------|
| `业绩预期下调` | 1.5 | `下调`, `不及预期`, `亏损加剧`, `净利润为负`, `指引下修` |
| `竞争格局恶化` | 1.5 | `竞争`, `价格战`, `降价`, `替代`, `地平线`, `Mobileye`, `竞品` |
| `盈利压力` | 1.0 | `毛利率`, `亏损`, `费用`, `利润`, `盈利压力`, `降本` |
| `资金流出` | 1.0 | `净流出`, `减持`, `做空`, `港股通`, `退通`, `流动性` |
| `技术路线风险` | 1.0 | `技术路线`, `架构`, `认证`, `替代`, `ASIL`, `功能安全` |

Status mapping:

| Claim action | Signal status | Score eligibility |
|--------------|---------------|-------------------|
| `verified` | `verified` | Can score if confidence >= 60 |
| `supported` | `supported` | Can half-score if confidence >= 60 |
| `needs_review` | `unverified` | Observation only |
| `unverified` | `unverified` | Observation only |

Confidence:

- Use row `confidence` if present and numeric.
- Default `verified` to 70 if confidence is missing.
- Default `supported` to 60 if confidence is missing.
- Default `needs_review`/`unverified` to 0.

Deduplication:

- At most one signal per name.
- Prefer highest scoring eligibility: `verified` > `supported` > `unverified`.
- Tie-break by confidence, then longer evidence text.

Evidence text:

- Use `claim_text`, truncated to 160 chars.
- Strip `[^n]`, `[n]`, URLs, and file paths.
- Do not include `url`, `source_file`, raw IDs, or local paths.

## Evidence Notes And Knowledge Writes

Implementation tests must use temp dirs only.

Runtime validation may write Black Sesame evidence notes only if explicitly enabled in config for this stock.

Safety rules:

- Evidence notes are append-only/dedupe by canonical URL.
- Do not write evidence notes for `quality_action=discard`.
- Do not write notes without `source_credit`.
- Do not write notes when `knowledge_eligible=False`.
- Do not modify legacy social notes.

## Non-Goals

- Do not feed Agent-Reach items directly into `KnowledgeSynthesizer` numbered sources.
- Do not make Agent-Reach citations appear as `[^n]`.
- Do not change technical analysis, EV, final recommendation, or pillar scoring.
- Do not change Xueqiu/Playwright/CDP behavior.
- Do not add new external fetches beyond existing Agent-Reach web URL fetch during runtime validation.
- Do not infer investment conclusions directly from official sources.
- Do not change `risk_score_section()` signal scoring rules in this phase.

## Failure Modes

| Failure Mode | Expected Behavior |
|--------------|-------------------|
| Evidence notes disabled | `claim_risk_signal_status` is `empty` or `disabled`; no risk signals |
| Evidence notes dry-run only | No new knowledge files; claim verification sees only existing evidence |
| Claim verification import/build fails | Pipeline continues with empty `structured_risk_signals` and status `error` |
| Summary contains only unverified claims | Render observations only; no score impact |
| Official source verifies product progress only | No risk signal if no risk keywords match |
| Company official source is promotional | It can verify facts, but risk signal derivation only fires on risk keywords |
| Duplicate official URLs | Evidence writer skips existing canonical URLs |
| Runtime generated notes change future runs | Expected only when `evidence_notes.dry_run=false`; side effect is explicit and scoped to stock evidence dir |

## Tests

### New `tests/utils/test_claim_risk_signals.py`

Cover:

1. `verified_claims` with `毛利率/亏损` derives `盈利压力`.
2. `supported_claims` derives supported signal and half-score-compatible status.
3. `unverified_claims` derives `unverified` observation-only signal.
4. Unknown/non-risk claims produce no signal.
5. Duplicate signal names dedupe by verified > supported > unverified, then confidence.
6. Evidence text strips URLs, file paths, and citation markers.
7. Malformed confidence/status does not crash.

### New/Updated `tests/reporter/test_claim_risk_signal_skill.py`

Cover:

1. Disabled skill sets empty signals and `disabled`.
2. Existing `claim_verification_summary` is reused; builder is not called.
3. Missing summary with enabled flag builds plan from temp knowledge dir.
4. Builder error is caught and pipeline continues.
5. Output `structured_risk_signals` is readable by `risk_score_section()`.

### Pipeline Tests

Update `tests/reporter/test_pipeline_integration.py`:

1. Default pipeline skill count unchanged.
2. Pipeline with `enable_claim_risk_signals=True` inserts the skill after `SynthesisSkill` and before `scoring_skill`.
3. Agent-Reach + evidence notes + claim risk signals combined pipeline order is correct.

### Reporter Config Tests

Update `tests/reporter/test_stock_reporter_agent_reach_config.py`:

1. Default reporter does not enable claim risk signals.
2. `claim_verification.risk_signals=True` passes `enable_claim_risk_signals=True`.
3. `claim_verification.risk_signals=True` can work whether or not `claim_verification.enabled=True`.
4. Other stocks are unaffected.

### Integration Smoke Test

Use a temp knowledge root:

1. Create one high-credit official evidence note with a risk-relevant claim.
2. Create one low-credit social note with matching risk claim.
3. Run `build_claim_verification_plan()`.
4. Run `derive_structured_risk_signals_from_claim_verification(summary)`.
5. Pass output to `risk_score_section()`.
6. Assert verified/supported signal can affect risk score only through `structured_risk_signals`.

## Runtime Validation

After implementation review:

1. Run focused tests.
2. Run `scripts/smoke_agent_reach.py --stock 黑芝麻智能 --write-audit --output-dir reports`.
3. If config enables evidence note writing, run `cd scripts && python3 run_黑芝麻智能.py --fast-test`.
4. Run `python3 scripts/check_report_quality.py reports/黑芝麻智能_20260614.md`.
5. Check:
   - evidence notes created or skipped by canonical URL
   - `claim_risk_signal_status`
   - `structured_risk_signals` count in logs/notes if visible
   - risk section has structured risk rows only if verified/supported risk claims exist
   - Agent-Reach still does not become numbered citations

## Expected Files To Change

Implementation:

- Create `scripts/utils/claim_risk_signals.py`
- Create `scripts/utils/report_skills/claim_risk_signal_skill.py`
- Modify `scripts/utils/report_skills/__init__.py`
- Modify `scripts/utils/stock_reporter.py`
- Add/modify tests listed above
- Create implementation notes

Optional runtime-config change, only if approved:

- Modify `config/stocks.json` for Black Sesame only, adding explicit `evidence_notes` and `claim_verification.risk_signals` config.

## Files That Must Not Change

- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/technical_*.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`, unless review discovers a reuse bug that cannot be solved in the new skill
- `scripts/utils/report_quality.py`
- `scripts/xueqiu_monitor_v2.py`
- existing `knowledge/**` during implementation tests
- existing `reports/**` during implementation tests

## Acceptance

Implementation is accepted when:

- Focused tests pass.
- The combined pipeline order is correct.
- Default behavior remains unchanged.
- With synthetic verified claim summary, `structured_risk_signals` are produced and affect `risk_score_section()` through the existing API.
- With no matching risk keywords, no risk signal is produced.
- Runtime validation for Black Sesame either:
  - writes/skips scoped evidence notes and shows risk signals if matched, or
  - reports no matching risk signals while preserving Agent-Reach isolation.

## Round 1 Feedback

### Status

**Must-fix before task**

### Findings

1. **[must-fix] Risk keyword mapping is too crude and will produce false positives from positive official sources.**
   The current keyword lists match neutral or positive phrases as risks:
   - `认证` / `ASIL` / `功能安全` in "华山A2000U获ISO 26262 ASIL-D最高功能安全认证" matches `技术路线风险`.
   - `地平线` / `Mobileye` / `竞品` as bare competitor mentions match `竞争格局恶化`.
   - `毛利率` alone matches `盈利压力`, regardless of whether the text says "毛利率提升" or "毛利率承压".
   This directly violates the Non-Goal "Do not infer investment conclusions directly from official sources" and will make the risk section unreliable for Black Sesame, whose Agent-Reach sources are almost all official product news.

2. **[must-fix] No negation or polarity handling in deterministic keyword matching.**
   The design derives risk signals solely by substring presence in `claim_text`. There is no exclusion for negated or favorable contexts (e.g., "毛利率改善", "通过认证", "竞争力提升"). Without polarity guards, verified high-credit sources are more likely to *mislead* the risk model than low-credit social claims.

3. **[must-fix] Evidence text is double-truncated before keyword matching.**
   `summarize_claim_verification_plan()` already truncates `claim_text` to 200 chars and `reason` to 160 chars. The design then proposes truncating `claim_text` again to 160 chars. This loses the surrounding context needed to judge whether a keyword is risk-polarized, increasing false positives.

4. **[medium] Config gating path is underspecified.**
   The design says `claim_verification.risk_signals` controls the new bridge, but `stock_reporter.py` currently only reads `claim_verification.enabled` for synthesis context. The design must explicitly show `stock_reporter.py` extracting `risk_signals` and passing `enable_claim_risk_signals=True` to `build_stock_report_pipeline()`, and a matching test must be added.

5. **[medium] Summary bucket caps can drop the highest-confidence verified claim before risk-signal deduplication.**
   `summarize_claim_verification_plan()` caps `verified_claims` at `max_verified` (default 6), `supported_claims` at 4, etc. If multiple verified claims map to the same risk signal name, the cap may discard the highest-confidence one before `derive_structured_risk_signals_from_claim_verification` deduplicates by confidence. This makes deduplication non-deterministic relative to the full plan.

6. **[medium] Pipeline skill-count tests need expansion.**
   Existing tests assert 11/14/15 skills for current flag combinations. Adding `enable_claim_risk_signals` changes these counts and needs new assertions for:
   - default: 11 skills
   - `enable_claim_risk_signals=True` only: 12 skills
   - `enable_agent_reach=True`: 14 skills
   - `enable_agent_reach=True, enable_evidence_notes=True`: 15 skills
   - `enable_agent_reach=True, enable_evidence_notes=True, enable_claim_risk_signals=True`: 16 skills

7. **[low] Agent-Reach isolation test is missing.**
   There is no test proving that enabling `claim_verification.risk_signals` does not cause Agent-Reach items to enter `synthesis_text`, `core_facts`, numbered citations, or final recommendation. This is the central correctness property of the design and should be asserted explicitly.

8. **[low] Error boundary for malformed `claim_verification_summary` is unspecified.**
   The new skill reuses `ctx["claim_verification_summary"]` if present. If `SynthesisSkill` sets a malformed or partial summary, the risk-signal skill should catch the error and continue with empty signals, not crash the report.

### Recommended Design Deltas

1. **Replace broad substring lists with risk-polarized keyword rules or explicit exclusions.**
   Example direction:
   - `技术路线风险`: require `风险` / `不确定性` / `迭代` near `技术路线` / `架构`; explicitly exclude `获.*认证` / `通过.*认证` / `获得.*ASIL`.
   - `竞争格局恶化`: require `恶化` / `加剧` / `价格战` / `降价` / `份额下滑`; exclude bare mentions of competitors unless paired with negative polarity words.
   - `盈利压力`: require `承压` / `下滑` / `下降` / `亏损加剧` / `毛利压缩`; exclude `毛利率提升` / `扭亏` / `盈利改善`.
   - `资金流出`: require `净流出` / `减持` / `做空` / `退通风险`; exclude `港股通纳入` / `流动性改善`.
   Alternatively, restrict the initial keyword set to a much smaller whitelist of unambiguous risk phrases (e.g., `毛利率承压`, `竞争格局恶化`, `资金净流出`, `技术路线不确定`) and expand only after runtime validation.

2. **Derive risk signals from the full `ClaimVerificationPlan`, not the truncated summary.**
   Pass the full `high_credit_claims`, `medium_credit_claims`, and `low_credit_claims` (or at least the full verifications) into `derive_structured_risk_signals_from_claim_verification` so keyword matching has access to complete `claim_text` and `reason`. Perform deduplication across the full set, then cap only for display/logging if needed.

3. **Add a polarity/whitelist gate before emitting a scored signal.**
   A signal should only score if:
   - `status` is `verified` or `supported` and `confidence >= 60` (already in design), AND
   - the matched keyword appears in a risk-polarized phrase or passes a small exclusion list.
   Signals that fail the polarity gate may still appear in the observation table as "不计分" with a note like "关键词命中但语境非风险".

4. **Explicitly specify the config pass-through.**
   Update the `PerStockReporter` and `build_stock_report_pipeline` sections to show:
   - `stock_reporter.py` reads `ar_cfg.get("claim_verification", {}).get("risk_signals", False)`.
   - It passes `enable_claim_risk_signals=claim_risk_signals_enabled` to `build_stock_report_pipeline()`.
   - `build_stock_report_pipeline` accepts `enable_claim_risk_signals: bool = False` and inserts `claim_risk_signal_skill` only when true.

5. **Decide whether Black Sesame runtime config change is part of the implementation task.**
   The design says config change is "only if approved." The implementation task should either include the explicit config change under a user-approval step or treat it as a separate runtime-validation-only step, not a silent default.

### Missing Tests

- `tests/utils/test_claim_risk_signals_false_positives.py` (or equivalent section):
  - Official certification news does NOT produce `技术路线风险`.
  - Competitor mention without negative polarity does NOT produce `竞争格局恶化`.
  - "毛利率提升" / "扭亏" does NOT produce `盈利压力`.
  - "港股通纳入" does NOT produce `资金流出`.
- `tests/reporter/test_stock_reporter_agent_reach_config.py` additions:
  - `claim_verification.risk_signals=True` passes `enable_claim_risk_signals=True` to pipeline builder.
  - `claim_verification.risk_signals=True` works independently of `claim_verification.enabled`.
  - Default reporter does not enable claim risk signals.
- `tests/reporter/test_pipeline_integration.py` additions:
  - Exact skill counts for all `enable_agent_reach` / `enable_evidence_notes` / `enable_claim_risk_signals` combinations.
  - `claim_risk_signal_skill` is inserted after `SynthesisSkill` and before `scoring_skill`.
  - Default pipeline is unchanged (11 skills, no claim risk skill).
- `tests/reporter/test_claim_risk_signal_skill.py` additions:
  - Malformed `claim_verification_summary` on context is caught and status becomes `error`.
  - Missing knowledge dir / empty evidence dir yields `empty` status without crash.
  - Skill does not call `build_claim_verification_plan` when summary is reused.
- `tests/reporter/test_scoring_engine_risk.py` additions:
  - Combined verified structured signals plus existing keyword observations do not double-count.
  - Risk signals from `claim_verification` source are labeled `claim_verification` in output.
- Isolation test (new file or existing):
  - With `enable_claim_risk_signals=True`, Agent-Reach URLs/titles do not appear in `synthesis_text`, `core_facts`, or report citations.

### Open Questions

- Should the keyword rules live in `claim_risk_signals.py` as a hard-coded table, or be loaded from a small config file so they can be tuned without code changes?
- For Black Sesame runtime validation, do we pre-approve the `evidence_notes.dry_run=false` config change, or keep it dry-run and rely on pre-existing evidence notes?

### R2 Needed?

**Yes.** The keyword false-positive issue is a must-fix that changes the core risk-signal derivation rules. After the design delta is applied, a lightweight Round 2 should review the revised keyword/exclusion rules and the false-positive regression tests before moving to implementation.

## Design Delta After Round 1

Status: revised for Round 2 review.

This delta supersedes the earlier sections that said risk signals should be derived from the prompt-safe `claim_verification_summary`. The bridge must derive risk signals from the full `ClaimVerificationPlan`, then expose only sanitized, truncated signal rows to `risk_score_section()`.

### 1. Derive From Full ClaimVerificationPlan, Not Truncated Summary

Create `scripts/utils/claim_risk_signals.py` with this primary API:

```python
def derive_structured_risk_signals_from_plan(plan: ClaimVerificationPlan) -> list[dict]:
    ...
```

Do not derive risk signals from `summarize_claim_verification_plan()` output. That summary is prompt-facing and intentionally truncated. Risk-signal derivation needs full claim text and verification metadata to avoid losing polarity context.

The new pipeline skill should:

1. Build a full plan with `build_claim_verification_plan(stock_name, base_dir, dry_run=True)`.
2. Pass the full plan to `derive_structured_risk_signals_from_plan(plan)`.
3. Optionally store a compact `claim_risk_signal_summary` for logs/debugging.

If `SynthesisSkill` already produced `claim_verification_summary`, do not reuse it for risk derivation. Duplicate local file reads are acceptable in this phase because the builder is pure, dry-run, and local-only.

### 2. Risk-Polarized Phrase Rules Only

Replace broad substring matching with a small risk-polarized phrase table. A bare domain term is never enough to produce a signal.

Allowed scored/observed signals must still use the existing `risk_score_section()` names:

| Signal | Allowed Risk Phrases | Explicit Non-Risk Exclusions |
|--------|----------------------|------------------------------|
| `业绩预期下调` | `业绩不及预期`, `指引下修`, `预期下调`, `净利润为负`, `亏损加剧`, `收入不及预期` | `指引上调`, `收入增长`, `营收增长`, `亏损收窄` |
| `竞争格局恶化` | `竞争格局恶化`, `竞争加剧`, `价格战`, `降价压力`, `份额下滑`, `被.*替代`, `竞品.*挤压` | bare `地平线`, bare `Mobileye`, bare `竞品`, `竞争力提升`, `份额提升` |
| `盈利压力` | `毛利率承压`, `毛利率下滑`, `毛利率下降`, `毛利压缩`, `费用扩张`, `利润侵蚀`, `盈利压力`, `亏损扩大` | `毛利率提升`, `毛利率改善`, `盈利改善`, `扭亏`, `亏损收窄`, `降本` unless paired with `承压/压力/下滑` |
| `资金流出` | `资金净流出`, `主力净流出`, `减持压力`, `做空压力`, `退通风险`, `流动性恶化` | `港股通纳入`, `流动性改善`, `增持`, `回购` |
| `技术路线风险` | `技术路线不确定`, `架构迭代风险`, `认证受阻`, `未通过认证`, `功能安全风险`, `技术替代风险` | `通过.*认证`, `获得.*认证`, `获.*认证`, `ASIL-D.*认证`, `功能安全认证`, `技术突破` |

Implementation notes:

- Use regex or deterministic phrase checks in code, not LLM.
- Match against full `claim_text` plus verification `reason`.
- If any exclusion pattern matches the same text, suppress that signal entirely.
- If only a non-risk domain term appears, produce no signal, not even an observation.
- Do not create signals from official product-progress claims unless a risk-polarized phrase is present.

### 3. Signal Status And Confidence

For each low-credit claim verification:

| Verification action | Signal status | Default confidence |
|---------------------|---------------|--------------------|
| `verified` | `verified` | use verification confidence, or 70 if missing |
| `supported` | `supported` | use verification confidence, or 60 if missing |
| `needs_review` | `unverified` | 0 |
| `unverified` | `unverified` | 0 |

Signals with `unverified` status may be emitted only when a risk-polarized phrase matches. They remain observation-only in `risk_score_section()`.

### 4. Deduplicate Across The Full Plan

Deduplicate after scanning all verifications in the full plan:

1. Prefer `verified` over `supported` over `unverified`.
2. Then prefer higher confidence.
3. Then prefer longer sanitized evidence text.

Only after deduplication should the helper apply an output cap such as `max_signals=5`.

### 5. Sanitized Evidence Text

`evidence_text` should be derived from the full low-credit `claim_text`, then sanitized:

- strip URLs
- strip local paths
- strip raw ids
- strip `[n]` and `[^n]`
- collapse whitespace
- truncate once to 180 chars after matching and deduplication

No double truncation before matching.

### 6. Pipeline Skill Behavior

`claim_risk_signal_skill` should not depend on `claim_verification_summary`.

Behavior:

1. Disabled:
   - `structured_risk_signals=[]`
   - `claim_risk_signal_status="disabled"`
2. Enabled:
   - build full `ClaimVerificationPlan`
   - derive signals from full plan
   - set `structured_risk_signals`
3. Empty plan/no signals:
   - `structured_risk_signals=[]`
   - `claim_risk_signal_status="empty"`
4. Error/malformed local knowledge:
   - catch exception
   - `structured_risk_signals=[]`
   - `claim_risk_signal_status="error"`
   - short `claim_risk_signal_error`

The skill must not call network, LLM, browser, CDP, Xueqiu, or Zhihu.

### 7. Explicit Config Pass-Through

Update `build_stock_report_pipeline`:

```python
def build_stock_report_pipeline(
    llm_client=None,
    enable_agent_reach: bool = False,
    enable_evidence_notes: bool = False,
    enable_claim_risk_signals: bool = False,
) -> SkillPipeline:
    ...
```

Insert `claim_risk_signal_skill` after `SynthesisSkill` and before `scoring_skill` only when `enable_claim_risk_signals=True`.

Update `PerStockReporter.generate_stock_report()`:

```python
cv_cfg = ar_cfg.get("claim_verification", {}) or {}
claim_verification_enabled = bool(cv_cfg.get("enabled", False))
claim_risk_signals_enabled = bool(cv_cfg.get("risk_signals", False))

pipeline = build_stock_report_pipeline(
    enable_agent_reach=agent_reach_enabled,
    enable_evidence_notes=agent_reach_enabled and evidence_notes_enabled,
    enable_claim_risk_signals=claim_risk_signals_enabled,
)
```

Risk signals may be enabled independently of `claim_verification.enabled`; that flag controls synthesis context only.

If `claim_risk_signals_enabled=True`, pass the same base-dir/cap config keys needed by the skill. Use `claim_verification_base_dir` when `cv_cfg.base_dir` exists; otherwise the skill defaults to repo-root `knowledge/`.

### 8. Config Change Policy

Implementation task must not modify `config/stocks.json`.

After implementation review, runtime validation can use either:

1. a temporary config/constructor path in tests, or
2. an explicit user-approved config change for Black Sesame only.

No silent `knowledge/` writes should be introduced by default. If Black Sesame runtime enables `evidence_notes.dry_run=false`, that side effect must be called out before running.

### 9. Additional Required Tests

Add false-positive regression tests in `tests/utils/test_claim_risk_signals.py`:

1. `A2000U 获 ISO 26262 ASIL-D 最高功能安全认证` produces no `技术路线风险`.
2. Bare `地平线` / `Mobileye` competitor mention produces no `竞争格局恶化`.
3. `毛利率提升` / `毛利率改善` / `亏损收窄` produces no `盈利压力`.
4. `港股通纳入` / `流动性改善` produces no `资金流出`.
5. Explicit negative phrases still produce signals:
   - `毛利率承压` -> `盈利压力`
   - `价格战` -> `竞争格局恶化`
   - `退通风险` -> `资金流出`
   - `技术路线不确定` -> `技术路线风险`

Add full-plan tests:

1. Deduplication sees all verifications before capping.
2. The highest-confidence verified claim wins even if it would have been after the old summary cap.
3. Evidence is matched before final display truncation.

Add skill/config/pipeline tests:

1. `claim_verification.risk_signals=True` passes `enable_claim_risk_signals=True`.
2. `claim_verification.risk_signals=True` works independently of `claim_verification.enabled`.
3. Default reporter does not enable claim risk signals.
4. Pipeline skill counts:
   - default: 11
   - `enable_claim_risk_signals=True`: 12
   - `enable_agent_reach=True`: 14
   - `enable_agent_reach=True, enable_evidence_notes=True`: 15
   - all three enabled: 16
5. Skill order: `SynthesisSkill` -> `claim_risk_signal_skill` -> `scoring_skill`.
6. Malformed/empty knowledge dirs yield `empty` or `error` without crashing.

Add Agent-Reach isolation test:

- With `enable_claim_risk_signals=True`, Agent-Reach URLs/titles must not appear in `synthesis_text`, `core_facts`, or citation metadata unless they were already part of normal numbered synthesis items. This bridge must only set `structured_risk_signals`.

### 10. Updated Implementation Acceptance

Implementation may proceed only after Round 2 confirms:

- risk-polarized phrase rules are conservative enough for official-source Black Sesame runtime
- full-plan derivation replaces truncated-summary derivation
- config pass-through is explicit
- false-positive tests are required in the implementation task

## Round 2 Feedback

### Status

Ready to implement (with required phrase-table adjustments)

### Delta Findings

1. **[must-fix design adjustment] `技术路线风险` exclusion patterns suppress the listed risk phrase `未通过认证`.**
   The exclusion table lists `通过.*认证` and `获.*认证`. The risk-phrase table lists `未通过认证`. Because "未通过认证" contains the substring "通过认证", a naive regex match will apply the exclusion and suppress the signal. The same problem affects `未获认证`. The phrase table contains a direct contradiction that will produce a false negative if implemented literally.

2. **[required adjustment] `竞争格局恶化` risk phrase `被.*替代` can false-positive on positive substitution resistance.**
   Phrases like `难以被替代`, `不被替代`, or `未被替代` (positive/neutral) match `被.*替代` and would emit a risk signal. The exclusion table should add negated-substitution patterns.

3. **[required adjustment] Some positive forms are not explicitly excluded in profit/capital signals.**
   - `盈利压力` exclusions miss `亏损减少` / `亏损改善`.
   - `费用扩张` exclusions miss `费用率下降` / `费用控制`.
   - `利润侵蚀` exclusions miss `利润增长`.
   These are lower-probability false positives but should be covered by the regression suite.

4. **[confirmed resolved] Full-plan derivation replaces truncated-summary derivation.**
   Section 1 correctly requires building the full `ClaimVerificationPlan` and deriving signals from it, avoiding the double-truncation and summary-cap problems raised in Round 1.

5. **[confirmed resolved] Config pass-through is explicit.**
   Section 7 shows exact `PerStockReporter` extraction of `claim_verification.risk_signals` and the `build_stock_report_pipeline` parameter. The independence from `claim_verification.enabled` is clear.

6. **[confirmed resolved] Conservative risk-polarized phrase rules address the core false-positive concern.**
   Official certification, bare competitor mentions, positive margin phrases, and Hong Kong Stock Connect inclusion are all explicitly excluded. The rules are much safer than the broad substring lists in the original design.

7. **[confirmed resolved] Comprehensive tests are specified.**
   Section 9 includes false-positive regression tests, full-plan deduplication tests, config/pipeline tests, and an Agent-Reach isolation test.

### Required Task Adjustments

- Fix the `技术路线风险` phrase table so `未通过认证` and `未获认证` produce a signal despite the `通过.*认证` / `获.*认证` exclusions. Use word boundaries, negative lookbehind, or split the risk phrase into `(未通过|未获|认证受阻)` matching.
- Add negated-substitution exclusions for `竞争格局恶化`: `难以被替代`, `不被替代`, `未被替代`.
- Expand the false-positive regression suite to include the profit/capital positive forms listed above.
- Implement phrase matching with regex word boundaries / polarity guards rather than raw substring `in`, so risk phrases are not accidentally suppressed by exclusion patterns.
- Keep `config/stocks.json` unchanged in the implementation task, per Section 8.

### Missing Tests

The design already specifies the required test categories. The implementation task must ensure these specific cases are included:

- `未通过认证` produces `技术路线风险` (regression against over-broad exclusion).
- `难以被替代` does NOT produce `竞争格局恶化`.
- `亏损减少` / `亏损改善` do NOT produce `盈利压力`.
- `费用率下降` / `费用控制有效` do NOT produce `盈利压力`.
- `利润增长` does NOT produce `盈利压力`.
- All tests listed in Section 9, especially:
  - official certification / ASIL-D does not produce `技术路线风险`
  - bare competitor names do not produce `竞争格局恶化`
  - positive margin phrases do not produce `盈利压力`
  - Hong Kong Stock Connect inclusion does not produce `资金流出`
  - full-plan deduplication before capping
  - config pass-through and pipeline skill counts
  - Agent-Reach isolation

### Final R2 Decision

**Ready to implement as one combined task**, provided the phrase-table contradictions above are fixed in the implementation task (or in a final design-doc amendment). The architecture is conservative, the isolation boundary is clear, and the test plan covers the Round 1 must-fix issues. No further design review round is needed after the phrase-table fix.

## Final Design Amendment Before Implementation

The Round 2 phrase-table adjustments are accepted and are part of the implementation contract.

### Final Phrase Matching Requirements

Implement phrase matching with explicit risk regexes and separate exclusion regexes. Do not use broad substring checks.

For each candidate text:

1. Build `match_text = claim_text + " " + reason`.
2. Check risk regexes for each signal.
3. Check exclusions for that signal.
4. Emit a signal only when a risk regex matches and no exclusion regex applies.

Signal-specific final requirements:

#### `技术路线风险`

Risk patterns must include:

- `技术路线不确定`
- `架构迭代风险`
- `认证受阻`
- `未通过认证`
- `未获认证`
- `功能安全风险`
- `技术替代风险`

Exclusion patterns must not suppress `未通过认证` or `未获认证`.

Safe exclusion examples:

- `(?<!未)通过.{0,12}认证`
- `(?<!未)获得.{0,12}认证`
- `(?<!未)获.{0,12}认证`
- `ASIL-D.{0,12}认证`
- `功能安全认证`
- `技术突破`

Implementation may use a different deterministic approach if tests prove:

- `未通过认证` produces `技术路线风险`
- `未获认证` produces `技术路线风险`
- `A2000U 获 ISO 26262 ASIL-D 最高功能安全认证` does not produce `技术路线风险`

#### `竞争格局恶化`

Risk patterns must include:

- `竞争格局恶化`
- `竞争加剧`
- `价格战`
- `降价压力`
- `份额下滑`
- `被.{0,12}替代`
- `竞品.{0,12}挤压`

Exclusion patterns must include:

- `难以被.{0,12}替代`
- `不被.{0,12}替代`
- `未被.{0,12}替代`
- bare `地平线`
- bare `Mobileye`
- bare `竞品`
- `竞争力提升`
- `份额提升`

The implementation should treat `被.{0,12}替代` as risky only when the negated-substitution exclusions do not match.

#### `盈利压力`

Risk patterns must include:

- `毛利率承压`
- `毛利率下滑`
- `毛利率下降`
- `毛利压缩`
- `费用扩张`
- `利润侵蚀`
- `盈利压力`
- `亏损扩大`

Exclusion patterns must include:

- `毛利率提升`
- `毛利率改善`
- `盈利改善`
- `扭亏`
- `亏损收窄`
- `亏损减少`
- `亏损改善`
- `费用率下降`
- `费用控制`
- `利润增长`
- `降本` unless also paired with `承压|压力|下滑|下降|压缩`

#### `资金流出`

Risk patterns must include:

- `资金净流出`
- `主力净流出`
- `减持压力`
- `做空压力`
- `退通风险`
- `流动性恶化`

Exclusion patterns must include:

- `港股通纳入`
- `流动性改善`
- `增持`
- `回购`

#### `业绩预期下调`

Risk patterns must include:

- `业绩不及预期`
- `指引下修`
- `预期下调`
- `净利润为负`
- `亏损加剧`
- `收入不及预期`

Exclusion patterns must include:

- `指引上调`
- `收入增长`
- `营收增长`
- `亏损收窄`

### Final Task Readiness

Ready to implement. No R3 required.

## Deferred Follow-up: Long Official PDF / Annual Report Extraction

Status: backlog, not part of the current claim-risk bridge implementation.

Current Agent-Reach evidence notes can ingest official disclosure PDFs through
WebConnector/Jina Reader and assign high `source_credit` to exchange/regulator
sources such as `cninfo.com.cn`. This is enough for short announcements and
targeted official disclosures, but long annual reports need a dedicated
structured extractor before they can become reliable high-credit claim sources.

Planned direction:

- Build a deterministic long-disclosure extractor for annual reports and other
  long regulator PDFs.
- Do not pass the full PDF body directly into scoring, risk, or synthesis.
- Extract section-aware `fact_candidate` claims from the full converted text:
  - financial summary: revenue, net profit, gross margin, cash flow, R&D expense
  - segment/product tables: revenue by product, margin by product, volume/capacity
  - risk factors: customer concentration, receivables, inventory, debt, litigation
  - management discussion: order trend, capex, capacity ramp, guidance wording
- Preserve provenance per extracted claim:
  - source URL
  - announcement id / disclosure id when available
  - section heading
  - page number if available from the reader output
  - extraction rule id
- Keep the output as evidence-note frontmatter claims, not numbered report
  citations.
- The extractor must be pure and testable: no network, browser, subprocess, or
  LLM calls inside the extraction helper.

Non-goals:

- Do not summarize full annual reports with an LLM as the primary source of
  truth.
- Do not treat every annual-report sentence as a claim.
- Do not let Agent-Reach annual-report content enter `KnowledgeSynthesizer`
  numbered citations directly.

Suggested future task:

`Annual Report Evidence Extractor Phase 1`:

1. Add a pure helper that accepts converted Markdown/text from an official PDF.
2. Extract a bounded list of structured `fact_candidate` claims with section
   metadata.
3. Integrate it behind `evidence_note_writer` only for high-credit official
   disclosure sources.
4. Validate with one A-share annual report and one quarterly/short announcement
   to ensure short announcements do not regress.
