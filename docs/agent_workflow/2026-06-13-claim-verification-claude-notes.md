# Claim Verification Phase 4 Review Round 1

**Date**: 2026-06-13  
**Design file reviewed**: `docs/agent_workflow/2026-06-13-claim-verification-design.md`  
**Scope**: Phase 4 — introduce a pure, dry-run claim verification framework that uses high-credit evidence notes to verify low-credit legacy social notes.

---

## Status

**Ready with changes.**

The overall direction is sound: a pure module, no LLM, no pipeline wiring, default dry-run, and a conservative trust direction. The design correctly isolates itself from `KnowledgeSynthesizer`, `SynthesisSkill`, scoring, renderers, and entry scripts. A few details must be tightened before implementation, mostly around frontmatter parsing formats, confidence scoring, and the matching algorithm's false-positive guardrails.

---

## Findings

### High

- None.

### Medium

1. **Frontmatter parser must handle both YAML and JSON formats.**
   - Evidence notes produced by `write_evidence_notes()` use YAML frontmatter (`---\nkey: value\n---`).
   - Legacy social notes in `knowledge/10-Stocks/<stock>/*.md` use JSON frontmatter (`---\n{...}\n---`), as seen in `knowledge/10-Stocks/三花智控/20260612-深度分析.md` and `MOC.md`.
   - PyYAML can parse JSON, but the implementation should not assume YAML-only. The parser must split on `---` first, then use a safe loader regardless of whether the content is YAML or JSON.
   - **Required clarification**: document that frontmatter parsing supports both YAML and JSON inside `---` fences, and that malformed frontmatter goes to `skipped_files` rather than raising.

2. **`MOC.md` matching rule needs to be explicit and robust.**
   - The design says "skip MOC.md". This should be based on filename matching (`MOC.md` or `moc.md`) rather than content heuristics, because `MOC.md` itself now carries `source_type: social_discussion` and could otherwise be treated as a social note.
   - **Recommendation**: skip any file whose basename (case-insensitive) is `MOC.md`, regardless of frontmatter content.

3. **Legacy social notes with `category: 公司公告` should not be confused with official announcements.**
   - Files like `20260612-公司公告.md` have `source_type: social_discussion` and `verification_status: market_opinion` in frontmatter, but their bodies contain announcement titles. The design correctly says trust the frontmatter, not the body. This must be emphasized in the implementation docstring to prevent a future maintainer from trying to extract "confirmed facts" from the body.
   - **Recommendation**: add an explicit guardrail: "Never infer claim credibility from legacy social note body sections such as `confirmed_facts`, `announcements`, or `inferences`. Only use frontmatter fields."

4. **Confidence scoring for `supported` vs `verified` needs a conservative rule.**
   - The design says medium-credit (55-79) sources can produce `supported` but not `verified`. This is good, but the numeric `confidence` field for `supported` could be close to `verified` if the matching is generous.
   - **Recommendation**: cap confidence for `supported` below the confidence for `verified`. For example:
     - `verified`: confidence 70-100 (high-credit source required)
     - `supported`: confidence 40-69 (medium-credit or weak high-credit match)
     - `unverified`: confidence 0-39
     - `conflicted` / `needs_review`: confidence 0 or special sentinel
   - This prevents medium-credit matches from being mistaken for verification.

5. **Deterministic key-term matching may produce false positives.**
   - Matching on `A2000U`, `ASIL-D`, etc. could link unrelated claims that share only a product name. The design acknowledges this by providing a `needs_review` action, but the threshold for `needs_review` is not specified.
   - **Recommendation**: define concrete thresholds for when to downgrade to `needs_review`:
     - If a low-credit claim matches high-credit claims from multiple topics.
     - If key-term overlap is only one generic term (e.g., `芯片`) and no specific product/customer/ certification term.
     - If date proximity cannot be checked and claims are time-sensitive.

### Low

1. **`ClaimCandidate.claim_status` may be redundant for legacy stubs.**
   - For legacy social notes, the design sets `claim_status=unverified_claim` for all coarse stubs. This is fine, but consider whether this field is needed in `ClaimCandidate` when `source_credit` and `verification_status` already encode the same information. Keeping it is acceptable for downstream readability.

2. **`source_platforms` default is an empty list for evidence notes.**
   - Evidence notes use `source_platform` (singular) in frontmatter. The design uses `source_platforms` (plural) in `ClaimCandidate` for legacy social notes. The implementation should normalize this: read `source_platform` for evidence notes and convert to `[source_platform]`, or leave as `[]` and document the asymmetry.

3. **`dry_run=False` guard should be explicit in the public API.**
   - The design allows two options: raise `NotImplementedError` or omit `dry_run=False` entirely. The API signature already exposes `dry_run: bool = True`, so the safest implementation is to raise if `dry_run=False`.
   - **Recommendation**: explicitly raise `NotImplementedError("Phase 4 only supports dry_run=True")` to make the limitation self-documenting.

4. **Skipped files should record why they were skipped.**
   - The design's `skipped_files` is `List[Dict[str, str]]`. This should include a `reason` key (e.g., `malformed_frontmatter`, `moc_index`, `unknown_source_type`) to aid debugging.

5. **Tests should verify that legacy social notes never become high-credit claim sources.**
   - Even if a legacy social note has a `claims` list in frontmatter, its `source_credit` (35) means it must always enter the low-credit bucket. Add a test case to guard against accidental trust elevation.

---

## Required Changes Before Implementation

1. **Document frontmatter parser dual-format support.**
   - The parser must accept both YAML (evidence notes) and JSON (legacy social notes) frontmatter inside `---` fences.

2. **Make `MOC.md` skip filename-based and case-insensitive.**
   - Skip `MOC.md` / `moc.md` by basename, regardless of frontmatter.

3. **Add explicit guardrail: legacy social note bodies are not sources of truth.**
   - Do not extract claims from `confirmed_facts`, `announcements`, or other body sections.
   - Only use frontmatter fields for credibility.

4. **Define conservative confidence score bands.**
   - `verified`: 70-100
   - `supported`: 40-69
   - `unverified`: 0-39
   - `conflicted` / `needs_review`: 0 or documented sentinel

5. **Define `needs_review` downgrade conditions.**
   - Generic single-term matches.
   - Cross-topic matches.
   - Missing date context for time-sensitive claims.

6. **Raise `NotImplementedError` for `dry_run=False`.**
   - Since the API signature exposes `dry_run`, make the Phase 4 limitation explicit.

7. **Include `reason` in `skipped_files` entries.**
   - Each skipped file dict should have `path` and `reason` keys.

---

## Nice To Have

- Add a `test_legacy_social_body_confirmed_facts_ignored` test to document the guardrail.
- Add a helper function `is_moc_file(path) -> bool` for clarity.
- Consider adding `source_credit_thresholds` as module constants so they can be adjusted in one place.
- Provide a small example of the expected plain-dict output in the module docstring.

---

## Files Reviewed

- `docs/agent_workflow/2026-06-13-claim-verification-design.md`
- `scripts/utils/evidence_note_writer.py`
- `knowledge/10-Stocks/三花智控/MOC.md`
- `knowledge/10-Stocks/三花智控/20260612-深度分析.md`
- `knowledge/10-Stocks/三花智控/20260612-公司公告.md`
- `knowledge/10-Stocks/黑芝麻智能/` (verified no `evidence/` directory currently exists)
- `docs/agent_workflow/2026-06-12-evidence-note-writer-design.md`
- `docs/agent_workflow/2026-06-12-evidence-note-pipeline-integration-design.md`

---

## Boundary Compliance Check

| Boundary | Design compliant? | Notes |
|---|---|---|
| `KnowledgeSynthesizer` untouched | ✓ | No changes. |
| `SynthesisSkill._build_synthesis_items()` untouched | ✓ | No changes. |
| No pipeline wiring | ✓ | Pure module only. |
| No real `knowledge/` writes in default tests | ✓ | `dry_run=True` default; writeback deferred to Phase 4B/5. |
| No LLM / network / browser / subprocess | ✓ | Deterministic matching only. |
| No `xueqiu_monitor_v2.py` changes or use | ✓ | Not involved. |
| No `config/stocks.json` changes | ✓ | Not involved. |
| No report renderer / scoring changes | ✓ | Not involved. |
| `evidence_note_writer.py` untouched | ✓ | Read-only dependency. |
| `evidence_note_skill.py` untouched | ✓ | Not wired. |

---

## Open Questions Responses

1. **Should medium-credit broker/media claims be allowed to produce `supported`?**
   - Yes, but with a confidence cap below `verified`. This is a reasonable conservative step.

2. **Should legacy social notes without explicit claims become coarse stubs?**
   - Yes, for Phase 4. It provides coverage over the existing legacy corpus without requiring LLM extraction. Document the coarse granularity as a known limitation.

3. **Should `MOC.md` be entirely ignored?**
   - Yes. Skip by filename to avoid treating the index as a claim source.

4. **Should Phase 4 include any writeback function at all?**
   - No. The API can expose `dry_run` but should explicitly reject `dry_run=False`. Writeback belongs to Phase 4B or Phase 5 with its own design review.

---

## Round 2 Review

### Status

**Ready to implement.**

All Round 1 required changes have been incorporated into the design. The revised architecture remains a pure, dry-run module with clear parsing rules, conservative trust direction, and explicit false-positive guardrails. No blockers remain.

---

### Remaining Findings

#### High

- None.

#### Medium

- None.

#### Low

- None.

---

### Implementation Guardrails

Use the guardrails already listed in the design, with the following confirmations for the implementer:

1. **Keep the module pure.**
   - `scripts/utils/claim_verification.py` must not import from `KnowledgeSynthesizer`, `SynthesisSkill`, pipeline skills, renderers, or scoring engine. It may read `evidence_note_writer.py` only if needed for dataclass reuse, but must not modify it.

2. **Frontmatter parsing must tolerate both formats safely.**
   - Split on `---` fences first.
   - Use `yaml.safe_load` if available; fall back to `json.loads` for JSON frontmatter if PyYAML is absent.
   - Never use `eval` or unsafe loaders.
   - Malformed frontmatter → `skipped_files` with reason `malformed_frontmatter`.

3. **MOC skip is filename-based only.**
   - Use `path.name.lower() == "moc.md"` and skip before parsing frontmatter.

4. **Legacy social note bodies are read-only for context, never for credibility.**
   - Do not parse `confirmed_facts`, `announcements`, `inferences`, or `原始数据` sections.
   - Coarse stub text must be derived from frontmatter `title`/`stock`/`category`, not body facts.

5. **Trust direction is one-way only.**
   - high-credit (>=80) can produce `verified` / `needs_review`.
   - medium-credit (55-79) can produce `supported` only.
   - low-credit social notes can never verify another claim.

6. **Confidence bands are enforced.**
   - `verified`: 70-100
   - `supported`: 40-69
   - `unverified`: 0-39
   - `needs_review` / `conflicted`: 0

7. **`dry_run=False` must raise `NotImplementedError`.**
   - The public API can expose the parameter, but Phase 4 must reject any non-dry-run call.

8. **Every `skipped_files` entry must contain `path` and `reason`.**
   - Reasons include: `moc_index`, `malformed_frontmatter`, `unknown_source_type`, `no_claims`, `insufficient_credit`.

9. **Tests must use `tmp_path` only.**
   - No test should read from or write to the real `knowledge/10-Stocks/**` directory unless explicitly testing read-only sample fixtures in isolation.

10. **Boundary compliance must be preserved.**
    - No pipeline wiring, no report generation, no LLM/network/browser/subprocess, no config changes, no entry-script changes.

---

### Files Re-Reviewed for Round 2

- `docs/agent_workflow/2026-06-13-claim-verification-design.md`
- `docs/agent_workflow/2026-06-13-claim-verification-codex-response.md`
- `docs/agent_workflow/2026-06-13-claim-verification-claude-notes.md`
- `knowledge/10-Stocks/三花智控/MOC.md`
- `knowledge/10-Stocks/三花智控/20260612-深度分析.md`
- `knowledge/10-Stocks/三花智控/20260612-公司公告.md`

---

### Boundary Compliance Re-Check

| Boundary | Design compliant? |
|---|---|
| Pure module, no pipeline wiring | ✓ |
| No `KnowledgeSynthesizer` changes | ✓ |
| No `SynthesisSkill` changes | ✓ |
| No scoring/renderer changes | ✓ |
| No real `knowledge/` writes | ✓ |
| No LLM / network / browser / subprocess | ✓ |
| No `config/stocks.json` changes | ✓ |
| No entry-script changes | ✓ |
| No `xueqiu_monitor_v2.py` use | ✓ |

The design is ready to move to the implementation task.
