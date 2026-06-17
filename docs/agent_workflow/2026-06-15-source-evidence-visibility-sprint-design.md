# Source Evidence Visibility Sprint Design

Date: 2026-06-15

## Goal

Make the upgraded evidence pipeline visible in single-stock reports without changing scoring, risk, technical analysis, EV, LLM synthesis, or final recommendation logic.

The current Source Intake pipeline already collects and writes evidence notes for:

- high-credit official announcements (`exchange_announcement`, credit 95, `confirmed_fact`)
- medium-credit Eastmoney stock news (`news`, credit 60, `professional_observation`)
- medium-credit Eastmoney broker research summaries (`research_report`, credit 65, `professional_observation`)

Runtime validation on three stocks is enough for this phase:

- 黑芝麻智能: official web / Agent-Reach path
- 中简科技: official announcement validates lower-credit claims
- 圣邦股份: cninfo announcements + Eastmoney news + Eastmoney research reports

Do not expand to a fourth stock in this sprint.

## Non-Goals

- Do not modify `KnowledgeSynthesizer` prompts or citation logic.
- Do not modify `scoring_engine.py`, risk scoring, EV scoring, technical analysis, or position advice rules.
- Do not promote Eastmoney news or broker research to official facts.
- Do not download broker research PDFs.
- Do not add social media ingestion yet; only leave it as the next-phase candidate.
- Do not run Xueqiu detail/CDP scraping or refresh Zhihu collection.

## Proposed Changes

### 1. Source Intake Evidence Overview Renderer

Add a read-only report section that renders when `source_intake_enabled=True` and Source Intake produced items.

Recommended placement:

- after `DeepAnalysisRenderer`
- before `AgentReachEvidenceRenderer` and `RiskRenderer`

The section should be independent from Agent-Reach. It should use existing ctx values:

- `source_intake_status`
- `source_intake_summary`
- `source_intake_items`
- `external_evidence_keep_items`
- `external_evidence_demote_items`

Suggested section title:

```markdown
## Source Intake 分层证据观察
```

Suggested disclaimer:

```markdown
> 本节仅展示结构化外部证据来源分层，不参与综合评分、风险评分、技术面判断或最终建议。
> 官方公告可用于事实确认；新闻与券商研报仅作为专业观察或背景线索，不等同于官方事实。
```

### 2. Credit-Tier Summary

Render a compact table grouped by `source_type`:

| 来源类型 | 数量 | 信用等级 | 事实用途 | 状态 |
|----------|------|----------|----------|------|
| 官方公告 | 11 | 高信用 95 | confirmed_fact | 可用于事实确认 |
| 东方财富新闻 | 10 | 中信用 60 | professional_observation | 背景资讯 |
| 券商研报摘要 | 8 | 中信用 65 | professional_observation | 专业观察 |

Rules:

- If a bucket is absent, do not render a zero row unless useful for status reporting.
- Use normalized labels, not raw internal names, for user-facing text.
- Unknown source types render as `其他来源` with neutral wording.
- Never show `confirmed_fact` for `news` or `research_report`.

### 3. Representative Evidence Rows

Render at most 6 representative items, prioritizing:

1. official announcements
2. broker research
3. news

Columns:

| 时间 | 来源层级 | 证据摘要 | 信用 | 用途 |

Constraints:

- Use title only or short sanitized content excerpt.
- Strip `[^n]`, `[n]`, raw `AgentReach(...)`, and raw long URLs from visible text.
- Links may be included as plain source URLs only inside the Source Intake section; do not create numbered citations.
- Do not mutate the item objects or ctx.

### 4. Verified Claim Summary

`DeepAnalysisRenderer` already has a verified claim summary hook via `claim_verification_summary`.

In this sprint:

- verify it still only displays `verified` / `supported` claims
- verify malformed summary rows are skipped
- verify it does not mutate `core_facts` or `synthesis`
- do not redesign it unless tests reveal a blocker

### 5. Runtime Validation

After implementation, run focused tests first, then validate existing single-stock reports:

- `scripts/run_黑芝麻智能.py --fast-test`
- `scripts/run_中简科技.py --fast-test`
- `scripts/run_圣邦股份.py --fast-test`

For each generated Markdown:

- run `scripts/check_report_quality.py`
- confirm no Source Intake / Agent-Reach numbered citation pollution
- confirm scoring, risk, EV, technical, and final recommendation are not unexpectedly changed
- confirm Source Intake section appears only for stocks with Source Intake enabled
- confirm Agent-Reach section remains separate

## Required Tests

Add focused tests for the new renderer:

- disabled Source Intake renders nothing
- source_intake enabled but empty renders nothing or a compact empty status without warnings
- official announcements render as high-credit confirmed facts
- news and research render as medium-credit professional observations
- research/news never render as confirmed facts
- representative rows are capped
- citation markers and raw long URLs are sanitized
- renderer does not mutate ctx or `SynthesisItem.extra`

Add assembly integration tests:

- new renderer is wired after deep analysis and before Agent-Reach/risk
- report still renders when Source Intake fields are absent
- Agent-Reach-only reports do not show Source Intake section

Runtime checks should be recorded in implementation notes.

## Acceptance Criteria

- Focused tests pass.
- Three-stock fast-test runtime validation completes or any environment blockers are explicitly recorded.
- Source Intake section is visible in 中简科技 / 圣邦股份 reports when enabled.
- 黑芝麻智能 Agent-Reach evidence remains isolated.
- No scoring/risk/EV/technical/prompt logic is changed.
- No Xueqiu detail/CDP/Chrome control is used beyond normal PDF generation.
- No broker research PDF download is introduced.

## Round 1 Feedback

- **Status**: Ready to implement
- **R2 Needed**: No

### Findings by severity

#### Info / Clarifications

1. **Ctx keys are valid and no pipeline changes are needed.**
   - `source_intake_status`, `source_intake_items`, and `source_intake_summary` are populated by `scripts/utils/report_skills/a_stock_source_intake_skill.py`.
   - `external_evidence_keep_items` / `external_evidence_demote_items` are populated by `scripts/utils/report_skills/source_intake_merge_skill.py`.
   - The new renderer can read these keys directly; no new skill wiring is required.

2. **Placement between deep analysis and Agent-Reach/risk is safe.**
   - Keeping the new section read-only and downstream of `DeepAnalysisRenderer` prevents it from influencing synthesis, scoring, or recommendations.
   - It also keeps Agent-Reach evidence as a separate, later section, preserving the isolation required for 黑芝麻智能.

3. **Scope is correctly constrained to display-only.**
   - The design does not modify `KnowledgeSynthesizer`, `scoring_engine.py`, technical analysis, EV, risk, or position advice.
   - The disclaimer explicitly states the section does not participate in scoring or recommendations.

#### Minor / Suggestions

4. **`assembly_skills.py` must be updated to register the new renderer.**
   - The design implies this but does not explicitly list it as a required file change.
   - `ReportAssemblySkill.RENDERERS` must insert the new renderer between `deep_analysis` and `agent_reach_evidence`; otherwise the section will not appear in Markdown output.
   - This is a necessary and allowed change for the sprint.

5. **HTML dashboard scope should be documented explicitly.**
   - `ReportAssemblySkill._assemble_html()` calls `HTMLDashboardRenderer` independently.
   - If the Source Intake section is intentionally Markdown-only for this sprint, state that in the implementation notes to avoid expectation mismatch.

6. **Report header data sources may need a minor update.**
   - `ReportAssemblySkill._data_sources()` currently appends "Agent-Reach外部检索" only when Agent-Reach is enabled.
   - Consider appending a Source Intake label (e.g., "Source Intake外部证据") when `source_intake_enabled=True` and items exist. This is cosmetic and optional.

7. **Credit-tier summary should be dynamic, not hard-coded.**
   - The example table uses fixed counts (11/10/8). Implement it by grouping `source_intake_items` by `source_type` and reading `source_credit` / `verification_status` from `item.extra`.
   - This guarantees correctness across stocks and avoids drift if max_items config changes.

8. **Sanitization can reuse existing patterns.**
   - `AgentReachEvidenceRenderer` already strips Jina metadata, `[^n]` / `[n]` markers, `AgentReach(...)` text, and escapes table cells.
   - Consider whether to extract shared helpers or duplicate the logic in the new renderer. Duplication is acceptable for a small sprint if tests cover both.

9. **Research report links must remain plain source URLs.**
   - The design allows plain source URLs inside the Source Intake section. Ensure these come from `item.url` and do not trigger broker research PDF downloads, consistent with the non-goal.

10. **Clarify distinction from DeepAnalysisRenderer's verified-claim summary.**
    - `DeepAnalysisRenderer` already renders an "官方事实核验摘要" subsection from `claim_verification_summary`.
    - The new Source Intake section shows raw evidence tiers. Make sure the two disclaimers do not contradict each other and that readers understand raw evidence ≠ verified claim.

#### Medium / Worth addressing before implementation

11. **Renderer must be strictly read-only.**
    - The design already says "do not mutate the item objects or ctx". Tests should enforce this explicitly: assert that `ctx` dict contents and item list identities remain unchanged after `render()`.

12. **Empty-state behavior.**
    - When Source Intake is enabled but produces zero items, prefer returning an empty string rather than an empty-status block, to keep reports clean. If a compact status is rendered, keep it to one line.

### Required task adjustments

- Add a new renderer file, e.g., `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`.
- Register it in `ReportAssemblySkill.RENDERERS` between `deep_analysis` and `agent_reach_evidence`.
- Map internal `source_type` values to user-facing labels:
  - `exchange_announcement` → `官方公告`
  - `news` → `东方财富新闻`
  - `research_report` → `券商研报摘要`
  - unknown → `其他来源`
- Build the credit-tier summary dynamically from `source_intake_items` using `item.extra["source_credit"]` and `item.extra["verification_status"]`.
- Render at most 6 representative rows, ordered by credit descending (official announcements first, then research reports, then news).
- Sanitize visible text: strip `[^n]`, `[n]`, `AgentReach(...)`, collapse whitespace, escape `|` in table cells.
- Include the proposed disclaimer verbatim.
- Do not emit numbered citations or `[^n]` markers.
- Keep score/risk/EV/technical/recommendation logic untouched.

### Missing tests

1. **Unit tests for the new renderer:**
   - `source_intake_enabled=False` returns empty string.
   - enabled but empty items returns empty string.
   - `exchange_announcement` renders as high-credit / `confirmed_fact`.
   - `news` renders as medium-credit / `professional_observation`.
   - `research_report` renders as medium-credit / `professional_observation`.
   - `news` / `research_report` never show `confirmed_fact`.
   - representative rows capped at 6.
   - citation markers and raw long URLs are sanitized in visible text.
   - unknown `source_type` falls back to `其他来源`.
   - renderer does not mutate `ctx` or `SynthesisItem` objects.

2. **Assembly integration tests:**
   - new renderer appears after `deep_analysis` and before `agent_reach_evidence` in `ReportAssemblySkill.RENDERERS`.
   - report renders successfully when Source Intake fields are absent from `ctx`.
   - Agent-Reach-only reports do not show the Source Intake section.

3. **Runtime validation checks:**
   - `scripts/run_圣邦股份.py --fast-test` generates a report containing the new section.
   - `scripts/run_中简科技.py --fast-test` generates a report containing the new section.
   - `scripts/run_黑芝麻智能.py --fast-test` does **not** show the Source Intake section.
   - `scripts/check_report_quality.py` passes on all three reports.
   - score/risk/EV/technical/final recommendation remain stable relative to baseline.

### Blocker

None. The design is safe to implement as a standalone, display-only renderer change.
