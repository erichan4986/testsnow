# Periodic Report Excerpt -> Source Intake Design

Date: 2026-06-16

## Goal

Integrate the standalone `periodic_report_extractor` into the A-share Source Intake path so long annual/semiannual reports can produce useful, structured evidence observations instead of title-only rows.

This phase is intentionally conservative:

- Use periodic report excerpts as **evidence notes / report display observations**.
- Do **not** promote extractor output into core facts, scoring, risk scoring, EV, technical analysis, LLM synthesis, or final recommendation.
- Keep extractor output visibly typed as management view, risk disclosure, capital action, or financial-forensics observation.

## Current State

Existing Source Intake already collects:

- `exchange_announcement` from cninfo, credit 95, `confirmed_fact`
- `news` from Eastmoney, credit 60, `professional_observation`
- `research_report` from Eastmoney report list, credit 65, `professional_observation`

The newly added standalone extractor can read annual/semiannual report text and return:

- `risk_disclosure`
- `management_view`
- `capital_action`
- `financial_forensics`

Recent review and fixes confirmed:

- `标准的无保留意见` is now recognized as `audited`.
- internal-control nonstandard opinion no longer overrides financial audit status.
- Jina/PDF table text no longer globally concatenates adjacent amount columns.
- TOC fragments with `...` are filtered from `sections_found`.
- `forensics_notes.not_extracted` explicitly lists unimplemented financial checks.

## Non-Goals

- Do not change `KnowledgeSynthesizer`, prompts, citations, or core-fact extraction.
- Do not modify `scoring_engine.py`, risk scoring, EV, technical analysis, or position advice.
- Do not treat extractor `management_view` or `financial_forensics` as confirmed facts.
- Do not run Xueqiu detail scraping, CDP, logged Chrome, or Zhihu refresh.
- Do not download broker research PDFs.
- Do not make Source Intake dependent on Agent-Reach.
- Do not bulk refresh all stocks.

## Proposed Config

Add optional nested config under each A-share cninfo source:

```json
"periodic_report_extraction": {
  "enabled": true,
  "max_reports": 1,
  "max_chars": 120000,
  "max_total_chars": 120000,
  "industry": "hardtech"
}
```

Recommended behavior:

- Default disabled unless explicitly enabled in `source_intake.a_stock.cninfo_announcements`.
- Only applies to titles containing `年度报告` or `半年度报告`.
- Exclude short summaries unless explicitly requested:
  - skip `年度报告摘要`
  - skip `半年度报告摘要`
- Prefer latest annual/semiannual reports within existing cninfo result set.
- Use the same Jina Reader path as existing detail reads, but with separate caps:
  - `max_reports`
  - `max_chars`
  - `max_total_chars`
  - timeout inherited from `detail_timeout` unless a specific override is added.
- `periodic_report_extraction.enabled` must override the normal `detail_content_categories` gate for long periodic reports. Users should not need to add `年度报告` / `半年度报告` to `detail_content_categories` just to enable this feature.

## Data Flow

```text
cninfo row
  -> title/url/date filter
  -> if periodic_report_extraction.enabled and title is long periodic report
  -> read full text via Jina Reader with periodic max_chars
  -> periodic_report_extractor.extract_periodic_report(...)
  -> convert extracted items into SynthesisItem observations
  -> source_intake_items
  -> source_intake_merge
  -> evidence_note_writer
  -> SourceIntakeEvidenceRenderer
```

## Extracted Item Mapping

Each extractor item becomes a `SynthesisItem` with:

| Extractor usage | source_type | source_credit | verification_status | report use |
|---|---|---:|---|---|
| `risk_disclosure` | `periodic_report_excerpt` | 75 | `risk_disclosure` | display / evidence note |
| `management_view` | `periodic_report_excerpt` | 75 | `management_view` | display / evidence note |
| `capital_action` | `periodic_report_excerpt` | 75 | `capital_action` | display / evidence note |
| `financial_forensics` | `periodic_report_excerpt` | 75 | `financial_forensics` | display / evidence note |

Why credit 75:

- The underlying annual/semiannual report is official.
- The extractor is rule-based and may misread table text, so derived observations should not be treated as credit 95 official facts.
- These items should support human review and downstream claim verification only after explicit matching, not direct scoring.

Suggested title:

```text
{report title} — {item title}
```

Suggested content:

```text
{evidence}

解读：{interpretation}
```

Suggested `extra` fields:

```python
{
  "source_type": "periodic_report_excerpt",
  "source_credit": 75,
  "verification_status": item["usage"],
  "periodic_report_usage": item["usage"],
  "periodic_report_title": original_title,
  "periodic_report_audit_status": result["audit_status"],
  "periodic_report_type": result["report_type"],
  "periodic_report_industry": result["industry"],
  "periodic_report_not_extracted": result.get("forensics_notes", {}).get("not_extracted", []),
  "periodic_report_schema_version": result.get("schema_version", ""),
  "knowledge_eligible": True,
  "report_eligible": True,
}
```

Extractor result consumption must validate the schema version. If `schema_version != "periodic_report_extractor.v1"`, skip derived excerpt creation for that report, keep the original announcement item, and record a warning.

## Renderer Changes

Extend `SourceIntakeEvidenceRenderer` rather than creating a new renderer.

Add a subsection after `来源分层概览` and before `代表性证据摘录`:

```markdown
### 定期报告关键摘录

> 以下为年报/半年报文本规则摘录，管理层观点和财报排雷仅供复核，不等同于确认事实，不参与评分或建议。
```

Recommended columns:

| 类型 | 摘录 | 解读 | 来源 |
|---|---|---|---|

Display rules:

- Include at most 8 rows.
- Prioritize:
  1. `financial_forensics`
  2. `risk_disclosure`
  3. `management_view`
  4. `capital_action`
- Always label `management_view` as `管理层观点`.
- Always label `financial_forensics` as `财报排雷观察`.
- Do not render numbered citations.
- Strip `[^n]`, `[n]`, raw URLs, and PDF/Jina metadata.
- Do not mutate ctx or items.

Representative evidence table must exclude `periodic_report_excerpt`. Periodic excerpts belong only in the dedicated subsection to avoid duplication and to prevent them from crowding out ordinary official announcements.

`_item_verification_status()` must guard periodic excerpts:

```python
if source_type == "periodic_report_excerpt":
    return status if status in {
        "risk_disclosure",
        "management_view",
        "capital_action",
        "financial_forensics",
    } else "management_view"
```

`_build_summary_rows()` must add a dedicated row label/status for `periodic_report_excerpt`, e.g.:

| 来源类型 | 状态 |
|---|---|
| 定期报告摘录 | 年报/半年报规则摘录 |

## Evidence Note Behavior

`evidence_note_writer` can consume these items through existing merged buckets.

Required constraints:

- Notes should preserve `verification_status` as `management_view`, `financial_forensics`, etc.
- Notes must not rewrite these observations as `confirmed_fact`.
- Current `_claim_status()` maps credit 75 to `professional_analysis`, not `fact_candidate`, so the present threshold is safe.
- Add an explicit source-type guard anyway: `periodic_report_excerpt` must never be written as `fact_candidate` even if thresholds change later.
- If existing writer assumes only `confirmed_fact` / `professional_observation`, add a narrow mapping or test before enabling writes.

## Merge / Dedup Behavior

`source_intake_merge_skill` currently deduplicates items by canonical URL and prefers the higher-credit item. The original cninfo announcement has credit 95 and the derived periodic excerpts have credit 75, so URL-only dedup would silently drop the excerpts.

Required behavior:

- `periodic_report_excerpt` items must survive merge even when they share the original announcement URL.
- Implement by making their dedup key include a deterministic suffix, for example:

```text
{canonical_url}#periodic-excerpt-{periodic_report_usage}-{index}
```

or by exempting `periodic_report_excerpt` from URL-only dedup and using a stable title/content hash.

The original `exchange_announcement` item should also remain available.

## Safety Boundaries

The integration must remain display/evidence-only:

- no scoring input
- no risk-score input
- no `core_facts` enrichment
- no LLM synthesis context injection
- no numbered references
- no final recommendation changes

If a later phase wants to use a financial-forensics signal in risk scoring, it must go through a separate design review and structured risk signal contract.

## Implementation Scope

Allowed files:

- `scripts/utils/a_stock_source_intake.py`
- `scripts/utils/report_skills/source_intake_merge_skill.py`
- `scripts/utils/evidence_note_writer.py`
- `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`
- focused tests under:
  - `tests/utils/test_a_stock_source_intake.py`
  - `tests/reporter/test_source_intake_merge_skill.py`
  - `tests/utils/test_evidence_note_writer.py`
  - `tests/reporter/test_source_intake_evidence_renderer.py`
  - optionally `tests/reporter/test_a_stock_source_intake_skill.py`

Optional if needed:

- `scripts/smoke_source_intake.py` only to expose a dry-run flag/status, not required for first pass.

Do not modify:

- `KnowledgeSynthesizer`
- `synthesis_skills.py`
- `scoring_engine.py`
- technical analyzers
- risk renderer/scoring
- `config/stocks.json` unless explicitly approved by user
- `knowledge/`, `reports/`, `data/raw/` except natural runtime output during validation

## Required Tests

### Source Intake Helper Tests

- Periodic extraction disabled: annual/semiannual rows remain normal announcement items; extractor not called.
- Enabled with long annual report title: reads detail text and creates `periodic_report_excerpt` items.
- `年度报告摘要` and `半年度报告摘要` do not trigger long extraction by default.
- `source_credit` is 75 for derived periodic excerpt items.
- derived items use `verification_status` from extractor usage; never `confirmed_fact`.
- `periodic_report_not_extracted` is preserved in `extra`.
- extractor failure does not abort Source Intake; original announcement item remains available and status/warning records failure.
- long report reads are capped by `max_reports`, `max_chars`, and `max_total_chars`.
- periodic extraction works even when `detail_content_categories` excludes `年度报告` / `半年度报告`.
- schema version mismatch skips derived excerpt creation and records a warning.

### Renderer Tests

- Source Intake section renders `### 定期报告关键摘录` when periodic excerpts exist.
- Labels render as `财报排雷观察`, `管理层观点`, `风险披露`, `资本事项`.
- Rows capped at 8.
- Rows contain no `[^n]`, `[n]`, raw URLs, `AgentReach(...)`, or Jina metadata.
- Renderer does not mutate ctx or item `extra`.
- News/research still render as `professional_observation`; periodic excerpts do not become official facts.
- Malformed periodic excerpt with `verification_status=confirmed_fact` is rendered as `management_view`, not `confirmed_fact`.
- Source summary renders `periodic_report_excerpt` as `定期报告摘录` / `年报/半年报规则摘录`, not `专业观察`.
- Representative evidence rows exclude `periodic_report_excerpt`.
- Disabled/empty Source Intake renders no periodic subsection.

### Merge / Writer Tests

- Original `exchange_announcement` and derived `periodic_report_excerpt` with the same URL both survive `source_intake_merge_skill`.
- `periodic_report_excerpt` with credit 75 writes as `professional_analysis`, not `fact_candidate`.
- If a future threshold would otherwise classify it as `fact_candidate`, source-type guard still prevents that status.

### Regression Tests

- Existing `tests/utils/test_periodic_report_extractor.py` still pass.
- Existing Source Intake renderer tests still pass.
- Existing assembly tests still pass if renderer output ordering changes.

## Runtime Validation

After focused tests pass:

1. Run Source Intake smoke for 中简科技 only if config allows without modifying `config/stocks.json`; otherwise use a test-local temp config.
2. If enabling runtime config requires editing `config/stocks.json`, ask user first.
3. Generate at most one 中简科技 fast-test report after user approval.
4. Confirm:
   - `定期报告关键摘录` appears.
   - report quality check passes.
   - no numbered citation pollution.
   - no scoring/risk/technical/recommendation drift attributable to periodic excerpts.

## Acceptance Criteria

- Focused tests pass.
- Periodic report excerpts are visible as typed Source Intake observations.
- No periodic excerpt is rendered as `confirmed_fact`.
- No periodic excerpt evidence note is stored as `fact_candidate`.
- Original cninfo announcement and derived periodic excerpts both survive merge.
- No core facts/scoring/risk/final recommendation path consumes periodic excerpts.
- No external scraping beyond existing cninfo/Jina detail-read mechanism.
- No full-report runtime is required unless user explicitly approves.

## Round 1 Feedback

**Reviewer**: Claude Code
**Date**: 2026-06-16
**Scope**: Read-only design review, no file changes.

### Status

**Needs minor fixes** before implementation.

- **R2 Needed**: **Yes**, but only a narrow R2 to tighten boundary conditions and add explicit renderer guards. No fundamental redesign required.

### Findings by Severity

#### High: `_item_verification_status()` will normalize `periodic_report_excerpt` down to `professional_observation` if not careful
- **Location**: `scripts/utils/reporter/sections/source_intake_evidence_renderer.py::_item_verification_status()` lines 218–229
- **Issue**: Current code only forces `news` and `research_report` to `professional_observation`. `periodic_report_excerpt` will pass through the raw `verification_status` (`risk_disclosure`, `management_view`, `capital_action`, `financial_forensics`) — this is the design intent. **However**, there is no defensive fallback if a future bug or upstream writer sets `verification_status: confirmed_fact` on a periodic excerpt. The renderer will display it as `confirmed_fact`.
- **Suggested fix**: Add an explicit guard:
  ```python
  if source_type == "periodic_report_excerpt":
      return status if status in {"risk_disclosure", "management_view", "capital_action", "financial_forensics"} else "management_view"
  ```

#### High: `evidence_note_writer._claim_status()` may map `source_credit=75` to `confirmed_fact`
- **Location**: `scripts/utils/evidence_note_writer.py` (around line 685, `_claim_status`)
- **Issue**: The writer maps source_credit ranges to `claim_status`. If the current threshold is `credit >= 80 → confirmed_fact`, then 75 is safe. **If** the threshold is `credit >= 70 → confirmed_fact`, periodic excerpts will be written as `confirmed_fact` notes. This design doc does not inspect the actual `_claim_status` function.
- **Suggested fix**: Before implementation, verify `_claim_status` thresholds. If necessary, hard-code an exception for `source_type == "periodic_report_excerpt"` to never produce `confirmed_fact` regardless of credit.

#### High: `_build_summary_rows()` hard-codes status labels for only three source types
- **Location**: `scripts/utils/reporter/sections/source_intake_evidence_renderer.py::_build_summary_rows()` lines 256–261
- **Issue**: The method renders status text by special-casing `exchange_announcement` → "可用于事实确认", `news` → "背景资讯", and everything else → "专业观察". `periodic_report_excerpt` will be bucketed as "专业观察" even though its `verification_status` is `management_view` / `financial_forensics`. This is misleading because the items are explicitly **not** professional observations — they are derived rule-based excerpts.
- **Suggested fix**: Add a dedicated branch for `periodic_report_excerpt` rendering "年报/半年报规则摘录" or similar, and keep the per-type `verification_status` visible.

#### Medium-High: No dedicated renderer subsection yet — design exists but not verified
- **Location**: `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`
- **Issue**: The design proposes a new `### 定期报告关键摘录` subsection. Current renderer only renders `来源分层概览` + `代表性证据摘录`. The proposed subsection is sound but must be implemented and tested.
- **Suggested fix**: Implement as designed; ensure it is placed between summary and representative rows; cap at 8 rows; use labels `财报排雷观察`, `管理层观点`, `风险披露`, `资本事项`.

#### Medium-High: `source_intake_merge_skill` deduplication may collapse original `exchange_announcement` and periodic excerpt if same URL
- **Location**: `scripts/utils/report_skills/source_intake_merge_skill.py::_canonical_url()` and `_pick_preferred()`
- **Issue**: Both the original cninfo announcement item and the derived periodic excerpt items share the same `url`. `_canonical_url()` normalizes by host+path+id. `_pick_preferred()` keeps higher credit. The original announcement has `source_credit=95`, the periodic excerpts have `source_credit=75`. The original announcement will **win** and all derived excerpts will be **dropped** from `external_evidence_keep_items`.
- **Impact**: This directly breaks the design goal of showing periodic report excerpts, because they will be deduplicated away by the higher-credit title-only announcement.
- **Suggested fix**: Include a deterministic fragment in the canonical key for periodic excerpts, e.g. append `#periodic-excerpt-{index}` or use `extra["periodic_report_usage"]` to make the key unique. Alternatively, exempt `periodic_report_excerpt` from `_canonical_url` dedup and always keep it.

#### Medium: `max_chars: 450000` is very large for Jina Reader
- **Location**: design doc Proposed Config
- **Issue**: Current `_read_jina_content()` defaults to `max_chars=6000`. The design proposes `450000` characters for long annual reports. Jina Reader free tier and timeouts may not reliably return 450K chars; even if it does, extracting from that much text is slow and memory-heavy.
- **Suggested fix**: Start with `max_chars: 60000`–`120000` (roughly 15K–30K tokens) for the first implementation. Add telemetry on actual returned sizes before raising to 450K. Also cap the extractor input itself to avoid pathological regex runtimes.

#### Medium: `max_reports: 2` may read both 年报 and 半年报, doubling Jina cost
- **Location**: design doc
- **Issue**: The design only caps count, not total chars. Two long reports could still be 120K+ chars each. This is acceptable but should be budgeted per-stock.
- **Suggested fix**: Add `max_total_chars` or reduce `max_reports` to 1 by default; allow user override.

#### Medium: `_should_read_detail_content()` interacts dangerously with new config
- **Location**: `scripts/utils/a_stock_source_intake.py::_should_read_detail_content()` lines 120–131
- **Issue**: If a user enables `periodic_report_extraction.enabled` but forgets to add `"年度报告"` / `"半年度报告"` to `detail_content_categories`, the long read will be blocked by `_should_read_detail_content()` returning `False`. The design says "Only applies to titles containing 年度报告 or 半年度报告" but does not say how it overrides this gate.
- **Suggested fix**: In `_adapt_cninfo_announcements()`, check `periodic_report_extraction.enabled` **before** calling `_should_read_detail_content()`, or relax `_should_read_detail_content()` to allow periodic reports when the new nested config is enabled.

#### Medium: Renderer "Representative evidence table can still include periodic excerpts" is risky
- **Location**: design doc Renderer Changes
- **Issue**: Allowing periodic excerpts in the representative table creates duplication with the dedicated subsection and can crowd out official announcements.
- **Suggested fix**: Exclude `source_type == "periodic_report_excerpt"` from `_build_representative_rows()`; keep them only in the dedicated subsection.

#### Low: `periodic_report_not_extracted` in `extra` assumes `forensics_notes` always exists
- **Location**: design doc Extracted Item Mapping
- **Issue**: `result["forensics_notes"]["not_extracted"]` will raise KeyError if the extractor result shape changes or if an older version of the extractor is used.
- **Suggested fix**: Use `result.get("forensics_notes", {}).get("not_extracted", [])` when building `extra`.

#### Low: No schema version check on extractor result
- **Location**: design doc Data Flow
- **Issue**: `extract_periodic_report()` returns `schema_version`. The design does not propose validating it before consuming.
- **Suggested fix**: Log a warning if `schema_version != "periodic_report_extractor.v1"` and skip extraction rather than silently misinterpreting fields.

### Required Task Adjustments

1. **Fix merge dedup collision**: ensure periodic excerpts are not dropped by `_pick_preferred()` against the original `exchange_announcement`.
2. **Add renderer verification_status guard**: never render `confirmed_fact` for `periodic_report_excerpt`.
3. **Add writer claim_status guard**: never map `periodic_report_excerpt` to `confirmed_fact` regardless of credit.
4. **Reduce default `max_chars`**: start at 60K–120K, not 450K; monitor actual Jina returns.
5. **Clarify/detail override**: make sure periodic report extraction can read full text even when `detail_content_categories` does not list annual/semiannual reports.
6. **Exclude periodic excerpts from representative table** to avoid duplication.
7. **Add dedicated summary row label** for `periodic_report_excerpt` instead of falling through to "专业观察".
8. **Defensive extra building**: guard `forensics_notes.not_extracted` access.

### Missing Tests

The proposed test list is good but incomplete. Add:

1. **Dedup survival test**: when original announcement (credit 95) and periodic excerpts (credit 75) share the same URL, merge skill keeps both or keeps the excerpts.
2. **Writer claim_status guard test**: `source_credit=75` + `source_type=periodic_report_excerpt` → `claim_status != confirmed_fact`.
3. **Renderer guard test**: item with `source_type=periodic_report_excerpt`, `verification_status=confirmed_fact` → rendered status is **not** `confirmed_fact`.
4. **Renderer label test**: summary row for `periodic_report_excerpt` shows a distinct label, not "专业观察".
5. **Jina size cap test**: `max_chars=120000` is respected and extractor input is capped.
6. **Detail-category override test**: periodic extraction works even when `detail_content_categories` excludes annual/semiannual reports.
7. **Exclusion of 年度报告摘要 / 半年度报告摘要 test**: already in design, keep it.
8. **No citation pollution test**: renderer output for periodic excerpts contains no `[^n]`, `[n]`, raw URLs, AgentReach markers.
9. **Schema version mismatch test**: old/unknown schema version → graceful skip.
10. **Extractor failure fallback test**: extractor raises → original announcement item remains and warning is recorded.

### Open Questions

1. What is the exact `_claim_status` threshold in `evidence_note_writer.py`? This determines whether `source_credit=75` is safe.
2. Does `evidence_note_writer` deduplicate by canonical key across `claim_status` values? If periodic excerpts share a URL with the original announcement, will the writer overwrite or skip?
3. Should the dedicated renderer subsection be shown even when representative rows are disabled/empty? (Design says yes; confirm no existing tests break.)
4. Is Jina Reader reliable for 60K–120K char returns from cninfo PDF pages? If not, should we fallback to title-only announcement.
5. Should `periodic_report_excerpt` items be `knowledge_eligible=True`? The design says yes, but this makes them eligible for evidence notes. Confirm this is intended.

### Final Recommendation

**Conditional go for implementation after a narrow R2.**

The overall architecture (cninfo row → Jina read → extractor → SynthesisItem → source_intake_merge → evidence_note_writer → renderer) is sound and aligns with the display-only/evidence-note goal. The biggest blockers are:

- Merge dedup will silently drop periodic excerpts (must fix).
- `confirmed_fact` leakage risk through renderer/writer guards (must fix).
- Default `max_chars=450000` is too aggressive for the first implementation (should reduce).

If these three are addressed in a short R2, implementation can proceed safely. The reviewer recommends entering implementation **only after** the R2 adjustments are approved and reflected in the design.

## R2 Design Adjustments

Codex reviewed the Round 1 feedback against the current code and updated the design accordingly.

### Accepted Adjustments

1. **Merge dedup collision must be fixed.**
   - `periodic_report_excerpt` items must use a dedup key that differs from the original cninfo announcement URL.
   - The original `exchange_announcement` and all derived periodic excerpts should both survive `source_intake_merge_skill`.

2. **Renderer must guard periodic excerpt status.**
   - `periodic_report_excerpt` may only render one of:
     - `risk_disclosure`
     - `management_view`
     - `capital_action`
     - `financial_forensics`
   - Malformed `confirmed_fact` metadata must be downgraded to `management_view`.

3. **Evidence-note writer must guard claim status.**
   - Current `_claim_status(75)` returns `professional_analysis`, so the present threshold is safe.
   - The implementation still needs a source-type guard so `periodic_report_excerpt` can never become `fact_candidate` if thresholds change later.

4. **Summary row needs a dedicated periodic label.**
   - `periodic_report_excerpt` must render as `定期报告摘录` / `年报/半年报规则摘录`, not `专业观察`.

5. **Dedicated subsection is required.**
   - Add `### 定期报告关键摘录`.
   - Place it between `来源分层概览` and `代表性证据摘录`.

6. **Representative evidence table must exclude periodic excerpts.**
   - This avoids duplicate display and prevents derived excerpts from crowding out official announcement rows.

7. **Long-report read defaults are reduced.**
   - Default `max_reports` becomes `1`.
   - Default `max_chars` becomes `120000`.
   - Add `max_total_chars` default `120000`.

8. **Periodic extraction must override `detail_content_categories`.**
   - Enabling `periodic_report_extraction.enabled` should be sufficient for long annual/semiannual report reads.

9. **Extractor result access must be defensive.**
   - Use `result.get("forensics_notes", {}).get("not_extracted", [])`.
   - Validate `schema_version == "periodic_report_extractor.v1"` before consuming.

### Implementation Scope Changes

The allowed file list now includes:

- `scripts/utils/report_skills/source_intake_merge_skill.py`
- `scripts/utils/evidence_note_writer.py`

These were added because Round 1 identified merge and note-writing risks that cannot be fixed solely in `a_stock_source_intake.py` or the renderer.

### R2 Open Question

One implementation detail remains open but bounded:

- Should the merge key for `periodic_report_excerpt` use `periodic_report_usage + title hash`, or should it use an explicit `extra["periodic_report_excerpt_id"]` generated by Source Intake?

Recommended answer: generate a deterministic `periodic_report_excerpt_id` in Source Intake and let merge use that when present. This avoids content-hash drift if excerpt wording changes slightly.

## Round 2 Feedback

**Reviewer**: Claude Code
**Date**: 2026-06-16
**Scope**: Read-only R2 design review, no file changes.

### Status

**Ready to implement** after resolving one small open question and adding one extra safety test.

- **R3 Needed**: **No**. R2 addresses all R1 blockers. The remaining question (`periodic_report_excerpt_id` key scheme) is bounded and can be decided during implementation.

### Findings by Severity

#### High: `source_intake_merge_skill` dedup key choice must be deterministic and stable
- **Location**: design doc `Merge / Dedup Behavior`, `R2 Open Question`
- **Issue**: Both URL+usage and explicit ID are acceptable, but the implementation must guarantee stability across re-runs. If `periodic_report_excerpt_id` is derived from title + usage + index, ensure it does not change when unrelated excerpt text drifts.
- **Suggested fix**: Use `{announcement_id_or_url_digest}-{periodic_report_usage}-{index}` as `periodic_report_excerpt_id`, and have `_canonical_url()` in `source_intake_merge_skill.py` prefer `extra["periodic_report_excerpt_id"]` when present. This is cleaner than appending a fragment to the canonical URL because it keeps URL normalization unchanged for all other source types.

#### Medium-High: Evidence-note writer guard wording should be precise
- **Location**: design doc `Evidence Note Behavior`
- **Issue**: The doc says "`periodic_report_excerpt` must never be written as `fact_candidate` even if thresholds change later." Verified: current `_claim_status(75) == "professional_analysis"` and `_claim_status(80) == "fact_candidate"`. So 75 is safe today.
- **Suggested fix**: Implement the guard as an explicit early return in `_claim_status` or in the writer loop:
  ```python
  if item.extra.get("source_type") == "periodic_report_excerpt":
      claim_status = "professional_analysis"  # or keep derived status, but never fact_candidate
  ```
  Add a test that patches `_claim_status` thresholds to `>= 70 → fact_candidate` and confirms periodic excerpts still map to `professional_analysis`.

#### Medium: `max_total_chars=120000` is shared across reports, not per report
- **Location**: design doc `Proposed Config`
- **Issue**: With `max_reports=1`, `max_total_chars` is effectively the same as `max_chars`. If a future config sets `max_reports=2`, the design should clarify whether `max_total_chars` is a per-report cap or a global cap. Current wording says both default 120000.
- **Suggested fix**: Document that `max_total_chars` is the global budget across all periodic reports for this stock in this run. Implementation should decrement remaining budget as each report is read.

#### Medium: Renderer `_item_verification_status()` guard is correct but should also reject empty/whitespace status
- **Location**: design doc `Renderer Changes`
- **Issue**: The proposed guard maps malformed `confirmed_fact` to `management_view`, but an empty or whitespace status would also fall through to `management_view`, which is acceptable. However, it should not fall through to the generic `"unknown"` path and then be rendered as `"unknown"`.
- **Suggested fix**: Keep the guard exactly as designed; add a regression test for empty status.

#### Low: Missing explicit test that `periodic_report_excerpt` items are not fed into `KnowledgeSynthesizer`
- **Location**: design doc `Non-Goals`, `Safety Boundaries`
- **Issue**: The design states that periodic excerpts do not enter LLM synthesis, but there is no test asserting that `source_intake_items` with `source_type == "periodic_report_excerpt"` are excluded from `KnowledgeSynthesizer` context. In practice, `KnowledgeSynthesizer` may consume `external_evidence_keep_items` or `source_intake_items` directly.
- **Suggested fix**: Add a no-synthesis-injection test at the integration level (can be in `test_a_stock_source_intake_skill.py` or a focused assembly test): after merge, verify no periodic excerpt item appears in the context passed to synthesis.

#### Low: `detail_content_categories` override must not accidentally enable all long reports
- **Location**: design doc `Proposed Config`, Accepted Adjustment #8
- **Issue**: The override should only apply to titles matching `年度报告` / `半年度报告` (excluding summaries). It must not cause `read_detail_content` to be called for other categories.
- **Suggested fix**: Implementation should keep the title filter separate from `detail_content_categories`. A test should verify that enabling `periodic_report_extraction` does not cause a non-periodic announcement (e.g., `股东大会决议公告`) to be read with long-report caps.

### Required Task Adjustments

1. **Decide and document the dedup key scheme** — prefer explicit `periodic_report_excerpt_id` in `extra`, consumed by `source_intake_merge_skill`.
2. **Add source-type guard in `evidence_note_writer`** to prevent any future threshold change from mapping periodic excerpts to `fact_candidate`.
3. **Clarify `max_total_chars` semantics** as a global per-run budget across all periodic reports.
4. **Add a no-synthesis-injection regression test** (at least at skill/assembly level).
5. **Add a negative test** confirming `periodic_report_extraction.enabled` does not cause non-periodic announcements to be read with long-report settings.

### Missing Tests

The R2 test list is already strong. Add these two to make it sufficient:

1. **Writer threshold mutation test**: patch `_claim_status` so credit 75 would normally be `fact_candidate`; confirm `periodic_report_excerpt` still writes as `professional_analysis`.
2. **No synthesis injection test**: verify `periodic_report_excerpt` items are not passed into `KnowledgeSynthesizer` context (or at least not into synthesis prompt context).

Optionally also add:

3. **Empty/whitespace verification_status test**: renderer falls back to `management_view`.
4. **`max_total_chars` global budget test**: with `max_reports=2`, second report read is truncated/skipped when total budget is exhausted.

### Open Questions

1. What is the canonical key for `periodic_report_excerpt`? (Bounded: explicit `periodic_report_excerpt_id` is recommended.)
2. Is `professional_analysis` the right fallback claim status for all periodic excerpts, or should `financial_forensics` / `risk_disclosure` map to a different note status? (Current design keeps `verification_status` in renderer; writer can uniformly fall back to `professional_analysis`.)
3. Does `KnowledgeSynthesizer` currently consume `external_evidence_keep_items`? If yes, the no-synthesis-injection test is essential.

### Final Recommendation

**Proceed to implementation.**

R2 resolves all R1 blockers:

- Merge dedup collision is addressed by a deterministic excerpt key.
- `confirmed_fact` / `fact_candidate` leakage is guarded at both renderer and writer.
- Long-report defaults are reduced to safe levels (`max_reports=1`, `max_chars=120000`, `max_total_chars=120000`).
- `detail_content_categories` override is explicit.
- Schema version validation and defensive field access are included.

Only minor bounded decisions remain (key scheme, two extra tests). These can be finalized in implementation without another full design round.
