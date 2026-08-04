# Annual Producer v2 Final Coverage Completion Design

**Status:** design complete

**Verdict:** proceed with one replacement-oriented implementation batch. Do not
generate reports, archive v1 notes, or remove the adapter in this batch.

**Implementation ready:** yes

## 1. Goal And Locked Boundary

Close the five-stock remainder so all eight local-cache stocks reach both:

```text
v1_actionable_needs_recovery_count == 0
v1_adapter_use_count == 0
```

The implementation must retain these invariants:

1. Raw annual-report source blocks are the only producer input. v1 notes are an
   offline acceptance oracle only.
2. `build_periodic_report_evidence_pack()` remains the only block selector and
   `_MAX_BLOCKS` remains `48`.
3. `build_periodic_report_narrative_evidence_cards()` remains the only card
   selector. There is no rejected-unit pass.
4. Every card belongs to one of the five canonical families.
5. Every admitted `SourceUnit` is an exact normalized source substring, has one
   owner, and is never reused by another card.
6. Material-pack coverage remains exact and same-block. It may remove a
   syntax-owned structural prefix before proof, but may not use fuzzy,
   token-overlap, semantic, or cross-block coverage.
7. A concrete source fact may not be labeled invalid merely to clear the gate.
8. No renderer, scoring, target, risk, technical, recommendation, LLM,
   collection, config, raw-data, Knowledge, or report behavior is in scope.

## 2. Verified Baseline

Baseline commit: `aa7bdd9`.

| Governed runtime file | Current net vs baseline |
| --- | ---: |
| `scripts/utils/annual_argument_schema.py` | +54 |
| `scripts/utils/annual_report_material_pack.py` | +84 |
| `scripts/utils/periodic_report_evidence_pack.py` | +30 |
| `scripts/utils/periodic_report_narrative_evidence_cards.py` | +191 |
| **Total** | **+359** |

Verified current gates: focused annual/schema/evidence/producer/material-pack
`292 passed`; renderer/quality/source-boundary `187 passed`; CI grep passed;
`git diff --check` passed.

The current five-stock remainder is 28 actionable fragments: Black Sesame 6,
Zhongjian 3, SGT Micro 6, Espressif 11, and Zhongji Innolight 2. All other three
stocks are already zero.

## 3. Root-Cause Matrix

### 3.1 Summary

| Class | Count | Finding | Required response |
| --- | ---: | --- | --- |
| C1: evidence-pack omission | 2 | Zhongji facts exist in raw source but not as exact text in any selected block | widen the existing `competitive_position` line window only; keep cap 48 |
| C2: producer omission | 24 | selected block contains the exact fact, but noise, seed, structural-prefix, or semantic-dedup logic leaves it unowned | replace the existing admission predicates and delete cross-block semantic dedup |
| C3: exact-coverage boundary mismatch | 1 | v2 owns the exact factual tail, while the v1 fragment prepends a structural heading | shared deterministic source-tail syntax; exact proof on the tail |
| C4: invalid OCR/table damage | 1 | the legacy fragment is an interleaved table row, not recoverable prose | reject the source block as table OCR and classify that legacy fragment invalid |

No remaining case requires a new family, second selector, fuzzy proof, rejected
unit recovery, stock rule, cap increase, or v1-guided producer input.

### 3.2 C1: Evidence-Pack Omission

| Stock / source block | Exact remainder | Verified state | Fix |
| --- | --- | --- | --- |
| 中际旭创 / `competitive_position-0` | `光 模块头部厂商凭借领先的研发实力及交付能力，竞争优势进一步强化，行业集中度有望持续提升。` | raw source contains it; selected block 0 ends immediately before it | replace `competitive_position` window line budget `12` with `20` |
| 中际旭创 / `competitive_position-0` | `另一 方面，随着 Scale‑up 、Scale‑across 网络快速兴起 ，硅光等下一代光互连技术需求显著提升，行业面临更 复杂的技术挑战。` | raw source contains it; block 1 begins at `方面` and therefore does not contain the exact unit | same window replacement keeps the complete unit in block 0 |

The anchor line is followed by Jina blank-line wrapping. A 12-line budget ends
at the preceding sentence; 20 lines include both complete target sentences and
remain far below `_MAX_CHARS_PER_BLOCK`. This proves a selected-window omission,
not a 48-block-cap failure. `_MAX_BLOCKS` and `_MAX_CHARS_PER_BLOCK` must not
change.

### 3.3 C2: Producer Omissions

| Stock / source block | Count | Exact fragments or trace key | Current classifier state | Replacement rule |
| --- | ---: | --- | --- | --- |
| 黑芝麻智能 / `hk_market_outlook-2` | 2 | `依託億智電子...共同定義並協作研發 2T-10T...` and `億智電子的下一代 AI SoC...場景橫向拓展。` | family market, `continuation`, no owner | mapped HK market unit with named technology plus concrete cooperation/coverage/outlook relation is a seed |
| 黑芝麻智能 / `hk_financial_commentary-2` | 1 | `我們智能影像解決方案業務的毛利率...85.4% 與84.7%。` | valid metric comparison rejected as `table_or_ocr` because of date digits | a complete financial metric comparison is narrative before numeric-density table rejection |
| 黑芝麻智能 / `hk_product_progress-1` | 3 | `A2000 家族全系列產品將很快亮相；`, `NPU 架構...研發中；`, `更先進制程...規劃中；` | no technology family/seed | technology object plus `迭代/亮相/研發/規劃` is a technology seed |
| 中简科技 / `product_capacity_profile-0` | 1 | `2、生产模式 因公司产品主要用于航空航天领域...性能参数不会发生改变。` | source unit is rejected because a page/report marker precedes the fact | exact structural-tail extraction, then business relation seed |
| 中简科技 / `financial_assets_note-0` | 1 | `公司前三季度在构建资产与项目投入耗资巨大；` | financial continuation without seed | capital/project subject plus concrete `投入/耗资` relation is a financial seed |
| 圣邦股份 / `cash_flow_capex_table-0` | 1 | `投资活动现金流出小计本期较上期增加51.86%...所致。` | page/report marker contaminates the unit and triggers page noise | exact structural-tail extraction; existing financial rule then seeds it |
| 圣邦股份 / `product_capacity_profile-2` | 2 | `38大类6,800余款...信号链类...；` and `电源管理类模拟芯片包括LDO...；` | business continuation without seed | product portfolio with `拥有/包括/涵盖` is a business seed |
| 圣邦股份 / `product_capacity_profile-2` | 1 | `面向汽车电子领域...推出通过车规级认证的新产品...` | valid seed built, then discarded as a cross-block semantic duplicate | delete producer semantic dedup; own this block's exact unit |
| 圣邦股份 / `product_capacity_profile-1` | 1 | `研发投入逐年增加，开发并积累了一系列...核心技术与产品...` | business continuation without seed | company plus concrete R&D/product accumulation is a business or technology seed, selected once by normal precedence |
| 乐鑫科技 / `product_capacity_profile-2` | 2 | `主要产品是物联网芯片和模组，符合...认证标准。` and `公司产品未产生任何安全事故。` | business continuation without seed | product identity/certification and dated product-safety result are business seeds |
| 乐鑫科技 / `product_capacity_profile-0` | 1 | `17/ 当客户产品从原型阶段...平台选择通常随之锁定。` | page/report prefix contaminates current source unit | exact structural-tail extraction; material proof strips the sanctioned `17/` prefix |
| 乐鑫科技 / `product_capacity_profile-0` | 2 | `客户产品进入量产后...持续销售5至10年。` and `客户每年持续采购...型号升级与功能增强。` | business continuation without an immediately preceding owned seed | lifecycle/recurring-purchase relation is a business seed; the second may continue only when adjacent and same subject |
| 乐鑫科技 / `market_demand_outlook-1` | 2 | `SoC...需要持续提升运算性能...控制功耗...` and `越来越多的企业...利用大模型...取得成果。` | market continuation without seed | concrete market/technology requirement or adoption outcome is a market seed |
| 乐鑫科技 / `rd_product_progress-0` | 2 | `芯片产品已从Wi-FiMCU...扩展AIoTSoC...` and `研发范围包括...芯片设计...软件技术。` | business continuation / no family | mapped R&D usage plus product-scope expansion or R&D-scope composition is a technology seed |
| 乐鑫科技 / `rd_investment_table-0` | 2 | `研发策略...核心技术自研...投入底层技术研发。` and `研发人员数量629人...增长13.74%。` | no family/seed | mapped R&D strategy/activity or R&D personnel metric/change is a technology seed |

The producer fix is generic by source syntax, usage, family subject, and relation.
No predicate may mention a stock, product list, industry, or source block ID.

### 3.4 C3: Exact-Coverage Boundary Mismatch

| Stock / source block | Legacy fragment | Existing v2 ownership | Fix |
| --- | --- | --- | --- |
| 中简科技 / `cash_flow_capex_table-0` | `报告期内公司经营活动产生的现金净流量与本年度净利润存在重大差异的原因说明 2025 年四季度客户付款形式由航信变动为电汇支付...存在较大差异。` | v2 `u6` already owns the exact factual tail beginning `2025 年四季度...` | classify the sanctioned `...原因说明` prefix as structure and prove the remaining tail exactly against `u6` |

This is not fuzzy coverage. The proof target is the exact tail returned by the
shared syntax helper. Arbitrary prose prefixes, noncontiguous units, and
cross-block matches remain uncovered.

### 3.5 C4: Invalid OCR/Table Damage

| Stock / source block | Fragment | Evidence |
| --- | --- | --- |
| 圣邦股份 / `rd_product_progress-1` | `针对当前更低电压、 部分产品已处于小批 更高转换速度、更小 完成新一代电平转 进一步扩展和健全电 量生产阶段；` | raw block is a multi-column R&D table flattened in column-interleaved order; adjacent lines splice unrelated columns and do not form recoverable prose |

The complete `rd_product_progress-1` fixture must be treated as table OCR. The
producer must emit no cards from that block. The material-pack classifier may
mark its legacy fragments invalid only when all of these structural conditions
hold: R&D table/progress source identity, at least four OCR whitespace seams,
no explicit company/report-period/named-product subject, and no complete
subject-relation sentence. A normal wrapped R&D paragraph is a negative control.

## 4. Locked Data Flow

```text
local raw annual report
  -> build_periodic_report_evidence_pack()       # sole block selector, cap 48
  -> selected source block
  -> punctuation SourceUnits in source order
  -> exact syntax-owned source tail or original unit
  -> unit noise/family/admission classification  # one pass
  -> adjacent same-argument bundling              # no rejected-unit pass
  -> validated canonical v2 cards                # one owner per SourceUnit
  -> v2 notes

legacy v1 notes --------------------------------- offline audit only
  -> syntax-owned structural tail
  -> exact same-block contiguous SourceUnit proof
  -> covered | actionable_uncovered | invalid_legacy
```

The producer must never read the lower audit path.

## 5. Replacement And Deletion Plan

### 5.1 `annual_argument_schema.py`

Replace, do not supplement, `annual_checkbox_tail()` with one shared syntax
helper named `annual_source_tail()`.

It recognizes only an anchored prefix at the start of normalized text:

- one complete checkbox marker run;
- A-share page/report prefixes such as `17/258 ... 2025年年度报告` or
  `27 ... 2025年年度报告全文`;
- a numbered mode heading such as `2、生产模式`;
- a `...原因说明` or `...情况说明` heading immediately followed by a dated
  factual sentence.

It returns a tail only when the tail is an exact substring, contains no second
structural marker, and ends in `。；;！？!?`. Otherwise it returns `None`.
Retain `ANNUAL_CHECKBOX_MARKER_RUN_RE` for incomplete-checkbox invalidation.

Delete the old checkbox-only helper and update its two runtime callers. Do not
keep both helpers.

### 5.2 `periodic_report_evidence_pack.py`

Replace only `max_lines_by_usage["competitive_position"] = 12` with `20`.
Do not change any selector, usage limit, priority, block cap, character cap, or
block reservation helper.

### 5.3 `periodic_report_narrative_evidence_cards.py`

1. Replace `_extract_a_share_causal_tail()` with `_extract_source_tail()` using
   `annual_source_tail()`. Allow any mapped canonical usage, not only the former
   financial/operating/technology set. Recompute offsets with `cleaned.find()`;
   fail closed if the tail is not an exact substring.
2. Pass the original block text, not whitespace-collapsed `cleaned`, to
   block-level noise checks so newline topology remains available. SourceUnit
   offsets still refer to `cleaned`.
3. Replace the four overlapping technology predicates
   `_has_product_progress()`, `_has_contextual_product_progress()`,
   `_has_explicit_technology_progress()`, and `_is_rd_table_complete_fact()`
   with one `_has_concrete_technology_fact(text, usage_hint)` predicate.
4. Modify `_has_concrete_business_fact()`, `_is_self_contained_atomic_fact()`,
   and the existing family signal resolver with the rules in section 6. Do not
   add a parallel admission helper or second unit loop.
5. Modify `_looks_like_table_fragment()` so complete financial comparisons are
   exempt from numeric-density rejection, while interleaved OCR remains noise.
   Extend `_looks_like_block_table()` with raw-newline topology for the exact SGT
   damaged block and its generic controls.
6. Delete `seen_by_family`, the `_is_semantic_duplicate()` admission branch,
   `_is_semantic_duplicate()`, `_distinct_product_or_period()`,
   `_ngram_similarity()`, and `_char_ngrams()`. Evidence-pack block dedup remains;
   producer cross-block semantic dedup is incompatible with same-block exact
   SourceUnit coverage.
7. Keep `_candidate_invariant_errors()` and validation fail-closed behavior.

### 5.4 `annual_report_material_pack.py`

1. Replace `annual_checkbox_tail()` calls with `annual_source_tail()`.
2. In `_classify_legacy_fragments()`, run exact proof against the syntax-owned
   tail when present; otherwise use the original normalized fragment.
3. Pass `source_block_id` into `_invalid_legacy_reason()` and add only the C4
   interleaved-R&D-table rule.
4. Do not alter `_proof_unit_ids()`: same block, adjacent ordinals, and exact
   normalized substring remain mandatory.

## 6. Exact Admission, Continuation, And Invalid Rules

```python
for block in evidence_pack["blocks"]:                 # existing sole selector
    cleaned, source_units = materialize(block)
    prepared = []
    for raw_unit in source_units:                      # one pass only
        unit = exact_source_tail(raw_unit) or raw_unit
        if noise_reason(unit, original_block_text, usage):
            prepared.append(None)
            continue

        family = resolve_one_canonical_family(unit, usage)
        if family is None:
            prepared.append(None)
        elif complete_family_fact(unit, family, usage, document_style):
            prepared.append((unit, family, "seed"))
        elif concrete_anchor(unit):
            prepared.append((unit, family, "continuation"))
        else:
            prepared.append(None)

    scan prepared once in source order:
        seed starts one bundle
        append only adjacent, non-noise, same-argument continuations
        a complete seed with a new subject starts its own later bundle
        validate exact offsets and exclusive ownership
        admit every valid candidate; do not semantic-dedupe across blocks
```

Family seed rules are conjunctive:

| Family | Required complete fact |
| --- | --- |
| `business_structure` | concrete company/product/customer/platform subject plus composition, certification, application, lifecycle, recurring-purchase, mode, or safety-result relation |
| `technology_product_progress` | named product/technology/R&D subject plus progress, research, planning, scope, release, production, or measured R&D-change relation; generic `研发` alone is insufficient |
| `operating_progress` | retain current report-period plus operating metric/change rule |
| `market_competition_outlook` | concrete market/industry/customer/technology subject plus demand, requirement, adoption, competition, cooperation, coverage, expansion, outlook, concentration, or challenge relation |
| `financial_quality_explanation` | financial/capital/cash subject plus value, comparison, change, expenditure, or causal relation |

Continuation is allowed only when ordinals and offsets are adjacent, neither
unit is noise, and the existing family-specific subject/continuation test says
the argument continues. A preceding `None` always breaks the bundle. A unit
that independently satisfies a seed rule must not depend on a rejected prior
unit.

Invalid classification is limited to existing syntax failures plus C4. In
particular, numeric density is not invalid when the unit has a financial metric,
two periods/values, and an explicit comparison/change relation.

## 7. Requirement-Test Matrix

| Requirement | Exact test |
| --- | --- |
| Zhongji C1 recovery | add a `test_periodic_report_evidence_pack.py` fixture with the exact heading and wrapped lines through both target sentences; assert both exact strings occur in `competitive_position-0`, block count `<= 48`, and each block length `<= 2000` |
| Shared source-tail syntax | replace checkbox-only schema test with parameterized checkbox, page/report, numbered-mode, and `原因说明` cases; assert returned tail is an exact substring; add arbitrary-prefix, multiple-marker, incomplete-tail negatives |
| Page-contaminated producer units | exact Zhongjian, SGT, and Espressif full units; assert the factual tail text and offsets are exact and page/report text owns no card |
| Black Sesame exact coverage | producer fixture for `hk_market_outlook-2`, `hk_financial_commentary-2`, and `hk_product_progress-1`; assert all six exact fragments are owned once in canonical families |
| Zhongjian exact coverage | fixtures for the three listed blocks; assert production-mode and capital-spend facts become owned; feed the existing cash-flow v2 tail to material pack and assert the heading-prefixed legacy fragment is covered exactly |
| SGT exact coverage | fixtures for cash flow, both product-profile blocks, and the complete damaged `rd_product_progress-1` block; assert five valid fragments are owned once and the damaged block emits zero cards |
| Espressif exact coverage | fixtures for the five listed source blocks; assert all 11 exact fragments are owned once after sanctioned prefix removal |
| Zhongji producer coverage | feed the expanded exact evidence block to the producer; assert the two target market SourceUnits are disjoint and owned once |
| No semantic-loss filter | replace cross-block semantic-dedup tests with tests asserting that two selected blocks with similar prose retain their own exact SourceUnits; retain one-family-per-unit and no-reuse assertions |
| C4 invalid only | material-pack fixture with the complete SGT garbled v1 excerpt and no v2 cards; assert all interleaved fragments are `invalid_legacy`, adapter zero; add a normally wrapped R&D paragraph negative control that remains actionable without proof |
| Exact proof unchanged | retain noncontiguous, foreign-block, arbitrary-prefix, and gap tests; all must remain uncovered |
| Producer invariants | all admitted unit IDs unique; source text equals `cleaned[start_pos:end_pos]`; validation failures clear cards |
| Eight-stock gate | regenerate cards from the eight local caches into a temporary Knowledge mirror and require actionable/adapter `0/0` for every stock |

The current synthetic `test_annual_coverage_fixture_fragments_are_covered_or_invalid`
is not sufficient because it writes a matching v2 card by hand. Replace it with
producer-to-material-pack fixtures so each proof originates from the real
single producer path.

Focused verification:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m pytest \
  tests/utils/test_annual_argument_schema.py \
  tests/utils/test_periodic_report_evidence_pack.py \
  tests/utils/test_periodic_report_narrative_evidence_cards.py \
  tests/utils/test_annual_report_material_pack.py -q -p no:cacheprovider

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_report_quality.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_report_source_boundary.py -q -p no:cacheprovider

bash tools/ci_grep_gates.sh
git diff --check
```

The eight-stock gate must use local caches only and write generated v2 notes to
`/tmp/annual-producer-v2-final-gate`, not repository `knowledge/`. Copy v1 notes
to that temporary mirror only after producer output is generated, then run the
material pack there. This preserves the rule that v1 never guides selection.

## 8. Complexity Ledger

The implementation must delete or replace before adding.

| File | Current net | Planned delete | Planned add | Incremental target | Expected final net |
| --- | ---: | ---: | ---: | ---: | ---: |
| `annual_argument_schema.py` | +54 | 7 | 12 | +5 | +59 |
| `annual_report_material_pack.py` | +84 | 4 | 10 | +6 | +90 |
| `periodic_report_evidence_pack.py` | +30 | 1 | 1 | 0 | +30 |
| `periodic_report_narrative_evidence_cards.py` | +191 | 66 | 25 | -41 | +150 |
| **Total** | **+359** | **78** | **48** | **-30** | **+329** |

The producer deletion budget comes primarily from removing cross-block semantic
dedup and consolidating four technology predicates into one. The expected
runtime delta is `-30` relative to the current worktree, producing about `+329`
versus `aa7bdd9`. Line counts are an implementation constraint, not a reason to
compress unreadably: the hard requirement is no positive incremental runtime
delta, and the target is at least `-25`.

## 9. Stop Conditions

Stop implementation and return to design review if any condition holds:

1. Either Zhongji fragment still cannot appear exactly in a selected block
   without changing `_MAX_BLOCKS`, `_MAX_CHARS_PER_BLOCK`, usage limits, or
   adding a selector.
2. A source tail cannot be represented as an exact substring with exact offsets.
3. Any valid C1-C3 fragment reaches zero only by `invalid_legacy` classification.
4. The C4 rule rejects the normal wrapped-R&D negative control.
5. Exact coverage requires fuzzy, semantic, cross-block, or noncontiguous proof.
6. Any SourceUnit has zero owners after admission, more than one owner, or is
   rewritten rather than sliced.
7. Removing semantic dedup causes candidate invariant failure or requires a
   second ranking/selection pass.
8. Runtime net delta is positive relative to current `+359`, or cannot reach at
   least the `-25` target without scope expansion.
9. A required change touches a file outside the allowed list below.
10. Any focused/downstream/CI/diff check fails for a behavior not resolved within
    the locked design.
11. Any of the eight stocks remains nonzero. In that case do not generate
    reports, archive v1, or delete the adapter.

## 10. Implementation Tasks And Allowed Files

### Task 1: Evidence And Syntax RED/GREEN

Add the Zhongji exact evidence-window fixture and shared source-tail syntax
fixtures. Replace the line budget and checkbox-only helper. Verify exact source
substrings and unchanged caps.

### Task 2: Producer Admission RED/GREEN

Add exact five-stock producer fixtures. Replace the source-tail extraction and
family seed predicates. Delete semantic dedup and consolidate technology
helpers. Verify every valid target SourceUnit has exactly one owner.

### Task 3: Invalid And Coverage RED/GREEN

Add the full SGT OCR fixture and exact material-pack boundary fixtures. Replace
material classification with shared source-tail proof and the single C4 rule.
Retain all exact-proof negatives.

### Task 4: Verification And Local Gate

Run focused and downstream suites, CI grep, diff check, numstat, then the
temporary eight-stock local-cache gate. Stop on any nonzero stock.

Allowed runtime files:

- `scripts/utils/annual_argument_schema.py`
- `scripts/utils/annual_report_material_pack.py`
- `scripts/utils/periodic_report_evidence_pack.py`
- `scripts/utils/periodic_report_narrative_evidence_cards.py`

Allowed test files:

- `tests/utils/test_annual_argument_schema.py`
- `tests/utils/test_annual_report_material_pack.py`
- `tests/utils/test_periodic_report_evidence_pack.py`
- `tests/utils/test_periodic_report_narrative_evidence_cards.py`

Allowed implementation note:

- `docs/agent_workflow/2026-07-12-annual-producer-v2-final-coverage-claude-notes.md`

Everything else is forbidden. In particular, no code or generated output under
`knowledge/`, `data/raw/`, or `reports/` may be modified.

## 11. Final Verdict

`implementation_ready: yes`

The remaining failure set is fully classified and has a bounded path that keeps
the 48-block cap, exact same-block SourceUnit proof, one selector, and five
families. The design is replacement-oriented and targets a `-30` runtime-line
delta. Report generation, v1 archival, and adapter removal remain blocked until
the post-implementation eight-stock gate is exactly zero.
