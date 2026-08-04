# Technical Analysis v2 Phase 2.2 Compression Design

## Goal

Compress the uncommitted Phase 2.2 implementation without changing its accepted facts, judgment contract, scenario provenance, renderer output, scoring, risk, target, or recommendation behavior.

## Baseline And Budget

- Comparison base: `fdd0941`
- Current five-file runtime delta: `+401` lines
- Compression target: at most `+360` lines
- Stretch target: at most `+330` lines
- The retired `+180` limit is not achievable without removing accepted Phase 2.2 behavior.

Stop immediately if compression requires changing an accepted output contract or deleting an active technical-analysis path.

## Allowed Runtime Scope

- `scripts/utils/reporter/technical_structure.py`
- `scripts/utils/reporter/technical_state_machine.py`
- `scripts/utils/reporter/technical_patterns.py`, only for a proven zero-call deletion

The existing analyzer, config, and renderer may be inspected but are not compression targets unless a small deletion clearly improves ownership.

## Compression Moves

1. Replace the duplicate private ATR implementation with `technical_indicators.atr`.
2. Delete `_is_support_resistance`, which is definition-only and not exported or called.
3. Replace scenario source branching with one declarative source map that owns both value lookup and persisted provenance.
4. Reuse the same source resolver for scenario construction and cache validation.
5. Consolidate repeated empty/status dictionaries only where names remain clearer than the expanded form.

## Invariants

- Scenario levels remain exact source values; no interpolation or fuzzy matching.
- `level_source` and `source_field` remain persisted and validated.
- Wrong-side, duplicate, and ordering checks remain unchanged.
- Context-free v2.2 caches continue to return core judgment without interpretation.
- Terminal shock continues to use prior-row ATR and shared volume context.
- Structure path remains confirmed-pivot only and source ordered.
- No changes to formulas, thresholds, scores, action state, target state, or report wording.

## Failure Modes And Tests

| Failure mode | Guard |
| --- | --- |
| ATR reuse changes path classification | `test_technical_structure_path.py` exact path/shock tests |
| Source map loses zone field provenance | state-machine source-field mismatch rebuild tests |
| Scenario ordering or side filtering changes | state-machine scenario ladder tests |
| Deleted helper is still called dynamically | repository `rg` audit plus technical pattern tests |
| Compression changes renderer contract | technical renderer and report-quality suites |
| Broader regression | downstream technical suites, full pytest, CI grep gates |

## Deferred Refactor Audit

After compression, produce a read-only technical-module audit. It may recommend owner consolidation or module splits, but this batch will not replace active structure, channel, bottoming, scoring, or target algorithms.
