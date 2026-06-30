# Verified Claim Summary Section Design

Date: 2026-06-14

## Goal

Add a read-only report subsection that surfaces verified/supported claim verification results in the fundamental report body.

Current issue:

- `claim_risk_signal_skill` can already use verified official evidence to score structured risk signals.
- `DeepAnalysisRenderer` can still show fallback text such as "基本面 LLM 合成未启用或未产生有效输出".
- This makes reports look inconsistent: risk scoring has official support, while the deep-analysis body does not show the same verified fact base.

The new section should make verified official facts visible without changing LLM synthesis, scoring, citations, or Agent-Reach isolation.

## Proposed Output

Insert a subsection in `## 四、深度分析`, before `### 4.1 产业逻辑与竞争格局`:

```markdown
### 官方事实核验摘要

> 以下仅展示已被高信用来源验证或支撑的事实，不新增编号引用，不直接参与综合评分或最终建议。

| 结论 | 核验状态 | 支撑来源 | 置信度 |
|------|----------|----------|--------|
| 2026年第一季度营业收入下降约50%-60% | verified | 中简科技2026年第一季度报告 | 84 |
| 研发费用同比增长约175%-185% | verified | 中简科技2026年第一季度报告 | 84 |
```

If there are no verified/supported claims, render nothing.

## Data Source

Use existing `claim_verification_summary` from `SynthesisSkill`.

Expected shape is the sanitized summary returned by `summarize_claim_verification_plan()`:

- `verified`: list of claim summaries
- `supported`: list of claim summaries
- each row may include `claim_text`, `status`, `verified_by_titles`, `confidence`, `reason`

Do not rebuild claim verification inside the renderer. The renderer should only consume data already present in ctx.

## Scope

Allowed implementation surface:

- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- optional implementation notes under `docs/agent_workflow/`

Do not modify:

- `KnowledgeSynthesizer`
- `synthesis_skills.py`
- `claim_verification.py`
- `claim_risk_signals.py`
- `scoring_engine.py`
- `risk_renderer.py`
- Agent-Reach skills
- config, knowledge, reports, data/raw, except natural runtime outputs during validation

## Rendering Rules

1. Render only `verified` and `supported` claims.
2. Exclude `unverified`, `needs_review`, `contradicted`, malformed, or empty rows.
3. Limit rows to 6 total, preserving summary order: verified first, then supported.
4. Strip Markdown citation markers such as `[1]` and `[^1]`.
5. Strip or neutralize URLs in displayed titles; use short source titles only.
6. Do not display Agent-Reach URLs or `AgentReach(web)` labels.
7. Escape table pipes.
8. If `verified_by_titles` is missing, render `高信用来源` as the source label.
9. This section must not add `[^n]` numbered citations.
10. This section must not mutate `core_facts`, `synthesis`, `structured_risk_signals`, or score inputs.

## Placement

`DeepAnalysisRenderer.render()` should append sections in this order:

1. `## 三、核心事实基座`
2. `## 四、深度分析`
3. `### 官方事实核验摘要` if available
4. existing 4.1 / 4.2 / 4.3 subsections
5. global citation source list

This keeps the section near fundamental discussion while preserving Agent-Reach as a separate evidence-observation section later in the report.

## Failure Modes

- Claim verification disabled: no section.
- Summary absent or malformed: no section, no exception.
- Only low-credit/unverified claims: no section.
- Evidence titles include URLs or citation markers: sanitize before rendering.
- Official claims are present but LLM synthesis fallback text remains: the summary section should still render, making official facts visible even when full LLM synthesis did not run.

## Tests

Add focused tests in `tests/reporter/test_deep_analysis_renderer.py`:

1. renders official fact summary for verified claims.
2. includes supported claims after verified claims.
3. does not render section when summary is absent or empty.
4. excludes unverified/needs_review claims.
5. strips `[1]` / `[^1]` markers from claim text and source titles.
6. escapes pipes in claim text/source titles.
7. caps rows at 6.
8. does not output `AgentReach`, raw `http`, or numbered citation markers inside this section.
9. still renders when synthesis uses fallback text.

Runtime validation after implementation:

- Run focused renderer tests.
- Run `cd scripts && python3 run_中简科技.py --fast-test`.
- Run `python3 scripts/check_report_quality.py reports/中简科技_20260614.md`.
- Inspect `reports/中简科技_20260614.md`:
  - `### 官方事实核验摘要` appears.
  - It shows the two verified claim-risk bridge facts.
  - Risk section remains unchanged except natural report variability.
  - No Agent-Reach numbered references appear.

## Acceptance Criteria

- Focused tests pass.
- 中简科技 fast-test report passes quality check.
- The new section is read-only and does not alter risk score, technical score, EV, or final recommendation logic.
- No network/browser/CDP/Xueqiu detail crawling is introduced by the implementation.

## Round 1 Feedback

- **Status:** Ready to implement (minor test additions before or with implementation).

- **Findings**
  - **Agent-Reach 隔离**：安全。renderer 只消费 `SynthesisSkill` 已写入 ctx 的 `claim_verification_summary`，不重建 plan、不调用 Agent-Reach skills、不访问 knowledge/外部 URL，不写入 `core_facts`/`synthesis`/`structured_risk_signals`。
  - **不误导为引用或合成事实**：明确。渲染规则禁止输出 `[^n]`，且仅展示 `verified`/`supported` 声明；附注文字已说明“不新增编号引用，不直接参与综合评分或最终建议”。
  - **不影响评分/技术/EV/最终建议**：明确为 read-only display layer，不修改 score inputs。
  - **数据来源合理**：仅消费 `ctx["claim_verification_summary"]`，符合 design 要求。
  - **中简科技场景足够**：当官方公告验证了低信用社区 claim（如 Q1 营收下降 50%-60%、研发费用同比大增），该摘要可在 LLM 合成降级时仍然展示已核验事实，填补当前不一致。
  - **依赖说明**：`claim_verification_summary` 仅在 `config/stocks.json` 中 `claim_verification.enabled=true` 时由 `SynthesisSkill` 生成。若仅开启 `claim_verification.risk_signals` 而未开启 `enabled`，本小节不会渲染；这与当前设计一致，但实现/文档中应明确说明。

- **Missing tests**
  - Malformed `claim_verification_summary`（缺少 `verified_claims`、值非 list、字段类型异常）应静默不渲染，不抛异常。
  - `verified_by_titles` 缺失时回退为 `高信用来源`。
  - `verified_by_titles` 中包含 `AgentReach(web)` 标签或 `http://...` URL 时的清洗/隐藏。
  - `contradicted`、`malformed`、空行等状态被排除。
  - `confidence` 为 `None`/字符串/负数时的健壮性。
  - 渲染后 `core_facts` 与 `synthesis` 不被 mutate。

- **Required adjustments**
  - 在 `tests/reporter/test_deep_analysis_renderer.py` 中补全上述 missing tests。
  - 保持 `DeepAnalysisRenderer.required_keys()` 不变（仍为 `["stock_name", "synthesis"]`），`claim_verification_summary` 作为可选字段，缺失时直接跳过本小节。
  - 在实现 notes 中记录：本小节仅在 `claim_verification.enabled=true` 时可用；与 `claim_risk_signals.risk_signals` 是独立开关。

- **是否需要 R2:** 否。设计已满足安全和清晰要求，可直接进入 implementation task；缺失的测试属于实现阶段补充项，不阻塞设计锁定。
