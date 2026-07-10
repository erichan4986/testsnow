# Chapter 4 Hardcode Slimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development and executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove dead code, merge duplicated Chapter 4 helpers, and replace stock-specific renderer keyword rules with MaterialRow metadata while preserving report structure and source boundaries.

**Architecture:** Keep shared annual-role classification and citation identity in `deep_analysis_material_snapshot.py`, the owner of MaterialRow. Make the renderer consume those helpers and use row title/render role for summaries and 4.4 variable names. Do not create another module or alter producer schemas.

**Tech Stack:** Python dataclasses/helpers, pytest, existing report renderer.

---

### Task 1: Shared Classification And Citation Identity

**Files:**

- Modify: `tests/utils/test_deep_analysis_material_snapshot.py`
- Modify: `scripts/utils/deep_analysis_material_snapshot.py`
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py`

- [ ] **Step 1: Write failing shared-helper tests**

Import the desired public helpers and assert:

```python
assert classify_annual_render_role("营业收入") == "financial_explanation"
assert classify_annual_render_role("主营业务与产品") == "product_business"
assert classify_annual_render_role("任意标题", "management_view") == "management_view"
assert citation_identity({"url": "https://example.com/a"}) == ("url", "https://example.com/a")
assert citation_identity({"source": "研报", "author": "机构", "title": "正文"}) == (
    "meta", "研报", "机构", "正文"
)
```

- [ ] **Step 2: Run the test and verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_deep_analysis_material_snapshot.py \
  -q -p no:cacheprovider
```

Expected: import failure because the public helper names do not exist.

- [ ] **Step 3: Implement and reuse the helpers**

- Rename `_annual_render_role` to `classify_annual_render_role`.
- Rename `_citation_identity` to `citation_identity` with an optional fallback
  ref.
- Import both in the renderer.
- Delete renderer `_annual_row_group` and
  `_curated_external_citation_identity`.
- Delete dead renderer `_compact_text`, which has no caller.

- [ ] **Step 4: Run snapshot and renderer tests and verify GREEN**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_deep_analysis_material_snapshot.py \
  tests/reporter/test_deep_analysis_renderer.py \
  -q -p no:cacheprovider
```

### Task 2: Replace Stock-Specific Projection Rules

**Files:**

- Modify: `tests/reporter/test_deep_analysis_renderer.py`
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py`

- [ ] **Step 1: Write failing generic-sector tests**

Add tests proving:

```python
portrait = renderer._select_annual_portrait_row([
    {"body": "光模块、FPGA、安全与识别、智能电表产品线介绍。"},
    {"body": "公司从事精密设备设计、开发、测试，并提供系统解决方案，面向多个行业客户。"},
])
assert portrait["body"].startswith("公司从事精密设备")
```

```python
consensus = renderer._broker_consensus_sentence([
    {"assumption": "产能利用率", "view": "研报认为产能利用率改善。"},
    {"assumption": "海外渠道", "view": "研报认为海外渠道扩张。"},
])
assert consensus == "研报关注点集中在产能利用率、海外渠道。"
```

Also render a generic-sector formal-medium fixture and assert 4.4 uses row
titles such as `渠道扩张`, `产能利用率`, and `海外认证`, rather than optical
module keyword mappings.

Add a cleaning test that preserves the meaningful prefix in:

```text
公司提供工业控制设备并服务大型制造客户，经营模式包括直销和经销。
```

- [ ] **Step 2: Run targeted tests and verify RED**

Run the new test node ids. Expected failures:

- portrait selection is biased by chip/optical keywords;
- consensus returns the generic fallback;
- 4.4 ignores structured row titles;
- official-row cleaner drops the generic-industry prefix.

- [ ] **Step 3: Implement generic structured logic**

- Score annual portraits using broad company-description signals only:
  `公司`, `主营业务`, `从事`, `设计`, `开发`, `制造`, `测试`, `系统解决方案`,
  `产品线`, and breadth of customer/application language.
- Build broker consensus from distinct non-risk assumption titles. Use the
  current generic sentence only if titles are missing or purely generic.
- Replace `_infer_key_variable(text, fallback)` with
  `_material_key_variable(row, fallback)`, preferring a meaningful MaterialRow
  title and then a render-role label.
- Preserve official prefixes using generic business signals such as
  `主营业务`, `产品`, `设备`, `客户`, `研发`, `生产`, `制造`, `销售`, and `服务`.
- Remove hardcoded `FPGA`, `光模块`, `800G`, `1.6T`, and `3.2T` branches from
  these projection helpers.

- [ ] **Step 4: Run renderer tests and verify GREEN**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_deep_analysis_renderer.py \
  -q -p no:cacheprovider
```

### Task 3: Verification And Line Audit

**Files:** No additional runtime files.

- [ ] **Step 1: Run focused regression suite**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_deep_analysis_material_snapshot.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_report_quality.py \
  tests/reporter/test_report_source_boundary.py \
  tests/reporter/test_synthesis_skills.py \
  -q -p no:cacheprovider
```

- [ ] **Step 2: Run repository gates**

```bash
bash tools/ci_grep_gates.sh
git diff --check
```

- [ ] **Step 3: Audit hardcode and line count**

Confirm the affected projection helpers no longer contain stock-specific
optical/chip terms and that runtime code has a net line reduction. Do not count
tests or this plan as runtime growth.

- [ ] **Step 4: Scope review**

Confirm no changes to scoring, target price, risk, technical analysis,
recommendation, collection, LLM prompts, producers, `formal_rich`, or
`formal_thin_external_rich` routing.
