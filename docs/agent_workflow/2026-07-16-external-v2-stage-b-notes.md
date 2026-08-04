# External v2 Stage B Notes

## Result

- Verdict: PASS
- Stage A complete: yes
- Stage B complete: yes

## Blocker Closure

- Enabled Black Sesame's curated external digest display in `config/stocks.json`.
- The 2026-07-16 fast report records `external.argument_v2_count: 3` and
  `status: ok` in material coverage.
- The report profile is `thin_all`, so it is pipeline evidence rather than a
  formal-thin/formal-rich Chapter 4 rendering sample.

## Stage B Runtime

- `deep_analysis_material_snapshot` now projects external rows only from
  `_curated_external_argument_cards_v2`.
- Formal-rich 4.4 now renders only v2 claim/evidence cards and keeps the
  Preview disclaimer, citation offsets, URL display, and exact-source
  de-duplication.
- Legacy paragraphs, reasoning cards, and topic groups remain available to
  freshness, risk-audit, and diagnostics consumers, but are no longer Chapter
  4 projection inputs.
- Removed the alternate formal-thin map/checklist renderer and the legacy
  formal-rich paragraph/topic-group addendum helpers.
- External titles and claims share the same deterministic attribution cleanup;
  unverified order wording is softened in the visible claim/title while the
  evidence quote remains unchanged.

## Tests

- Snapshot + renderer: `152 passed`.
- Affected external/synthesis/prose/entry suite: `318 passed`.
- Full suite: `2615 passed, 16 skipped`.
- `tools/ci_grep_gates.sh`: PASS.
- `git diff --check`: clean.

The first full-suite run had one transient preview CLI failure. The same test
and its file passed independently; after adding assertion diagnostics, the
second full-suite run passed completely.

## Runtime Delta

Against `16865c89577d1fda8ea20fed551bd639ad37805b`:

- Tracked runtime files: +263 / -794 lines.
- New `curated_external_argument_cards.py`: +290 lines.
- Total External Producer v2 runtime delta: **-241 lines net**.
- Configuration delta: +4 lines.

## Scope Audit

- No scoring, target-price, risk-score, technical-analysis, recommendation,
  collection, or LLM-prompt changes.
- No cached source material was deleted.
- The refreshed Black Sesame narrative JSON is retained as generated input.
- No commit or push was performed.

## Remaining Warning

- Black Sesame's current evidence profile is `thin_all`; a future formal-rich
  or formal-thin report sample is useful for visual acceptance, but it is not a
  Stage B code blocker because both profile paths have focused v2 projection
  and citation regression coverage.

## Formal Report Follow-up

The first Zhongji/Fudan formal rerun exposed two compatibility defects that the
focused Stage B tests did not cover:

- Argument-v2 counts were accidentally used by evidence-profile routing. This
  moved Zhongji from `formal_medium` to `formal_thin_external_rich`, contrary to
  the locked non-goal. Routing now remains on legacy narrative/topic signals;
  digest-only v2 input retains a narrow compatibility signal because the old
  digest renderer previously supplied equivalent topic groups.
- `report_quality.py` recognized only legacy external-map structures and read
  `不确定性` as strong confirmation through the `确定` substring. It now accepts
  the canonical v2 title/claim/citation/evidence shape and strips negative
  uncertainty wording before strong-confirmation checks.

Regression coverage was added for both profile paths, canonical-v2 quality
recognition, and uncertainty wording. The affected suite passes with 419 tests;
the full suite passes with 2618 tests and 16 skips. Both existing 2026-07-16
reports now pass `check_report_quality.py`, but Zhongji must be regenerated to
prove the corrected `formal_medium` route and 4.4 rendering in a fresh output.

## Final Formal Acceptance

Fresh reports generated after the compatibility fixes close the remaining
acceptance condition:

- Zhongji is again `formal_medium`, exposes all four source-layer sections,
  projects nine canonical v2 external cards, and builds 4.4 from annual,
  broker, and the same canonical external material.
- Fudan remains `formal_thin_external_rich`, preserves the no-broker fallback,
  and projects seven canonical v2 external cards with intact citation offsets.
- Both reports pass report-quality and source-boundary checks. The only prose
  warnings are cross-section `800G` repetition for Zhongji and a Fudan margin
  term inside quoted external evidence; neither changes source ownership,
  citation hygiene, scoring, risk, or target-price inputs.

Stage B formal report acceptance is complete.
