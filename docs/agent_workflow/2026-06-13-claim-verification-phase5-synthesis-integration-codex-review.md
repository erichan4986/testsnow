# Codex Review — Claim Verification Phase 5 Synthesis Integration

> **Date**: 2026-06-13  
> **Design**: `docs/agent_workflow/2026-06-13-claim-verification-phase5-synthesis-integration-design.md`  
> **Task**: `docs/agent_workflow/2026-06-13-claim-verification-phase5-synthesis-integration-claude-task.md`  
> **Claude Notes**: `docs/agent_workflow/2026-06-13-claim-verification-phase5-synthesis-integration-implementation-claude-notes.md`  
> **Status**: Accepted after fix round

---

## Summary

The implementation is broadly aligned with the Phase 5 design: it adds a default-off verification context, sanitized prompt appendix, modern and legacy synthesis path support, reporter pass-through, and focused tests.

The original review found one must-fix issue. The fix round corrected the runtime path behavior. Codex then strengthened the focused test to assert the actual path passed to the builder.

---

## Findings

### 1. Must-fix: Default knowledge base path is cwd-dependent

`scripts/utils/report_skills/synthesis_skills.py` sets:

```python
base_dir = ctx.get("claim_verification_base_dir", "knowledge")
```

This violates the design requirement that the default knowledge base directory resolves to the repo root `knowledge/`.

The project commonly runs reports from `scripts/`, for example:

```bash
cd scripts
python run_黑芝麻智能.py --fast-test
```

Under that runtime posture, the current default `"knowledge"` points to `scripts/knowledge`, not `/Users/erichan/testsnow/knowledge`, unless the user explicitly passes `claim_verification_base_dir`. That makes default-enabled per-stock config fragile and can silently produce `empty` verification context.

Smoke check performed by Codex from `workdir=/Users/erichan/testsnow/scripts` captured the builder receiving:

```text
knowledge
```

Expected default:

```text
/Users/erichan/testsnow/knowledge
```

Recommended fix:

- Add a small resolver in `synthesis_skills.py`, similar to evidence note writer:

```python
def _resolve_claim_verification_base_dir(self, ctx: SkillContext):
    base_dir = ctx.get("claim_verification_base_dir")
    if base_dir:
        return base_dir
    return Path(__file__).resolve().parents[3] / "knowledge"
```

- Use that resolver before calling `build_claim_verification_plan()`.
- Add a focused test that calls `_build_claim_verification_context()` without `claim_verification_base_dir` and asserts the builder receives a path ending in repo-root `knowledge`, not a bare relative `"knowledge"`.

---

## Verification Run

| Command | Result | Notes |
|---------|--------|-------|
| `python3 -m pytest tests/utils/test_claim_verification.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py tests/reporter/test_stock_reporter_agent_reach_config.py -q` | 78 passed | Fresh Codex run. |
| Package-mode smoke check from `scripts/` | Demonstrated issue | Builder received bare `knowledge` default. |

---

## Scope Check

The implementation files listed in Claude notes match the task-allowed Phase 5 files. The wider worktree contains many pre-existing unrelated modifications and untracked generated files, including `config/stocks.json`, reports, and knowledge notes; this review did not attribute those to Phase 5 and did not revert them.

---

## Fix Round Revalidation

Claude fix round changed `SynthesisSkill._build_claim_verification_context()` so the default base dir resolves to:

```text
/Users/erichan/testsnow/knowledge
```

instead of the cwd-dependent bare string:

```text
knowledge
```

Codex strengthened `test_default_base_dir_resolves_to_repo_root_knowledge()` to mock `build_claim_verification_plan()` directly and assert the builder receives the repo-root path.

Fresh verification:

| Command | Result | Notes |
|---------|--------|-------|
| `python3 -m pytest tests/reporter/test_synthesis_skills.py::test_default_base_dir_resolves_to_repo_root_knowledge -q` | 1 passed | Direct regression test. |
| `python3 -m pytest tests/reporter/test_synthesis_skills.py -q` | 9 passed | Synthesis focused tests. |
| `python3 -m pytest tests/utils/test_claim_verification.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py tests/reporter/test_stock_reporter_agent_reach_config.py -q` | 79 passed | Full Phase 5 focused group. |

## Final Decision

Accepted for the engineering portion of Phase 5.

Remaining acceptance gate before enabling this in a real report run:

- Manual sample prompt/output review, especially checking that `unverified` social claims do not enter `core_facts` or confirmed narrative as facts.
