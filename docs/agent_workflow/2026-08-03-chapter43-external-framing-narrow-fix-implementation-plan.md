# Chapter 4.3 External Framing Narrow Fix Implementation Plan

**Goal:** Make external narratives read as attributed incremental observations
without dropping or rewriting evidence.

## Task 1: Renderer framing

1. Add failing expectations to `test_deep_analysis_renderer.py` for target and
   peer leads, exact citations, connector preservation and no generated
   `；此外，` chain.
2. Run the focused tests and record RED.
3. Update only `_external_evidence_paragraph()` to satisfy those expectations.
4. Run the renderer suite and record GREEN.

## Task 2: Negated assertion warning

1. Add a failing prose-quality test showing that `不代表目标公司已确认事实` is
   not a strong assertion while `公司已确认订单` remains one.
2. Run the focused test and record RED.
3. Strip only the negated disclaimer span before scanning strong assertions.
4. Run the prose-quality suite and record GREEN.

## Task 3: Verification

Run the snapshot, renderer, report-quality, source-boundary and prose-quality
suites, then CI grep gates and `git diff --check`. Inspect the freshly generated
20260803 Chapter 4.3 sections without using their unavailable technical data as
acceptance evidence.

Stop if implementation requires changing producer material, canonical packs,
LLM prompts, citation offsets, scoring or technical analysis.
