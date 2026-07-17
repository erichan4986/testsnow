# External Producer v3 Gate B2 Narrow Fix Design

## Goal

Close the three deterministic Gate B2 defects without changing target-family ownership, selector behavior,
profile thresholds, citation allocation, or LLM prompts.

## Locked Approach

1. Source-unit boundaries treat an ASCII period between digits as part of the source text. An ASCII period
   immediately following a digit is not accepted as a complete Chinese-source sentence terminator, so
   truncated fragments such as `增长64.` fail closed.
2. Generic extraction residue is rejected before target/peer admission only when it starts with a narrow
   structural prefix such as `cn)记者...` or `本报告系统调研...`. No stock or industry dictionary is added.
3. Canonical external display adds one section-level `外部材料原文摘录（Preview，未经官方核验）` heading and
   renders every exact evidence unit as a Markdown quote with its own existing citation refs.
4. Display lint exempts strong wording only when the field contains that exact canonical heading and the
   sentence is a Markdown quote. Unframed curated claims, unresolved refs, and non-quote prose remain blocked.

## Failure Modes and Tests

- `1.6T` / `19.30%` split at decimal point: exact materialization fixture.
- terminal `64.` enters a card: incomplete-unit fixture expects no unit.
- `cn)记者...` and report self-description enter peer selection: structural-noise fixtures.
- raw `公告显示` / `锁定` still causes display failure: v3 display fixture must become framed and pass.
- a caller manually prefixes `>` without the canonical heading: lint must still fail.
- canonical heading plus quoted exact evidence: lint passes, while the evidence remains present verbatim.

## Scope

Runtime:

- `scripts/utils/curated_external_argument_cards.py`
- `scripts/utils/curated_external_display.py`
- `scripts/utils/curated_external_display_lint.py`

Tests:

- `tests/utils/test_curated_external_argument_cards.py`
- `tests/utils/test_curated_external_display.py`
- `tests/utils/test_curated_external_display_lint.py`

No live LLM call or report generation is part of implementation verification.
