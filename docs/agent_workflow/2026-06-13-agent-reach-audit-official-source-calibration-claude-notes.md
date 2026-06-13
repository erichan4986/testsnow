# Claude Notes: Agent-Reach Audit Persistence + Official Source Calibration

## Summary

Implemented Agent-Reach audit persistence and official seed source calibration without changing synthesis prompts, scoring engine, technical analysis, Xueqiu/CDP collection, or core report structure. Official `blacksesame.com` URLs are now marked as official seeds, receive a calibrated credibility bonus, and use a precise navigation-noise reason instead of a misleading "content value low" label. A compact, content-free audit summary is written to `SkillContext` and persisted as a sidecar JSON during report assembly.

## Files Changed

- `scripts/utils/report_skills/agent_reach_query_skill.py` — passes `agent_reach_official_domains` into web query spec.
- `scripts/utils/report_skills/agent_reach_skill.py` — `WebConnector` marks records with `official_seed_url` and `source_type=official` based on conservative hostname matching.
- `scripts/utils/report_skills/agent_reach_quality_skill.py` — adds official-seed credibility bonus and calibrated portal reason; writes compact `agent_reach_run_summary` to context.
- `scripts/utils/report_skills/assembly_skills.py` — persists sidecar audit JSON and sets `agent_reach_audit_path`.
- `scripts/utils/stock_reporter.py` — passes per-stock `agent_reach.official_domains` into pipeline input.
- `config/stocks.json` — added `"official_domains": ["blacksesame.com"]` to Black Sesame's `agent_reach` config.
- `tests/reporter/test_agent_reach_skills.py` — official_domains pass-through tests.
- `tests/reporter/test_agent_reach_connector.py` — official seed URL metadata and hostname matching tests.
- `tests/reporter/test_agent_reach_quality_skill.py` — calibration, portal, and runtime summary tests.
- `tests/reporter/test_assembly_skills.py` — audit JSON persistence tests.
- `tests/reporter/test_stock_reporter_agent_reach_config.py` — reporter pass-through test.
- `tests/reporter/test_run_black_sesame_entry.py` — updated expected config shape to include `official_domains`.

## Tests Run

| Command | Result |
|---------|--------|
| `python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_assembly_skills.py tests/reporter/test_stock_reporter_agent_reach_config.py -q` | 116 passed |
| `python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_stock_reporter_agent_reach_config.py tests/reporter/test_run_black_sesame_entry.py -q` | 48 passed |
| Combined focused + optional | 150 passed |

## Runtime Validation

Ran the optional Black Sesame fast-test report:

```bash
cd scripts && python3 run_黑芝麻智能.py --fast-test
python3 scripts/check_report_quality.py reports/黑芝麻智能_20260613.md
```

- Report generated: `reports/黑芝麻智能_20260613.md`
- Dashboard generated: `reports/黑芝麻智能_20260613.html`
- PDF generated: `reports/黑芝麻智能_20260613.pdf`
- Sidecar audit JSON: `reports/黑芝麻智能_20260613_agent_reach.json`
- Quality check: **PASS**

## Sidecar Audit JSON

Path: `reports/黑芝麻智能_20260613_agent_reach.json`

Contents:
- `stock_name`, `date_str`, `enabled`, `fetch_status`, `quality_status`
- Query metadata including `official_domains`
- Counts: `total`, `keep`, `demote`, `discard`
- Warnings list
- Compact results with `title`, `source`, `url`, `action`, `score`, `reasons`, `official_seed_url`, `query_type`
- No full fetched `content` is included

## Official Seed Calibration Result

For Black Sesame's 6 official URLs:

| URL | Action | Score | Official Seed |
|-----|--------|-------|---------------|
| /zh/list_10/972.html | keep | 91 | yes |
| /zh/list_9/977.html | keep | 95 | yes |
| /zh/list_9/966.html | keep | 90 | yes |
| /zh/list_9/964.html | keep | 95 | yes |
| /zh/list_9/961.html | keep | 95 | yes |
| /zh/list_10/912.html | keep | 93 | yes |

Reasons now include:
- `官方/认证来源`
- `官方种子来源`
- `官方页面含导航噪音，已保守降权`

The misleading reason `疑似门户/导航页，内容价值低` no longer appears for official seed URLs.

## Deviations From Task

- None.

## Blockers

- None.

## Notes

- The audit JSON is intentionally an audit artifact and is not used as an input for scoring or synthesis.
- Low-substance non-official portals and low-substance official portals are still discarded, as verified by tests.
- Hostname matching is conservative: `blacksesame.com` matches `www.blacksesame.com` and `sub.blacksesame.com`, but not `notblacksesame.com`, `blacksesame.com.cn`, or `xblacksesame.com`.
