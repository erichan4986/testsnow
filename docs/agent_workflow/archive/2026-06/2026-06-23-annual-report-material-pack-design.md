# Annual Report Material Pack Design

Date: 2026-06-23

Status: Ready for implementation after R1 clarifications

## 1. Background

The annual-report path is now useful but mentally too fragmented:

- `periodic_report_fulltext_analysis`: fulltext LLM digest, display/material only.
- Ground Truth numbers: deterministic financial-number constraints for the fulltext LLM path.
- `periodic_report_narrative_evidence`: short annual-report evidence cards persisted under Knowledge.
- `periodic_report_filing_fact`: structured financial fact notes, writer-only and not the current priority.
- HK/A-share cache and evidence-pack handling: improving, but still a separate intake/source concern.

The current synthesis skill reads fulltext material and narrative cards through separate code paths. That worked for safety, but the next problem is selection quality: cards are still effectively read by filename order and count limit. For companies with many cards, such as 黑芝麻智能, high-value product/strategy cards can be omitted from display synthesis even though they exist in Knowledge.

This design introduces one narrow consolidation layer:

```text
Annual Report Knowledge / material artifacts
        ↓
annual_report_material_pack
        ↓
synthesis_display
```

The pack does not redefine Knowledge, facts, scoring, or report structure. It only prepares a better, safer annual-report display material set for synthesis.

## 2. Goals

1. Give synthesis one annual-report material entry point instead of several ad hoc branches.
2. Select narrative cards by deterministic quality ranking and card-type balance, not filename order.
3. Preserve all existing safety invariants:
   - `ctx["synthesis"]` remains baseline.
   - `ctx["synthesis_text"]` remains baseline.
   - risk/scoring/Knowledge persistence do not read display-only annual-report material.
4. Keep fulltext LLM digest, Ground Truth, and filing facts out of scope for the first implementation, except for future-compatible schema fields.
5. Make the next implementation small enough to test with focused unit tests and two report smoke checks: 圣邦股份 and 黑芝麻智能.

## 3. Non-Goals

This design does not:

- change `KnowledgeSynthesizer` prompt;
- change scoring, risk scoring, technical analysis, or claim verification;
- change Knowledge write rules;
- promote narrative cards to `confirmed_fact` or `fact_candidate`;
- connect filing facts to scoring/core facts;
- implement HK/A-share fetch/cache unification;
- implement synthesis-output evidence backtracking;
- require LLM, network, Chrome/CDP, or report regeneration during unit tests.

## 3.1 Implementation Boundary

Allowed files for the first implementation:

- `scripts/utils/annual_report_material_pack.py` (new pack builder)
- `scripts/utils/periodic_report_narrative_card_synthesis_items.py` (reuse pack selection or convert selected cards to `SynthesisItem`s)
- `scripts/utils/report_skills/synthesis_skills.py` (wire pack-selected display items behind the existing display-only path)
- `tests/utils/test_annual_report_material_pack.py` (new focused tests)
- `tests/reporter/test_synthesis_skills.py` (display-only integration tests)
- `tests/reporter/test_fulltext_material_isolation.py` (only if a narrative-card isolation fixture is needed)

Forbidden files for this implementation:

- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- `scripts/utils/report_skills/knowledge_skills.py`
- `scripts/utils/periodic_report_filing_fact_note_writer.py`
- `scripts/utils/knowledge_synthesizer.py`
- report renderers, unless a failing test proves they already read the wrong key
- `data/raw/`, `reports/`, and `knowledge/` outputs, except temporary fixtures created under test `tmp_path`

If implementation needs any forbidden file, stop and write a design delta before coding.

## 4. Knowledge Definition

The annual-report system should treat Knowledge as a reusable evidence/memory store, not as a synonym for confirmed facts.

Recommended layers:

| Layer | Meaning | Example | Can enter Knowledge | Can enter confirmed/core fact |
| --- | --- | --- | --- | --- |
| Evidence Knowledge | Reusable evidence snippets with provenance | narrative cards, management commentary, product progress | yes | no by default |
| Filing Facts | Structured, anchored disclosures | revenue, gross margin, R&D expense | writer-only now / future yes | future gated |
| Opinions / Signals | Viewpoints and soft signals | management outlook, community thesis | yes if labeled | no |

`periodic_report_narrative_evidence` belongs to Evidence Knowledge:

- It can be persisted.
- It can be cited.
- It can be used as display-only synthesis material.
- It must not automatically become a confirmed fact, scoring input, risk input, or fact candidate.

The reason is simple: a card proves that the annual report said something. It does not prove every forward-looking, promotional, or management-judgment statement as an objective fact.

## 5. Proposed Pack

Add a helper:

```text
scripts/utils/annual_report_material_pack.py
```

Public API:

```python
def build_annual_report_material_pack(
    *,
    stock_name: str,
    base_dir: str | Path,
    max_cards: int = 16,
    per_type_limit: int = 3,
) -> dict:
    ...
```

Pack shape:

```python
{
    "schema_version": "annual_report_material_pack.v1",
    "stock_name": "黑芝麻智能",
    "selected_narrative_cards": [
        {
            "card_id": "...",
            "card_type": "rd_product_progress",
            "title": "...",
            "excerpt": "...",
            "quality_score": 8.5,
            "quality_reasons": ["product_name", "specific_metric", "complete_sentence"],
            "source_type": "periodic_report_narrative_evidence",
            "source_credit": 75,
            "synthesis_display_only": True,
        }
    ],
    "diagnostics": {
        "cards_seen": 24,
        "cards_selected": 16,
        "by_type_seen": {"rd_product_progress": 5},
        "by_type_selected": {"rd_product_progress": 3},
        "skipped_high_value": [
            {"term": "Robotaxi", "reason": "budget_exhausted", "card_id": "..."}
        ],
        "skipped": [],
    },
}
```

The first implementation only populates `selected_narrative_cards`. Future keys may include `fulltext_digest`, `ground_truth_numbers`, and `filing_facts`, but they should remain inert until separately designed.

## 6. Card Quality Ranking

Quality ranking should be deterministic and explainable. Do not use an LLM for v1.

### 6.1 Positive signals

Add score for cards that contain:

- product, technology, platform, or project names;
- customer, model, vehicle, application, or business-line names;
- concrete financial/operating numbers;
- gross-margin/revenue/R&D/cash-flow explanations;
- forward-looking but specific strategy, such as product roadmap or commercialization plan;
- complete sentence structure that can stand alone without extensive prior context;
- high-value card types:
  - `rd_product_progress`
  - `market_outlook`
  - `margin_competitiveness`
  - `technology_platform`
  - `management_market_view`

Examples of high-value terms that should score well when present in the excerpt:

- product/technology terms: `A2000`, `Robotaxi`, `SesameX`, `CPO`, `硅光`, `Chiplet`, `HBM`, `800G`, `1.6T`, `AI眼镜`, `端侧AI`
- financial explanation terms: `毛利率`, `同比提升`, `收入增长`, `减值`, `存货`, `现金流`

The terms are illustrative ranking features, not universal business rules and not a company-specific whitelist. They should be implemented as an extensible signal set. A company such as 圣邦股份 must still score well through its own concrete vocabulary, for example product categories, application fields, R&D progress, customers, margin explanations, or business-line metrics. Do not hardcode 黑芝麻/AI hardware terms as required conditions or dominant weights.

### 6.2 Negative signals

Deduct score for cards that are:

- table fragments without narrative context;
- "适用/不适用" boilerplate;
- generic management slogans;
- duplicated or near-duplicated excerpts;
- dangling snippets that start or end mid-thought;
- too short to be useful or too long to be a focused card.

The ranking should keep diagnostics so manual review can see why a card was selected or skipped.

## 7. Selection Algorithm

Use a two-stage selector.

1. Parse all narrative-card notes under:

```text
knowledge/10-Stocks/<stock>/periodic_narrative_cards/
```

2. Score and dedupe cards.
   - Normalize excerpts by lowercasing ASCII, replacing punctuation with spaces where practical, and collapsing whitespace.
   - Drop exact duplicates after normalization.
   - Treat two cards as near-duplicates when token Jaccard similarity is `>= 0.85`; keep the higher `quality_score`, then the lexicographically smaller `card_id` as a stable tie-breaker.
3. Group by `card_type`.
   - Missing or empty `card_type` becomes `uncategorized`.
   - `uncategorized` cards can be selected after known high-value types, but should not displace high-value typed cards when the budget is tight.
4. Round-robin select from high-value types first, respecting:
   - `max_cards`, default 16;
   - `per_type_limit`, default 3;
   - stable tie-breaker by `quality_score desc`, then `card_id`, then filename.
   - `per_type_limit` is a soft balance limit: after each type reaches the limit, the selector may continue another pass through remaining high-quality cards until the total budget is filled.
5. Convert selected cards to display-only `SynthesisItem`s.

This prevents `business_model` or another abundant type from consuming the whole display budget.

## 8. Synthesis Integration

Current behavior:

```text
SynthesisSkill.run()
  baseline = _synthesize(...)
  if fulltext/cards enabled:
      display = _synthesize(..., extra_items=display_items)
      ctx["synthesis_display"] = display
```

Proposed behavior for v1:

```text
if annual_report_material_pack enabled:
    display_items += pack.selected_narrative_cards_as_items
else:
    preserve existing narrative-card reader behavior for compatibility
```

The initial implementation may keep the current config flags and add an internal pack path behind the existing narrative-card flag. A config rename can happen later.

Safety requirements:

- `ctx["synthesis"]` unchanged.
- `ctx["core_facts"]` unchanged.
- `ctx["synthesis_text"]` unchanged.
- `ctx["synthesis_sources"]` unchanged.
- `ctx["synthesis_display"]` may include annual-report material.
- `ctx["synthesis_text_with_periodic_narrative_cards"]` remains debug/display only.
- `periodic_report_narrative_evidence` must stay blocked from scoring/risk/Knowledge persistence paths by CI gates and tests.

## 9. Config Direction

Short term: keep existing config names to avoid churn:

```json
"periodic_narrative_cards_synthesis_display": {
  "enabled": true,
  "max_display_items": 16
}
```

Effective budget rule for v1:

- The existing `periodic_narrative_cards_synthesis_display.max_display_items` remains authoritative for the actual display budget.
- In the compatibility path, `max_display_items` is passed to the pack as `max_cards`.
- If a future `annual_report_material_pack.max_cards` key exists alongside the legacy key, use `effective_max_cards = min(max_display_items, pack_max_cards)`.
- `per_type_limit` is a soft balance limit, not a hard cap that may underfill the budget. After all available types reach `per_type_limit`, the selector may continue additional passes through remaining high-quality cards until `effective_max_cards` is reached.
- This prevents 黑芝麻智能 configured at 8 cards from silently receiving 16, and prevents 圣邦股份 from being reduced to too few cards merely because its cards are concentrated in fewer types.

Later, after v1 stabilizes, migrate to:

```json
"annual_report_material_pack": {
  "enabled": true,
  "max_cards": 16,
  "per_type_limit": 3,
  "include_narrative_cards": true,
  "include_fulltext_digest": false,
  "include_ground_truth_numbers": false
}
```

Do not rename config in the first implementation unless tests show the compatibility layer is painless.

## 10. Tests

Required focused tests:

1. Pack reader parses current narrative-card notes and extracts body blockquote excerpts, not frontmatter `source_excerpt`.
2. Quality ranking promotes specific product/technology/metric cards over generic management slogans.
3. Deduping removes duplicate or near-duplicate excerpts.
4. Type-balanced selection prevents `business_model` from consuming all slots.
5. Stable ordering: repeated pack builds return the same card ids.
6. Synthesis integration keeps baseline `ctx["synthesis"]` and `ctx["synthesis_text"]` byte-for-byte unchanged.
7. Synthesis display includes annual-report pack items when enabled.
8. Risk/scoring isolation remains unchanged, preferably reusing `test_fulltext_material_isolation.py` style fixtures with `source_type=periodic_report_narrative_evidence`.
9. CI grep gate still rejects `periodic_report_narrative_evidence` in scoring/risk/Knowledge persistence files.
10. Compatibility: if pack build raises an exception or no cards exist, report generation falls back to baseline/no display cards without crashing.
11. Missing or empty `card_type` becomes `uncategorized` and participates only after known high-value types.
12. Diagnostics expose `skipped_high_value` when a card contains configured high-interest terms but is not selected.

Suggested report smoke checks after tests:

- 圣邦股份 fast-test: narrative cards still improve deep analysis; report quality PASS.
- 黑芝麻智能 fast-test: high-value product/strategy terms such as `Robotaxi`, `SesameX`, `AI眼镜`, `华山`, `武当`, or `A2000` are more likely to appear if their cards exist and rank high. This is a quality check, not a hard unit-test condition.

## 11. Stop Conditions

Stop and redesign if implementation requires:

- modifying `KnowledgeSynthesizer` prompt;
- modifying scoring/risk/technical logic;
- making narrative cards enter `confirmed_fact`, `fact_candidate`, core facts, or scoring;
- changing Knowledge write semantics;
- adding LLM calls, network fetches, Chrome/CDP, or Xueqiu detail scraping;
- changing the annual-report fetch/cache layer.

## 12. Next Tasks

Recommended implementation order:

1. Write pack helper tests first.
2. Implement `annual_report_material_pack.py`.
3. Refactor `periodic_report_narrative_card_synthesis_items.py` to either reuse pack selection or accept selected card records.
4. Wire `SynthesisSkill` to use the pack path behind the existing narrative-card display flag.
5. Run focused tests and CI grep gate.
6. Run one local report smoke through Claude Code or local fast-test if needed.

The separate P2 task is `HK/A-share periodic report fetch/cache unification`. It should not be mixed into this implementation.

## 13. Claude Review Prompt

```text
You are Claude Code reviewing a design in /Users/erichan/testsnow.

Read:
- docs/agent_workflow/2026-06-23-annual-report-material-pack-design.md
- scripts/utils/report_skills/synthesis_skills.py
- scripts/utils/periodic_report_narrative_card_synthesis_items.py
- tools/ci_grep_gates.sh
- tests/reporter/test_fulltext_material_isolation.py

Task:
Review the annual_report_material_pack design for correctness and implementation risk.

Focus on:
1. Whether the pack meaningfully reduces annual-report material complexity without over-abstracting.
2. Whether quality ranking and card-type balancing can be deterministic and testable.
3. Whether the display-only safety boundary remains intact.
4. Whether the proposed tests catch the likely regressions.
5. Whether any allowed/forbidden file boundary is missing.

Do not modify source, tests, config, reports, data/raw, or knowledge.
As the only exception to the read-only rule, append your review to the bottom of
this design doc under "## 14. Claude Review Log".

Return:
- Status: Ready / Needs fixes / Blocked
- Blockers
- Must-fix
- Nice-to-have
- Whether R2 is needed
- Whether implementation may start
```

## 14. Claude Review Log

Pending.

### 2026-06-23 Claude R1 Review

**Status: Ready with must-fix doc clarifications**

No blockers for implementation, provided the must-fix items below are addressed either in this doc or in the first implementation PR before code review.

#### Blockers
- None.

#### Must-fix
1. **Config limit relationship must be explicit.** The existing `periodic_narrative_cards_synthesis_display.max_display_items` (e.g. 8 for 黑芝麻智能, 16 default) and the new pack params `max_cards`/`per_type_limit` interact. State whether the effective budget is `min(max_display_items, max_cards)` or whether the pack ignores the legacy key. Without this, a stock configured for 8 display items could silently receive 16 pack-selected cards, or a `per_type_limit=3` could reduce 圣邦股份 from 12 cards to ~7.
2. **Add allowed/forbidden file boundary list.** The design says what not to change in stop conditions, but should also list the concrete files that may be touched: `scripts/utils/annual_report_material_pack.py` (new), `scripts/utils/periodic_report_narrative_card_synthesis_items.py` (refactor), `tests/utils/test_annual_report_material_pack.py` (new), and additions to `tests/reporter/test_synthesis_skills.py`. Forbidden files mirror Gate A: `scoring_engine.py`, `risk_renderer.py`, `knowledge_skills.py`, `periodic_report_filing_fact_note_writer.py`.
3. **Define deduplication metric deterministically.** "Near-duplicate excerpts" needs a testable rule, e.g. normalized whitespace/punctuation Jaccard ≥ 0.85, or exact match after normalization. Otherwise tests cannot assert stability and the feature may behave differently across small excerpt edits.
4. **Clarify that the example term list is illustrative, not hardcoded company weights.** Terms like `A2000`, `Robotaxi`, `SesameX`, `CPO`, `硅光`, `Chiplet`, `HBM`, `800G`, `1.6T`, `AI眼镜`, `端侧AI` are 黑芝麻/科技硬件-centric. The implementation must treat them as a configurable/extensible signal set and not let a stock like 圣邦股份 (analog chip, different product vocabulary) receive zero score simply because its cards lack those literal terms.

#### Nice-to-have
1. Specify fallback behavior when `card_type` is missing or empty: treat as `uncategorized` and still allow selection, or skip? Currently 圣邦股份 cards all have valid types; 黑芝麻智能 cards all have valid types, but tests should cover the empty-type edge case.
2. Add a test for "pack build raises an exception" to the compatibility/fallback test list, ensuring `SynthesisSkill.run()` catches it and falls back to baseline/no-display.
3. Include a `skipped_high_value` diagnostic or assertion hook so a manual reviewer can see why expected terms like `Robotaxi`/`SesameX` did not make it into display synthesis.

#### R2 needed?
- **No R2 required**, but the first implementation PR should include the must-fix clarifications above. If the implementer wants to change the config naming strategy or significantly alter the selection algorithm, then a quick R2 is warranted.

#### Implementation recommendation
- **May start.** The consolidation layer is justified: the current filename-order reader in `periodic_report_narrative_card_synthesis_items.py` is the exact complexity this design targets. The safety boundary is already correct in `synthesis_skills.py` (baseline `synthesis`/`synthesis_text`/`core_facts`/`synthesis_sources` remain untouched; only `synthesis_display` receives extra items). The test plan covers the main regression vectors. Address the must-fix items before writing production code.

#### Files read
- `docs/agent_workflow/2026-06-23-annual-report-material-pack-design.md`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/periodic_report_narrative_card_synthesis_items.py`
- `tools/ci_grep_gates.sh`
- `tests/reporter/test_fulltext_material_isolation.py`
- `tests/reporter/test_synthesis_skills.py`

#### Files modified
- `docs/agent_workflow/2026-06-23-annual-report-material-pack-design.md` (appended this review entry).

### 2026-06-23 Codex Design Delta

Accepted:

- Clarified the v1 config relationship: the legacy `periodic_narrative_cards_synthesis_display.max_display_items` remains the authoritative display budget; future pack config uses `min(legacy_max, pack_max)` if both exist.
- Added explicit allowed and forbidden implementation files.
- Defined deterministic duplicate handling: normalized exact match and token Jaccard `>= 0.85`.
- Clarified that high-value term examples are illustrative and extensible, not 黑芝麻/AI-hardware-specific hard requirements.
- Added `uncategorized` fallback for missing `card_type`.
- Added explicit pack-exception fallback testing.
- Added `skipped_high_value` diagnostics for high-interest terms that fail selection.

Rejected:

- None.

Deferred:

- Full config rename to `annual_report_material_pack`.
- Fulltext digest binding, Ground Truth packing, filing facts, fetch/cache unification, and synthesis-output evidence backtracking.

R2 required: no. The fixes are doc/spec clarifications and do not change the implementation boundary.
