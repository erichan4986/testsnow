# Report Terminal Citations Design

## Goal

Improve report readability by keeping inline footnote markers next to claims while moving every rendered
source list into one global `## 引用来源` appendix at the end of the report body.

The final order is:

1. normal report sections through `## 综合风险评分`;
2. one global `## 引用来源` section;
3. the existing disclaimer and report-generation-time footer.

## Non-Goals

- Do not change citation IDs, offsets, aliases, source selection, source metadata, or inline `[^n]` markers.
- Do not change Chapter 4 content, scoring, target price, risk, technical analysis, recommendation, or prompts.
- Do not make the assembly layer rebuild or deduplicate citation metadata.
- Do not modify report-quality or source-boundary rules unless a focused regression proves an existing rule
  incorrectly assumes local source lists.

## Current State

`DeepAnalysisRenderer` owns citation construction and currently appends the global citation section to the
end of Chapter 4. `ReportAssemblySkill` renders Chapter 4 before optional evidence sections and risk, so the
global list appears before the end of the report. Legacy and curated-external helper paths can also emit
`**本节引用来源：**` lists, duplicating information already present in the global list.

## Design

### Citation ownership

`DeepAnalysisRenderer` remains the only owner of citation merging, offsetting, aliasing, visible-reference
filtering, and final source-line formatting. Its global `## 引用来源` output is unchanged.

All section-local source-list calls are removed. Their `used` bookkeeping and
`include_section_citations` parameters are deleted where they have no other purpose. Inline footnotes remain
the source-to-claim link, so no traceability is lost.

### Terminal placement

`ReportAssemblySkill` gains one exact-heading helper:

```python
_detach_global_citation_section(markdown: str) -> tuple[str, str]
```

The helper recognizes only a line exactly equal to `## 引用来源`. It returns the Chapter 4 body and the
unchanged citation appendix. Zero matches returns the input unchanged and an empty appendix. More than one
match raises a bounded assembly error. The report must not be emitted with ambiguous citation ownership or
silently truncated content.

During assembly, only the rendered `deep_analysis` section is passed through this helper. The body keeps its
normal position. The detached appendix is appended after every renderer, including risk, and immediately
before `FOOTER_TEMPLATE`.

The assembly layer does not parse citation rows, renumber markers, or read source metadata.

Assembly also enforces two ownership invariants before joining the report: no non-deep renderer may emit the
exact global citation heading, and no rendered section may retain `**本节引用来源：**`. Either condition raises
a bounded assembly error instead of producing a partially migrated report.

### Prose-quality compatibility

The advisory `duplicate_4_4_citation_source` rule currently reads local source-list lines. Its semantics are
preserved by resolving the inline refs used in 4.4 against the terminal global citation table. It does not
scan unrelated global sources and does not alter citation metadata. Existing fixtures with local lists remain
supported by the checker so historical reports can still be audited.

The resolver uses unique 4.4 citation IDs, so repeated use of one footnote is not a duplicate source. When a
historical local list exists it remains the preferred input; otherwise the checker resolves those unique IDs
from the global table. Source identity normalization supports both legacy plain rows and global rows with
separator pipes and bold source labels, including no-URL source/author/title fallback.

### Removal ledger

Delete rather than disable:

- `_append_section_citations()` and all of its call sites;
- `used` / `used_refs` accumulators that exist only for local lists;
- `include_section_citations` parameters and forwarding arguments;
- annual/broker citation dictionaries that are passed only for local-list formatting;
- the `display_refs` return from `_curated_external_display_ref_map()` once no caller needs it.

Global merging, offsetting, canonical ref mapping, visible-ref filtering, reserved-ref aliasing, and
`_citations_section()` remain unchanged.

### Profile behavior

The behavior applies equally to:

- `formal_rich`;
- `formal_medium`;
- `formal_thin_external_rich`;
- thin/material-insufficient output.

If no visible citation exists, no appendix is emitted. If Chapter 4 is absent, assembly behavior is unchanged.

## Allowed Files

Runtime:

- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/report_skills/assembly_skills.py`
- `scripts/utils/report_prose_quality.py`

Tests:

- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_assembly_skills.py`
- `tests/reporter/test_report_prose_quality.py`
- focused source-boundary fixtures only if required by a demonstrated regression

Workflow notes:

- `docs/agent_workflow/2026-07-23-report-terminal-citations-implementation-plan.md`
- `docs/agent_workflow/2026-07-23-report-terminal-citations-codex-notes.md`

## Test Contract

1. Deep-analysis output contains no `本节引用来源` for legacy, formal-medium, formal-thin, or curated addendum
   paths.
2. Inline `[^n]` markers and the global source entries retain their original IDs.
3. Assembly emits exactly one `## 引用来源` when citations exist.
4. Its position is after `## 综合风险评分` and before the disclaimer footer.
5. A report without citations emits no empty citation heading.
6. A malformed deep-analysis result with duplicate global headings is not partially moved or truncated.
7. Reserved executive-summary refs remain in the terminal appendix without renumbering.
8. The 4.4 duplicate-source warning resolves only 4.4 inline refs against the terminal appendix.
9. Repeated use of one ref does not trigger duplicate-source warning; two refs with the same URL or normalized
   source/author/title do trigger it.
10. A non-deep global appendix or any residual local-list marker fails assembly.
11. Existing global missing/unused-reference and source-boundary checks remain green.
12. Phase 2.3A technical tests remain green; no technical runtime file changes.

## Failure Modes

| Failure | Visible symptom | Guard |
|---|---|---|
| Citation IDs are recomputed during movement | inline markers point to wrong rows | exact appendix identity test |
| Local lists survive one profile | repeated source blocks interrupt Chapter 4 | profile matrix test |
| Appendix is placed after the legal footer | report metadata is no longer terminal | assembly ordering test |
| Split consumes risk or footer text | missing report tail | sentinel preservation test |
| Duplicate headings are silently normalized | malformed report appears valid | assembly raises in duplicate-heading test |
| No-citation report gains empty appendix | visual clutter | empty-citation test |
| Social-source boundary scans include appendix | false source-boundary failure | focused boundary regression |
| 4.4 duplicate-source warning disappears | repeated source identities become invisible to prose audit | global-ref resolution test |
| Reserved summary source is dropped | summary footnote has no terminal source row | reserved-ref relocation test |
| One ref reused several times is called duplicate | false prose warning | unique-ref test |
| Global no-URL row is parsed as empty source | duplicate fallback identity is missed | global-row fallback test |
| Another renderer emits a source appendix | multiple or interrupted appendices | sole-owner assembly test |

## Budget And Stop Conditions

- Runtime target: net non-positive, because local-list code and dead parameters are removed.
- Runtime hard stop: net `+60` lines across the three runtime files.
- Stop if correct placement requires changing citation offsets, citation metadata, report-quality semantics, or
  any renderer outside the allowed scope.
- Formal report generation is deferred until this change and Phase 2.3A are tested together.
