# Deep Analysis Prose Structure Design

Date: 2026-06-30

## Status

Revised after Round 1 review. This design follows the current `formal_first` source boundary:

- 4.1-4.3 are canonical main analysis from formal / professional sources.
- 4.4 is display-only external viewpoints and watch variables.
- Social / curated external material must not leak into scoring, risk, summary, target price, or 4.1-4.3 canonical synthesis.

## Problem

The latest `reports/中际旭创_20260630.md` proves that `formal_first` source separation works, but the 4.1-4.3 prose is still not publication-grade.

Observed issues:

- 4.1 / 4.2 / 4.3 repeat the same themes: AI算力, 800G, 1.6T, 硅光, NPO/CPO.
- Paragraphs are too long; several paragraphs exceed 300-500 Chinese characters.
- Sentences are dense and often try to carry multiple claims at once.
- Template-like transitions appear repeatedly, such as “综合来看”, “展望未来”, “与此同时”, “结构性繁荣”.
- Some wording is too assertive for mixed formal/news/research sources, such as “近乎垄断级”.
- 4.4 citations are traceable but repeated by URL, making the source list verbose.

The direction is right, but the report still reads like a raw LLM synthesis rather than an edited research note.

## Goals

1. Make 4.1-4.3 section boundaries sharper.
2. Reduce cross-section repetition without losing necessary context.
3. Prefer compact tables for financial path, bull/bear debate, catalyst timeline, and watch variables.
4. Keep every material claim cited.
5. Preserve `formal_first` and 4.4 display-only isolation.
6. Make prose-quality regressions measurable with a checker before and after prompt/template changes.

## Non-goals

- Do not change scoring, risk scoring, technical analysis, target price, or recommendation logic.
- Do not expand social sources into 4.1-4.3.
- Do not call LLM/API as part of unit tests.
- Do not force 4.4 for stocks without enough high-quality external viewpoints.
- Do not make prose warnings fail the production report pipeline in the first implementation.

## Current Guardrail

Codex added an advisory prose checker:

- `scripts/utils/report_prose_quality.py`
- `scripts/check_report_prose_quality.py`
- `tests/reporter/test_report_prose_quality.py`

It currently flags:

- `long_paragraph`
- `long_sentence`
- `repeated_theme_across_sections`
- `aiish_transition_overuse`
- `strong_assertion_wording`
- `duplicate_4_4_citation_source`

Example run on `reports/中际旭创_20260630.md` flags long paragraphs in 4.1-4.3, repeated AI算力/800G/1.6T/NPO, AI-ish transitions, and duplicate 4.4 citation URLs. This checker should become the acceptance baseline for the next implementation, but remain warning-only for now.

## Proposed Section Contract

### 4.1 产业逻辑与竞争格局

Purpose: explain why the industry/company matters structurally.

Should contain:

- Industry demand driver and technology route.
- Competitive positioning and direct competitors.
- Supply-chain / technology architecture nuance.
- One compact competition or technology-route table when source material supports it.

Should avoid:

- Repeating quarterly revenue/profit numbers except one cited sentence if needed.
- Funding, financing balance, valuation target price, or near-term trading sentiment.
- Full re-explanation of 800G/1.6T in every paragraph.

Target shape:

- 2-3 short paragraphs, each under 260 chars.
- Optional table:
  `| 维度 | 中际旭创 | 主要对手/行业状态 | 判断 | 来源 |`

### 4.2 业绩路径与多空分歧

Purpose: translate sources into company financial path and debate.

Should contain:

- Latest revenue/profit/margin/order path as a compact evidence table.
- Bull / bear disagreement table.
- A short synthesis paragraph after the table.

Should avoid:

- Rebuilding industry history already covered in 4.1.
- Repeating funding sentiment or trading pressure.
- Assertive conclusions such as “确定性极强” unless backed by official formal disclosures.

Target shape:

- Table first:
  `| 变量 | 当前证据 | 对业绩路径的含义 | 需跟踪 | 来源 |`
- Then:
  `| 多方观点 | 依据 | 反方约束 | 关键验证点 |`
- 1-2 short paragraphs under 260 chars each.

### 4.3 资金面与催化剂时间线

Purpose: separate market behavior and next verification points from fundamentals.

Should contain:

- Funding / positioning / sentiment only when supported by formal market data or formal/professional sources.
- A timeline table for upcoming catalysts.
- Clear distinction between confirmed events and watch variables.

Should avoid:

- Reusing 4.1 industry setup or 4.2 earnings path as filler.
- Treating social rumors as canonical funding evidence.

Target shape:

- Table:
  `| 时间点 | 催化剂/事件 | 当前状态 | 验证指标 | 来源 |`
- 1-2 short paragraphs under 260 chars each.

### 4.4 精选外部观察（Preview）

Purpose: display-only external viewpoints, differentiated from canonical analysis.

Should contain:

- 2-4 narrative paragraphs or a watch-variable table when claims are heterogeneous.
- Source labels by type: 微信公众号精选观察 / 雪球专栏观察 / 雪球评论观察 / 知乎精选观察.
- Duplicate source URLs should be merged in the citation list.

Should avoid:

- Feeding claims into scoring/risk/final recommendation.
- Repeating official financial facts already covered by 4.1-4.3.

## Round 1 Design Delta

Accepted from `/tmp/deep_analysis_prose_structure_review_round1.md`:

- Phase B must not be prompt-only. The design now requires prompt contract updates plus deterministic post-processing / sanitization.
- Section boundaries must be explicit negative constraints in the actual prompts, not only prose in this design.
- 4.4 citation de-duplication belongs in the renderer/display layer; narrative JSON should keep original audit mappings.
- Focused tests must be expanded before Phase B/C/D implementation.

Deferred:

- Sector-aware repeated-theme dictionaries for the prose checker remain advisory and can follow after validation on 中际旭创 / 黑芝麻智能 / 圣邦股份.
- Promoting prose warnings into the main hard quality gate is deferred until thresholds prove stable.

Rejected:

- None.

## Implementation Strategy

### Phase A: Checker Baseline

Keep the advisory prose checker and add it to the manual release-candidate checklist.

Acceptance:

- `python3 scripts/check_report_prose_quality.py reports/中际旭创_20260630.md` returns warning-only output.
- `--fail-on-warning` can be used locally to enforce stricter review, but CI does not use it yet.

### Phase B: Prompt Contract Update + Deterministic Sanitizer

Update `KnowledgeSynthesizer` theme prompts to ask for:

- shorter paragraphs,
- no cross-section repetition,
- table-first structures for 4.2 and 4.3,
- explicit section boundaries,
- source-confidence wording,
- no generic transitions.

This phase must also add deterministic post-processing / sanitization after LLM output and before renderer consumption. Prompt-only changes are not sufficient.

Required sanitizer responsibilities:

- Preserve citation markers and fail closed if citation markers become unparseable.
- Keep table rows intact and avoid treating Markdown table rows as prose paragraphs.
- Normalize overlong prose blocks where safe, or emit advisory warnings if deterministic splitting would risk citation drift.
- Guard against malformed Markdown tables if table-first output is requested.
- Keep source-credit / formal-first constraints unchanged.

Do not change LLM provider behavior in this phase.

Acceptance:

- Unit tests verify prompt text contains section-boundary and prose constraints.
- Unit tests verify sanitizer preserves citation markers in paragraphs and tables.
- No LLM/API calls in unit tests.
- A local report run on 中际旭创 shows fewer prose warnings than the current baseline.

### Phase C: Renderer-Safe Table Support

If LLM already emits Markdown tables correctly, no renderer change is required. If source citation formatting breaks around tables, adjust only the final Markdown sanitizer / citation handling.

Acceptance:

- Tables render in Markdown and HTML without losing citations.
- Existing citation-aware gates still pass.

### Phase D: 4.4 Citation Merge

Add a small renderer-side merge for duplicate 4.4 citation URLs/titles. Do not alter narrative JSON production: the JSON keeps original per-claim / per-paragraph citation IDs for auditability, while the renderer remaps duplicated display footnotes to a single visible source entry.

Acceptance:

- Same URL appears once in 4.4 source list.
- Body footnotes remain resolvable.
- Display-only isolation gate still passes.

## Failure Modes And Tests

### Failure: prompt reduces content too much

Symptom: 4.1-4.3 become short but shallow.

Tests / checks:

- Existing report quality still requires deep analysis sections.
- Manual sample run must confirm each section has substantive formal-source citations.

### Failure: tables lose citations

Symptom: facts appear in tables without `[^n]`, or footnotes no longer map to source list.

Tests / checks:

- Add renderer or synthesis tests for table rows containing citation markers.
- Run `tools/ci_grep_gates.sh`.

### Failure: section boundaries become too strict

Symptom: 4.2 lacks industry context needed to interpret financial variables, or 4.3 lacks enough catalyst content.

Tests / checks:

- Prose checker should warn on repetition, not ban necessary one-line context.
- Human review of 中际旭创 and 圣邦股份 outputs.

### Failure: checker overfits 中际旭创

Symptom: warnings are useful for optical-module stocks but noisy for analog-chip or HK stocks.

Tests / checks:

- Run checker on 中际旭创, 黑芝麻智能, 圣邦股份.
- Keep warnings advisory until thresholds prove stable.

### Failure: 4.4 citation merge breaks footnotes

Symptom: body has `[^n]` that no longer appears in source list.

Tests / checks:

- Add deep analysis renderer test for duplicate 4.4 sources.
- Confirm all displayed body footnotes have a source-list entry.

### Failure: sanitizer corrupts LLM tables

Symptom: Markdown table pipes or citation markers inside table cells are escaped incorrectly, causing broken HTML output or missing citations.

Tests / checks:

- Add tests where 4.2/4.3 table rows include `[^n]`.
- Confirm prose checker ignores table rows for long-paragraph warnings.
- Confirm renderer keeps citation markers in table cells.

## Open Questions For Review

1. Should Phase B update only `KnowledgeSynthesizer` prompts, or should it add deterministic post-processing for table/paragraph shape?
2. Should 4.2 always contain tables, or only when enough financial variables are present?
3. Should prose warnings remain separate from `check_report_quality.py`, or should selected warnings be folded into the main quality checker later?
4. Should duplicate 4.4 citations merge by URL only, or by `(source_label, author, title)` when URL is missing?

## Recommended Next Step

Run Round 1 design review before changing LLM prompts. If there are no blockers, implement Phase B + targeted tests first, then validate with one 中际旭创 formal_first report run.

Updated recommendation after Round 1 review:

1. Implement Phase A missing tests and Phase D renderer-side duplicate citation merge first.
2. Revise Phase B implementation task to include prompt updates plus deterministic sanitizer.
3. Only after Phase B tests pass, run one real 中际旭创 report to compare prose checker warning counts against the current baseline.

## Phase B Closeout

Status: accepted for current release candidate.

The post-review implementation and rerun validation addressed the blocking
issues found in `/tmp/phase_b_deep_analysis_prose_validation.md`:

- `KnowledgeSynthesizer` now normalizes LLM-emitted plain source markers such as
  `[1]` / `[23]` into renderer-compatible footnotes `[^1]` / `[^23]`.
- The theme prompt explicitly asks for `[^n]` citation format and forbids
  assistant role prefaces such as “好的，作为资深分析师”.
- The deterministic sanitizer removes common opening role-play prefaces while
  preserving substantive analysis, Markdown tables, and citation markers.
- The 4.4 renderer keeps the audit JSON untouched but merges duplicate display
  citations by URL, or by `(source, author, title)` when URL is missing.
- After citation remapping, adjacent duplicate body footnotes are collapsed so
  output such as `[^1][^1][^3][^1]` does not appear in the report.

Real-entry rerun validation in
`/tmp/phase_b_deep_analysis_prose_fix_rerun_validation.md` covered 中际旭创,
圣邦股份, and 黑芝麻智能:

- 4.1-4.3 contained zero naked `[n]` references.
- 4.1-4.3 retained parseable `[^n]` references and per-section source lists.
- LLM role-play prefaces did not appear.
- 4.4 repeated footnote clusters did not appear.
- Display-only isolation remained intact.
- `check_report_quality.py`, `check_report_prose_quality.py`,
  `tools/ci_grep_gates.sh`, and `git diff --check` passed in the rerun.

### Citation Source Semantics

This phase keeps two citation layers intentionally separate:

- 4.1-4.3 citations are canonical main-analysis citations. Under
  `formal_first`, they should resolve to formal or professional sources such as
  company announcements, periodic reports, broker research, industry research,
  policy/news materials, and other accepted canonical source-intake items.
- 4.4 citations are display-only external viewpoint citations. They may point to
  微信公众号精选观察、雪球专栏观察、雪球评论观察、知乎精选观察, or similar curated
  observation labels, but they must not affect scoring, risk scoring, executive
  summary, target price, or final recommendation.
- The renderer may merge duplicated 4.4 display footnotes for readability, but
  the underlying narrative/digest JSON keeps original claim-to-source mappings
  for auditability.

Known residual warnings are advisory rather than release blockers:

- `repeated_theme_across_sections` can still fire when the same industry term is
  genuinely needed across sections.
- Occasional strong wording such as “必然” should be polished when visible, but
  it is not a citation or isolation failure.
