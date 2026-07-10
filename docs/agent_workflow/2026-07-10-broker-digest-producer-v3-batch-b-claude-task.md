# Broker Digest Producer V3 Batch B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use test-driven development and
> execute this plan task-by-task. Mark each checkbox as completed.

**Goal:** Select complementary, complete source units that satisfy an explicit
claim/evidence contract for each existing broker card family.

**Architecture:** One source-unit selector owns sentence extraction, semantic
roles, family admission, and order preservation. It replaces the current family
validators, fallback joiner, generic signal helper, and product-driver candidate
special case. It must not create a parallel third selection path.

**Tech stack:** Python standard library, pytest, existing deterministic broker
digest and source-boundary gates.

---

## Preconditions

- HEAD contains Batch A commit `a564898` or an equivalent reviewed commit.
- Batch A producer tests pass.
- `selection_version: broker_digest_v3` refresh behavior is present.
- Batch A combined runtime net delta was +79 and does not count against Batch B.

## Scope

**Runtime file allowed:**

- `scripts/utils/broker_research_digest.py`

**Test file allowed:**

- `tests/utils/test_broker_research_digest.py`

**Notes output:**

- `docs/agent_workflow/2026-07-10-broker-digest-producer-v3-batch-b-claude-notes.md`

**Forbidden:** note writer, renderer, synthesis/profile routing, scoring, target
price, risk, technical analysis, recommendation, collection/PDF download, LLM
prompt, reports, data, and knowledge files.

**Runtime budget:** Target no more than +80 net runtime lines; hard stop +100.
The expected result should be close to neutral because at least these helpers
must be deleted or folded into the new selector:

- `_extract_section` (no active callers)
- `_select_section_candidates`
- `_condense_excerpt`
- `_unit_has_signal`
- `_fallback_excerpt`
- `_is_valid_excerpt`
- `_is_valid_product_driver_excerpt`
- `_is_valid_forecast_excerpt`
- `_is_valid_risk_excerpt`

## Task 1: Lock Family Admission With Failing Tests

**Files:**

- Modify: `tests/utils/test_broker_research_digest.py`

- [ ] **Step 1: Add one claim-without-evidence rejection test per family**

Use `pytest.mark.parametrize` with these cases:

```python
(
    "broker_core_view",
    "核心观点",
    "公司长期发展前景良好。",
),
(
    "broker_product_driver",
    "产品布局",
    "公司产品需求有望增长。",
),
(
    "broker_earnings_forecast",
    "盈利预测",
    "我们预计公司业绩增长，维持买入评级。",
),
(
    "broker_risk_note",
    "风险提示",
    "市场竞争风险。",
),
```

Build one report per case and assert no returned card has the target
`card_type`. Keep the fixtures free of unrelated evidence terms.

- [ ] **Step 2: Add one positive claim/evidence test per family**

Use these minimum positive shapes:

```python
(
    "broker_core_view",
    "核心观点",
    "公司2026年一季度收入同比增长39.08%，产品结构升级推动毛利率改善。",
),
(
    "broker_product_driver",
    "产品布局",
    "800G与1.6T产品需求增长，重点客户订单和产能扩张支撑交付。",
),
(
    "broker_earnings_forecast",
    "盈利预测",
    "预计公司2026年归母净利润为80亿元，对应PE为30倍，维持买入评级。",
),
(
    "broker_risk_note",
    "风险提示",
    "若客户资本开支不及预期，订单放量和收入增长可能受到影响。",
),
```

Assert the expected card exists and its excerpt contains the original complete
sentence.

- [ ] **Step 3: Run the family tests and confirm RED**

Run only the new parametrized tests. Expected: at least the weak one-clause
cases are currently admitted by term/length validators.

## Task 2: Lock Complementary Unit Selection And Source Fidelity

**Files:**

- Modify: `tests/utils/test_broker_research_digest.py`

- [ ] **Step 1: Add a within-section complementarity test**

Use one `产品布局` section containing, in this order:

```text
AI算力资本开支持续增长，高速互联需求保持高景气。
800G与1.6T产品进入重点客户验证，订单和产能扩张支撑交付。
AI算力需求保持高景气，高速互联市场继续增长。
```

Assert the card keeps the first demand claim and second customer/order evidence,
does not keep the semantically repeated third sentence, and preserves source
order.

- [ ] **Step 2: Add a source-substring test over all selected units**

Split the final excerpt by terminal punctuation, restore each terminator, and
assert every non-empty unit occurs verbatim in the cleaned source. Assert unit
positions are monotonically increasing. Do not merely assert a few keywords.

- [ ] **Step 3: Add product-driver cross-heading complementarity regression**

Keep the existing long-report behavior where `产业趋势` contributes demand and
`竞争格局` contributes technology/customer evidence. Assert both survive when
the two heading candidates are not near duplicates.

- [ ] **Step 4: Run these tests and confirm RED where behavior is missing**

Existing keyword condensation may retain a duplicate unit or fail the explicit
role contract.

## Task 3: Replace Selection And Validators With One Unit Contract

**Files:**

- Modify: `scripts/utils/broker_research_digest.py`

- [ ] **Step 1: Introduce one semantic-role owner**

Use a single role function with these stable roles:

```python
def _unit_roles(text: str) -> set[str]:
    roles: set[str] = set()
    if any(term in text for term in (
        "增长", "提升", "改善", "受益", "推动", "带动", "实现", "认为", "看好",
    )):
        roles.add("claim")
    if re.search(r"\d+(?:\.\d+)?\s*(?:亿元|%|pct|倍|G|T|元)", text) or any(
        term in text for term in ("客户", "订单", "产能", "毛利率", "净利润", "收入")
    ):
        roles.add("evidence")
    if any(term in text for term in (
        "产品", "需求", "客户", "订单", "产能", "应用", "下游", "技术", "供应链", "交付",
    )):
        roles.add("driver")
    if any(term in text for term in (
        "预计", "预测", "上调", "维持", "评级", "目标价", "EPS", "PE", "估值",
    )):
        roles.add("forecast")
    if any(term in text for term in (
        "风险", "不及预期", "下滑", "竞争加剧", "波动", "承压",
    )):
        roles.add("risk")
    if any(term in text for term in (
        "导致", "影响", "拖累", "压制", "取决于", "若", "受到", "价格", "毛利率", "收入", "利润",
    )):
        roles.add("mechanism")
    return roles
```

Do not create stock/industry-specific role dictionaries.

- [ ] **Step 2: Replace unit splitting and generic `_unit_has_signal`**

Replace `_condense_excerpt` and `_unit_has_signal` with one complete-unit
extractor. It must:

- preserve `。；;！？!?` terminators;
- return only ordered substrings of the cleaned source;
- admit a no-terminator bullet only when its length is at most 180 characters;
- reject units shorter than 14 characters, front-matter noise, or with no roles;
- use Batch A `_bounded_complete_excerpt()` as the only length boundary owner.

The function signature should be:

```python
def _complete_source_units(text: str) -> List[str]:
    units: List[str] = []
    cursor = 0
    for match in re.finditer(r"[^。；;！？!?]+[。；;！？!?]", text):
        cursor = match.end()
        unit = match.group(0).strip()
        if len(unit) < 14 or _looks_like_front_matter_noise(unit):
            continue
        if _unit_roles(unit):
            units.append(unit)
    tail = text[cursor:].strip()
    if (
        14 <= len(tail) <= 180
        and not _looks_like_front_matter_noise(tail)
        and _unit_roles(tail)
    ):
        units.append(tail)
    return units
```

The implementation may use a punctuation-preserving `re.finditer`; do not split
and reconstruct partial clauses.

- [ ] **Step 3: Add one family contract**

Use this exact admission policy:

```python
def _family_requirements_met(card_type: str, units: List[str]) -> bool:
    roles = set().union(*(_unit_roles(unit) for unit in units)) if units else set()
    text = " ".join(units)
    if card_type == "broker_core_view":
        return "claim" in roles and bool(roles & {"evidence", "driver"})
    if card_type == "broker_product_driver":
        clusters = _generic_driver_cluster_labels(text)
        return "driver" in roles and ("evidence" in roles or len(clusters) >= 2)
    if card_type == "broker_earnings_forecast":
        return "forecast" in roles and "evidence" in roles
    if card_type == "broker_risk_note":
        return "risk" in roles and bool(roles & {"mechanism", "evidence"})
    return False
```

Delete the four legacy `_is_valid_*` functions and replace their build call
sites with this contract through the selector. Preserve table/rating/risk-only
guards before family admission.

- [ ] **Step 4: Add one complementary selector**

The selector must rank complete units by Batch A candidate score plus role
novelty, select at most five units, and preserve original order in output:

```python
def _select_excerpt_units(text: str, card_type: str, max_units: int = 5) -> str:
    units = _complete_source_units(text)
    ranked = sorted(
        enumerate(units),
        key=lambda item: (-_section_candidate_score(item[1]), item[0]),
    )
    chosen: List[Tuple[int, str]] = []
    covered: set[str] = set()
    for index, unit in ranked:
        roles = _unit_roles(unit)
        if chosen and not (roles - covered):
            continue
        chosen.append((index, unit))
        covered.update(roles)
        if len(chosen) >= max_units:
            break
    selected = [unit for _, unit in sorted(chosen)]
    if not _family_requirements_met(card_type, selected):
        return ""
    return _bounded_complete_excerpt(" ".join(selected))
```

If tests show this exact greedy loop loses a required evidence role, adjust the
ranking with a deterministic required-role bonus inside this same function. Do
not add another selector.

- [ ] **Step 5: Thread card type through the existing path**

- Add `card_type` to `_extract_section_candidates()` and pass it from the
  `_SECTION_SPECS` loop.
- Clean each heading occurrence through `_select_excerpt_units()` before scoring.
- Re-run selection on the joined product-driver heading excerpts so combined
  output remains admitted and boundary-safe.
- Delete unused `_extract_section()`.
- Replace `_select_section_candidates()` internals so product-driver may retain
  up to two non-duplicate candidates with different driver clusters; all other
  families retain the best admitted candidate.
- Keep diagnostics for selected/skipped/rejected heading candidates.

- [ ] **Step 6: Run Task 1-3 tests and confirm GREEN**

Run all `tests/utils/test_broker_research_digest.py` tests. Do not weaken old
expectations merely to accommodate the new selector.

## Task 4: Replace No-Heading Fallback

**Files:**

- Modify: `scripts/utils/broker_research_digest.py`
- Modify: `tests/utils/test_broker_research_digest.py`

- [ ] **Step 1: Add failing incoherent-fallback test**

Provide no recognized heading and only a generic positive sentence without a
business/financial reason. Assert no card is returned.

- [ ] **Step 2: Preserve coherent fallback regression**

Keep the existing AIoT fallback fixture: platform/product claim plus sales or
margin evidence must still produce one `broker_product_driver` card.

- [ ] **Step 3: Replace `_fallback_excerpt`**

Fallback must call the same `_select_excerpt_units()` owner. It may attempt
`broker_core_view` first and `broker_product_driver` second, but may return only
the first admitted result. This ordered family attempt is part of the same
selector contract, not a third extraction path.

Delete the old chunk join loop. Preserve `_allow_fallback_excerpt()` disclaimer,
table, and risk-only guards.

- [ ] **Step 4: Run fallback tests and confirm GREEN**

## Task 5: Verification And Notes

- [ ] **Step 1: Run focused producer tests**

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_broker_research_digest.py \
  tests/utils/test_broker_research_digest_note_writer.py \
  tests/utils/test_broker_research_digest_synthesis_items.py \
  -q -p no:cacheprovider
```

- [ ] **Step 2: Run downstream contracts**

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_synthesis_skills.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_report_source_boundary.py \
  tests/reporter/test_report_quality.py \
  -q -p no:cacheprovider
```

- [ ] **Step 3: Run repository gates**

```text
bash tools/ci_grep_gates.sh
git diff --check
```

- [ ] **Step 4: Enforce Batch B runtime budget**

Use `git diff --numstat` against the Batch A commit for
`scripts/utils/broker_research_digest.py`. Stop if Batch B runtime net growth
exceeds +100 lines. Report deleted legacy helpers and final runtime delta.

- [ ] **Step 5: Write notes and requirement-test matrix**

Record:

- family negative and positive admission tests;
- within-section role complementarity;
- cross-heading product-driver complementarity;
- source-substring and order proof;
- coherent/incoherent fallback behavior;
- no third selection path;
- focused/downstream/CI results;
- runtime additions, deletions, and net;
- blocker, warning, deviation;
- whether producer v3 is ready for a newly generated 中际旭创 report.

Do not run the formal report in this task.

## Stop Conditions

Stop and report instead of expanding scope if:

- runtime net growth exceeds +100 lines;
- any second/third semantic selector is introduced;
- source units need paraphrasing or non-source text;
- passing tests requires stock/industry-specific role terms;
- note writer, renderer, synthesis/profile, scoring/target/risk/technical,
  recommendation, collection, LLM prompt, reports/data/knowledge must change.
