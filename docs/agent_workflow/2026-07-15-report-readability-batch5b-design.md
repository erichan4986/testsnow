# Report Readability Batch 5B Design

## Goal

Improve the reading rhythm of Chapter 4 external-variable maps without
shortening, rewriting, or reclassifying source material.

## Scope

Allowed runtime file:

- `scripts/utils/reporter/sections/deep_analysis_renderer.py`

Allowed test file:

- `tests/reporter/test_deep_analysis_renderer.py`

This batch does not change the external producer, composer, snapshot, citation
allocation/offsets, source-intake flags, scores, targets, risk, technical
analysis, profiles, prompts, quality gates, data, knowledge, or reports.

## Renderer Contract

`_append_external_variable_paragraph()` will format an already-admitted
external claim as one heading followed by readable source-preserving blocks.

- Split only at existing Chinese sentence or semicolon boundaries (`。！？；`),
  retaining the delimiter.
- Put at most two complete boundary units in one Markdown paragraph.
- Do not truncate, summarize, add causal language, or reorder content.
- Attach the existing inline citation marker sequence to every visible block.
- Drop a boundary unit only when its whitespace/punctuation-normalized text is
  exactly identical to an earlier boundary unit in the same source claim.
- If no safe boundary is available, render the original claim as one cited
  paragraph.

The same helper is used by formal-medium 4.3 and formal-thin 4.3. Formal-thin
continues to receive citation refs from the complete MaterialSnapshot; no
offset arithmetic changes are permitted.

## Non-Goals

- Do not delete a topic merely because official material or broker research also
  discusses it. Cross-layer repetition can be meaningful evidence separation.
- Do not apply semantic similarity, embeddings, token-overlap heuristics, or
  content-length caps.
- Do not turn the map back into a table or a checklist.

## Tests

1. A five-clause external claim becomes three cited Markdown paragraphs in
   source order, with no text loss.
2. Exact duplicate clauses within one claim render once while adjacent distinct
   clauses remain.
3. A no-boundary claim remains one cited paragraph.
4. Formal-thin output preserves complete global citation alignment after the
   paragraph projection.

## Stop Conditions

- Any necessary edit reaches producer, MaterialSnapshot, citation offset logic,
  scoring, targets, risk, technical analysis, profiles, prompts, or quality
  gates.
- The implementation requires a semantic dedupe rule or a character truncation.
- Runtime net addition exceeds 60 lines.
