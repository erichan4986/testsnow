# Claude Notes: Agent-Reach Single-Stock Source Expansion

## Summary

Implemented Phase 6A–6C of the Agent-Reach single-stock source expansion for 黑芝麻智能 / HK02533.

- **Phase 6A**: Created a source inventory document documenting candidate sources, risks, and recommendations.
- **Phase 6B**: Reviewed the inventory and confirmed the existing 6 `blacksesame.com` article URLs remain the appropriate Agent-Reach web source. No new URLs or RSS feeds were added to `config/stocks.json` because the remaining candidates are portal/JS-heavy or unstable.
- **Phase 6C**: Added `scripts/smoke_agent_reach.py --stock <name>` for lightweight query/fetch/quality validation without full report generation.

No changes were made to KnowledgeSynthesizer, synthesis_skills, scoring_engine, technical analysis, Xueqiu/CDP collection, or report conclusions outside the Agent-Reach evidence section.

## Files Changed

- `docs/agent_workflow/2026-06-13-agent-reach-source-inventory.md` — source inventory for 黑芝麻智能.
- `scripts/smoke_agent_reach.py` — single-stock smoke validation script.
- `tests/reporter/test_agent_reach_smoke_script.py` — tests proving smoke scope and safety.
- `tests/reporter/test_agent_reach_source_config.py` — tests proving config remains scoped to the target stock.

## Files Not Changed

- `config/stocks.json` — no new URLs/feeds added; existing 6 official `blacksesame.com` URLs remain valid after smoke validation.
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/reporter/scoring_engine.py`
- Technical-analysis modules
- Xueqiu fetchers / CDP scripts

## Source Inventory Summary

| Recommendation | Count | Notes |
|----------------|-------|-------|
| Keep | 6 | Existing `blacksesame.com` article URLs already in config |
| Rejected | 5 | `ir.blacksesame.com` portal pages, HKEX form-based pages, news center listing, generic RSS |
| Needs-test | 0 | — |
| RSS enabled | 0 | No stable stock-specific RSS feed identified |

Key rejected sources:

- `https://ir.blacksesame.com/announcement.html?lang=zh-cn` — JS-heavy navigation container; unstable for Jina Reader.
- `https://ir.blacksesame.com/report.html?lang=zh-cn` — Same as above.
- HKEX disclosure pages — Require form submission; no stable direct URL pattern.
- `https://www.blacksesame.com/zh/news-center/` — Listing/portal page; per-article URLs are preferred.
- Curated third-party RSS — No suitable feed identified; risk of unrelated articles.

## Config Update Decision

- **No new URLs or feeds added** to `config/stocks.json`.
- Reason: the inventory concluded the existing 6 official article URLs are the highest-confidence sources. Portal and exchange pages are not fetchable through the current `WebConnector` without JS/form interaction, and no suitable RSS feed exists.
- `official_domains` remains `["blacksesame.com"]`.
- No other stock received `agent_reach.enabled=true`.

## Smoke Script

`scripts/smoke_agent_reach.py --stock 黑芝麻智能`

Behavior:

- Loads `config/stocks.json`.
- Builds a minimal `SkillContext`.
- Runs only `agent_reach_query_skill`, `agent_reach_fetch_skill`, `agent_reach_quality_skill`.
- Prints a compact status table (or compact JSON when `--json` is passed).
- Writes audit JSON only when `--write-audit` is explicitly provided; `--dry-run` suppresses writes.
- Does **not** import or instantiate `PerStockReporter`, `ZhihuCollector`, `KnowledgeSynthesizer`, PDF export, or full report assembly.

## Tests Run

| Command | Result |
|---------|--------|
| `python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_stock_reporter_agent_reach_config.py tests/reporter/test_agent_reach_source_config.py tests/reporter/test_agent_reach_smoke_script.py tests/reporter/test_run_black_sesame_entry.py tests/reporter/test_assembly_skills.py -q` | 136 passed |

New tests specifically added:

- `test_smoke_script_does_not_import_forbidden_modules` — AST check for banned names.
- `test_smoke_runs_only_query_fetch_quality` — mocks the three skills, verifies no other paths run.
- `test_smoke_disabled_stock` / `test_smoke_unknown_stock` — disabled/unknown handling.
- `test_smoke_writes_audit_json` — audit JSON is written and contains no `content` key.
- `test_smoke_dry_run_does_not_write_audit` — `--dry-run` suppresses file write.
- `test_smoke_summary_does_not_contain_full_content` — compact audit guarantee.
- `test_only_target_stock_has_agent_reach_enabled` — config scope assertion.
- `test_other_stocks_do_not_have_agent_reach_urls` — no cross-stock leakage.

## Runtime Validation

Ran the smoke script for the target stock:

```bash
python3 scripts/smoke_agent_reach.py --stock 黑芝麻智能 --write-audit --output-dir reports
```

Output:

```text
enabled:        True
query count:    1
fetch status:   ok
quality status: ok
keep:           6
demote:         0
discard:        0
total:          6
warnings:       0
audit path:     reports/黑芝麻智能_20260613_agent_reach_smoke.json
```

Smoke script contract fixes (post-review):

- `--json` now outputs compact JSON to stdout.
- Audit JSON is written only when `--write-audit` is explicitly provided; default run only prints the CLI table.
- Audit filename changed from `*_agent_reach.json` to `*_agent_reach_smoke.json` to avoid collision with formal report audits.

## Audit File Generated

- `reports/黑芝麻智能_20260613_agent_reach_smoke.json`
  - Compact, content-free summary.
  - Contains `stock_name`, `date_str`, `enabled`, `fetch_status`, `quality_status`, query metadata, counts, warnings, and compact result rows.
  - No full fetched `content` included.

## Full Report Run

No full report was generated. The focused tests and smoke validation were run instead.

## Deviations From Task

- None.

## Blockers

- None.

## Notes

- The smoke script intentionally avoids the full `build_stock_report_pipeline` so it cannot accidentally trigger LLM synthesis, scoring, technical analysis, PDF export, or Xueqiu/Zhihu collection.
- Scores in the generated audit JSON (80–85) are consistent with the official-seed calibration logic: official seed URLs still receive the credibility bonus and the reduced portal-noise penalty.
- The source inventory is written before config decisions; config was left unchanged because the inventory validated the existing sources and rejected new candidates.
