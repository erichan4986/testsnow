# External Producer v2 Batch A Implementation Notes

## Outcome

- Added one deterministic `curated_external_argument_card.v2` producer for enabled digest claims and cached narrative reasoning cards.
- `source_quote_verified` now requires the normalized quote SHA256 to match; narrative-only material is labeled `cached_excerpt`.
- Entity scope, topic family, claim/evidence admission, source identity, and exact argument dedupe have one owner.
- Removed the legacy digest topic classifier, stock-specific semantic clusters, and duplicate Synthesis display builder.
- V2 cards are the exclusive external projection bucket when present; legacy display rows remain a whole-batch fallback.
- `MaterialSnapshot` still owns citation allocation. Formal-thin offsets remain based on the full snapshot.
- Renderer only formats selected claim/evidence rows. No scoring, target, risk, recommendation, technical, collection, or LLM prompt path changed.

## Self-Review Fixes

1. Profile routing remains on the legacy evidence contract so narrative v2 projection cannot change an existing profile. Digest-only v2 input keeps a narrow compatibility signal because the superseded digest renderer previously supplied equivalent topic groups.
2. The first implementation exceeded the `+240` runtime budget. The producer was reduced from 395 to 290 lines and the total runtime delta to `+223`.
3. Removed specific-company entity tokens and retained generic entity/title/peer-context rules.
4. Tightened verified digest evidence from hash-presence to exact normalized SHA256 matching.
5. The prose exception is limited to cited v2 delta paragraphs of at most 110 characters with an adjacent labeled evidence block.

## Requirement-Test Matrix

| Requirement | Implementation | Verification |
|---|---|---|
| Digest and narrative share one admission path | `curated_external_argument_cards.py` | `test_curated_external_argument_cards.py` |
| Verified quote and cached excerpt remain distinct | card `evidence_status` | digest/narrative card tests |
| Foreign-only source cannot support target fact | generic entity/title scope gate | foreign-only negative tests |
| Same source can retain different arguments | exact `argument_key` dedupe only | same-URL distinct-argument tests |
| V2 projection excludes legacy rows | `_external_rows()` v2 bucket | snapshot exclusive-bucket test |
| Full snapshot citation offsets remain stable | unchanged `_CitationAllocator` path | external ref maps to global ref 6 test |
| No display count cap | selector returns every distinct v2 row | three-argument selector test |
| Renderer preserves complete evidence | claim + evidence block rendering | renderer v2 test |
| Theme warning exception stays narrow | framed/cited/adjacent evidence grammar | prose positive and negative tests |
| Formal-rich/formal-thin regressions remain covered | existing suites | full test suite |

## Verification

- Affected suites: `289 passed`.
- Full offline suite: `2610 passed, 16 skipped`.
- `bash tools/ci_grep_gates.sh`: passed.
- `git diff --check`: clean.
- Runtime delta against `16865c8`: `+223` lines, below the `+240` hard stop.
- Fast sample entry: `python3 scripts/run_黑芝麻智能.py --fast-test`, exit 0; Markdown and HTML generated.
- Sample source-boundary gate: passed.
- Sample prose gate: passed with one pre-existing nested-heading warning.

## Environment Warnings

- Restricted network caused quote/technical data fetches to fail, so the sample hard quality gate reported missing daily/weekly/volume/volatility/confidence fields.
- Chromium sandbox permissions prevented chart/PDF export. These failures are outside this batch and did not alter source files.

## Blocker / Deviation

- Blocker: none.
- Deviation: no formal external-data sample was refreshed; the fast sample had no usable external intake under restricted network. Contract, integration, offset, renderer, and profile behavior are covered by deterministic fixtures.
