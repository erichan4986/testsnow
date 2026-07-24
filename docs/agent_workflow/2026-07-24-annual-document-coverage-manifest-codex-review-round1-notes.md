# Annual Document Coverage Manifest - Codex Self-Review Round 1

Verdict: needs revision

## Findings

1. **Validity and completeness are conflated.** A structurally valid manifest with one unmapped section must
   not look like a partially corrupt artifact. Keep `status` for schema availability and add a separate
   `analysis_coverage_status`.
2. **Container headings can create false gaps.** Jina output frequently emits a parent heading immediately
   followed by a child heading. A heading with no substantive body must be `structural_only`, not `unmapped`.
3. **Block joins are underspecified.** `coverage_block_id` is not the existing evidence block ID. Selected
   decisions need both IDs so producer unit decisions can join without fuzzy matching.
4. **Empty and legacy inputs need exact compatibility behavior.** Empty evidence packs and hand-built test
   packs without coverage must yield an unavailable diagnostic without changing cards.
5. **Page proof is too vague.** The design must name accepted page-marker shapes and keep all other numbers,
   especially table-of-contents numbers, out of page fields.
6. **Budget wording is inconsistent.** The planned runtime scope is one new module plus two modified producers,
   not three modified runtime files.

## Required Delta

- Split `status` from `analysis_coverage_status`.
- Add `structural_only` section state based on an exact substantive-body rule.
- Define `evidence_block_id` and `coverage_block_id` fields and exact producer join.
- Lock unavailable-manifest behavior and page-marker grammar.
- Correct runtime scope and tests.
