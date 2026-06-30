# Claude Implementation Task: Agent-Reach Audit Persistence + Official Seed Calibration

## Status

Ready for local Claude Code implementation.

## Goal

Improve Agent-Reach observability and official-source scoring without changing report conclusions, scoring engine, LLM prompts, Xueqiu collection, or the core report structure.

This is a Level 2 file task handoff. Do not run a new design review unless implementation reveals that the required changes need to touch synthesis, scoring, or broad pipeline architecture.

## Background

Black Sesame local validation on 2026-06-13 showed:

- `WebConnector` successfully fetched 6 configured official `blacksesame.com` URLs.
- Quality gate kept all 6 items.
- The generated report included `## Agent-Reach 外部证据观察`.
- `reports/黑芝麻智能_20260613.md` passed `scripts/check_report_quality.py`.
- The raw report input snapshot did not contain `agent_reach_*` keys, so Agent-Reach runtime evidence is not easily auditable outside the rendered report.
- All official pages were still marked with `疑似门户/导航页，内容价值低` because Jina Reader preserves navigation-heavy text.

## Desired Outcome

1. Agent-Reach runs produce a compact, content-safe audit summary in `SkillContext`.
2. Report generation optionally persists that audit summary to JSON for later review.
3. User-provided official seed URLs can be marked as official, receive a small credibility calibration, and avoid misleading "content value low" language when the page is a real official article with navigation noise.
4. Low-substance portal/home pages must still be discarded, even if user-provided.

## Allowed Files

Prefer keeping edits within this list:

- `scripts/utils/report_skills/agent_reach_query_skill.py`
- `scripts/utils/report_skills/agent_reach_skill.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/report_skills/assembly_skills.py`
- `scripts/utils/stock_reporter.py`
- `config/stocks.json`
- `tests/reporter/test_agent_reach_skills.py`
- `tests/reporter/test_agent_reach_connector.py`
- `tests/reporter/test_agent_reach_quality_skill.py`
- `tests/reporter/test_assembly_skills.py`
- `docs/agent_workflow/2026-06-13-agent-reach-audit-official-source-calibration-claude-notes.md`

If you need to touch files outside this list, stop and report why.

## Forbidden Changes

- Do not modify `KnowledgeSynthesizer`, synthesis prompts, or citation parsing.
- Do not modify `scripts/utils/reporter/scoring_engine.py`.
- Do not modify technical analysis algorithms.
- Do not modify Xueqiu fetch/detail/CDP logic.
- Do not make Agent-Reach mandatory.
- Do not feed Agent-Reach items into LLM synthesis or investment conclusions in this task.
- Do not store full fetched content in the audit JSON.
- Do not access Xueqiu detail pages, Chrome/CDP, or external websites for tests.
- Do not run full report generation unless focused tests pass.

## Implementation Requirements

### 1. Official seed URL metadata

Add support for optional official domains in Agent-Reach web queries.

Recommended shape:

- `agent_reach_official_domains` may be provided in `SkillContext`.
- `generate_agent_reach_queries()` passes it into the web query spec as `official_domains`.
- `PerStockReporter.generate_stock_report()` passes `agent_reach.official_domains` from per-stock config into `pipeline_input` when present.
- Add `"official_domains": ["blacksesame.com"]` under Black Sesame's existing `agent_reach` config.
- `WebConnector.run()` marks each fetched record with:
  - `user_provided_url: True`
  - `query_type: "web_read"`
  - `official_seed_url: True` only when the URL hostname matches one of the configured official domains.
  - `source_type: "official"` only for `official_seed_url`.

Hostname matching should be conservative:

- `blacksesame.com` matches `www.blacksesame.com`.
- `notblacksesame.com` must not match `blacksesame.com`.

Use standard-library URL parsing.

### 2. Quality calibration for official seed URLs

Update Agent-Reach quality scoring so official seed URLs are treated as official evidence, while remaining conservative.

Required behavior:

- Official seed URL records get an explicit reason such as `官方种子来源`.
- Official seed URL records may receive a small credibility bonus through the existing credibility path.
- If a page is portal-like but is an official seed URL:
  - Do not use the misleading reason `疑似门户/导航页，内容价值低`.
  - Use a more precise reason such as `官方页面含导航噪音，已保守降权`.
  - Apply at most a reduced portal/navigation penalty. Do not remove navigation risk entirely.
- Non-official generic portal pages must still be capped below demote and discarded.
- Low-substance explicit URL portals must still be discarded.

### 3. Runtime audit summary in context

Add a compact `agent_reach_run_summary` dict to `SkillContext`.

The summary must not include full fetched `content`. It should include only compact audit fields, for example:

```json
{
  "stock_name": "黑芝麻智能",
  "date_str": "20260613",
  "enabled": true,
  "fetch_status": "ok",
  "quality_status": "ok",
  "queries": [
    {
      "query": "web_read",
      "target_platforms": ["web"],
      "url_count": 6,
      "urls": ["https://www.blacksesame.com/zh/list_10/972.html"],
      "official_domains": ["blacksesame.com"]
    }
  ],
  "counts": {"total": 6, "keep": 6, "demote": 0, "discard": 0},
  "warnings": [],
  "results": [
    {
      "title": "...",
      "source": "AgentReach(web)",
      "url": "https://www.blacksesame.com/zh/list_10/972.html",
      "action": "keep",
      "score": 56,
      "reasons": ["包含股票名称", "官方种子来源"],
      "official_seed_url": true,
      "query_type": "web_read"
    }
  ]
}
```

The exact field order does not matter, but tests should verify:

- Disabled/skipped/empty states still produce a summary with counts.
- Successful runs include query metadata, warnings, counts, and compact result metadata.
- No full item content is present in `agent_reach_run_summary`.

### 4. Optional audit JSON persistence

Persist `agent_reach_run_summary` to a sidecar JSON when a report is assembled and Agent-Reach is enabled.

Recommended default path:

```text
<output_dir>/<stock_name>_<date_str>_agent_reach.json
```

Requirements:

- Write only when `agent_reach_enabled` is true and `agent_reach_run_summary` exists.
- Use `ensure_ascii=False`, `indent=2`, and `default=str`.
- Set `ctx["agent_reach_audit_path"]` to the written path.
- Do not fail report generation if audit persistence fails; log a warning and continue.
- This JSON is an audit artifact, not a new source for scoring or synthesis.

## Tests To Add Or Update First

Write failing tests before implementation.

Minimum tests:

1. Query/config pass-through:
   - `agent_reach_official_domains` reaches the web query spec.
   - `PerStockReporter` passes `agent_reach.official_domains` into `pipeline_input`.

2. Web connector metadata:
   - URL under `www.blacksesame.com` with `official_domains=["blacksesame.com"]` gets `official_seed_url=True` and `source_type="official"`.
   - `https://notblacksesame.com/a` does not match `blacksesame.com`.

3. Quality calibration:
   - Official seed URL with navigation-heavy but article-rich content remains keep or demote, has `官方种子来源`, and does not include `内容价值低`.
   - Generic non-official portal is still discarded.
   - Low-substance explicit URL portal is still discarded.

4. Runtime summary:
   - `agent_reach_quality_skill()` writes `agent_reach_run_summary` for success and skipped/empty paths.
   - Summary contains no `content`.
   - Summary result includes compact URL/action/score/reasons and official metadata.

5. Audit persistence:
   - `ReportAssemblySkill.run()` writes `<stock>_<date>_agent_reach.json` when summary exists and Agent-Reach is enabled.
   - It sets `agent_reach_audit_path`.
   - It does not write the sidecar when Agent-Reach is disabled.

## Focused Test Commands

Run at least:

```bash
python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_assembly_skills.py -q
```

If those pass, optionally run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_stock_reporter_agent_reach_config.py tests/reporter/test_run_black_sesame_entry.py -q
```

Do not run network-dependent report generation until focused tests pass.

## Optional Local Runtime Validation

If focused tests pass and local network is available, run the Black Sesame fast-test report once:

```bash
cd scripts && python3 run_黑芝麻智能.py --fast-test
python3 scripts/check_report_quality.py reports/黑芝麻智能_20260613.md
```

Record whether the sidecar audit JSON exists and whether official seed reasons appear in the Agent-Reach section.

## Notes Output

Write implementation notes to:

```text
docs/agent_workflow/2026-06-13-agent-reach-audit-official-source-calibration-claude-notes.md
```

The notes must include:

- Files changed.
- Tests run and exact pass/fail result.
- Whether runtime validation was run.
- Sidecar audit path if generated.
- Any deviation from this task.
- Any blocker.

## Stop Conditions

Stop and report before implementing if:

- The task requires changing synthesis prompts or LLM behavior.
- The task requires changing scoring engine or technical analysis.
- The task requires modifying Xueqiu/Chrome/CDP collection.
- You need to persist full fetched page content in audit JSON.
- Focused tests expose broad unrelated failures.

