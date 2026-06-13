# Claude Task: Implement Evidence Note Pipeline Integration Phase 3

请按本任务实现代码。先写测试，再写实现。不要越界修改。

## Context

设计与审查文件：

- `docs/agent_workflow/2026-06-12-evidence-note-pipeline-integration-design.md`
- `docs/agent_workflow/2026-06-12-evidence-note-pipeline-integration-codex-response.md`
- `docs/agent_workflow/2026-06-12-evidence-note-pipeline-integration-claude-notes.md`

Round 2 status: `Ready to implement`.

已有模块：

- `scripts/utils/evidence_note_writer.py`
  - exposes `write_evidence_notes(stock_name, stock_code, items, base_dir, collected_at=None, dry_run=False)`
  - returns `EvidenceWritePlan(written, skipped_existing, filtered)`
  - pure module; no network/LLM/browser/subprocess
- `scripts/utils/source_adapter.py`
  - `AgentReachAdapter` already attaches source-credit metadata into `SynthesisItem.extra`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
  - outputs `agent_reach_keep_items`, `agent_reach_demote_items`, `agent_reach_quality_status`

## Goal

Add an optional pipeline skill that writes or dry-runs evidence notes after Agent-Reach quality scoring.

The new skill must not affect report conclusions and must not pass evidence notes into `KnowledgeSynthesizer`.

## Files Allowed To Change

Create:

- `scripts/utils/report_skills/evidence_note_skill.py`
- `tests/reporter/test_evidence_note_skill.py`
- `docs/agent_workflow/2026-06-12-evidence-note-pipeline-integration-implementation-claude-notes.md`

Modify:

- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/stock_reporter.py`
- `tests/reporter/test_pipeline_integration.py`
- `tests/reporter/test_stock_reporter_agent_reach_config.py`

Do not modify any other source file unless a test proves a direct import issue in these exact changes.

## Files That Must Not Change

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/report_skills/agent_reach_skill.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/run_黑芝麻智能.py`
- `scripts/xueqiu_monitor_v2.py`
- `config/stocks.json`
- `knowledge/10-Stocks/**`
- `reports/**`

Do not run `xueqiu_monitor_v2.py`.

## Required Behavior

### 1. New Skill

Create `scripts/utils/report_skills/evidence_note_skill.py`.

It must define:

```python
@skill(name="evidence_note_writer")
def evidence_note_writer_skill(ctx: SkillContext) -> SkillContext:
    pass
```

Import style must support both root pytest imports and `scripts/` cwd imports, following existing patterns:

```python
if __name__.startswith("utils."):
    from ..skill_pipeline import skill, SkillContext
    from ..evidence_note_writer import write_evidence_notes
else:
    from skill_pipeline import skill, SkillContext
    from evidence_note_writer import write_evidence_notes
```

If this exact import form fails in tests because of package context, use the closest existing project pattern.

### 2. Skill Status Machine

The skill writes these ctx keys:

- `evidence_note_status`
- `evidence_note_write_plan`
- `evidence_note_summary`
- `evidence_note_error`

All terminal statuses:

- `disabled`
- `skipped`
- `empty`
- `dry_run`
- `written`
- `completed`
- `error`

Rules:

1. If `enable_evidence_notes=False`:
   - status `disabled`
   - reason `disabled`
   - do not call `write_evidence_notes`

2. If `agent_reach_enabled=False`:
   - status `skipped`
   - reason `agent_reach_disabled`
   - do not call writer

3. If `agent_reach_quality_status != "ok"`:
   - status `skipped`
   - reason `agent_reach_quality_status=<status>`
   - do not call writer

4. If both keep/demote lists are empty:
   - status `empty`
   - reason `no_keep_or_demote_items`
   - do not call writer

5. If `evidence_notes_dry_run=True`:
   - call writer with `dry_run=True`
   - status `dry_run`
   - no files should be created

6. If `evidence_notes_dry_run=False`:
   - call writer with `dry_run=False`
   - if `written_count > 0`, status `written`
   - if `written_count == 0` and writer succeeds, status `completed`

7. If writer raises:
   - catch internally
   - status `error`
   - `evidence_note_error=str(e)`
   - do not re-raise
   - return `ctx`

Important: the project `@skill` decorator re-raises uncaught exceptions, so the new skill must catch exceptions before they escape.

### 3. Data Handling

Inputs:

- `stock_name`
- `stock_codes`
- `agent_reach_enabled`
- `agent_reach_quality_status`
- `agent_reach_keep_items`
- `agent_reach_demote_items`
- `enable_evidence_notes`
- `evidence_notes_dry_run`
- `knowledge_base_dir`

Stock code:

```python
stock_codes = ctx.get("stock_codes", {}) or {}
stock_code = stock_codes.get(stock_name, "")
```

Items:

```python
keep_items = list(ctx.get("agent_reach_keep_items", []) or [])
demote_items = list(ctx.get("agent_reach_demote_items", []) or [])
items = keep_items + demote_items
```

Do not mutate original keep/demote lists or item objects.

collected_at:

```python
collected_at = datetime.now().isoformat()
```

Base dir:

```python
base_dir = ctx.get("knowledge_base_dir")
if not base_dir:
    base_dir = Path(__file__).resolve().parents[3] / "knowledge"
```

Note: `evidence_note_skill.py` lives in `scripts/utils/report_skills/`, so `parents[3]` resolves to repo root.

Write plan:

Convert `EvidenceWritePlan` to a plain dict before writing to ctx:

```python
from dataclasses import asdict
plan_dict = asdict(plan)
```

Summary:

```python
summary = {
    "written_count": len(plan_dict["written"]),
    "skipped_existing_count": len(plan_dict["skipped_existing"]),
    "filtered_count": len(plan_dict["filtered"]),
    "dry_run": dry_run,
    "base_dir": str(base_dir),
    "reason": reason,
    "collected_at": collected_at,
}
```

`evidence_note_error` should be `""` for non-error statuses.

Add one `logger.info` call for each terminal status.

### 4. Pipeline Builder

Modify `scripts/utils/report_skills/__init__.py`.

Add import/export:

```python
from .evidence_note_skill import evidence_note_writer_skill
```

Add to `__all__`.

Change signature:

```python
def build_stock_report_pipeline(
    llm_client=None,
    enable_agent_reach: bool = False,
    enable_evidence_notes: bool = False,
) -> SkillPipeline:
```

Insert `evidence_note_writer_skill` only when both flags are true:

```python
if enable_agent_reach:
    skills.extend([
        agent_reach_query_skill,
        agent_reach_fetch_skill,
        agent_reach_quality_skill,
    ])
    if enable_evidence_notes:
        skills.append(evidence_note_writer_skill)
```

Expected counts:

- default: 11
- `enable_agent_reach=True`: 14
- `enable_agent_reach=True, enable_evidence_notes=True`: 15
- `enable_agent_reach=False, enable_evidence_notes=True`: 11

### 5. PerStockReporter Wiring

Modify `scripts/utils/stock_reporter.py`.

Read per-stock config:

```python
ar_cfg = self.agent_reach_configs.get(stock_name, {})
agent_reach_enabled = self.enable_agent_reach or ar_cfg.get("enabled", False)
evidence_cfg = ar_cfg.get("evidence_notes", {}) or {}
evidence_notes_enabled = bool(evidence_cfg.get("enabled", False))
```

Call builder:

```python
pipeline = build_stock_report_pipeline(
    enable_agent_reach=agent_reach_enabled,
    enable_evidence_notes=agent_reach_enabled and evidence_notes_enabled,
)
```

When evidence notes are enabled:

```python
pipeline_input["enable_evidence_notes"] = True
pipeline_input["evidence_notes_dry_run"] = evidence_cfg.get("dry_run", True)
if evidence_cfg.get("base_dir"):
    pipeline_input["knowledge_base_dir"] = evidence_cfg["base_dir"]
```

Do not modify `config/stocks.json`.

## Required Tests

### A. New `tests/reporter/test_evidence_note_skill.py`

Use:

```python
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))
from skill_pipeline import SkillContext
from source_adapter import SynthesisItem
from report_skills.evidence_note_skill import evidence_note_writer_skill
```

Add a local `_make_item(**kwargs) -> SynthesisItem` helper with source-credit metadata:

```python
extra={
    "raw": {},
    "source_credit": 85,
    "source_type": "company_official",
    "source_domain": "blacksesame.com",
    "verification_status": "primary_source",
    "credit_reasons": ["公司官网域名: blacksesame.com"],
    "knowledge_eligible": True,
    "report_eligible": True,
    "agent_reach_quality_score": 70,
    "agent_reach_quality_action": "keep",
}
```

Tests to include:

1. disabled does not call writer
2. Agent-Reach disabled skips
3. quality status not ok skips
4. empty keep/demote returns empty
5. dry-run returns status `dry_run`, plain dict plan, no files under tmp_path
6. real write returns status `written`, one file under `tmp_path/10-Stocks/黑芝麻智能/evidence/`
7. real write with pre-existing same evidence returns `completed`, `written_count == 0`
8. keep + demote are both passed to writer
9. keep/demote lists in ctx are unchanged after skill runs
10. writer exception returns status `error`, sets `evidence_note_error`, does not raise
11. default base dir resolves to repo-root `knowledge`, not `scripts/knowledge`; monkeypatch writer and assert received base_dir ends with `/testsnow/knowledge`

Use monkeypatch where needed:

```python
monkeypatch.setattr(
    "report_skills.evidence_note_skill.write_evidence_notes",
    fake_writer,
)
```

### B. Modify `tests/reporter/test_pipeline_integration.py`

Update/add:

- default still 11
- Agent-Reach only still 14
- Agent-Reach + evidence notes is 15
- evidence notes without Agent-Reach stays 11
- order: query -> fetch -> quality -> evidence_note_writer -> cross_source_consolidation

### C. Modify `tests/reporter/test_stock_reporter_agent_reach_config.py`

Existing assertions like:

```python
mock_build.assert_called_once_with(enable_agent_reach=False)
```

must be updated to include `enable_evidence_notes=False`.

Add tests:

1. no `evidence_notes` config:
   - builder called with `enable_evidence_notes=False`

2. `agent_reach.enabled=True`, `evidence_notes.enabled=True`:
   - builder called with `enable_agent_reach=True, enable_evidence_notes=True`
   - pipeline input has `enable_evidence_notes=True`
   - default `evidence_notes_dry_run=True`

3. `evidence_notes.dry_run=False`, `evidence_notes.base_dir=<tmp_path>`:
   - pipeline input carries `evidence_notes_dry_run=False`
   - pipeline input carries `knowledge_base_dir=<tmp_path>`

4. `evidence_notes.enabled=True` but Agent-Reach disabled:
   - builder called with `enable_agent_reach=False, enable_evidence_notes=False`
   - pipeline input does not include `enable_evidence_notes`

## Validation Commands

Run focused tests:

```bash
python3 -m pytest tests/reporter/test_evidence_note_skill.py \
  tests/reporter/test_pipeline_integration.py \
  tests/reporter/test_stock_reporter_agent_reach_config.py \
  tests/utils/test_evidence_note_writer.py -q
```

Run broader Agent-Reach/evidence tests:

```bash
python3 -m pytest tests/utils \
  tests/reporter/test_agent_reach_quality_skill.py \
  tests/reporter/test_agent_reach_evidence_renderer.py -q
```

Do not run `xueqiu_monitor_v2.py`.

Do not run `run_黑芝麻智能.py` unless the focused tests pass first. If you do run it, use:

```bash
cd scripts
python3 run_黑芝麻智能.py --fast-test
```

## Notes File

After implementation, write:

`docs/agent_workflow/2026-06-12-evidence-note-pipeline-integration-implementation-claude-notes.md`

Include:

- files changed
- tests run and exact results
- whether any real `knowledge/` files were written
- confirmation that `KnowledgeSynthesizer`, `SynthesisSkill`, scoring, renderer, connector, entry scripts, and config were not modified
- any deviations from this task
