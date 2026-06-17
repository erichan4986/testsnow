# Credit-Aware Synthesis Layer Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three runtime validation issues in the Credit-Aware Synthesis Layer: illegal citation markers in LLM output, supported claims written as confirmed facts, and misleading core facts table rendering with all-invalid rows.

**Architecture:** Add a deterministic sanitizer in `synthesis_credit.py` shared by all consumers; strengthen prompt rules to explicitly forbid non-numeric citation markers; make `DeepAnalysisRenderer` skip the core facts table when all rows are invalid; change claim verification display labels to be neutral; add executive summary guardrails via LLM prompt instructions.

**Tech Stack:** Python 3.11+, pytest, regex, standard library only for sanitizer.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `scripts/utils/synthesis_credit.py` | Shared sanitizer + credit usage rules + claim verification appendix |
| `scripts/utils/knowledge_synthesizer.py` | Theme synthesis; applies sanitizer to LLM output; strips citations from core facts |
| `scripts/utils/report_skills/synthesis_skills.py` | Provenance enrichment for core facts; no sanitizer needed (reuses upstream) |
| `scripts/utils/reporter/sections/deep_analysis_renderer.py` | Core facts table rendering + claim verification summary section |
| `scripts/utils/reporter/sections/executive_summary_renderer.py` | Executive summary rendering with LLM-based thesis extraction |
| `tests/utils/test_synthesis_credit.py` | Sanitizer tests + prompt rule tests |
| `tests/utils/test_knowledge_synthesizer.py` | Sanitizer integration tests in `_parse_with_citations` and `extract_core_facts` |
| `tests/reporter/test_synthesis_skills.py` | No new tests needed (sanitizer is upstream) |
| `tests/reporter/test_deep_analysis_renderer.py` | Empty-state table tests + supported claim display tests |
| `tests/reporter/test_executive_summary_renderer.py` | Guardrail prompt tests |

---

## Task 1: Deterministic Sanitizer in synthesis_credit.py

**Files:**
- Modify: `scripts/utils/synthesis_credit.py:1-10` (add import) and after line 103 (add function)
- Test: `tests/utils/test_synthesis_credit.py`

**Requirement:** Delete/escape non-numeric citation markers like `[^supported]`, `[^needs_review]`, `[^unverified]`, `[^verified]`, `[^abc]`. Preserve legal numeric citations `[^1]`, `[^23]`.

- [ ] **Step 1: Write the failing test**

Add to `tests/utils/test_synthesis_credit.py` after the existing tests:

```python
def test_sanitize_citation_markers_removes_non_numeric_markers():
    from scripts.utils.synthesis_credit import sanitize_citation_markers
    text = "营收增长[^supported]，毛利率提升[^needs_review]，订单增加[^1]，客户导入[^23]。"
    result = sanitize_citation_markers(text)
    assert "[^supported]" not in result
    assert "[^needs_review]" not in result
    assert "[^1]" in result
    assert "[^23]" in result
    assert "订单增加[^1]" in result


def test_sanitize_citation_markers_handles_all_illegal_variants():
    from scripts.utils.synthesis_credit import sanitize_citation_markers
    text = "a[^verified] b[^unverified] c[^supported] d[^needs_review] e[^abc] f[^XYZ123]"
    result = sanitize_citation_markers(text)
    assert "[^verified]" not in result
    assert "[^unverified]" not in result
    assert "[^supported]" not in result
    assert "[^needs_review]" not in result
    assert "[^abc]" not in result
    assert "[^XYZ123]" not in result


def test_sanitize_citation_markers_preserves_numeric_refs():
    from scripts.utils.synthesis_credit import sanitize_citation_markers
    text = "[^1] [^23] [^456] [^0]"
    result = sanitize_citation_markers(text)
    assert result == "[^1] [^23] [^456] [^0]"


def test_sanitize_citation_markers_no_false_positives_on_bracket_text():
    from scripts.utils.synthesis_credit import sanitize_citation_markers
    text = "参见[附录A]和[^1]以及[注：重要]"
    result = sanitize_citation_markers(text)
    assert "[附录A]" in result
    assert "[注：重要]" in result
    assert "[^1]" in result


def test_sanitize_citation_markers_empty_string():
    from scripts.utils.synthesis_credit import sanitize_citation_markers
    assert sanitize_citation_markers("") == ""


def test_sanitize_citation_markers_none_returns_empty():
    from scripts.utils.synthesis_credit import sanitize_citation_markers
    assert sanitize_citation_markers(None) == ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/erichan/testsnow
pytest tests/utils/test_synthesis_credit.py::test_sanitize_citation_markers_removes_non_numeric_markers -v
```

Expected: FAIL with `ImportError: cannot import name 'sanitize_citation_markers'`

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/utils/synthesis_credit.py` after the imports at the top (after line 12):

```python
import re
```

Then add the function after `credit_usage_rules_text()` (after line 103):

```python
def sanitize_citation_markers(text: str) -> str:
    """Remove non-numeric citation markers like [^supported] while preserving [^n].

    LLMs sometimes emit illegal markers such as [^verified], [^needs_review],
    [^supported], [^unverified], or arbitrary labels like [^abc].  This function
    strips them deterministically, leaving only numeric citations [^\d+].
    """
    if text is None:
        return ""
    # Match [^<anything not purely digits>]
    return re.sub(r"\[\^(?!\d+\])[^\]]*\]", "", text)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/erichan/testsnow
pytest tests/utils/test_synthesis_credit.py -k "sanitize" -v
```

Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/erichan/testsnow
git add scripts/utils/synthesis_credit.py tests/utils/test_synthesis_credit.py
git commit -m "feat: add deterministic citation marker sanitizer

- sanitize_citation_markers() removes [^supported], [^needs_review],
  [^verified], [^unverified], [^abc] while preserving [^1], [^23]
- 6 unit tests covering illegal variants, numeric preservation,
  false positives, empty string, and None input"
```

---

## Task 2: Strengthen Prompt Rules in synthesis_credit.py

**Files:**
- Modify: `scripts/utils/synthesis_credit.py:93-103` (`credit_usage_rules_text()`)
- Modify: `scripts/utils/synthesis_credit.py:289-353` (`format_claim_verification_appendix()`)
- Test: `tests/utils/test_synthesis_credit.py`

**Requirement:**
- Explicitly state claim verification action/status is NOT a citation number; forbid `[^verified]`/`[^supported]`/`[^needs_review]`/`[^unverified]`
- supported discussion must be written as "该线索获得部分支持，但仍非官方确认", not as confirmed fact
- needs_review/unverified must not enter executive summary, core facts, or conclusions

- [ ] **Step 1: Write the failing test**

Add to `tests/utils/test_synthesis_credit.py`:

```python
def test_credit_usage_rules_text_forbids_status_citation_markers():
    text = credit_usage_rules_text()
    assert "[^verified]" not in text or "禁止" in text or "不得" in text or " forbid" in text.lower()
    # Check that the rules explicitly tell LLM not to use status markers as citations
    assert "claim verification action/status 不是引用编号" in text or \
           "验证状态不是引用编号" in text or \
           "不得使用 [^verified]" in text or \
           "禁止 [^verified]" in text or \
           "[^verified]、[^supported]、[^needs_review]、[^unverified] 不是合法引用" in text


def test_credit_usage_rules_text_supported_must_be_qualified():
    text = credit_usage_rules_text()
    assert "该线索获得部分支持，但仍非官方确认" in text


def test_credit_usage_rules_text_unverified_needs_review_excluded():
    text = credit_usage_rules_text()
    assert "needs_review/unverified 不得进入" in text or \
           "needs_review 和 unverified 不得进入" in text or \
           "needs_review/unverified 不得写入" in text or \
           "unverified 不得进入核心事实" in text


def test_claim_verification_appendix_forbids_status_markers():
    context = {
        "enabled": True,
        "counts": {"high_credit_claims": 1, "low_credit_claims": 1, "verified": 1, "supported": 0, "unverified": 0, "needs_review": 0},
        "verified_claims": [{"claim_text": "营收增长", "action": "verified", "confidence": 84}],
    }
    text = format_claim_verification_appendix(context)
    assert "[^verified] 不是合法引用" in text or \
           "不得使用 [^verified]" in text or \
           "禁止用 [^verified]" in text or \
           "status 标记不是引用编号" in text
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/erichan/testsnow
pytest tests/utils/test_synthesis_credit.py::test_credit_usage_rules_text_forbids_status_citation_markers -v
```

Expected: FAIL with assertion error (new rules not present)

- [ ] **Step 3: Write minimal implementation**

Replace `credit_usage_rules_text()` in `scripts/utils/synthesis_credit.py` (lines 93-103) with:

```python
def credit_usage_rules_text() -> str:
    """Return the shared credit-usage rules block for synthesis prompts."""
    return """证据信用与写法规则：
- 高信用/官方/公告/交易所来源可作为事实，可写为"公司公告披露/业绩预告显示"。
- 中信用/研报/新闻/政策/微信公众号来源只能写为"券商研报关注/媒体报道显示/政策文件指向/微信公众号观点"，不得写成公司确认。
- verified discussion 必须写为"社区讨论线索已与……相互印证"或"已验证讨论线索"，并且正文引用必须来自上方编号的高信用来源。
- supported discussion 必须写为"该线索获得部分支持，但仍非官方确认"，不得写成官方确认事实。
- 多个低信用来源重复出现只表示"社区共振/市场关注"，不得写成事实确认。Phase 1 不使用 corroborated schema。
- unverified discussion 只能作为待验证观点，不得进入核心事实、结论或风险加分。
- needs_review/unverified 不得进入执行摘要、核心事实基座或结论段落。
- 推论必须显式使用"可能/若/需要验证"，不得把推论写成事实。
- 中信用新闻/研报/微信公众号可进入风险观察文字，但不得生成结构化风险信号，不得影响风险评分。
- 重要：claim verification 的 action/status（verified/supported/needs_review/unverified）不是引用编号，禁止在正文中使用 [^verified]、[^supported]、[^needs_review]、[^unverified] 等标记。只允许使用 [^n] 形式的数字引用。"""
```

Then modify `format_claim_verification_appendix()` in `scripts/utils/synthesis_credit.py`. Add the following lines after the existing "重要约束：" block (after line 308, before the stats line):

```python
        "- 验证状态标记（verified/supported/needs_review/unverified）不是引用编号，禁止在正文使用 [^verified]、[^supported]、[^needs_review]、[^unverified] 等标记。",
```

The full updated `format_claim_verification_appendix()` lines 305-312 should read:

```python
    lines = [
        "Claim Verification Context（以下不是新的引用来源）",
        "",
        "重要约束：",
        "- 以下内容不是新的引用来源，不能用 [^n] 引用，也不能单独作为事实写入正文。",
        "- 它只用于判断社区观点的可信度，帮助你决定如何强调或弱化某些信息。",
        "- 多个低信用来源重复出现只表示"社区共振/市场关注"，不得写成事实确认。Phase 1 不输出 corroborated bucket。",
        "- 验证状态标记（verified/supported/needs_review/unverified）不是引用编号，禁止在正文使用 [^verified]、[^supported]、[^needs_review]、[^unverified] 等标记。",
        "",
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/erichan/testsnow
pytest tests/utils/test_synthesis_credit.py -k "credit_usage_rules_text or claim_verification_appendix" -v
```

Expected: PASS for all tests including the new ones

- [ ] **Step 5: Commit**

```bash
cd /Users/erichan/testsnow
git add scripts/utils/synthesis_credit.py tests/utils/test_synthesis_credit.py
git commit -m "feat: strengthen prompt rules to forbid status citation markers

- credit_usage_rules_text() now explicitly forbids [^verified], [^supported],
  [^needs_review], [^unverified] and states they are not citation numbers
- supported discussion must be written as '该线索获得部分支持，但仍非官方确认'
- needs_review/unverified are barred from executive summary, core facts, conclusions
- format_claim_verification_appendix() repeats the prohibition"
```

---

## Task 3: Apply Sanitizer to KnowledgeSynthesizer Theme Outputs

**Files:**
- Modify: `scripts/utils/knowledge_synthesizer.py:301-317` (`_parse_with_citations()`)
- Modify: `scripts/utils/knowledge_synthesizer.py:384-386` (`extract_core_facts()` inline stripping)
- Test: `tests/utils/test_knowledge_synthesizer.py`

**Requirement:** Apply sanitizer to LLM synthesis output in 5 theme narratives. Strip non-numeric markers from fact/data fields in `extract_core_facts()`.

- [ ] **Step 1: Write the failing test**

Add to `tests/utils/test_knowledge_synthesizer.py`:

```python
def test_parse_with_citations_sanitizes_illegal_markers():
    synth = KnowledgeSynthesizer(client=None)
    text = "营收增长[^supported]，毛利率提升[^needs_review]，订单增加[^1]。"
    parsed, cites = synth._parse_with_citations(text)
    assert "[^supported]" not in parsed
    assert "[^needs_review]" not in parsed
    assert "[^1]" in parsed
    assert 1 in cites


def test_parse_with_citations_preserves_numeric_refs_only():
    synth = KnowledgeSynthesizer(client=None)
    text = "a[^verified] b[^unverified] c[^1] d[^23]"
    parsed, cites = synth._parse_with_citations(text)
    assert "[^verified]" not in parsed
    assert "[^unverified]" not in parsed
    assert "[^1]" in parsed
    assert "[^23]" in parsed
    assert cites == {1: {"_placeholder": True, "ref_id": 1}, 23: {"_placeholder": True, "ref_id": 23}}


def test_extract_core_facts_strips_non_numeric_citation_markers():
    synth = KnowledgeSynthesizer(client=object())
    llm_output = (
        '[{"fact_id": 1, "fact": "营收增长[^supported]", "data": "10% [^needs_review]", "confidence": "高", "source_refs": []}]'
    )
    synth._call_llm = lambda prompt: llm_output
    result = synth.extract_core_facts("测试股", {"industry_logic": "营收增长。"})
    assert len(result) == 1
    assert "[^supported]" not in result[0]["fact"]
    assert "[^needs_review]" not in result[0]["data"]
    assert result[0]["fact"] == "营收增长"
    assert result[0]["data"] == "10%"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/erichan/testsnow
pytest tests/utils/test_knowledge_synthesizer.py::test_parse_with_citations_sanitizes_illegal_markers -v
```

Expected: FAIL because `_parse_with_citations` does not call sanitizer yet.

- [ ] **Step 3: Write minimal implementation**

In `scripts/utils/knowledge_synthesizer.py`, add the import at the top (after line 15, in the existing try block):

```python
        from .synthesis_credit import (
            credit_usage_rules_text,
            format_synthesis_source_line,
            format_claim_verification_appendix,
            sanitize_citation_markers,
        )
```

And in the `except ImportError` block (after line 25):

```python
    from synthesis_credit import (
        credit_usage_rules_text,
        format_synthesis_source_line,
        format_claim_verification_appendix,
        sanitize_citation_markers,
    )
```

Then modify `_parse_with_citations()` in `scripts/utils/knowledge_synthesizer.py` (lines 301-317). Replace the method body with:

```python
    def _parse_with_citations(self, text: str) -> Tuple[str, Dict[int, Dict]]:
        """
        解析 LLM 输出，提取 [^n] 引用标记，并清理非法标记如 [^supported]。

        Returns:
            (叙事文本（保留 [^n] 标记，已清理非法标记）, 引用编号集合)
        """
        if not text:
            return "", {}

        # Sanitize illegal non-numeric citation markers before parsing
        text = sanitize_citation_markers(text)

        # 提取所有 [^n] 引用
        refs = set(int(m) for m in re.findall(r"\[\^(\d+)\]", text))
        citations = {}
        for ref_id in refs:
            # 占位：caller 负责回填真实元数据
            citations[ref_id] = {"_placeholder": True, "ref_id": ref_id}
        return text, citations
```

Then modify `extract_core_facts()` in `scripts/utils/knowledge_synthesizer.py` (lines 384-386). Replace:

```python
                    # Strip inline citation markers like [1] or [^1] from displayed fields
                    fact_text = re.sub(r"\[\^?\d+\]", "", fact_text).strip()
                    data_text = re.sub(r"\[\^?\d+\]", "", data_text).strip()
```

With:

```python
                    # Strip ALL inline citation markers (numeric and non-numeric) from displayed fields
                    fact_text = sanitize_citation_markers(fact_text)
                    data_text = sanitize_citation_markers(data_text)
                    # Also strip plain [n] markers (no ^)
                    fact_text = re.sub(r"\[\d+\]", "", fact_text).strip()
                    data_text = re.sub(r"\[\d+\]", "", data_text).strip()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/erichan/testsnow
pytest tests/utils/test_knowledge_synthesizer.py -k "sanitize or strip" -v
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/erichan/testsnow
git add scripts/utils/knowledge_synthesizer.py tests/utils/test_knowledge_synthesizer.py
git commit -m "feat: apply citation sanitizer to KnowledgeSynthesizer outputs

- _parse_with_citations() now calls sanitize_citation_markers() before parsing
- extract_core_facts() uses sanitize_citation_markers() on fact/data fields
- Preserves [^n] numeric refs, removes [^supported], [^needs_review], etc."
```

---

## Task 4: Fix DeepAnalysisRenderer Core Facts Table Empty-State

**Files:**
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py:50-74` (`_core_facts_table()`)
- Test: `tests/reporter/test_deep_analysis_renderer.py`

**Requirement:** If all core_facts provenance_status are `invalid_ref` or `missing_ref`, do NOT render the table. Instead render an empty-state note. If some supported/partially_supported and some invalid_ref, keep the table; invalid_ref rows continue showing "引用无效 (unknown)".

- [ ] **Step 1: Write the failing test**

Add to `tests/reporter/test_deep_analysis_renderer.py`:

```python
def test_render_all_invalid_core_facts_shows_empty_state():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "行业逻辑。",
            "citations": {},
        },
        "core_facts": [
            {"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_labels": [], "evidence_type": "unknown", "provenance_status": "invalid_ref"},
            {"fact_id": 2, "fact": "毛利提升", "data": "5%", "confidence": "高", "source_labels": [], "evidence_type": "unknown", "provenance_status": "missing_ref"},
            {"fact_id": 3, "fact": "订单增加", "data": "20%", "confidence": "中", "source_labels": [], "evidence_type": "unknown", "provenance_status": "invalid_ref"},
        ],
    }
    result = renderer.render(ctx)
    assert "## 三、核心事实基座" in result
    assert "当前未形成可由高信用来源支撑的核心事实基座" in result
    assert "以下深度分析仅作为多源观察，不作为确认事实" in result
    # Table rows should NOT be present
    assert "| # | 事实 | 数据/来源 | 证据 | 置信度 |" not in result
    assert "营收增长" not in result
    assert "毛利提升" not in result
    assert "订单增加" not in result


def test_render_all_missing_ref_core_facts_shows_empty_state():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "行业逻辑。",
            "citations": {},
        },
        "core_facts": [
            {"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_labels": [], "evidence_type": "unknown", "provenance_status": "missing_ref"},
        ],
    }
    result = renderer.render(ctx)
    assert "当前未形成可由高信用来源支撑的核心事实基座" in result
    assert "| # | 事实 | 数据/来源 | 证据 | 置信度 |" not in result


def test_render_mixed_valid_and_invalid_keeps_table():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "行业逻辑。",
            "citations": {1: {"source": "公告"}},
        },
        "core_facts": [
            {"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_labels": ["公告"], "evidence_type": "announcement", "provenance_status": "supported"},
            {"fact_id": 2, "fact": "毛利提升", "data": "5%", "confidence": "高", "source_labels": [], "evidence_type": "unknown", "provenance_status": "invalid_ref"},
        ],
    }
    result = renderer.render(ctx)
    assert "| # | 事实 | 数据/来源 | 证据 | 置信度 |" in result
    assert "营收增长" in result
    assert "毛利提升" in result
    assert "引用无效 (unknown)" in result
    assert "当前未形成可由高信用来源支撑的核心事实基座" not in result


def test_render_empty_core_facts_still_empty():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "## 三、核心事实基座" not in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/erichan/testsnow
pytest tests/reporter/test_deep_analysis_renderer.py::test_render_all_invalid_core_facts_shows_empty_state -v
```

Expected: FAIL because the table is still rendered with all invalid rows.

- [ ] **Step 3: Write minimal implementation**

Replace `_core_facts_table()` in `scripts/utils/reporter/sections/deep_analysis_renderer.py` (lines 50-74) with:

```python
    def _core_facts_table(self, core_facts: List[Dict]) -> str:
        """渲染核心事实基座表格。如果全部无效/缺失，渲染空状态提示。"""
        if not core_facts:
            return ""

        # Determine if there are any actually supported facts
        has_supported = any(
            f.get("provenance_status") in ("supported", "partially_supported")
            for f in core_facts
        )

        if not has_supported:
            return (
                "## 三、核心事实基座\n"
                "\n"
                "> 当前未形成可由高信用来源支撑的核心事实基座；"
                "以下深度分析仅作为多源观察，不作为确认事实。\n"
                "\n"
            )

        lines = [
            "## 三、核心事实基座",
            "",
            "| # | 事实 | 数据/来源 | 证据 | 置信度 |",
            "|---|---|-----------|------|--------|",
        ]
        for f in core_facts:
            fid = f.get("fact_id", "")
            fact = f.get("fact", "").replace("|", "\\|")
            data = f.get("data", "").replace("|", "\\|")
            conf = f.get("confidence", "中")
            evidence = self._render_evidence_cell(f)
            lines.append(f"| {fid} | {fact} | {data} | {evidence} | {conf} |")

        lines.extend([
            "",
            "> **说明**：后续深度分析模块不再重复展开这些数据，仅在需要支撑论点时引用编号（如\"见事实#1\"）。",
            "",
        ])
        return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/erichan/testsnow
pytest tests/reporter/test_deep_analysis_renderer.py -k "invalid or missing or mixed or empty" -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/erichan/testsnow
git add scripts/utils/reporter/sections/deep_analysis_renderer.py tests/reporter/test_deep_analysis_renderer.py
git commit -m "feat: DeepAnalysisRenderer skips core facts table when all invalid

- _core_facts_table() checks if any fact has supported/partially_supported status
- If all are invalid_ref/missing_ref, renders empty-state note instead of table
- Mixed valid/invalid still renders table with invalid rows showing '引用无效'"
```

---

## Task 5: Supported Claim Display Changes

**Files:**
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py:216` (title)
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py:220-226` (status labels)
- Test: `tests/reporter/test_deep_analysis_renderer.py`

**Requirement:** Change "官方事实核验摘要" to neutral "事实核验摘要". verified rows show "已验证". supported rows show "部分支持，非官方确认".

- [ ] **Step 1: Write the failing test**

Add to `tests/reporter/test_deep_analysis_renderer.py`:

```python
def test_verified_claim_summary_title_is_neutral():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中简科技",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "claim_verification_summary": {
            "verified_claims": [
                {"claim_text": "营收增长", "action": "verified", "verified_by_titles": ["公告"], "confidence": 84}
            ]
        },
    }
    result = renderer.render(ctx)
    assert "### 事实核验摘要" in result
    assert "### 官方事实核验摘要" not in result


def test_verified_claim_summary_verified_status_label():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中简科技",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "claim_verification_summary": {
            "verified_claims": [
                {"claim_text": "营收增长", "action": "verified", "verified_by_titles": ["公告"], "confidence": 84}
            ]
        },
    }
    result = renderer.render(ctx)
    assert "| 营收增长 | 已验证 |" in result
    assert "| 营收增长 | verified |" not in result


def test_verified_claim_summary_supported_status_label():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中简科技",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "claim_verification_summary": {
            "supported_claims": [
                {"claim_text": "研发费用增加", "action": "supported", "verified_by_titles": ["研报"], "confidence": 76}
            ]
        },
    }
    result = renderer.render(ctx)
    assert "| 研发费用增加 | 部分支持，非官方确认 |" in result
    assert "| 研发费用增加 | supported |" not in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/erichan/testsnow
pytest tests/reporter/test_deep_analysis_renderer.py::test_verified_claim_summary_title_is_neutral -v
```

Expected: FAIL because title still says "官方事实核验摘要".

- [ ] **Step 3: Write minimal implementation**

In `scripts/utils/reporter/sections/deep_analysis_renderer.py`, modify `_verified_claim_summary_section()` (lines 216-226):

Replace line 216:
```python
            "### 官方事实核验摘要",
```
With:
```python
            "### 事实核验摘要",
```

Replace lines 220-226:
```python
        for row in rows:
            lines.append(
                f"| {row['claim_text']} | {row['status']} | {row['source']} | {row['confidence']} |"
            )
```

With:
```python
        for row in rows:
            status_label = self._status_display_label(row['status'])
            lines.append(
                f"| {row['claim_text']} | {status_label} | {row['source']} | {row['confidence']} |"
            )
```

Then add the new helper method after `_verified_claim_summary_section()` (after line 228, before `_verified_claim_summary_rows()`):

```python
    @staticmethod
    def _status_display_label(status: str) -> str:
        """Map internal status to human-readable neutral label."""
        if status == "verified":
            return "已验证"
        if status == "supported":
            return "部分支持，非官方确认"
        return status
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/erichan/testsnow
pytest tests/reporter/test_deep_analysis_renderer.py -k "title or status_label" -v
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/erichan/testsnow
git add scripts/utils/reporter/sections/deep_analysis_renderer.py tests/reporter/test_deep_analysis_renderer.py
git commit -m "feat: neutral claim verification labels and title

- Change title from '官方事实核验摘要' to '事实核验摘要'
- verified rows display '已验证' instead of 'verified'
- supported rows display '部分支持，非官方确认' instead of 'supported'"
```

---

## Task 6: Executive Summary Guardrails

**Files:**
- Modify: `scripts/utils/reporter/sections/executive_summary_renderer.py:32-47` (`_llm_extract_thesis()` prompt)
- Test: `tests/reporter/test_executive_summary_renderer.py`

**Requirement:** If ExecutiveSummaryRenderer extracts arguments from deep analysis, avoid rewriting sentences containing "仍非官方确认"/"尚未获得官方公告确认"/"supported"/"部分支持" into confirmed facts. Minimum: prompt instructs supported/unverified/needs_review can only enter bearish/wait-for-verification or be skipped, not bullish confirmed arguments.

- [ ] **Step 1: Write the failing test**

Add to `tests/reporter/test_executive_summary_renderer.py`:

```python
def test_llm_extract_thesis_prompt_forbids_supported_as_bullish():
    """Verify the LLM prompt contains guardrails against treating supported claims as confirmed facts."""
    from scripts.utils.reporter.sections.executive_summary_renderer import _llm_extract_thesis
    # We cannot easily mock the OpenAI client here, but we can inspect the prompt
    # by monkeypatching the client call. Instead, verify the prompt text via a spy.
    import inspect
    source = inspect.getsource(_llm_extract_thesis)
    # The prompt must contain guardrails
    assert "仍非官方确认" in source or "尚未获得官方公告确认" in source or "supported" in source or "部分支持" in source
    assert "不得将" in source or "不能将" in source or "禁止将" in source or "不得把" in source or "不能作为" in source
    # supported/unverified/needs_review must be directed to bearish or skipped
    assert "bearish" in source.lower() or "看空" in source or "谨慎" in source or "待验证" in source or "skip" in source.lower() or "跳过" in source or "排除" in source


def test_llm_extract_thesis_prompt_credit_aware_instructions():
    """Verify the LLM prompt explicitly instructs on credit tiers."""
    from scripts.utils.reporter.sections.executive_summary_renderer import _llm_extract_thesis
    import inspect
    source = inspect.getsource(_llm_extract_thesis)
    assert "官方确认" in source or "confirmed" in source.lower() or "高信用" in source or "verified" in source.lower()
    assert "supported" in source.lower() or "部分支持" in source or "unverified" in source.lower() or "未验证" in source or "needs_review" in source.lower() or "需复核" in source
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/erichan/testsnow
pytest tests/reporter/test_executive_summary_renderer.py::test_llm_extract_thesis_prompt_forbids_supported_as_bullish -v
```

Expected: FAIL because the current prompt lacks guardrail instructions.

- [ ] **Step 3: Write minimal implementation**

Replace the prompt in `_llm_extract_thesis()` in `scripts/utils/reporter/sections/executive_summary_renderer.py` (lines 32-47) with:

```python
    prompt = (
        "你是资深投资分析师。请基于以下分析文本，提取核心投资论点。\n\n"
        "要求：\n"
        "1. 看多论点：最多3条，每条不超过60字，只保留最核心的判断和数据支撑\n"
        "2. 看空论点：最多3条，每条不超过60字，只保留最核心的判断和数据支撑\n"
        "3. 给每条论点一个风险/机会等级（1-5星，整数）\n"
        "4. 一句话结论（不超过40字，概括多空博弈的核心）\n\n"
        "信用层级约束（必须遵守）：\n"
        "- 只有由高信用来源（公告/官方/交易所/巨潮）直接确认的事实，才可作为看多论据。\n"
        "- 含有'仍非官方确认'、'尚未获得官方公告确认'、'部分支持'、'supported'、'unverified'、'needs_review'等措辞的线索，"
        "  不得作为看多/确认论据，只能归入看空或待验证观点，或直接跳过。\n"
        "- 来自研报、新闻、雪球、知乎、微信公众号、AgentReach、资金流向等中低信用来源的线索，"
        "  不得被改写成官方确认事实。\n\n"
        "输出严格 JSON 格式，不要有任何其他内容：\n"
        '{\n'
        '  "bullish": [{"text": "...", "stars": 4}, ...],\n'
        '  "bearish": [{"text": "...", "stars": 3}, ...],\n'
        '  "conclusion": "..."\n'
        '}\n\n'
        "分析文本：\n"
        f"{text[:3000]}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/erichan/testsnow
pytest tests/reporter/test_executive_summary_renderer.py -k "llm_extract_thesis" -v
```

Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/erichan/testsnow
git add scripts/utils/reporter/sections/executive_summary_renderer.py tests/reporter/test_executive_summary_renderer.py
git commit -m "feat: executive summary guardrails against supported-as-confirmed

- _llm_extract_thesis() prompt now contains credit-tier constraints
- supported/unverified/needs_review claims barred from bullish arguments
- Only high-credit official sources can support bullish claims"
```

---

## Task 7: Update Existing Tests That Assert Old Title

**Files:**
- Modify: `tests/reporter/test_deep_analysis_renderer.py`
- Test: `tests/reporter/test_deep_analysis_renderer.py`

**Requirement:** Existing tests assert "### 官方事实核验摘要" which must be updated to "### 事实核验摘要".

- [ ] **Step 1: Find and update all occurrences**

In `tests/reporter/test_deep_analysis_renderer.py`, replace all occurrences of "### 官方事实核验摘要" with "### 事实核验摘要".

The occurrences are on:
- Line 199: `assert "### 官方事实核验摘要" in result`
- Line 232: `assert "### 官方事实核验摘要" in result`
- Line 262: `assert "### 官方事实核验摘要" in result`
- Line 408: `assert "官方事实核验摘要" not in renderer.render(base_ctx)`
- Line 410: `assert "官方事实核验摘要" not in renderer.render(...)`

Also update the assertion on line 201 that checks for `| supported |` to expect the new label:

```python
assert "| 研发费用同比增长约175%-185% | supported | 中简科技2026年第一季度报告 | 76 |" in result
```

This should become:

```python
assert "| 研发费用同比增长约175%-185% | 部分支持，非官方确认 | 中简科技2026年第一季度报告 | 76 |" in result
```

And line 234:

```python
assert "| 研发费用同比增长约175%-185% | supported | 中简科技2026年第一季度报告 | 76 |" in result
```

Should become:

```python
assert "| 研发费用同比增长约175%-185% | 部分支持，非官方确认 | 中简科技2026年第一季度报告 | 76 |" in result
```

- [ ] **Step 2: Run all DeepAnalysisRenderer tests**

```bash
cd /Users/erichan/testsnow
pytest tests/reporter/test_deep_analysis_renderer.py -v
```

Expected: ALL PASS (19 original + 7 new = 26 tests)

- [ ] **Step 3: Commit**

```bash
cd /Users/erichan/testsnow
git add tests/reporter/test_deep_analysis_renderer.py
git commit -m "fix: update existing tests for neutral claim verification title

- Replace all '官方事实核验摘要' assertions with '事实核验摘要'
- Update supported status assertions to '部分支持，非官方确认'"
```

---

## Task 8: Full Test Suite Verification

**Files:**
- All modified files
- Test: All test files

- [ ] **Step 1: Run the complete test suite for modified modules**

```bash
cd /Users/erichan/testsnow
pytest tests/utils/test_synthesis_credit.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py tests/reporter/test_executive_summary_renderer.py -v
```

Expected: ALL PASS. Count should be approximately:
- test_synthesis_credit.py: 22 original + 10 new = 32 tests
- test_knowledge_synthesizer.py: 17 original + 3 new = 20 tests
- test_synthesis_skills.py: 34 tests (no new tests, all pass)
- test_deep_analysis_renderer.py: 19 original + 7 new = 26 tests
- test_executive_summary_renderer.py: 4 original + 2 new = 6 tests

- [ ] **Step 2: If any failures, fix and re-run**

Common issues to watch for:
1. Import errors for `sanitize_citation_markers` — ensure the import is in both try/except blocks
2. Test assertion mismatches on title strings — double-check all "官方" references removed
3. `extract_core_facts` regex changes — ensure `sanitize_citation_markers` is imported

- [ ] **Step 3: Final commit**

```bash
cd /Users/erichan/testsnow
git commit -m "test: full test suite passes for credit-aware synthesis fixes

All 5 requirements verified:
1. Deterministic sanitizer removes [^supported]/[^needs_review] while preserving [^1]
2. Prompt rules strengthened to forbid status markers as citations
3. DeepAnalysisRenderer skips core facts table when all rows invalid
4. Claim verification title changed to neutral; supported shows '部分支持，非官方确认'
5. Executive summary prompt guards against rewriting supported claims as confirmed"
```

---

## Verification Commands Summary

Run these commands to verify each requirement independently:

```bash
# Requirement 1: Sanitizer
cd /Users/erichan/testsnow
pytest tests/utils/test_synthesis_credit.py -k "sanitize" -v

# Requirement 2: Prompt rules
cd /Users/erichan/testsnow
pytest tests/utils/test_synthesis_credit.py -k "credit_usage_rules_text or claim_verification_appendix" -v

# Requirement 3: DeepAnalysisRenderer empty-state
cd /Users/erichan/testsnow
pytest tests/reporter/test_deep_analysis_renderer.py -k "invalid or missing or mixed" -v

# Requirement 4: Supported claim display
cd /Users/erichan/testsnow
pytest tests/reporter/test_deep_analysis_renderer.py -k "title or status_label" -v

# Requirement 5: Executive summary guardrails
cd /Users/erichan/testsnow
pytest tests/reporter/test_executive_summary_renderer.py -k "llm_extract_thesis" -v

# Full suite
cd /Users/erichan/testsnow
pytest tests/utils/test_synthesis_credit.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py tests/reporter/test_executive_summary_renderer.py -v
```

---

## Risks and Deviations

| Risk | Mitigation |
|------|----------|
| LLM still emits illegal markers despite prompt rules | Sanitizer is deterministic and runs AFTER LLM output, so prompt rules are defense-in-depth |
| `sanitize_citation_markers` regex false-positive on `[^(digits)]` | Regex uses negative lookahead `(?!\d+\])` — only matches when contents are NOT purely digits; tested |
| Executive summary prompt too long | Prompt is ~3000 chars + text; added guardrails are ~200 chars; within token limits |
| Core facts empty-state breaks downstream consumers | Empty-state still renders `## 三、核心事实基座` section header, so any downstream parser looking for the section will find it; only the table is suppressed |
| Existing tests that snapshot full report output may break | Plan only modifies unit tests for the specific modules; integration/snapshot tests outside scope per constraints |
| `extract_core_facts` prompt still asks LLM to extract 8-12 facts | The prompt already says "only high-credit confirmed sources"; the sanitizer cleans any accidental status markers from the LLM response; the empty-state in renderer handles when all are invalid |

---

## Spec Coverage Checklist

| Spec Requirement | Task | Status |
|-----------------|------|--------|
| 1. Deterministic sanitizer — delete/escape non-numeric markers | Task 1 | Covered |
| 1. Preserve legal numeric citations [^1], [^23] | Task 1 | Covered |
| 1. Apply to LLM synthesis output in 5 theme narratives | Task 3 | Covered |
| 1. Tests proving [^supported] cleaned and [^1] preserved | Task 1 | Covered |
| 2. Strengthen prompt rules — forbid [^verified]/[^supported]/[^needs_review]/[^unverified] | Task 2 | Covered |
| 2. supported discussion must be "该线索获得部分支持，但仍非官方确认" | Task 2 | Covered |
| 2. needs_review/unverified must not enter executive summary, core facts, conclusions | Task 2 | Covered |
| 3. Fix DeepAnalysisRenderer — all invalid_ref/missing_ref = no table | Task 4 | Covered |
| 3. Empty-state note instead of 12 rows of "引用无效" | Task 4 | Covered |
| 3. Mixed valid/invalid keeps table, invalid rows show "引用无效" | Task 4 | Covered |
| 3. Tests covering all-invalid does not show table | Task 4 | Covered |
| 4. supported claim display — "官方事实核验摘要" to "事实核验摘要" | Task 5 | Covered |
| 4. verified rows show "已验证" | Task 5 | Covered |
| 4. supported rows show "部分支持，非官方确认" | Task 5 | Covered |
| 4. Tests ensuring supported rows not rendered as "官方事实" | Task 5 | Covered |
| 5. Executive summary guardrails — avoid rewriting supported as confirmed | Task 6 | Covered |
| 5. supported/unverified/needs_review only enter bearish or skipped | Task 6 | Covered |
| 5. Minimum: prompt instructs supported can only enter bearish/wait | Task 6 | Covered |

---

## Placeholder Scan

No placeholders found. All steps contain:
- Exact file paths
- Complete function signatures
- Complete code blocks
- Complete test code
- Exact commands with expected output
- No "TBD", "TODO", "implement later", "fill in details", "similar to Task N", or "add appropriate error handling"

---

## Type Consistency Check

| Symbol | Definition | Usage | Consistent? |
|--------|-----------|-------|-------------|
| `sanitize_citation_markers(text: str) -> str` | Task 1, synthesis_credit.py | Task 3, knowledge_synthesizer.py | Yes |
| `_parse_with_citations(text: str) -> Tuple[str, Dict[int, Dict]]` | Task 3, knowledge_synthesizer.py | Same file | Yes |
| `_core_facts_table(core_facts: List[Dict]) -> str` | Task 4, deep_analysis_renderer.py | Same file | Yes |
| `_status_display_label(status: str) -> str` | Task 5, deep_analysis_renderer.py | Same file | Yes |
| `_llm_extract_thesis(text: str) -> Dict` | Task 6, executive_summary_renderer.py | Same file | Yes |

All type signatures and property names are consistent across the plan.
