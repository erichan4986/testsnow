# External Producer v2 Batch B Gate B1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use test-driven-development and executing-plans.

**Goal:** Build the offline extractor-to-pack path and report-time v2 pack consumer without switching production config or deleting the legacy production path before sample confirmation.

**Architecture:** The refresh path converts LLM candidate v2 objects plus local source packets into one persisted `curated_external_argument_pack.v2`. The report path reads only that pack and projects existing canonical argument cards. Gate B1 keeps current production config untouched; Gate B2 performs the final legacy deletion after three-stock sample approval.

**Tech Stack:** Python, JSON, pytest, existing SkillContext/report pipeline.

---

## Allowed runtime files

- `scripts/utils/curated_external_argument_cards.py`
- `scripts/utils/curated_external_full_body_viewpoint_claims.py`
- `scripts/utils/curated_external_display.py`
- `scripts/previews/curated_external_full_body_viewpoint_preview.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/stock_reporter.py`
- `scripts/utils/evidence_freshness.py`
- `scripts/utils/report_skills/assembly_skills.py`

## Allowed tests and notes

- `tests/utils/test_curated_external_argument_cards.py`
- `tests/utils/test_curated_external_full_body_viewpoint_claims.py`
- `tests/utils/test_curated_external_display.py`
- `tests/utils/test_evidence_freshness.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_stock_reporter_source_intake_config.py`
- `tests/reporter/test_recommendation_decision.py`
- `tests/reporter/test_curated_external_full_body_viewpoint_preview.py`
- `docs/agent_workflow/2026-07-16-external-producer-v2-batch-b-notes.md`

## Forbidden in Gate B1

- No edits to `config/stocks.json`, `data/curated_external`, `knowledge`, or `reports`.
- No network, LLM call, Chrome/CDP, or report generation.
- No deletion of legacy runtime/cache/tests before the three-stock sample gate.
- No scoring, target, risk-score, technical, recommendation, annual/broker producer, or KnowledgeSynthesizer prompt changes.

## Task 1: Candidate validation and canonical pack

1. Add failing tests for 1--3 evidence units, exact normalized quote matching, 4-unit rejection, unknown source, unsupported numeric/model anchors, ambiguous entity, stable citation identity, no card cap, and pack round-trip.
2. Run the focused test and confirm failures are caused by missing v2 APIs.
3. Add v2 constants and a single validator/pack builder in `curated_external_argument_cards.py`.
4. Add a pack reader that validates schema/version/stock/status/card safety/evidence hashes/dangling refs without opening source packets.
5. Run focused tests green and refactor only after green.

Required public API:

```python
build_external_argument_pack(
    *, stock_name: str, source_packets: list[dict], baseline_text: str,
    candidates: list[dict], extractor_prompt_version: str
) -> dict

read_external_argument_pack(
    pack_json: str | Path | None, *, expected_stock_name: str
) -> dict
```

## Task 2: Extractor candidate v2

1. Add failing fake-client tests for candidate v2 prompt/schema, empty candidates, 1--3 evidence units, exact quote preservation, and no fuzzy repair.
2. Implement `_default_extractor_prompt()` v2 and candidate normalization. The v2 path must never call `repair_quote()`.
3. Add `build_curated_external_argument_pack()` and `write_curated_external_argument_pack()` wrappers in the extractor module.
4. Keep v1 functions temporarily callable for current production tests; the new v2 APIs must not import or invoke them.
5. Run focused tests green.

## Task 3: Pack display and pipeline plumbing

1. Add failing tests for `missing_config`, `missing`, `stale`, `invalid`, stock mismatch, empty, and ok display states.
2. Implement `build_curated_external_argument_display()` as the only v2 report-time reader.
3. Add optional v2 pack arguments through `report_skills/__init__.py`, `stock_reporter.py`, and `SynthesisSkill` without enabling them in production config.
4. Store only `curated_external_argument_pack_status/stats/lint` plus `deep_analysis_display` and sources.
5. When v2 is explicitly enabled, fail closed and do not fall back to narrative/digest. When v2 is disabled, preserve current production behavior until Gate B2.
6. Run focused pipeline/config tests green.

## Task 4: Freshness, risk, and profile v2 consumers

1. Add failing tests proving freshness reads v2 cards/citations, missing dates remain unknown, and legacy paragraphs are ignored when v2 is active.
2. Add failing tests proving deep-display risk rows come from v2 cards while explicit non-viewpoint risk inputs retain their current behavior and do not alter risk score.
3. Add profile fixtures for Zhongji formal-medium, Fudan formal-thin-external-rich, and Black Sesame external-only thin-all.
4. Implement v2-first branches guarded by `curated_external_argument_pack_status == "ok"`; keep current legacy branch only for disabled-v2 production config until Gate B2.
5. Run focused and affected tests green.

## Task 5: Preview sample entry

1. Add CLI/parser tests showing the full-body preview writes a pack and no digest/narrative JSON.
2. Default sample output to `/tmp/<stock>-curated-external-argument-pack-v2.json`; explicit output remains supported.
3. Do not run the CLI with a live LLM in Gate B1.
4. Run preview tests green.

## Verification and stop conditions

Run:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest <focused files> -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_deep_analysis_renderer.py tests/reporter/test_report_quality.py tests/reporter/test_report_source_boundary.py -q -p no:cacheprovider
bash tools/ci_grep_gates.sh
git diff --check
```

Stop if Gate B1 temporary runtime net change relative to `62be6bf` exceeds +450, any v2 path reads legacy files, any test requires external decisions, or a production config/cache must change. Gate B2 still has the final +120 hard stop after legacy deletion.

Write results to `docs/agent_workflow/2026-07-16-external-producer-v2-batch-b-notes.md` and stop at the B2 sample gate.
