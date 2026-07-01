# Deep Analysis Topic Ownership And Repetition Control Design

Date: 2026-07-01

## Status

Revised after read-only design review. No implementation is included in this document.

This design continues the current report-quality line after:

- `formal_first` source boundary: 4.1-4.3 use formal / professional sources; social / WeChat / Xueqiu / Zhihu external viewpoints mainly live in 4.4.
- Phase B prose structure work: `KnowledgeSynthesizer` already asks for shorter paragraphs, table-friendly output, `[^n]` citation format, and no assistant role preface.
- Recommendation / EV / entry / risk consistency work: report recommendation and risk position advice now share a central decision object.

## Problem

The remaining visible report-quality issue is not source leakage or citation breakage. It is editorial structure.

Recent smoke runs show that the generated 4.1-4.3 sections can pass hard gates while still repeating the same themes across all three sections. Examples:

- `毛利率` appears in 4.1, 4.2, and 4.3 for 黑芝麻智能.
- `AI算力 / 800G / 1.6T / 硅光 / CPO / NPO` can appear in 4.1, 4.2, and 4.3 for 中际旭创.
- Some repetition is necessary as one-line context, but repeated full explanations make the report feel like raw LLM synthesis rather than edited research.

The current checker can detect `repeated_theme_across_sections`, but it does not explain which section owns which theme, and it cannot yet turn warnings into a stable repair strategy.

## Goals

1. Make each 4.1-4.3 section own a distinct analytical job.
2. Allow short cross-references, but prevent full theme re-expansion across sections.
3. Preserve all existing source-boundary and citation guarantees.
4. Keep the first implementation deterministic enough to test without calling LLM.
5. Reduce prose checker warnings on 中际旭创 / 黑芝麻智能 / 圣邦股份 without making sections shallow.

## Non-Goals

- Do not change scoring, recommendation, EV, risk scoring, technical indicators, or source-intake policy.
- Do not change 4.4 narrative composer behavior.
- Do not make prose warnings hard blockers in production immediately.
- Do not delete necessary one-line context just because a keyword repeats.
- Do not rely on repeated full report runs for every unit-level validation.

## Current Behavior

### Existing Prompt Layer

`scripts/utils/knowledge_synthesizer.py` already contains theme-specific prompt prefixes:

- `industry_logic`
- `fundamentals`
- `valuation_debate`
- `funding_sentiment`
- `events_catalysts`

It also passes `previous_narratives` into later themes and asks the model not to repeat facts already discussed.

However, this remains too soft:

- It does not name explicit theme ownership rules.
- It gives later sections a truncated prose excerpt, not a structured ownership ledger.
- It cannot distinguish "one-line context" from "full repeated explanation".
- It does not give the sanitizer enough structure to enforce repetition budgets.

### Existing Checker Layer

`scripts/utils/report_prose_quality.py` flags:

- long paragraphs,
- long sentences,
- AI-ish transitions,
- strong assertion wording,
- repeated themes across 4.1-4.3,
- duplicate 4.4 citation sources.

The checker currently identifies repeated terms if the same keyword appears in all three main sections. This is useful as a smoke alarm, but too coarse for implementation.

## Review Delta

Accepted review findings:

- The design must govern final report sections, not only the five internal synthesis themes.
- Abstract ownership terms must be tied to concrete keyword / topic-family maps, or the checker cannot be deterministic.
- Markdown tables should be exempt from long-prose checks, but not exempt from repetition checks.
- "One short borrowed reference" must have a numeric budget.
- LLM-generated heading levels inside 4.1-4.3 need explicit constraints because sample reports show `##` / `###` child headings inside the deep-analysis body.

Rejected:

- No aggressive deterministic deletion / movement of LLM prose in this phase. Rewriting generated facts would create citation and meaning drift.

Deferred:

- Promoting repetition warnings into hard report-quality failures. The checker remains advisory until it is validated across more sectors.

## Proposed Design

### 0. Map Internal Themes To Final Report Sections

The implementation must distinguish internal synthesis themes from final report sections.

```python
FINAL_SECTION_THEME_MAP = {
    "4.1": ["industry_logic"],
    "4.2": ["fundamentals", "valuation_debate"],
    "4.3": ["funding_sentiment", "events_catalysts"],
}
```

This matters because the reader sees only 4.1 / 4.2 / 4.3:

- 4.1 owns structural industry and competitive logic.
- 4.2 owns financial path and valuation debate. `fundamentals` and `valuation_debate` may share terms such as revenue, margin, and order visibility, but valuation debate must use them as scenario variables, not repeat the full performance path.
- 4.3 owns funding behavior and catalyst timeline. `funding_sentiment` and `events_catalysts` may share event references, but the catalyst timeline must not repeat the full market-sentiment explanation.

The prompt can still be generated per internal theme, but the ownership ledger and checker must reason at both levels:

1. internal theme ownership, and
2. final section ownership.

### 1. Add A Section Topic Ownership Contract

Introduce a small deterministic contract in `KnowledgeSynthesizer` or a nearby helper:

```python
SECTION_TOPIC_OWNERSHIP = {
    "industry_logic": {
        "owns": ["产业需求", "技术路线", "供应链位置", "竞争格局", "直接竞争对手"],
        "may_reference": ["营收", "毛利率", "订单", "资金情绪"],
        "must_not_expand": ["季度利润路径", "估值多空", "融资盘", "催化剂时间线"],
    },
    "fundamentals": {
        "owns": ["营收", "利润", "毛利率", "费用率", "订单兑现", "客户结构", "业绩指引"],
        "may_reference": ["行业景气", "技术路线", "竞争格局"],
        "must_not_expand": ["完整产业背景", "资金流", "融资余额", "交易情绪"],
    },
    "valuation_debate": {
        "owns": ["估值分歧", "多空情景", "关键验证变量", "市场预期差"],
        "may_reference": ["业绩变量", "产业变量"],
        "must_not_expand": ["产业历史", "完整财务复盘", "资金面时间线"],
    },
    "funding_sentiment": {
        "owns": ["主力资金", "融资余额", "机构/北向", "市场情绪", "短期交易结构"],
        "may_reference": ["业绩兑现", "产业催化"],
        "must_not_expand": ["完整产业技术路线", "完整业绩路径"],
    },
    "events_catalysts": {
        "owns": ["时间点", "事件", "政策催化", "业绩披露节点", "验证指标"],
        "may_reference": ["产业变量", "业绩变量"],
        "must_not_expand": ["完整产业背景", "完整业绩路径", "交易建议"],
    },
}
```

The exact terms can be tuned, but the concept should be explicit and testable.

### 2. Add A Concrete Topic-Family Map

The abstract ownership contract is not enough for deterministic checks. Add a minimal concrete topic-family map that starts with the current `THEME_TERMS` list and can be extended by sector later.

Initial cross-sector / current-report map:

```python
TOPIC_FAMILIES = {
    "高速光互连技术路线": {
        "terms": ["AI算力", "800G", "1.6T", "硅光", "CPO", "NPO", "XPO", "英伟达", "谷歌", "北美云厂商"],
        "owner_theme": "industry_logic",
        "owner_section": "4.1",
        "allowed_borrowers": {
            "fundamentals": "revenue_or_order_driver",
            "valuation_debate": "scenario_variable",
            "events_catalysts": "validation_point",
        },
    },
    "业绩质量变量": {
        "terms": ["营收", "利润", "毛利率", "费用率", "订单", "客户结构"],
        "owner_theme": "fundamentals",
        "owner_section": "4.2",
        "allowed_borrowers": {
            "valuation_debate": "valuation_variable",
            "funding_sentiment": "funding_reaction_context",
            "events_catalysts": "earnings_validation_metric",
        },
    },
    "估值与预期差": {
        "terms": ["估值", "目标价", "市盈率", "预期差", "情景"],
        "owner_theme": "valuation_debate",
        "owner_section": "4.2",
        "allowed_borrowers": {
            "funding_sentiment": "sentiment_context",
        },
    },
    "交易资金结构": {
        "terms": ["融资盘", "融资余额", "主力资金", "北向资金", "机构持仓", "卖空比例"],
        "owner_theme": "funding_sentiment",
        "owner_section": "4.3",
        "allowed_borrowers": {},
    },
    "事件催化与验证点": {
        "terms": ["半年报", "季报", "年报", "披露", "量产", "定点", "政策催化", "时间点"],
        "owner_theme": "events_catalysts",
        "owner_section": "4.3",
        "allowed_borrowers": {
            "fundamentals": "performance_context",
            "valuation_debate": "scenario_trigger",
        },
    },
}
```

Sector-specific additions should be small and explicit:

- `optical_module`: 800G / 1.6T / CPO / NPO / XPO / 硅光.
- `auto_chip`: A2000 / A1000 / L3 / L4 / Robotaxi / ASIL-D / 舱驾一体.
- `analog_chip`: 信号链 / 电源管理 / 车规 / 数据中心 / GaN / ADC.

Phase 1 should not create a large taxonomy. It should cover only the terms already causing warnings in the three sample stocks.

### 3. Build A Previous Topic Ledger Instead Of Passing Raw Previous Prose

Replace or supplement the current `previous_narratives` excerpt with a compact ledger derived from prior generated sections:

```text
已展开主题：
- 4.1 产业逻辑与竞争格局:
  - 技术路线: 800G / 1.6T / 硅光 / CPO
  - 竞争格局: 中际旭创 vs 新易盛 / 光迅科技

本节规则：
- 如果必须引用上述主题，只能用一句话说明与本节变量的关系。
- 不要再次解释技术路线背景。
- 本节应优先展开: 营收、毛利率、费用率、订单兑现、客户结构。
```

The ledger should be generated deterministically from:

- theme key,
- section title,
- keyword matches,
- optional table headers / headings from previous section output.

It does not need to perfectly understand semantics in Phase 1. It only needs to provide a clear, compact prompt hint and later support tests.

### 4. Add A Repetition Budget Rule

Define a section-level rule:

- Owned terms may appear freely in their owner section.
- Borrowed terms may appear in non-owner sections only if:
  - they appear in at most one prose sentence under 110 Chinese characters, or
  - they are part of a table row explaining impact on that section's owned variable.
- The same non-owned term should not appear in more than one paragraph in the borrower section.
- The same non-owned topic family should not appear in both multiple prose paragraphs and multiple table rows in the same borrower section.
- If a borrowed topic family appears in tables, it should be tied to the current section function:
  - 4.2: revenue / margin / order / valuation variable.
  - 4.3: funding reaction / event timeline / verification point.

The first implementation should not delete text post-hoc. Instead, it should:

1. Put this rule into the prompt.
2. Extend `report_prose_quality.py` to report a more specific issue:
   - current: `repeated_theme_across_sections`
   - proposed additional warning: `theme_reexpanded_outside_owner`
3. Keep it warning-only until multiple smoke runs prove stable.

### 5. Keep The Sanitizer Conservative

Do not implement aggressive paragraph deletion or LLM-output rewriting in this phase. It is too easy to remove useful reasoning or orphan citations.

Allowed sanitizer behavior:

- split overlong prose blocks at sentence boundaries,
- preserve Markdown tables,
- normalize `[n]` to `[^n]`,
- strip role prefaces,
- optionally collapse repeated adjacent sentence prefixes if exact duplicates appear.

Not allowed in this phase:

- deleting a paragraph because a keyword repeats,
- moving sentences between sections,
- replacing citations,
- rewriting financial claims.

### 6. Use Tables To Separate Repeated Terms By Function

When a repeated term is unavoidable, force the model to tie it to the current section's owned variable:

- 4.1: `800G` as technology / industry demand.
- 4.2: `800G` only as revenue / margin / order driver.
- 4.3: `800G` only as catalyst / market expectation verification point.

This is acceptable repetition because the analytical function changes.

### 7. Constrain Heading Levels Inside 4.1-4.3

The LLM should not emit `##` or `###` headings inside the body of 4.1-4.3. Sample reports currently contain internal headings such as:

- `## 产业需求与供应链位置` inside 4.1.
- `### 资金面与情绪跟踪分析` inside 4.3.

These can confuse Markdown hierarchy and section extractors.

Rules:

- 4.1 / 4.2 / 4.3 section headings are owned by the renderer.
- Inside each section, LLM output may use bold inline labels such as `**产业需求与市场驱动**`, or plain paragraph lead-ins.
- LLM output must not contain lines matching `^##+\s+` inside theme narratives.
- The sanitizer should not rewrite headings in Phase 1. The checker should warn with `nested_heading_in_deep_analysis`.

## Implementation Phases

### Phase A: Prompt Ownership Contract

Modify `KnowledgeSynthesizer` prompt construction to include:

- `FINAL_SECTION_THEME_MAP`,
- the current theme's `owns / may_reference / must_not_expand`,
- the concrete topic-family terms relevant to the current stock / sector,
- a compact previous-topic ledger,
- a "borrowed theme budget" rule.
- an explicit "do not emit ## / ### headings" rule.

Tests:

- `_build_prompt()` includes owner and forbidden-theme rules for `fundamentals`.
- `_build_prompt()` identifies that `fundamentals` and `valuation_debate` both belong to final section 4.2.
- `_build_prompt()` includes previous-topic ledger when prior sections are passed.
- `_build_prompt()` includes the borrowed-theme budget and nested-heading ban.
- Existing citation and source-credit prompt tests remain green.

### Phase B: Checker Precision

Extend `report_prose_quality.py` with a more precise advisory warning:

- `theme_reexpanded_outside_owner`

Heuristic example:

- If `800G` appears in 4.1 and also appears in 2+ paragraphs in 4.2 or 4.3, flag as re-expanded.
- If `毛利率` appears in 4.2 and appears in 2+ paragraphs in 4.1 or 4.3, flag as re-expanded.
- Ignore Markdown table rows for long-paragraph / long-sentence checks, but scan table cells for borrowed-topic repetition.
- Flag `nested_heading_in_deep_analysis` when 4.1-4.3 bodies contain renderer-level headings.

Suggested issue evidence schema:

```json
{
  "term_family": "业绩质量变量",
  "terms": ["毛利率"],
  "owner_section": "4.2",
  "offending_section": "4.3",
  "prose_paragraph_count": 2,
  "table_row_count": 1,
  "sample": "2026年毛利率能否随规模放量改善..."
}
```

Tests:

- A one-line borrowed context sentence does not warn.
- Two prose paragraphs expanding a non-owned term do warn.
- Table-only borrowed references do not warn when they are concise and tied to the current section function.
- Multi-row table repetition of a non-owned topic family does warn.
- Nested `##` / `###` headings inside 4.1-4.3 warn.

### Phase C: Real Report Validation

Run focused smoke on three stocks:

- 中际旭创: optical module / AI infra stock.
- 黑芝麻智能: HK autonomous-driving chip stock with 4.4 social narrative.
- 圣邦股份: A-share analog-chip stock without 4.4.

Acceptance:

- `check_report_quality.py` PASS.
- `check_report_source_boundary.py` PASS.
- `check_report_prose_quality.py` does not regress long paragraph / long sentence / AI-ish transition warnings.
- Repetition warnings either decrease or become more specific and actionable.
- 4.1-4.3 still have substantive formal-source citations.
- 4.1-4.3 do not contain nested `##` / `###` headings.

## Failure Modes And Tests

### Failure: Prompt Becomes Too Rigid

Symptom: 4.2 or 4.3 loses necessary one-line context and becomes shallow.

Mitigation:

- Keep "may_reference" terms.
- Checker should allow one short borrowed context sentence.
- Human sample review required before final acceptance.

### Failure: Checker Overfits Keywords

Symptom: The checker flags normal sector vocabulary as repeated even when analytical use differs.

Mitigation:

- Keep warnings advisory.
- Include examples from optical module, autonomous-driving chip, and analog-chip stocks.
- Do not fail CI on these warnings yet.

### Failure: Citations Break In Tables

Symptom: table rows use `[n]`, lose source list entries, or produce orphan footnotes.

Mitigation:

- Preserve existing citation sanitizer tests.
- Add at least one test where borrowed themes appear in table rows with `[^n]`.

### Failure: Repetition Moves From Paragraphs Into Tables

Symptom: prose warnings disappear, but tables repeat the same borrowed theme across many rows.

Tests / checks:

- Add a fixture where `800G` appears in multiple non-owner table rows and assert `theme_reexpanded_outside_owner`.
- Add a fixture where `800G` appears in one 4.2 revenue-driver row and assert no warning.

### Failure: Nested Headings Break Section Structure

Symptom: generated 4.1-4.3 contain `##` / `###` headings that interfere with renderer or section parsing.

Tests / checks:

- Add a prose checker test where 4.1 contains `## 产业需求` and assert `nested_heading_in_deep_analysis`.
- Add prompt test requiring `不要输出 ## 或 ### 子标题`.

### Failure: Sanitizer Corrupts Meaning

Symptom: deterministic post-processing deletes or rewrites claims.

Mitigation:

- Do not implement deletion/moving/rewrite in this phase.
- Use prompt and checker first.

### Failure: Real Report Runs Become Too Slow

Symptom: every iteration requires three full LLM report runs.

Mitigation:

- Use unit tests for prompt/checker first.
- Run one stock first, then three-stock validation only for acceptance.
- Reuse local data and `--no-pdf` when possible.

## Acceptance Checklist

- `python3 -m pytest tests/utils/test_knowledge_synthesizer.py tests/reporter/test_report_prose_quality.py -q`
- `python3 -m pytest tests/reporter/test_deep_analysis_renderer.py tests/reporter/test_stock_reporter_source_intake_config.py -q`
- `bash tools/ci_grep_gates.sh`
- `git diff --check`
- `python3 scripts/check_report_prose_quality.py reports/<sample>.md`
- One smoke report run before broad validation.
- Three-stock validation before making this the default release-candidate standard.

## Recommended Review Questions For GPT / Claude

1. Is the topic ownership contract too rigid for real research writing?
2. Is the proposed checker precise enough to distinguish useful cross-reference from repeated filler?
3. Are there simpler deterministic checks that would catch most repetition without needing semantic classification?
4. Does this design risk making 4.1-4.3 too table-heavy?
5. Are there missing failure modes around citations, formal-first source boundaries, or LLM hallucination?
