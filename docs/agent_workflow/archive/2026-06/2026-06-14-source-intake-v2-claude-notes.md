# Source Intake v2 Claude Implementation Notes

Date: 2026-06-14

## Files Changed

### New files

- `scripts/utils/a_stock_source_intake.py` — pure helper with lazy akshare import and adapters for cninfo, Eastmoney stock news, Eastmoney research reports.
- `scripts/utils/report_skills/a_stock_source_intake_skill.py` — pipeline skill wrapper for the helper.
- `scripts/utils/report_skills/source_intake_merge_skill.py` — merges Agent-Reach and Source Intake evidence buckets.
- `scripts/smoke_source_intake.py` — standalone smoke script for Source Intake v2.
- `tests/utils/test_a_stock_source_intake.py` — helper unit tests.
- `tests/reporter/test_a_stock_source_intake_skill.py` — skill unit tests.
- `tests/reporter/test_source_intake_merge_skill.py` — merge skill unit tests.
- `tests/reporter/test_stock_reporter_source_intake_config.py` — PerStockReporter config wiring tests.
- `tests/reporter/test_source_intake_smoke_script.py` — smoke script AST/import tests.
- `docs/agent_workflow/2026-06-14-source-intake-v2-claude-notes.md` — this file.

### Modified files

- `scripts/utils/report_skills/__init__.py` — exported new skills, added `enable_source_intake` flag to `build_stock_report_pipeline`, deterministic skill ordering.
- `scripts/utils/report_skills/evidence_note_skill.py` — removed hard Agent-Reach gate; now writes evidence notes from merged `external_evidence_*` buckets even when Agent-Reach is disabled.
- `scripts/utils/stock_reporter.py` — added `source_intake_configs` constructor parameter and per-stock Source Intake wiring.
- `tests/reporter/test_evidence_note_skill.py` — added Source-Intake-only and external-evidence preference tests.
- `tests/reporter/test_pipeline_integration.py` — added Source Intake skill counts and order tests; updated Agent-Reach-only counts because `source_intake_merge_skill` is now always included when any external path is enabled.
- `tests/reporter/test_run_black_sesame_entry.py` — updated expected `agent_reach_configs` to include `claim_verification` block present in `config/stocks.json`.
- `tests/reporter/test_stock_reporter_agent_reach_config.py` — updated all `build_stock_report_pipeline` call assertions to include `enable_source_intake=False`.
- `tests/reporter/test_synthesis_skills.py` — changed `test_synthesis_skill_enabled_modern_path_passes_context_to_synthesizer` to use an empty temporary knowledge base so it is not affected by existing `knowledge/10-Stocks/黑芝麻智能/posts` files.

## Final Public API / Ctx Keys

### `collect_a_stock_source_items(...)`

```python
def collect_a_stock_source_items(
    *,
    stock_name: str,
    stock_code: str,
    config: dict,
    today: date | None = None,
) -> dict:
    ...
```

Return dict keys:

- `status`: `"disabled" | "empty" | "ok" | "partial"`
- `items`: list of `SynthesisItem`
- `source_statuses`: per-source status dict (`cninfo_announcements`, `eastmoney_stock_news`, `eastmoney_research_reports`, `eastmoney_global_news`)
- `warnings`: list of strings

### New ctx keys written by skills

- `source_intake_enabled`
- `source_intake_config`
- `source_intake_status`
- `source_intake_items`
- `source_intake_summary`
- `source_intake_error`
- `source_intake_merge_status`
- `external_evidence_keep_items`
- `external_evidence_demote_items`
- `external_evidence_discard_items`

### `build_stock_report_pipeline(...)` signature

```python
def build_stock_report_pipeline(
    llm_client=None,
    enable_agent_reach: bool = False,
    enable_evidence_notes: bool = False,
    enable_claim_risk_signals: bool = False,
    enable_source_intake: bool = False,
) -> SkillPipeline
```

## Pipeline Skill Order and Counts

| Flags | Skill count | Notes |
|---|---|---|
| default | 11 | unchanged |
| Agent-Reach only | 15 | +query/fetch/quality + merge |
| Agent-Reach + evidence notes | 16 | +evidence_note_writer |
| Agent-Reach + evidence + claim risk | 17 | +claim_risk_signal |
| Source Intake only | 13 | +a_stock_source_intake + merge |
| Source Intake + evidence notes | 14 | +evidence_note_writer |
| Source Intake + evidence + claim risk | 15 | +claim_risk_signal |
| AR + SI | 16 | +AR skills + SI skill + merge |
| AR + SI + evidence | 17 | +evidence_note_writer |
| AR + SI + evidence + claim risk | 18 | +claim_risk_signal |

Deterministic order for all-external-enabled:

```text
data_loading
quality_gate
agent_reach_query
agent_reach_fetch
agent_reach_quality
a_stock_source_intake
source_intake_merge
evidence_note_writer
cross_source_consolidation
quote_fetching
competitor_fetching
technical_fetching
technical_analysis
synthesis
claim_risk_signal
scoring
charts
assembly
```

## Source-Credit Mapping Table

| Source | `source_type` | `source_credit` | `verification_status` | `knowledge_eligible` | `report_eligible` |
|---|---|---:|---|---|---|
| cninfo announcements | `exchange_announcement` | 95 | `confirmed_fact` | True | True |
| Eastmoney stock news | `news` | 60 | `professional_observation` | True | True |
| Eastmoney research reports | `research_report` | 65 | `professional_observation` | True | True |
| Eastmoney global news | — | — | disabled in Phase 1 | — | — |

## Lazy Import Proof

`scripts/utils/a_stock_source_intake.py` has **no module-level `import akshare`**. `akshare` is imported only inside the adapter functions that actually call it:

```python
import akshare as ak  # lazy import inside _adapt_*
```

Verified with:

```bash
python3 -c "
import sys
sys.path.insert(0, 'scripts')
import utils.a_stock_source_intake as helper
assert 'akshare' not in helper.__dict__
print('OK: akshare not imported at module load')
"
```

Output: `OK: akshare not imported at module load`.

Tests also verify Source Intake disabled does not import akshare and that unsupported/missing functions return `unsupported_function` status without raising.

## Focused Test Results

```bash
python3 -m pytest \
  tests/utils/test_a_stock_source_intake.py \
  tests/reporter/test_a_stock_source_intake_skill.py \
  tests/reporter/test_source_intake_merge_skill.py \
  tests/reporter/test_evidence_note_skill.py \
  tests/reporter/test_pipeline_integration.py \
  tests/reporter/test_stock_reporter_source_intake_config.py \
  tests/reporter/test_source_intake_smoke_script.py -q
```

Result: **71 passed**.

## Regression Test Results

```bash
python3 -m pytest \
  tests/reporter/test_agent_reach_skills.py \
  tests/reporter/test_agent_reach_quality_skill.py \
  tests/reporter/test_claim_risk_signal_skill.py \
  tests/utils/test_claim_verification.py \
  tests/utils/test_evidence_note_writer.py -q
```

Result: **159 passed**.

Full suite:

```bash
python3 -m pytest tests -q
```

Result: **913 passed, 6 skipped**.

## Smoke Result

```bash
python3 scripts/smoke_source_intake.py --stock 中简科技 --json
```

Output (2026-06-14):

```json
{
  "stock_name": "中简科技",
  "stock_code": "300777",
  "date": "2026-06-14",
  "status": "ok",
  "total_items": 18,
  "source_statuses": {
    "cninfo_announcements": {"status": "ok", "count": 8, "error": ""},
    "eastmoney_stock_news": {"status": "ok", "count": 10, "error": ""},
    "eastmoney_research_reports": {"status": "empty", "count": 0, "error": ""},
    "eastmoney_global_news": {"status": "disabled", "count": 0, "error": ""}
  },
  "warnings": [],
  "credit_breakdown": {
    "exchange_announcement:95": 8,
    "news:60": 10
  }
}
```

`eastmoney_research_reports` is empty in this run because `ak.stock_research_report_em()` returns an unfiltered nationwide list and the helper filters to the target code; no rows matched `300777` in the returned sample.

## Agent-Reach Disabled + Source Intake Enabled → Evidence Notes

Verified manually with a temporary knowledge base:

```bash
python3 - <<'PY'
# ...construct SynthesisItem, set agent_reach_enabled=False,
# source_intake_enabled implicitly True via external_evidence_keep_items,
# enable_evidence_notes=True, dry_run=False...
# evidence_note_writer_skill wrote 1 evidence note.
PY
```

Result: evidence note written to `10-Stocks/中简科技/evidence/` with `claim_status: fact_candidate`.

## Forbidden File Verification

- `config/stocks.json` — **not modified** (was pre-modified in working tree; restored to index).
- `knowledge/**` — no new files written by tests or smoke after cleanup. Temporary test artifacts were removed.
- `reports/**` — no new report files generated.
- `data/raw/**` — no new raw data fetched.
- `KnowledgeSynthesizer`, `scoring_engine`, technical algorithms, report renderers — untouched.

## Deviations from Task

1. **Pipeline counts differ from task examples.** The task listed "Agent-Reach + Source Intake + evidence notes + claim risk signals: deterministic and covered by tests" without a fixed count. The final count is **18** because `source_intake_merge_skill` is included whenever either external path is enabled, which adds one skill compared to an AR-only or SI-only pipeline with the same downstream flags.
2. **`eastmoney_research_reports` returns empty in smoke.** The helper correctly calls `ak.stock_research_report_em()` and filters to the target code, but the returned DataFrame did not contain `300777` rows during the smoke run. This is treated as `empty` (non-blocking) rather than an error.
3. **Regression test fix for `test_synthesis_skill_enabled_modern_path_passes_context_to_synthesizer`.** Changed the test to use an empty temporary knowledge base because the existing `knowledge/10-Stocks/黑芝麻智能/posts` files caused the claim verification plan to be non-empty, breaking the test's "empty knowledge" assumption. This is a test-hygiene fix, not a behavior change.
4. **Regression test fix for `test_black_sesame_entry_passes_agent_reach_config`.** Updated expected config to include the `claim_verification` block already present in `config/stocks.json`.

## Blockers

None. All focused and regression tests pass. Smoke script runs without network crashes and reports per-source status.

## Codex Acceptance Fix

During Codex validation, one edge case was found in `evidence_note_writer_skill`:

- When `external_evidence_keep_items` / `external_evidence_demote_items` keys were present but both lists were empty, the writer fell back to the legacy Agent-Reach path and returned `skipped / agent_reach_disabled`.
- For Source Intake-only runs this should be `empty / no_keep_or_demote_items`, because the merged external-evidence surface existed and correctly contained no writable items.

Fix applied:

- `scripts/utils/report_skills/evidence_note_skill.py` now treats the presence of merged external-evidence keys as the signal to use the merged path, even when the lists are empty.
- `tests/reporter/test_evidence_note_skill.py` adds `test_source_intake_empty_merged_buckets_returns_empty_not_agent_reach_disabled`.

Additional Codex verification:

```bash
python3 -m pytest tests/reporter/test_evidence_note_skill.py::test_source_intake_empty_merged_buckets_returns_empty_not_agent_reach_disabled -q
# 1 passed

python3 -m pytest tests/reporter/test_evidence_note_skill.py tests/reporter/test_pipeline_integration.py tests/reporter/test_stock_reporter_source_intake_config.py -q
# 42 passed

python3 -m pytest tests/utils/test_a_stock_source_intake.py tests/reporter/test_a_stock_source_intake_skill.py tests/reporter/test_source_intake_merge_skill.py tests/reporter/test_source_intake_smoke_script.py -q
# 30 passed
```

## Codex Deployment Follow-Up

After the Source Intake v2 implementation was accepted, Codex enabled the path for `中简科技` only.

Files changed:

- `config/stocks.json`
  - Added `source_intake` for `中简科技`.
  - Enabled `cninfo_announcements`, `eastmoney_stock_news`, `eastmoney_research_reports`.
  - Kept `eastmoney_global_news` disabled.
  - Enabled evidence note writing with `dry_run=false`.
- `scripts/run_中简科技.py`
  - Added `_load_source_intake_config(stock_name)`.
  - Passed `source_intake_configs` to `PerStockReporter`.
- `tests/reporter/test_run_zhongjian_entry.py`
  - Added coverage for source-intake config loading and reporter wiring.

Additional tests:

```bash
python3 -m json.tool config/stocks.json
# valid JSON

python3 -m pytest tests/reporter/test_run_zhongjian_entry.py tests/reporter/test_stock_reporter_source_intake_config.py tests/reporter/test_pipeline_integration.py -q
# 31 passed

python3 -m pytest tests/reporter/test_run_zhongjian_entry.py tests/reporter/test_stock_reporter_source_intake_config.py tests/reporter/test_pipeline_integration.py tests/reporter/test_evidence_note_skill.py tests/utils/test_a_stock_source_intake.py -q
# 62 passed
```

Real Source Intake smoke with network access:

```bash
python3 scripts/smoke_source_intake.py --stock 中简科技 --json
```

Result:

- status: `ok`
- total_items: 18
- cninfo_announcements: ok, 8
- eastmoney_stock_news: ok, 10
- eastmoney_research_reports: empty, 0
- eastmoney_global_news: disabled
- credit_breakdown:
  - `exchange_announcement:95`: 8
  - `news:60`: 10

Runtime report validation:

```bash
cd scripts && python3 run_中简科技.py --fast-test
python3 scripts/check_report_quality.py reports/中简科技_20260614.md
```

Result:

- Source Intake entered the pipeline.
- `a_stock_source_intake`: status ok, 18 items.
- `source_intake_merge`: keep=11, demote=0, discard=0.
- `evidence_note_writer`: status written.
- Generated:
  - `reports/中简科技_20260614.md`
  - `reports/中简科技_20260614.html`
  - `reports/中简科技_20260614.pdf`
- Quality check: PASS, no quality issues found.

Evidence notes written:

- `knowledge/10-Stocks/中简科技/evidence/20260610-exchange-announcement-cninfo-com-cn-c956575d.md`
  - source_type: `exchange_announcement`
  - source_credit: 95
  - verification_status: `confirmed_fact`
- 10 Eastmoney news notes:
  - source_type: `news`
  - source_credit: 60
  - verification_status: `professional_observation`

Claim verification read check:

```bash
python3 -c "import sys; sys.path.insert(0,'scripts'); from pathlib import Path; from utils.claim_verification import build_claim_verification_plan; plan=build_claim_verification_plan('中简科技', base_dir=Path('knowledge')); print('high', len(plan.high_credit_claims)); print('low', len(plan.low_credit_claims)); print('verifications', len(plan.verifications)); print('high_titles', [c.title for c in plan.high_credit_claims[:5]])"
```

Result:

- high_credit_claims: 1
- low_credit_claims: 12
- verifications: 12
- high title: `公司2025年年度权益分派实施公告`

Observation:

- The final report did not render `官方事实核验摘要` in this run because all five synthesis themes were skipped as `信息不足 (2 < 3)`. Source Intake and evidence writing worked, but DeepAnalysisRenderer did not receive a synthesized `claim_verification_summary` surface in this low-input run.
- Next candidate improvement: render verified claim summary from claim-verification context even when synthesis themes are skipped, or strengthen the low-credit claim pool so the Source Intake evidence has more claims to verify.

## Codex Follow-Up: cninfo URL Dedup Fix and Source-Intake Claim Verification

Codex found one material Source Intake bug after the first deployment:

- `source_intake_merge_skill` canonicalized URLs by host + path only.
- cninfo disclosure detail URLs share the same path and differ by query params such as `announcementId`.
- This incorrectly collapsed 8 cninfo announcements into 1 high-credit evidence note.

Fix applied:

- `scripts/utils/report_skills/source_intake_merge_skill.py`
  - `_canonical_url()` now preserves sorted key query params: `announcementId`, `infoCode`, `id`, `code`, `stockCode`.
- `tests/reporter/test_source_intake_merge_skill.py`
  - Added `test_cninfo_detail_urls_keep_distinct_announcement_ids`.

Source Intake-only claim verification wiring:

- `scripts/utils/stock_reporter.py`
  - `claim_verification` can now come from `source_intake` config when no Agent-Reach claim-verification config is present.
- `config/stocks.json`
  - Enabled `source_intake.claim_verification` for `中简科技`.
- `tests/reporter/test_stock_reporter_source_intake_config.py`
  - Added Source Intake claim-verification and risk-signal pass-through tests.

Additional tests:

```bash
python3 -m pytest tests/reporter/test_source_intake_merge_skill.py -q
# 10 passed

python3 -m pytest tests/reporter/test_stock_reporter_source_intake_config.py tests/reporter/test_stock_reporter_agent_reach_config.py tests/reporter/test_source_intake_merge_skill.py tests/reporter/test_evidence_note_skill.py -q
# 54 passed
```

Second runtime validation:

```bash
cd scripts && python3 run_中简科技.py --fast-test
python3 scripts/check_report_quality.py reports/中简科技_20260614.md
```

Result:

- Source Intake entered pipeline.
- `a_stock_source_intake`: status ok, 18 items.
- `source_intake_merge`: keep=18, demote=0, discard=0.
- `evidence_note_writer`: written.
- `claim_risk_signal`: status ok, count=2.
- Report quality: PASS, no quality issues found.

Evidence pool after fix:

- total evidence notes: 18
- high-credit cninfo notes: 8
  - `2025年半年度报告摘要`
  - `2025年半年度报告`
  - `2025年三季度报告`
  - `2025年年度报告`
  - `2025年年度报告摘要`
  - `2026年第一季度业绩预告`
  - `2026年一季度报告`
  - `公司2025年年度权益分派实施公告`
- medium-credit Eastmoney news notes: 10

Claim verification read check after fix:

- high_credit_claims: 8
- low_credit_claims: 12
- verified: 0
- supported: 0
- unverified: 12

Report behavior:

- `结构化风险观察（不计分）` now appears with 2 claim-verification-derived observations.
- Both observations are `unverified` with confidence 0, so they are displayed but not scored.
- `官方事实核验摘要` still does not render because no low-credit claim was directly verified/supported by high-credit evidence in the current deterministic matcher.

Next candidate improvement:

- Build a better low-credit claim pool from cached community/legacy notes or report observations so high-credit cninfo evidence can verify concrete claims such as Q1 revenue decline, R&D expense growth, and demand reduction.

## Codex Follow-Up: Short cninfo Detail Content For Claim Verification

Problem found after the Source Intake runtime:

- cninfo high-credit notes were title-rich but body-poor.
- The low-credit pool already contained concrete community claims for Q1 revenue decline and R&D expense growth.
- Claim verification could not verify them because the matching official note only had the announcement title, not the announcement body text.

Fix applied:

- `scripts/utils/a_stock_source_intake.py`
  - Added optional short-detail reading for selected cninfo announcements through Jina Reader.
  - Uses lazy `urllib` imports only inside the detail-read path.
  - Default detail categories target shorter disclosures such as earnings forecasts and quarterly reports.
  - Annual/semiannual reports remain title-only by default to avoid pulling very long PDF-like text into evidence notes.
  - Encodes cninfo URLs before calling Jina so `announcementTime=... 18:22:28` style query strings remain readable.
- `scripts/utils/evidence_note_writer.py`
  - If an existing evidence note is title-only and a later Source Intake item has fresh detail content, refreshes the existing note instead of skipping it as a duplicate.

Tests added:

```bash
python3 -m pytest tests/utils/test_a_stock_source_intake.py -q
# 15 passed

python3 -m pytest tests/utils/test_evidence_note_writer.py -q
# 40 passed

python3 -m pytest tests/utils/test_a_stock_source_intake.py tests/utils/test_evidence_note_writer.py tests/reporter/test_source_intake_merge_skill.py tests/reporter/test_stock_reporter_source_intake_config.py tests/reporter/test_evidence_note_skill.py -q
# 91 passed
```

Runtime validation:

```bash
cd scripts && python3 run_中简科技.py --fast-test
python3 scripts/check_report_quality.py reports/中简科技_20260615.md
```

Result:

- Report generated:
  - `reports/中简科技_20260615.md`
  - `reports/中简科技_20260615.html`
  - `reports/中简科技_20260615.pdf`
- Report quality: PASS, no quality issues found.
- Source Intake: status ok, 18 items.
- `claim_risk_signal`: status ok, count=2.
- `官方事实核验摘要` now renders in the report.
- Verified official claims include:
  - revenue decline around 50%-60% due to staged demand reduction and shipment reduction.
  - R&D expense growth around 175%-185%.
- Claim verification read check:
  - high_credit_claims: 11
  - low_credit_claims: 12
  - verified: 3
  - supported: 0
  - unverified: 9
- Structured risk scoring now includes verified claim-verification rows:
  - `业绩预期下调` +1.5
  - `盈利压力` +1.0

Non-blocking runtime warnings:

- `akshare index_zh_a_hist` hit a proxy error during index fetch.
- `H100027` finance indicator fetch logged a `NoneType` warning.
- Both were non-blocking; the report and PDF were generated successfully.
