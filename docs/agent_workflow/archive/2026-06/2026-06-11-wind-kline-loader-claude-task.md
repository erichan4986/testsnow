# Claude Code Task: Wind Excel K-Line Loader

> **Design Source**: User-approved Codex design in chat, 2026-06-11
> **Notes Output**: `docs/agent_workflow/2026-06-11-wind-kline-loader-claude-notes.md`
> **Local Runner**: user runs this prompt from their local trusted Claude Code terminal

You are implementing a locked task for the stock report pipeline. Stay within scope. Use test-first development: write the failing tests, run them and observe the expected failure, then implement the minimal code to pass.

---

## 0. Local Command

Recommended local command:

```bash
claude < docs/agent_workflow/2026-06-11-wind-kline-loader-claude-task.md
```

Record the actual command or interaction mode used in the notes output file.

---

## 1. Objective

Add a local Wind Excel K-line loader so Hong Kong stocks can use manually exported行情数据 before falling back to network collectors.

The immediate acceptance target is 黑芝麻智能:

- Read `data/raw/黑芝麻智能数据.xlsx`.
- Use sheet `黑芝麻智能` as the stock OHLCV source.
- Preserve sheets `恒生人工智能主题` and `恒生科技指数` as benchmark OHLCV data.
- Let `technical_fetching_skill` prefer the local Wind Excel data for `黑芝麻智能` / `02533`.
- Keep existing report generation entry points working.

Do not fetch Xueqiu detail pages. Do not start Chrome. Do not change LLM prompts.

---

## 2. Current Excel Shape

The source file is:

```text
data/raw/黑芝麻智能数据.xlsx
```

Observed sheets:

```text
恒生人工智能主题
黑芝麻智能
恒生科技指数
```

Observed layout:

- Wind metadata rows first.
- English header row at Excel row 6, parsed with `header=5`.
- Columns after parsing: `Date`, `open`, `high`, `low`, `close`, `volume`, `amt`.
- Final row may contain only `Date` and `close`; incomplete OHLCV rows must be excluded from indicator computation.

Use `pandas.read_excel(path, sheet_name=..., header=5)` for parsing.

---

## 3. Allowed Changes

You may modify:

- `scripts/utils/wind_kline_loader.py` — create a focused local Wind Excel loader.
- `scripts/utils/report_skills/technical_skills.py` — prefer local Wind data before network collection and expose benchmark data in `technical`.
- `tests/reporter/test_wind_kline_loader.py` — add parser tests.
- `tests/reporter/test_technical_skills_contract.py` — add pipeline contract tests for local Wind priority.
- `README.md` — optional, only add a short command/note for local Wind Excel usage if useful.
- `docs/agent_workflow/2026-06-11-wind-kline-loader-claude-notes.md` — write concise execution notes.

If you believe `scripts/utils/data_collector.py` must change, stop and write the reason in notes. The intended implementation should avoid changing core indicator algorithms by reusing `TechnicalCollector.compute_indicators()` from `technical_skills.py`.

---

## 4. Do Not Modify

Do not modify:

- `scripts/xueqiu_monitor_v2.py`
- `scripts/run_*.py`
- `scripts/run_technical_analysis.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/technical_analyzer.py`
- `scripts/utils/reporter/price_target.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/reporter/sections/**`
- `data/raw/**`
- `knowledge/10-Stocks/**`
- `reports/**`

Do not change scoring thresholds, technical indicator formulas, LLM prompts, report templates, Xueqiu scraping behavior, or existing generated output files.

The repository may already contain unrelated uncommitted changes. Do not revert them.

---

## 5. Required Behavior

### 5.1 Loader Contract

Create `scripts/utils/wind_kline_loader.py`.

Required public functions:

```python
from pathlib import Path
from typing import Dict
import pandas as pd


def find_wind_excel(stock_name: str, raw_dir: Path | None = None) -> Path | None:
    ...


def load_wind_ohlcv(path: Path, sheet_name: str, days: int | None = None) -> pd.DataFrame:
    ...


def load_wind_package(stock_name: str, days: int = 120, raw_dir: Path | None = None) -> Dict:
    ...
```

Expected `load_wind_ohlcv` behavior:

- Parse with `header=5`.
- Rename columns to lowercase standard names:
  - `Date` -> `date`
  - `open` -> `open`
  - `high` -> `high`
  - `low` -> `low`
  - `close` -> `close`
  - `volume` -> `volume`
  - `amt` -> `amount`
- Convert date with `pd.to_datetime`.
- Convert numeric fields with `pd.to_numeric(errors="coerce")`.
- Drop rows missing any of `date`, `open`, `high`, `low`, `close`, `volume`.
- Sort ascending by date.
- Tail to `days` when provided.
- Reset index.
- Set attrs:
  - `df.attrs["data_source"] = "wind_excel"`
  - `df.attrs["adjustment"] = "raw"`
  - `df.attrs["wind_sheet"] = sheet_name`

Expected `load_wind_package` behavior:

- Return `{}` when no matching Excel exists.
- Load the stock sheet matching `stock_name`.
- Load benchmark sheets if present:
  - `恒生人工智能主题`
  - `恒生科技指数`
- Return:

```python
{
    "path": "...",
    "daily": df_daily,
    "benchmarks": {
        "恒生人工智能主题": df_ai,
        "恒生科技指数": df_tech,
    },
}
```

### 5.2 Pipeline Contract

Modify `technical_fetching_skill` so the priority is:

1. Existing `stock_raw["technical"]`.
2. Local Wind Excel package.
3. Existing `TechnicalCollector.collect(...)` network path.

When Wind data is used:

- Reuse `TechnicalCollector().compute_indicators(df_daily, code=code)`.
- Do not fetch network data only to compute indicators.
- Store `daily_data` as lists under `technical["daily_data"]` with keys:
  - `date`, `open`, `high`, `low`, `close`, `volume`, `amount`
- Store `technical["benchmark_data"]` as a dict of benchmark list payloads.
- Store `technical["data_source"] = "wind_excel"`.
- Store `technical["adjustment"] = "raw"`.
- Store `technical["code"] = code`.
- Store `technical["market"] = "hk"` for `02533`.
- Store `technical["price_target"] = None` unless you can compute it without changing core price target logic.
- Call the existing `_set_technical_outputs(tech_data)` so `ctx.technical`, `ctx.daily_data`, `ctx.indicators`, and `ctx.stock_raw["technical"]` stay synchronized.

If Wind loading fails with an exception, log a warning and fall back to the existing network collector.

---

## 6. Test-First Implementation Steps

### Task 1: Add Wind Loader Tests

Create `tests/reporter/test_wind_kline_loader.py`.

Add tests equivalent to:

```python
from pathlib import Path

from scripts.utils.wind_kline_loader import (
    find_wind_excel,
    load_wind_ohlcv,
    load_wind_package,
)


def test_find_wind_excel_locates_black_sesame_file():
    path = find_wind_excel("黑芝麻智能")
    assert path is not None
    assert path.name == "黑芝麻智能数据.xlsx"


def test_load_wind_ohlcv_normalizes_and_drops_incomplete_rows():
    path = Path("data/raw/黑芝麻智能数据.xlsx")
    df = load_wind_ohlcv(path, "黑芝麻智能", days=120)

    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume", "amount"]
    assert len(df) <= 120
    assert df[["open", "high", "low", "close", "volume"]].isna().sum().sum() == 0
    assert str(df["date"].iloc[-1].date()) == "2026-06-09"
    assert df.attrs["data_source"] == "wind_excel"
    assert df.attrs["adjustment"] == "raw"
    assert df.attrs["wind_sheet"] == "黑芝麻智能"


def test_load_wind_package_includes_benchmarks():
    package = load_wind_package("黑芝麻智能", days=120)

    assert package["daily"].attrs["data_source"] == "wind_excel"
    assert "恒生人工智能主题" in package["benchmarks"]
    assert "恒生科技指数" in package["benchmarks"]
    assert len(package["benchmarks"]["恒生科技指数"]) <= 120
```

Run:

```bash
PYTHONPATH=. pytest tests/reporter/test_wind_kline_loader.py -v
```

Expected before implementation: import failure for `scripts.utils.wind_kline_loader`.

Record the failing output summary in notes.

### Task 2: Implement `wind_kline_loader.py`

Create the loader with only the behavior described above.

Run:

```bash
PYTHONPATH=. pytest tests/reporter/test_wind_kline_loader.py -v
```

Expected after implementation: pass.

### Task 3: Add Technical Skill Priority Test

Modify `tests/reporter/test_technical_skills_contract.py`.

Add a test equivalent to:

```python
def test_hk_code_prefers_local_wind_excel_before_network_collector():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "stock_codes": {"黑芝麻智能": "02533"},
        "stock_raw": {},
    })

    with patch("report_skills.technical_skills.TechnicalCollector") as mock_collector:
        mock_collector.return_value.compute_indicators.return_value = {
            "close": 14.02,
            "volume": 5959595,
            "_resonance": {
                "trend": "多头",
                "composite_score": 7,
                "trend_state": {"primary_state": "上升趋势", "stage": "推进期"},
                "trend_health": {"score": 72, "grade": "B+"},
            },
        }
        result = technical_fetching_skill(ctx)

    mock_collector.return_value.collect.assert_not_called()
    mock_collector.return_value.compute_indicators.assert_called_once()
    assert result.get("technical")["data_source"] == "wind_excel"
    assert result.get("technical")["market"] == "hk"
    assert result.get("daily_data")["close"][-1] == 14.02
    assert "恒生科技指数" in result.get("technical")["benchmark_data"]
    assert result.get("stock_raw")["technical"]["data_source"] == "wind_excel"
```

Run:

```bash
PYTHONPATH=. pytest tests/reporter/test_technical_skills_contract.py::test_hk_code_prefers_local_wind_excel_before_network_collector -v
```

Expected before implementation: `TechnicalCollector.collect` is called or `technical` remains unavailable.

Record the failing output summary in notes.

### Task 4: Implement Technical Skill Wind Priority

Modify `scripts/utils/report_skills/technical_skills.py`.

Implementation guidance:

- Add a module-level import for `load_wind_package` with the same fallback style used for `TechnicalCollector`.
- Add helpers near existing helper functions:

```python
def _df_to_daily_data(df):
    result = {}
    for col in ("date", "open", "high", "low", "close", "volume", "amount"):
        if col not in df.columns:
            continue
        values = df[col]
        if col == "date":
            result[col] = [str(v.date()) if hasattr(v, "date") else str(v) for v in values]
        else:
            result[col] = [float(v) for v in values]
    return result
```

- For benchmarks, convert each DataFrame through the same helper.
- Try Wind package only after market is known and before `TechnicalCollector.collect(...)`.
- Keep cached `stock_raw["technical"]` priority above Wind.
- Fall back to network collection if no Wind package exists or the Wind package is invalid.

Run:

```bash
PYTHONPATH=. pytest tests/reporter/test_technical_skills_contract.py -v
```

Expected after implementation: pass.

---

## 7. Required Verification

Run focused tests:

```bash
PYTHONPATH=. pytest tests/reporter/test_wind_kline_loader.py tests/reporter/test_technical_skills_contract.py -v
```

Run related report quality checks:

```bash
python3 scripts/check_report_quality.py --sample
```

If time allows, run the real single-stock entry:

```bash
cd scripts
python3 run_黑芝麻智能.py
```

Then run:

```bash
python3 scripts/check_report_quality.py reports/黑芝麻智能_20260611.md
```

If the real entry fails only because of external network, LLM, Chrome, or PDF export, record the exact failure in notes. The Markdown report should still be generated when local Wind data is available.

---

## 8. Stop Conditions

Stop and write the blocker into the notes file if:

- You need to modify files outside the allowed list.
- The Excel file is missing or has a different sheet/column layout than described.
- You need to change technical indicator formulas, scoring thresholds, price-target algorithms, or renderers.
- You need to fetch Xueqiu detail pages, start Chrome, or access a logged-in browser session.
- LLM synthesis prompt/output changes become necessary.
- Tests reveal broad unrelated failures.

---

## 9. Required Notes Format

Write `docs/agent_workflow/2026-06-11-wind-kline-loader-claude-notes.md`:

```markdown
# Claude Notes: Wind Excel K-Line Loader

## Summary

- 

## Files Changed

- 

## Tests Run

| Command | Result | Notes |
|---------|--------|-------|
|  |  |  |

## Local Command Used

```bash

```

## Deviations From Task

- None.

## Blockers Or Follow-Ups

- None.
```
