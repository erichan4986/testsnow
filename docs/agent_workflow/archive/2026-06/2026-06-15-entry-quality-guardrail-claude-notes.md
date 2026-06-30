# Entry Quality Guardrail Implementation Notes

Date: 2026-06-15

Implementer: Codex

## Files Changed

- `scripts/utils/reporter/scoring_engine.py`
  - Added `_entry_quality_guardrail(stock_raw)`.
  - Added entry-quality capping in `risk_score_section()`.
  - Added entry-quality recommendation tempering in `composite_score_section()`.
- `tests/reporter/test_scoring_engine_risk.py`
  - Added helper and risk-section coverage for `entry_blocked` and `overheated_entry`.
  - Added precedence coverage for severe technical guardrail.
- `tests/reporter/test_scoring_engine_contract.py`
  - Added composite-score recommendation coverage.

## Behavior

`entry_blocked`:

- Trigger: `stock_raw["technical"]["price_target"]["error"] == "关注/不操作"` and reason contains `盈亏比不足`.
- Risk section:
  - Keeps risk score unchanged.
  - Caps only aggressive `积极配置，最大仓位 20%` to `当前入场质量不足，建议等待回调或盈亏比改善，仓位 5-10%`.
  - Adds `> **入场约束**`.
- Composite section:
  - Keeps total score and EV unchanged.
  - Replaces `强烈看多` / `看多` label with `看多但等待入场`.
  - Adds caution text about waiting for pullback or improved risk/reward.

`overheated_entry`:

- Trigger: `bias_5_extreme_high` or `bias_10_extreme_high`.
- Risk section only:
  - Caps aggressive position advice to `BIAS严重正偏离，追高风险较大，仓位 5-10%`.
  - Does not temper the composite recommendation label.

Existing severe/moderate technical guardrails remain higher priority.

## Tests

```bash
python3 -m pytest tests/reporter/test_scoring_engine_risk.py tests/reporter/test_scoring_engine_contract.py -q
# 40 passed

python3 -m pytest tests/reporter/test_scoring_engine_risk.py tests/reporter/test_scoring_engine_contract.py tests/reporter/test_risk_renderer.py tests/reporter/test_report_quality.py tests/reporter/test_run_shengbang_entry.py -q
# 56 passed
```

## Local Render Check

Used a minimal Shengbang-like `stock_raw` with:

- `price_target.error = 关注/不操作`
- `reason` containing `盈亏比不足`
- BIAS extreme high
- strong positive EV fixture

Output:

- `### 综合评分: 7.5/10 | EV: +10.25%（看多但等待入场）`
- AI recommendation uses `看多但等待入场`, not `强烈看多`.
- Risk score remains unchanged.
- Position advice becomes `当前入场质量不足，建议等待回调或盈亏比改善，仓位 5-10%`.

## Runtime Validation

Full `run_圣邦股份.py --fast-test` was not rerun in this implementation step to avoid unnecessary LLM/PDF runtime cost. The next runtime validation should regenerate the Shengbang report and confirm:

- No `强烈看多` when `price_target.error=关注/不操作` and `盈亏比不足`.
- No `积极配置，最大仓位 20%` under blocked entry quality.
- Score/EV/risk numeric values remain unchanged.

## Blockers

None.
