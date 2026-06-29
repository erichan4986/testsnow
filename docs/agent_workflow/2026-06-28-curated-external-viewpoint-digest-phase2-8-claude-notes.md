# Phase 2.8 Curated External Full-Body Viewpoint Digest — Claude Notes

Date: 2026-06-28

## What changed

Implemented Phase 2.8 preview-only polish for the curated external full-body
viewpoint digest.

### New features

- **Theme coverage gating**: added `THEME_PROFILES` with a `zhongji_ai_optics`
  benchmark profile covering 7 themes. `build_viewpoint_digest` now reports
  `theme_coverage_count`, `theme_coverage_total`, `theme_coverage_ratio`,
  `covered_themes`, and `missing_themes`. The CLI gained `--theme-profile` and
  `--min-theme-coverage`; when both are set, the digest fails closed with
  `theme_coverage_failed` if coverage is below the threshold.
- **Near-duplicate merge**: after exact `source_quote_hash` dedup, claims are
  now merged by normalized `claim_type:topic:claim`. The more informative claim
  is kept. Stats report `near_duplicate_dropped_count`.
- **Preserve all qualified claims in JSON**: removed the previous
  `max_display_claims` slicing so the JSON output retains every claim that
  passes validation and dedup.
- **Prompt strengthening**: the extractor prompt and multipass focus
  instructions now explicitly instruct the model not to miss 1260H/export
  control, global capex, CPO-vs-pluggable, NPO/XPO, 800G rumors,
  prepayment/material tightness, and 2026–2028 demand/capex guidance.
- **Post-review hardening**: quote repair now truly prefers the longest
  unique exact fragment, theme matching supports keyword groups to reduce broad
  false positives, and extractor pass metadata is stored on each `_ClaimList`
  instance rather than as shared class state.

### Files changed

- `scripts/utils/curated_external_full_body_viewpoint_claims.py`
- `scripts/curated_external_full_body_viewpoint_preview.py`
- `prompts/curated_external_full_body_viewpoint_extractor.txt`
- `tests/utils/test_curated_external_full_body_viewpoint_claims.py`
- `tests/reporter/test_curated_external_full_body_viewpoint_preview.py`

### Test-first coverage

Added fake-extractor / fake-LLM tests for:

- Theme coverage pass/fail and `missing_themes`.
- Near-duplicate merge keeping the more informative claim.
- 1260H cue appearing in the multipass prompt.
- JSON retention of all qualified claims regardless of `max_display_claims`.
- CLI `--theme-profile` / `--min-theme-coverage` args and failure path.

### Verification

```bash
python3 -m pytest \
  tests/utils/test_curated_external_full_body_viewpoint_claims.py \
  tests/reporter/test_curated_external_full_body_viewpoint_preview.py -q
# 49 passed

python3 -m pytest \
  tests/utils/test_curated_external_display_lint.py \
  tests/reporter/test_synthesis_skills.py -q
# 70 passed

python3 -m compileall \
  scripts/curated_external_full_body_viewpoint_preview.py \
  scripts/utils/curated_external_full_body_viewpoint_claims.py
# clean

bash tools/ci_grep_gates.sh
# all gates passed

git diff --check
# clean
```

### Final benchmark

Ran `deepseek-v4-pro` `llm-multipass` three times against existing `/tmp`
source/baseline files. Report:
`/tmp/curated_external_full_body_phase2_8_v4pro_final_benchmark.md`.

Key result: all runs `ok`, coverage 6/7, 5/7, 6/7. 1260H/geopolitics remains
unstable (1/3). A hard single-run ≥6/7 gate would have failed Run 2.

## Open issues

- 1260H/geopolitics coverage is not yet reliable; consider a dedicated pass or
  exemplar prompt.
- Theme coverage variance persists; downstream may need a multi-run acceptance
  rule rather than a single-run threshold.

## Constraints respected

- No changes to report pipeline, renderer, `config/stocks.json`,
  KnowledgeSynthesizer, scoring, risk, technical, or target-price logic.
- No changes to `data/raw`, `reports`, or `knowledge`.
- No Chrome/CDP scraping or re-fetching of WeChat/Xueqiu/Zhihu content.
- All outputs written only to `/tmp`.
