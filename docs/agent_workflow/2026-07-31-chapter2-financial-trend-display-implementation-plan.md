# Chapter 2 Financial Trend Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Project the latest three comparable annual financial periods into a compact Chapter 2 trend table without changing any scoring or annual-material authority.

**Architecture:** A new pure display-view builder reuses `read_periodic_financial_scan_source()` as the single MetricSeries contract reader. Periodic-report intake stores only the compact view in `SkillContext`, and `ValuationRenderer` performs Markdown layout without reading the compute-only source pack.

**Tech Stack:** Python 3, `Decimal`, existing `SkillContext`, pytest.

---

## File Map

- Create `scripts/utils/periodic_report_financial_trend_view.py`: select and format the strict three-year display view.
- Create `tests/utils/test_periodic_report_financial_trend_view.py`: projection contract and failure-mode tests.
- Modify `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`: build and store the display view.
- Modify `tests/utils/test_periodic_report_fulltext_intake.py`: verify context plumbing and unavailable behavior.
- Modify `scripts/utils/reporter/sections/valuation_renderer.py`: render the already-built view after the latest snapshot.
- Modify `tests/reporter/test_valuation_renderer.py`: verify formatting, placement, and no-view regression.
- Create `docs/agent_workflow/2026-07-31-chapter2-financial-trend-display-implementation-notes.md`: record RED/GREEN and verification evidence.

Do not commit intermediate tasks in this dirty worktree. Commit only after the full batch is accepted by the user.

### Task 1: Financial Trend View Contract

**Files:**
- Create: `tests/utils/test_periodic_report_financial_trend_view.py`
- Create: `scripts/utils/periodic_report_financial_trend_view.py`

- [ ] **Step 1: Write failing happy-path tests**

Create API-sourced MetricSeries fixtures with 2022-2025 annual revenue, net profit,
operating cash flow, and derived cash conversion. Add tests asserting:

```python
view = build_periodic_report_financial_trend_view(
    stock_code="300001",
    metric_series_pack=pack,
)
assert view["schema_version"] == "financial_trend_view.v1"
assert view["status"] == "ready"
assert view["display_eligible"] is True
assert view["scoring_eligible"] is False
assert view["years"] == [2023, 2024, 2025]
assert [row["metric_key"] for row in view["rows"]] == [
    "revenue", "net_profit", "operating_cash_flow",
]
assert view["rows"][0]["values"] == ["1.00", "1.20", "1.50"]
assert view["rows"][0]["latest_growth_rate"] == "+25.0%"
assert view["cash_conversion"]["values"] == ["80.0%", "90.0%", "100.0%"]
```

Use values in `万元` that produce exact `亿元` output. Also assert the summary uses
the fixed metric order and contains only the approved direction vocabulary.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_periodic_report_financial_trend_view.py -q -p no:cacheprovider
```

Expected: collection/import failure because the new module does not exist.

- [ ] **Step 3: Implement the minimum ready projection**

Create the module with this public API:

```python
FINANCIAL_TREND_VIEW_SCHEMA_VERSION = "financial_trend_view.v1"
_BASE_METRICS = (
    ("revenue", "营业收入"),
    ("net_profit", "归母净利润"),
    ("operating_cash_flow", "经营现金流"),
)

def build_periodic_report_financial_trend_view(
    *, stock_code: str, metric_series_pack: Dict[str, Any]
) -> Dict[str, Any]:
    source = read_periodic_financial_scan_source(
        stock_code=stock_code,
        metric_series_pack=metric_series_pack,
    )
    if source["status"] != "ok":
        return _unavailable(stock_code)
    candidates = {
        key: [row for row in source["filing_series"]
              if row["report_type"] == "annual" and row["metric_key"] == key]
        for key, _ in _BASE_METRICS
    }
    if any(len(rows) != 1 for rows in candidates.values()):
        return _unavailable(stock_code)
    selected = [candidates[key][0] for key, _ in _BASE_METRICS]
    if len({row["value_basis"] for row in selected}) != 1:
        return _unavailable(stock_code)
    common_years = set.intersection(*(
        {point["report_year"] for point in row["points"]} for row in selected
    ))
    years = sorted(common_years)[-3:]
    if len(years) != 3 or years != list(range(years[0], years[0] + 3)):
        return _unavailable(stock_code)
    raw_values = {
        row["metric_key"]: _point_values(row, years) for row in selected
    }
    rows = [
        _display_row(row, label, years)
        for row, (_, label) in zip(selected, _BASE_METRICS)
    ]
    ratio = _cash_conversion_row(source["derived_series"], selected[0]["value_basis"], years)
    if ratio is None:
        return _unavailable(stock_code)
    return {
        "schema_version": FINANCIAL_TREND_VIEW_SCHEMA_VERSION,
        "status": "ready",
        "display_eligible": True,
        "scoring_eligible": False,
        "stock_code": str(stock_code),
        "years": years,
        "rows": rows,
        "cash_conversion": ratio,
        "summary": "，".join(
            f"{label}{_direction(raw_values[key])}"
            for key, label in _BASE_METRICS
        ) + "。",
        "source_label": "东方财富结构化年度财务数据；仅用于趋势观察，不替代年报确认，不参与评分。",
    }
```

Keep all view field names exactly as defined in the design. Use `Decimal` for
`万元 / 10000` conversion and fixed precision. Read the latest growth string from the
sanitized series change whose interval is `years[-2] -> years[-1]`; do not recompute.

- [ ] **Step 4: Verify GREEN**

Run the Task 1 command. Expected: happy-path tests pass.

- [ ] **Step 5: Write failing admission and sparse-ratio tests**

Add parametrized tests for:

```python
invalid_cases = [
    "wrong_schema", "stock_mismatch", "eligibility_violation",
    "fewer_than_three_common_years", "non_consecutive_common_years",
    "duplicate_annual_metric_series", "mixed_value_basis",
]
```

For each case assert an atomic unavailable result:

```python
assert view == {
    "schema_version": "financial_trend_view.v1",
    "status": "unavailable",
    "display_eligible": False,
    "scoring_eligible": False,
    "stock_code": "300001",
    "years": [],
    "rows": [],
    "cash_conversion": {},
    "summary": "",
    "source_label": "",
}
```

Add one ready case where a non-positive net-profit year causes only the corresponding
cash-conversion value to be `—`. Add a semiannual series and assert it is ignored.

- [ ] **Step 6: Run the expanded tests and verify RED**

Expected: at least the new admission or sparse-ratio assertion fails.

- [ ] **Step 7: Complete admission, direction, and formatting helpers**

Implement only private helpers required by the tests:

```python
_BASE_METRICS = (
    ("revenue", "营业收入"),
    ("net_profit", "归母净利润"),
    ("operating_cash_flow", "经营现金流"),
)

def _unavailable(stock_code: str) -> Dict[str, Any]:
    return {
        "schema_version": FINANCIAL_TREND_VIEW_SCHEMA_VERSION,
        "status": "unavailable",
        "display_eligible": False,
        "scoring_eligible": False,
        "stock_code": str(stock_code),
        "years": [],
        "rows": [],
        "cash_conversion": {},
        "summary": "",
        "source_label": "",
    }

def _point_values(row: Dict[str, Any], years: List[int]) -> List[Decimal]:
    index = {
        point["report_year"]: Decimal(point["numeric_value"])
        for point in row["points"]
    }
    return [index[year] for year in years]

def _latest_growth(row: Dict[str, Any], years: List[int]) -> str:
    interval = (str(years[-2]), str(years[-1]))
    match = next((change for change in row["changes"]
                  if (change["from_period"], change["to_period"]) == interval), None)
    if not match or not match["growth_rate"]:
        return "—"
    value = Decimal(match["growth_rate"].removesuffix("%"))
    return f"{value:+.1f}%"

def _display_row(row: Dict[str, Any], label: str, years: List[int]) -> Dict[str, Any]:
    return {
        "metric_key": row["metric_key"],
        "label": label,
        "unit": "亿元",
        "values": [f"{value / Decimal('10000'):.2f}" for value in _point_values(row, years)],
        "latest_growth_rate": _latest_growth(row, years),
    }

def _cash_conversion_row(
    rows: List[Dict[str, Any]], value_basis: str, years: List[int]
) -> Dict[str, Any] | None:
    candidates = [row for row in rows if row["report_type"] == "annual"
                  and row["value_basis"] == value_basis]
    if len(candidates) > 1:
        return None
    index = ({point["report_year"]: Decimal(point["numeric_value"])
              for point in candidates[0]["points"]} if candidates else {})
    return {
        "metric_key": "operating_cash_flow_to_net_profit",
        "label": "现金转换率",
        "unit": "%",
        "values": [f"{index[year]:.1f}%" if year in index else "—" for year in years],
        "latest_growth_rate": "—",
    }

def _direction(values: List[Decimal]) -> str:
    if values[0] < 0 and values[-1] > 0:
        return "由负转正"
    if values[0] > 0 and values[-1] < 0:
        return "由正转负"
    if all(value < 0 for value in values):
        return "持续为负"
    if values[0] < values[1] < values[2]:
        return "连续增长"
    if values[0] > values[1] > values[2]:
        return "连续下滑"
    return "存在波动"
```

Use the design's strict precedence. Do not add diagnostics, recovery selectors,
fallback periods, or free-form prose.

- [ ] **Step 8: Verify Task 1 GREEN**

Run the Task 1 command. Expected: all projection tests pass.

### Task 2: Intake Context Plumbing

**Files:**
- Modify: `tests/utils/test_periodic_report_fulltext_intake.py`
- Modify: `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`

- [ ] **Step 1: Write failing intake tests**

Extend the existing structured-history-cache test to assert:

```python
trend = result.get("financial_trend_view")
assert trend["schema_version"] == "financial_trend_view.v1"
assert trend["status"] == "ready"
assert trend["years"] == [2023, 2024, 2025]
assert result.get("periodic_report_metric_series_pack")["report_eligible"] is False
```

Add a malformed/missing-history case asserting `financial_trend_view.status` is
`unavailable`, while the intake itself keeps its existing status and outputs.

- [ ] **Step 2: Run the focused intake tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_periodic_report_fulltext_intake.py -q -p no:cacheprovider
```

Expected: failure because `financial_trend_view` is absent.

- [ ] **Step 3: Add the import and one builder call**

Add the package and script-mode imports for
`build_periodic_report_financial_trend_view`. Immediately after MetricSeries creation:

```python
financial_trend_view = build_periodic_report_financial_trend_view(
    stock_code=stock_code,
    metric_series_pack=metric_series_pack,
)
```

Store it once:

```python
ctx.set("financial_trend_view", financial_trend_view)
```

Do not pass the view into synthesis, scoring, snapshots, or source maps.

- [ ] **Step 4: Verify Task 2 GREEN**

Run the Task 2 command. Expected: all intake tests pass.

### Task 3: Chapter 2 Rendering

**Files:**
- Modify: `tests/reporter/test_valuation_renderer.py`
- Modify: `scripts/utils/reporter/sections/valuation_renderer.py`

- [ ] **Step 1: Write failing renderer tests**

Add a ready view to the renderer context and patch the quarterly and peer helpers.
Assert exact content and ordering:

```python
assert "### 近三年财务趋势" in result
assert "| 营业收入（亿元） | 1.00 | 1.20 | 1.50 | +25.0% |" in result
assert "| 现金转换率 | 80.0% | — | 100.0% | — |" in result
assert "仅用于趋势观察，不替代年报确认，不参与评分" in result
assert result.index("### 最新财务快照") < result.index("### 近三年财务趋势")
assert result.index("### 近三年财务趋势") < result.index("### 同业估值对比")
```

Add tests that unavailable, malformed, or absent views render no trend heading and do
not change the existing valuation content.

- [ ] **Step 2: Run renderer tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_valuation_renderer.py -q -p no:cacheprovider
```

Expected: ready-view test fails because the trend subsection is not rendered.

- [ ] **Step 3: Implement a narrow view renderer**

Add a private method that validates only the display-view envelope, never raw series:

```python
def _safe_cells(values: Any, count: int) -> bool:
    return (
        isinstance(values, list)
        and len(values) == count
        and all(isinstance(value, str) and value
                and "|" not in value and "\n" not in value for value in values)
    )

@staticmethod
def _financial_trend_table(view: Any) -> str:
    if not isinstance(view, dict):
        return ""
    if (
        view.get("schema_version") != "financial_trend_view.v1"
        or view.get("status") != "ready"
        or view.get("display_eligible") is not True
        or view.get("scoring_eligible") is not False
    ):
        return ""
    years = view.get("years")
    rows = view.get("rows")
    ratio = view.get("cash_conversion")
    if (
        not isinstance(years, list)
        or len(years) != 3
        or not all(isinstance(year, int) for year in years)
        or years != list(range(years[0], years[0] + 3))
        or not isinstance(rows, list)
        or len(rows) != 3
        or not isinstance(ratio, dict)
    ):
        return ""
    expected = (
        ("revenue", "营业收入", "亿元"),
        ("net_profit", "归母净利润", "亿元"),
        ("operating_cash_flow", "经营现金流", "亿元"),
    )
    display_rows = []
    for row, identity in zip(rows, expected):
        values = row.get("values") if isinstance(row, dict) else None
        if (
            (row.get("metric_key"), row.get("label"), row.get("unit")) != identity
            or not _safe_cells(values, 3)
            or not _safe_cells([row.get("latest_growth_rate")], 1)
        ):
            return ""
        display_rows.append([f"{row['label']}（{row['unit']}）", *values, row["latest_growth_rate"]])
    if (
        ratio.get("metric_key") != "operating_cash_flow_to_net_profit"
        or ratio.get("label") != "现金转换率"
        or not _safe_cells(ratio.get("values"), 3)
    ):
        return ""
    display_rows.append(["现金转换率", *ratio["values"], "—"])
    summary = view.get("summary")
    source_label = view.get("source_label")
    if (
        not _safe_cells([summary, source_label], 2)
        or source_label != "东方财富结构化年度财务数据；仅用于趋势观察，不替代年报确认，不参与评分。"
    ):
        return ""
    lines = [
        "### 近三年财务趋势", "",
        "| 指标 | " + " | ".join(map(str, years)) + " | 最新同比 |",
        "|------|------|------|------|----------|",
        *("| " + " | ".join(row) + " |" for row in display_rows),
        "", f"> **趋势观察**: {summary}", ">", f"> 数据来源：{source_label}", "",
    ]
    return "\n".join(lines)
```

Call it immediately after `_quarterly_financials_table(code)` and before peer metrics:

```python
trend_md = self._financial_trend_table(ctx.get("financial_trend_view"))
if trend_md:
    lines.append(trend_md)
```

Fail closed on malformed row counts, labels, years, or value lengths. Do not format or
infer raw financial numbers in this renderer.

- [ ] **Step 4: Verify Task 3 GREEN**

Run the Task 3 command. Expected: all valuation renderer tests pass.

### Task 4: Regression, Scope, And Notes

**Files:**
- Create: `docs/agent_workflow/2026-07-31-chapter2-financial-trend-display-implementation-notes.md`

- [ ] **Step 1: Run focused suites together**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_periodic_report_financial_trend_view.py \
  tests/utils/test_periodic_report_fulltext_intake.py \
  tests/reporter/test_valuation_renderer.py \
  -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 2: Run affected downstream suites**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_assembly_skills.py \
  tests/reporter/test_report_quality.py \
  tests/reporter/test_report_source_boundary.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_synthesis_skills.py \
  -q -p no:cacheprovider
```

Expected: PASS with no scoring, target, risk, technical, executive-summary, or
Chapter 4 assertion changes.

- [ ] **Step 3: Run repository gates**

```bash
bash tools/ci_grep_gates.sh
git diff --check
```

Expected: all gates pass and no whitespace errors.

- [ ] **Step 4: Audit the diff and runtime size**

Confirm only the allowed runtime/test/docs files changed for this batch. Record
`git diff --numstat` for those files. Target no more than 160 net runtime lines. Stop
if the implementation introduces a second MetricSeries validator, touches a forbidden
consumer, or exceeds the +200 runtime hard limit; return to design instead of
compressing correctness into opaque code.

- [ ] **Step 5: Write implementation notes**

Record:

- modified files
- each RED and GREEN command/result
- focused and downstream totals
- CI and diff-check results
- runtime numstat
- proof that the renderer does not read `periodic_report_metric_series_pack`
- blocker, warning, and deviation
- whether formal report rerun is allowed

Do not generate a formal report in this task. Report generation is the separate
acceptance step after code review.
