# Claude Task: Agent-Reach Curated URL Expansion for Black Sesame

## Goal

Expand Agent-Reach coverage for 黑芝麻智能 by adding a small, curated set of explicit official/public Web URLs to `config/stocks.json`, then validate through the single-stock deep report entry.

This is a low-risk source-expansion task. Do not add login-based platforms, do not change connector code, and do not run the legacy batch monitor.

## Background

Current Agent-Reach runtime is working for 黑芝麻智能 with one explicit official URL:

```json
"agent_reach": {
  "enabled": true,
  "web_urls": [
    "https://www.blacksesame.com/zh/list_10/972.html"
  ]
}
```

The existing URL scores `51 / keep` and renders cleanly after the Jina cleanup fix.

Codex found several official Black Sesame pages that are good candidates for curated Web evidence:

- `https://www.blacksesame.com/zh/list_10/972.html`
  - A2000U/A2000X ISO 26262 ASIL-D certification, already configured.
- `https://www.blacksesame.com/zh/list_9/977.html`
  - Strategic cooperation with 上实科技 around embodied intelligence and Hong Kong robotics innovation platform.
- `https://www.blacksesame.com/zh/list_9/966.html`
  - Joins 理想星环OS open-source ecosystem; chip-platform adaptation and vehicle OS cooperation.
- `https://www.blacksesame.com/zh/list_9/964.html`
  - Platform-level cooperation with Dongfeng; 武当C1296 powering 天元智舱Plus.
- `https://www.blacksesame.com/zh/list_9/961.html`
  - Strategic cooperation with 如祺出行 for localized L4 Robotaxi ecosystem.
- Optional if you want one product/award evidence page:
  - `https://www.blacksesame.com/zh/list_10/912.html`
  - 华山A1000 “中国芯”整车芯应用 award and mass-production examples.

## Scope

Allowed changes:

- `config/stocks.json`
- `docs/agent_workflow/2026-06-12-agent-reach-curated-url-expansion-claude-notes.md`

Do not modify:

- `scripts/utils/report_skills/agent_reach_skill.py`
- `scripts/utils/report_skills/agent_reach_query_skill.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- pipeline assembly, scoring, technical analysis, LLM synthesis, report templates, or entry scripts
- `scripts/xueqiu_monitor_v2.py`

## Implementation Instructions

1. Update only the 黑芝麻智能 item in `config/stocks.json`.
2. Preserve the existing URL.
3. Add 3-5 additional official URLs from the candidate list above.
4. Keep the list short. Prefer signal diversity:
   - one certification/product-safety item
   - one customer/platform cooperation item
   - one vehicle OS/ecosystem item
   - one L4/Robotaxi or embodied intelligence expansion item
5. Do not add Twitter/X, 小红书, 抖音, 雪球, 微信, 微博, Exa, or any source requiring cookie/login.

## Validation

Run from the repo root unless noted.

1. Focused tests:

```bash
python3 -m pytest tests/reporter/test_run_black_sesame_entry.py \
  tests/reporter/test_stock_reporter_agent_reach_config.py \
  tests/reporter/test_agent_reach_evidence_renderer.py -q
```

2. Generate the single-stock deep report in fast-test mode:

```bash
cd scripts
python3 run_黑芝麻智能.py --fast-test
```

Important: Do not run `xueqiu_monitor_v2.py` for this task. Do not refresh Zhihu content or run ZhihuCurator/LLM curator; fast-test mode should reuse local `report_input` data where available and avoid paid Zhihu curation.

3. Quality check:

```bash
cd ..
python3 scripts/check_report_quality.py reports/黑芝麻智能_20260612.md
```

If the report date differs, use the generated Markdown file from the latest `run_黑芝麻智能.py --fast-test` output.

4. Inspect the generated Markdown/PDF for:

- `## Agent-Reach 外部证据观察` exists.
- At least 2 Agent-Reach records are `keep` or `demote`; ideally multiple themes appear.
- No `Title:`, `URL Source:`, or `Markdown Content:` residue.
- No huge table-cell overflow in Markdown/PDF.
- Report quality checker passes.

## Stop Conditions

Stop and write notes without further changes if:

- Any added URL repeatedly times out or makes `run_黑芝麻智能.py --fast-test` unstable.
- Agent-Reach section becomes unreadable or overly long.
- Quality gate discards all newly added URLs.
- Any source file other than `config/stocks.json` would need changes.

## Notes Output

Write:

`docs/agent_workflow/2026-06-12-agent-reach-curated-url-expansion-claude-notes.md`

Include:

- URLs added
- keep/demote/discard result per URL if visible
- tests run and results
- generated report paths
- any discarded URL and suspected reason
- git status summary
