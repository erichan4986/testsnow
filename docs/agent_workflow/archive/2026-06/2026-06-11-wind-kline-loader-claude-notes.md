# Claude Notes: Wind Excel K-Line Loader

## Summary

Added a local Wind Excel K-line loader (`scripts/utils/wind_kline_loader.py`) that reads `data/raw/黑芝麻智能数据.xlsx` and parses OHLCV data from the `黑芝麻智能` sheet, along with benchmark sheets `恒生人工智能主题` and `恒生科技指数`. Modified `scripts/utils/report_skills/technical_skills.py` so that `technical_fetching_skill` prefers local Wind Excel data before falling back to network collection for HK stocks. All focused tests pass. No Xueqiu detail pages were fetched, no Chrome was started.

## Files Changed

| File | Change |
|------|--------|
| `scripts/utils/wind_kline_loader.py` | Created. Provides `find_wind_excel`, `load_wind_ohlcv`, and `load_wind_package` for parsing Wind Excel files with `header=5`, normalizing columns, dropping incomplete rows, and setting DataFrame attrs. |
| `scripts/utils/report_skills/technical_skills.py` | Added `load_wind_package` import. Added `_df_to_daily_data` helper. Inserted Wind Excel priority logic between cached `technical` check and network `TechnicalCollector.collect()` fallback. |
| `tests/reporter/test_wind_kline_loader.py` | Created. Tests `find_wind_excel`, `load_wind_ohlcv` normalization, and `load_wind_package` benchmark inclusion. |
| `tests/reporter/test_technical_skills_contract.py` | Added `test_hk_code_prefers_local_wind_excel_before_network_collector` verifying that Wind data bypasses network collection and sets correct `data_source`, `market`, `benchmark_data`, and `stock_raw` sync. |

## Tests Run

| Command | Result | Notes |
|---------|--------|-------|
| `PYTHONPATH=. pytest tests/reporter/test_wind_kline_loader.py -v` (before impl) | Fail (import error) | `ModuleNotFoundError: No module named 'wind_kline_loader'` — expected red. |
| `PYTHONPATH=. pytest tests/reporter/test_wind_kline_loader.py -v` (after impl) | Pass (3/3) | All loader tests pass. |
| `PYTHONPATH=. pytest tests/reporter/test_technical_skills_contract.py::test_hk_code_prefers_local_wind_excel_before_network_collector -v` (before impl) | Fail | `collect` was called when it should not have been — expected red. |
| `PYTHONPATH=. pytest tests/reporter/test_technical_skills_contract.py -v` (after impl) | Pass (5/5) | All contract tests pass, no regressions. |
| `PYTHONPATH=. pytest tests/reporter/test_wind_kline_loader.py tests/reporter/test_technical_skills_contract.py -v` | Pass (8/8) | Combined focused tests pass. |
| `python3 scripts/check_report_quality.py --sample` | Pass | No quality issues found. |
| `cd scripts && python3 run_黑芝麻智能.py` | Interrupted | Full pipeline involves external LLM and network calls; stopped after confirming pipeline starts. Markdown report generation was not the acceptance target for this task. |

## Local Command Used

User triggered this task from an already-open local Claude Code session by pasting the task file path and instructions.

## Deviations From Task

- None.

## Blockers Or Follow-Ups

- The full `run_黑芝麻智能.py` end-to-end run was interrupted because it involves external LLM calls (DeepSeek API) and network scraping that are out of scope for this Wind loader task. The core acceptance criteria — Wind Excel loader parsing, technical skill priority logic, and focused tests — are all verified.
- No modifications were needed outside the allowed file list.
