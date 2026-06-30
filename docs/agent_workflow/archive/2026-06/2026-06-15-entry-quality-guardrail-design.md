# Entry Quality Guardrail Design

Date: 2026-06-15

## Context

The Shengbang Source Intake pilot generated a report that passed the current quality checker but still read inconsistently:

- `AI 综合推荐`: `强烈看多`
- risk position advice: `积极配置，最大仓位 20%`
- technical section: `BIAS 严重正偏离`, `MACD 柱线翻绿`, and price-target status `关注/不操作（形态存在但盈亏比不足...）`

This is not a Source Intake failure. It is a recommendation wording gap: the existing technical position guardrail only handles broken/downtrend states. It does not handle an uptrend that is extended and has poor entry quality.

## Goal

Add a conservative entry-quality guardrail so reports do not recommend aggressive buying or 20% position sizing when technical analysis says the stock is not an attractive entry.

## Non-Goals

- Do not change composite score math.
- Do not change EV calculation.
- Do not change price target, BIAS, MACD, trend, or technical algorithms.
- Do not add new data sources.
- Do not turn every overbought signal into sell advice.

## Proposed Behavior

Add a helper in `scoring_engine.py`, tentatively named `_entry_quality_guardrail(stock_raw)`.

It should inspect existing technical outputs:

- `stock_raw["technical"]["price_target"]`
  - `error == "关注/不操作"`
  - `reason` contains `盈亏比不足`
- `stock_raw["technical"]["indicators"]`
  - `bias_5_extreme_high` or `bias_10_extreme_high`
  - optional text from `_resonance.risk_flags` / existing indicators if present

Trigger level:

- `entry_blocked`: price target says `关注/不操作` and reason contains `盈亏比不足`.
- `overheated_entry`: BIAS is extreme high, but no `entry_blocked`.

Guardrail effects:

1. Risk/position section:
   - Keep `total_risk` and risk factor table unchanged.
   - If original advice is `积极配置，最大仓位 20%`, cap it to:
     - `趋势仍可跟踪，但当前入场质量不足，建议等待回调或盈亏比改善，仓位 5-10%`
   - If original advice is already more conservative, keep it.
   - Render an extra blockquote line:
     - `> **入场约束**: 技术面提示关注/不操作或追高风险，仓位建议已按入场质量降级。`

2. Composite recommendation section:
   - Keep total score and EV unchanged.
   - If recommendation label is `强烈看多` or other strong-recommendation text while entry quality is blocked, render the label as a tempered form:
     - `看多但等待入场`
   - Keep the original EV sentence, but append:
     - `技术面提示当前不适合追高，需等待回调或盈亏比改善。`
   - Do not emit strings matching `STRONG_RECOMMENDATION_PATTERNS` when guardrail is active.

## Data Flow

Existing pipeline already passes `stock_raw` into:

- `composite_score_section(...)`
- `risk_score_section(...)`

No pipeline changes should be necessary.

## Expected Shengbang Outcome

For `reports/圣邦股份_20260615.md`-like input:

- Composite score remains `7.5/10`.
- EV remains `+10.25%`.
- AI recommendation no longer says `强烈看多`.
- Risk score remains `2.0/10`.
- Position advice no longer says `积极配置，最大仓位 20%`.
- Report quality checker should have no strong-recommendation contradiction.

## Tests Required

Focused tests should cover:

- `price_target.error == "关注/不操作"` + `reason` contains `盈亏比不足`:
  - risk section caps aggressive position advice.
  - composite recommendation does not contain `强烈看多`.
  - score/EV text remains unchanged.
- BIAS extreme high alone:
  - caps only aggressive position advice.
  - does not force sell/reduce advice.
- Already conservative advice:
  - not made more aggressive.
- Broken/downtrend severe guardrail:
  - still takes precedence over entry-quality guardrail.
- `STRONG_RECOMMENDATION_PATTERNS`:
  - no matches in guarded output.
- Regression:
  - existing black sesame severe guardrail behavior unchanged.
  - source intake / claim risk tests unaffected.

## Implementation Scope

Allowed files:

- `scripts/utils/reporter/scoring_engine.py`
- `tests/reporter/test_scoring_engine_risk.py`
- A focused composite score test file if one already exists, otherwise add tests in a suitable existing reporter test file.
- `docs/agent_workflow/2026-06-15-entry-quality-guardrail-claude-notes.md`

Forbidden:

- `technical_analyzer.py`
- `price_target.py`
- `KnowledgeSynthesizer`
- data collection scripts
- `config/stocks.json`
- report generated files except runtime validation outputs

## Open Questions For Review

1. Should the composite recommendation label become `看多但等待入场` or should it keep `看多` and only add caution text?
2. Is `BIAS extreme high alone` enough to cap position advice, or should it require `price_target.error` too?
3. Should `check_report_quality.py` also learn this contradiction pattern now, or should we first fix renderer output and add quality-rule expansion later?

## Round 1 Feedback

- **Status**: Ready to implement
- **R2 Needed**: No

### Findings by severity

#### Info / Clarifications

1. **Data paths are correct.**
   - `stock_raw["technical"]["price_target"]` is written by `scripts/utils/reporter/price_target.py::analyze_price_target` and returned under `technical["price_target"]` in `advanced_medium_term_resonance`.
   - The exact error/reason strings `关注/不操作` and `盈亏比不足` match the current `price_target.py` implementation.
   - `stock_raw["technical"]["indicators"]["_resonance"]` is populated and `bias_extreme` is present; `indicators["bias_5_extreme_high"]` / `"bias_10_extreme_high"` are also present.
   - No new data source or pipeline wiring is required because `stock_raw` is already passed to both `composite_score_section` and `risk_score_section`.

2. **Scope is well-scoped to `scoring_engine.py`.**
   - The design correctly avoids touching `technical_analyzer.py`, `price_target.py`, or `KnowledgeSynthesizer`.

#### Minor / Suggestions

3. **Guardrail strength is reasonable but `entry_blocked` vs `overheated_entry` priority should be explicit.**
   - `entry_blocked` (price target says 关注/不操作 + 盈亏比不足) is the strongest signal and should take precedence over `overheated_entry`.
   - `overheated_entry` (BIAS extreme high alone) should only temper position advice, not the composite label, because BIAS can stay extreme for extended periods in a clean主升 trend.

4. **Composite recommendation label wording.**
   - `看多但等待入场` is acceptable for `entry_blocked`.
   - For `overheated_entry` alone, keep the original label (e.g., `看多`) and only append caution text, so clean主升 trends are not mis-labeled.

5. **Do not introduce a new global state if it can be avoided.**
   - The helper `_entry_quality_guardrail` should return a small dict or `None`, exactly like `_technical_position_guardrail`. Callers (`risk_score_section`, `composite_score_section`) then decide how to mutate rendered text. This keeps scoring math pure.

6. **Position advice capping must be explicit and reversible in tests.**
   - The proposed replacement text `趋势仍可跟踪，但当前入场质量不足，建议等待回调或盈亏比改善，仓位 5-10%` is good, but ensure it does not itself contain any `STRONG_RECOMMENDATION_PATTERNS`.
   - Current patterns include `趋势仍可跟踪`, so the proposed text would still trigger `contradiction_weak_trend_strong_recommendation` if the quality checker is expanded. Consider removing or softening that phrase in the capped advice.

7. **Composite score section: EV sentence append text should avoid contradiction.**
   - Appending `技术面提示当前不适合追高，需等待回调或盈亏比改善。` is clear and does not change score/EV numbers. Good.

### Required task adjustments

- Add `_entry_quality_guardrail(stock_raw)` in `scoring_engine.py`.
- In `risk_score_section`:
  - Evaluate `_entry_quality_guardrail` after the existing `_technical_position_guardrail` (severe/moderate takes precedence).
  - For `entry_blocked`: if original position advice is `积极配置，最大仓位 20%`, replace with `当前入场质量不足，建议等待回调或盈亏比改善，仓位 5-10%`.
  - For `overheated_entry`: cap aggressive advice to `趋势仍可跟踪，但BIAS严重正偏离，追高有风险，仓位 5-10%` (or similar) only when current advice is `积极配置，最大仓位 20%`.
  - Add a new `> **入场约束**: ...` blockquote line.
- In `composite_score_section`:
  - Only apply label tempering when `entry_blocked` is active (not for `overheated_entry` alone).
  - Replace `强烈看多` with `看多但等待入场` when `entry_blocked`.
  - Append the caution sentence to the AI recommendation paragraph.
  - Keep total score, EV, and target-price lines unchanged.
- Ensure `score/EV/risk` numeric values are never modified.

### Missing tests

1. **Unit test for `_entry_quality_guardrail` helper itself** (private helper, can be tested via direct import in tests):
   - price_target error = 关注/不操作 + reason 包含 盈亏比不足 → returns `entry_blocked`.
   - only BIAS extreme high → returns `overheated_entry`.
   - neither → returns `None`.
   - missing `price_target` / missing `indicators` → returns `None`.

2. **Integration tests in `tests/reporter/test_scoring_engine_risk.py`:**
   - `entry_blocked` caps aggressive position advice to the new conservative text.
   - `entry_blocked` does not change `风险等级` numeric value.
   - `entry_blocked` does not change risk factor table.
   - `entry_blocked` with already conservative advice (`建议减仓或不买入`) is left unchanged.
   - `overheated_entry` alone caps only aggressive advice.
   - `overheated_entry` alone does NOT temper the composite label (but this is composite section behavior; still worth an end-to-end assertion if feasible).
   - Severe `_technical_position_guardrail` still takes precedence when both severe trend weakness and `entry_blocked` are present.
   - No `STRONG_RECOMMENDATION_PATTERNS` match in guarded output.

3. **Tests in `tests/reporter/test_composite_score_renderer.py` or a new focused test file:**
   - `entry_blocked` replaces `强烈看多` with `看多但等待入场`.
   - `entry_blocked` keeps score `7.5/10` and EV `+10.25%` text unchanged.
   - `entry_blocked` appends caution sentence in the AI recommendation block.
   - `overheated_entry` alone keeps original `强烈看多` / `看多` label.
   - Missing `stock_raw["technical"]["price_target"]` does not crash renderer.

4. **Regression tests:**
   - Existing severe/moderate guardrail tests in `test_scoring_engine_risk.py` continue to pass.
   - Black sesame / 中简科技 / 圣邦股份 report generation paths are not broken.

### check_report_quality.py 建议

- **This stage**: do **not** modify `check_report_quality.py`.
- The guardrail is a renderer-level wording fix; once implemented, the generated report will no longer contain the contradiction string `强烈看多` + `关注/不操作`/`盈亏比不足`, so no new quality rule is strictly necessary for the immediate goal.
- **Next stage**: after the renderer fix is verified on real reports, consider adding a contradiction rule that flags the co-occurrence of `STRONG_RECOMMENDATION_PATTERNS` with `关注/不操作` / `盈亏比不足` / `BIAS.*严重正偏离`. That rule will act as a regression guard and can be added independently.
- Keeping the two changes separate reduces the risk of the quality checker producing false positives before the renderer behavior is stable.
