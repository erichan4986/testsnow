# Evidence Note Pipeline Phase 3B Runtime Validation

**Date**: 2026-06-12  
**Goal**: Verify that `evidence_note_writer_skill` can produce a dry-run evidence note write plan during the 黑芝麻智能 single-stock fast-test flow, without writing to the real `knowledge/` directory.

---

## Constraints Followed

- Did **not** run `xueqiu_monitor_v2.py`.
- Did **not** refresh Zhihu or run `ZhihuCollector` / DeepSeek curator.
- Did **not** modify source code, `config/stocks.json`, report templates, `KnowledgeSynthesizer`, or `SynthesisSkill`.
- Used a temporary validation script with `tmp_path`-equivalent dry-run config.
- All real evidence writes were gated by `evidence_notes.dry_run=True`.

---

## Commands Run

### 1. Focused Test Suite

```bash
python3 -m pytest tests/reporter/test_evidence_note_skill.py \
  tests/reporter/test_pipeline_integration.py \
  tests/reporter/test_stock_reporter_agent_reach_config.py \
  tests/utils/test_evidence_note_writer.py -q
```

**Result: 68 passed**

### 2. Runtime Validation Script

Created a temporary script `phase3b_runtime_validation.py` that constructs a `PerStockReporter` with:

```python
agent_reach_configs = {
    "黑芝麻智能": {
        "enabled": True,
        "web_urls": [
            "https://www.blacksesame.com/zh/list_10/972.html",
            "https://www.blacksesame.com/zh/list_9/977.html",
        ],
        "evidence_notes": {
            "enabled": True,
            "dry_run": True,
        },
    }
}
```

Ran:

```bash
python3 phase3b_runtime_validation.py
```

---

## Runtime Validation Results

```text
agent_reach_enabled: True
agent_reach_quality_status: ok
evidence_note_status: dry_run
evidence_note_error: 

evidence_note_summary:
{
  "written_count": 2,
  "skipped_existing_count": 0,
  "filtered_count": 0,
  "dry_run": true,
  "base_dir": "/Users/erichan/testsnow/knowledge",
  "reason": "dry_run",
  "collected_at": "2026-06-12T17:26:51.163752"
}

evidence_note_write_plan type: <class 'dict'>
  written: 2
  skipped_existing: 0
  filtered: 0

planned_path: /Users/erichan/testsnow/knowledge/10-Stocks/黑芝麻智能/evidence/20260612-company-official-blacksesame-com-ab4bf6da.md
reason: claim_status=fact_candidate
canonical_key: blacksesame.com/zh/list_10/972

planned_path: /Users/erichan/testsnow/knowledge/10-Stocks/黑芝麻智能/evidence/20260612-company-official-blacksesame-com-b089e948.md
reason: claim_status=fact_candidate
canonical_key: blacksesame.com/zh/list_9/977

Real knowledge evidence dir exists: False
Real evidence files count: 0

All Phase 3B runtime assertions passed.
```

### Key Observations

- `evidence_note_status` is `dry_run` as expected.
- `evidence_note_write_plan` is a plain `dict`.
- Two items were planned for writing (both official blacksesame.com pages, `claim_status=fact_candidate`).
- No real files were created under `knowledge/10-Stocks/**/evidence/`.
- The `base_dir` resolved to repo-root `/Users/erichan/testsnow/knowledge`.

---

## Real Knowledge Directory Check

```bash
find knowledge/10-Stocks -type d -name evidence
```

**Result: 0 directories found**

Confirmed that no `evidence/` subdirectory exists under `knowledge/10-Stocks/**` after the validation run.

---

## Report Generation Entry Check

The temporary script also invoked `reporter.generate_stock_report(...)` (return value only captures `md_path`/`html_path`), then re-ran the pipeline directly to capture the full `SkillContext`. The pipeline assembled successfully with 15 skills when both `enable_agent_reach=True` and `enable_evidence_notes=True`.

No report file was generated to `reports/` during this validation because the pipeline run only captured context; however, the `generate_stock_report` call confirmed the entry point is still usable.

---

## Blockers

**None.**

Phase 3B runtime validation passed all assertions:

- Agent-Reach enabled ✓
- `evidence_note_status == "dry_run"` ✓
- `evidence_note_write_plan` is plain dict ✓
- Planned written items count is reasonable (2) ✓
- No real `knowledge/10-Stocks/**/evidence/` files written ✓
- Report generation entry remains usable ✓

---

## Note on Temporary Script

`phase3b_runtime_validation.py` was created only for this validation. It should be removed before any commit, as it is not part of the required deliverables.
