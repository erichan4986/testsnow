# HK Periodic Report Evidence Pack Design

> **Date**: 2026-06-20
> **Owner**: Codex
> **Status**: Under Claude Review

---

## 1. Goal

Add deterministic HK annual-report evidence-pack blocks so `periodic_report_structured_facts.py` can anchor HK filing facts instead of failing closed.

The immediate validation target is 黑芝麻智能 02533.HK using local Chinese HK annual-report text. The expected outcome is not a full HK financial model. The expected outcome is that `build_periodic_report_evidence_pack(...)` preserves current-year HK financial statement snippets with stable block ids and bounded excerpts, and that `periodic_report_structured_facts.py` can anchor supported HK labels to those scoped blocks.

---

## 2. Non-Goals

- Do not fetch HKEX or company websites.
- Do not change `hk_periodic_report_fetcher.py`.
- Do not register structured facts into pipeline, Knowledge, scoring, or risk scoring.
- Do not change `periodic_report_structured_facts.py` beyond HK label variants needed for evidence anchoring.
- Do not support every HK annual-report layout in the first pass.
- Do not anchor to five-year summaries when a current-year income statement/cash-flow statement is available.

---

## 3. Current Context

| Area | Current Behavior | Relevant Files |
|------|------------------|----------------|
| Evidence pack | A-share-oriented section/table windows; HK financial summary blocks are often missed | `scripts/utils/periodic_report_evidence_pack.py` |
| HK required financial metrics | Can extract some HK values from flattened text, but lacks source block provenance | `scripts/utils/periodic_report_required_financial_metrics.py` |
| Structured facts | Requires evidence-pack block anchors; skips unanchored facts | `scripts/utils/periodic_report_structured_facts.py` |
| HK fetch helper | Helper-only cache/fetch wrapper exists, no pipeline integration | `scripts/utils/hk_periodic_report_fetcher.py` |
| Recorded gap | 黑芝麻 preview emitted zero structured facts because evidence pack lacked HK financial blocks | `docs/agent_workflow/2026-06-20-vibe-trading-inspired-safety-and-periodic-report-roadmap.md` |

Preview finding: 黑芝麻中文 HK cache produced mostly unrelated blocks such as contingency/government grants. It did not produce HK income statement or cash-flow statement blocks. In addition, the structured-facts helper currently anchors Phase A metrics with A-share simplified labels (`营业收入`, `归属于上市公司股东的净利润`, `经营活动产生的现金流量净额`), while the HK cache uses labels such as `收入` and `經營活動所用現金淨額`.

---

## 4. Proposed Design

### 4.1 Add HK-Specific Block Extractors

Keep existing A-share extraction intact. Add bounded HK-specific keyword/table windows in `periodic_report_evidence_pack.py`.

Candidate new usages:

| Usage | Purpose | Typical Labels |
|-------|---------|----------------|
| `hk_financial_summary_table` | current-year summary row block | 收入, 毛利, 毛利率, 研發開支, 經營虧損, 經調整虧損淨額 |
| `hk_income_statement_table` | primary consolidated income statement | 綜合損益表, 合併損益表, 來自客戶合同的收入, 銷售成本, 毛利, 年內虧損 |
| `hk_cash_flow_table` | primary cash-flow statement | 綜合現金流量表, 經營活動所用現金淨額, 經營活動產生的現金流量淨額 |
| `hk_trade_receivables_note` | receivables note | 貿易應收款項, 應收票據, 減值撥備 |
| `hk_financial_assets_cash_note` | cash and fair-value financial assets | 現金及現金等價物, 按公允價值計入損益的金融資產 |

For Phase HK-A, only the first three are required for structured facts.

### 4.1.1 Structured-Facts HK Label Variants

Phase HK-A includes a small structured-facts change: filing fact anchoring must accept HK label variants while remaining scoped to evidence-pack blocks.

Required Phase HK-A label variants:

| Metric | Existing A-share Label | HK Variants |
|--------|------------------------|-------------|
| `revenue` | `营业收入` | `收入`, `來自客戶合同的收入`, `来自客户合同的收入` |
| `operating_cash_flow` | `经营活动产生的现金流量净额` | `經營活動所用現金淨額`, `经营活动所用现金净额`, `經營活動產生的現金流量淨額`, `经营活动产生的现金流量净额` |

Do not map `年內虧損` / `年内亏损` / `經調整虧損淨額` to `net_profit` in this task. For 黑芝麻-style loss-making HK reports, the expected conservative outcome is:

- `revenue` anchored;
- `operating_cash_flow` anchored as a negative value when reported as cash used;
- `net_profit` missing;
- no cash-flow-to-profit derived ratio;
- no `cashflow_quality_weak` signal.

### 4.2 Priority And Anti-Misanchor Rules

HK financial statement blocks should have priority near A-share financial summary blocks:

- `hk_income_statement_table`: priority 0
- `hk_financial_summary_table`: priority 0 or 1
- `hk_cash_flow_table`: priority 6, near `cash_flow_capex_table`

Avoid five-year summary misanchors:

- Exclude any window containing `五年財務概要` / `五年财务概要` from primary `hk_income_statement_table` and `hk_cash_flow_table` usages.
- If five-year summaries are retained later, use a distinct low-priority diagnostic usage id, not a primary statement usage.
- Prefer windows containing `截至 12 月31 日止年度`, `綜合損益表`, `合併損益表`, or `綜合現金流量表`.
- Keep five-year summaries only as fallback diagnostic material, not as primary filing fact anchors.

### 4.3 Text And Label Normalization

Support simplified and traditional labels:

- income/revenue: `收入`, `來自客戶合同的收入`, `来自客户合同的收入`
- gross profit: `毛利`
- operating loss: `經營虧損`, `经营亏损`
- net loss: `年內虧損`, `年内亏损`, `年內經調整虧損淨額`, `经调整亏损净额`
- cash flow: `經營活動所用現金淨額`, `经营活动所用现金净额`, `經營活動產生的現金流量淨額`, `经营活动产生的现金流量净额`

Do not require full translation. Use label variants and whitespace normalization in the extractor.

Bare `收入` is too generic in raw HK annual reports. It is valid for anchoring only inside a dedicated `hk_income_statement_table` / `hk_financial_summary_table` block selected by priority. Do not anchor bare `收入` from arbitrary raw text.

### 4.4 Data Flow

```text
HK annual report text
  -> build_periodic_report_evidence_pack(...)
      -> existing A-share blocks
      -> new HK financial blocks
  -> build_required_financial_risk_metrics(...)
  -> build_periodic_report_structured_fact_pack(...)
      -> anchored HK filing facts where supported
```

No new network step.

---

## 5. Failure Modes And Tests

| Failure Mode | Symptom | Test Or Check |
|--------------|---------|---------------|
| HK income statement not extracted | 黑芝麻 revenue cannot anchor | Fixture with 黑芝麻-style `截至 12 月31 日止年度` table asserts `hk_income_statement_table` block exists |
| HK cash-flow statement not extracted | operating cash flow cannot anchor | Fixture with `經營活動所用現金淨額` asserts `hk_cash_flow_table` block exists |
| HK labels not accepted by structured facts | HK blocks exist but facts still skip | End-to-end fixture asserts `revenue` and negative `operating_cash_flow` anchor using HK labels |
| Five-year summary used instead of current-year statement | structured facts anchor to old summary block | Fixture containing both five-year summary and income statement; assert primary block id is income statement |
| Five-year summary is the only financial window | false facts emitted from multi-year summary | Fixture with five-year summary only asserts no filing facts and diagnostics only |
| Existing A-share pack regresses | A-share required metrics lose blocks | Existing `test_periodic_report_evidence_pack.py` and required metrics tests |
| Too many noisy HK blocks | LLM prompt/evidence pack bloats | Block cap and priority tests keep top blocks stable |
| Missing HK block leads to fake fact | placeholder refs emitted | Existing structured-facts tests confirm fail-closed diagnostics |

---

## 6. Files Expected To Change

| File | Change Type | Reason |
|------|-------------|--------|
| `scripts/utils/periodic_report_evidence_pack.py` | Modify | Add HK-specific block extraction/priority |
| `tests/utils/test_periodic_report_evidence_pack.py` | Modify | HK fixtures for income statement/cash flow/five-year summary avoidance |
| `scripts/utils/periodic_report_structured_facts.py` | Modify | Add HK label variants for supported Phase A metrics only |
| `tests/utils/test_periodic_report_structured_facts.py` | Modify | End-to-end HK anchor tests and fail-closed tests |
| `tests/utils/test_periodic_report_required_financial_metrics.py` | Modify if needed | Confirm HK revenue/operating cash-flow values remain under expected keys |
| `docs/agent_workflow/2026-06-20-hk-periodic-report-evidence-pack-design.md` | Update | Review log |

---

## 7. Files That Must Not Change In This Task

| File/Area | Reason |
|-----------|--------|
| `scripts/utils/hk_periodic_report_fetcher.py` | No network/fetch behavior change |
| `scripts/utils/report_skills/__init__.py` | No pipeline registration |
| `scripts/utils/report_skills/synthesis_skills.py` | No synthesis change |
| `scripts/utils/evidence_note_writer.py` | No Knowledge persistence change |
| `scripts/utils/reporter/scoring_engine.py` | No scoring change |
| `scripts/utils/reporter/sections/risk_renderer.py` | No risk rendering/scoring change |
| `data/raw`, `reports`, `knowledge` | No runtime artifacts |

---

## 8. Acceptance Gates

Focused tests:

```bash
python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_structured_facts.py -q
python3 -m pytest tests/utils/test_periodic_report_required_financial_metrics.py tests/utils/test_periodic_report_required_metrics.py -q
python3 -m pytest tests/reporter/test_fulltext_material_isolation.py tests/utils/test_ci_grep_gates.py -q
bash tools/ci_grep_gates.sh
git diff --check
```

No report generation is required. If preview is needed, generate `/tmp` Markdown only and do not write `reports/`, `data/raw`, or `knowledge`.

---

## 9. Open Questions

| Question | Owner | Decision |
|----------|-------|----------|
| Should HK current-year financial blocks use new usages or reuse `financial_summary_table`/`cash_flow_capex_table`? | R1 Review | Use new `hk_*` usages. |
| Should five-year summaries be excluded entirely or kept as low-priority diagnostic blocks? | R1 Review | Exclude from primary HK statement usages; optional diagnostic usage only later. |
| Is `net_profit` support required for HK loss-making companies in this task, or should operating loss / adjusted loss remain a separate later fact? | R1 Review | Do not map HK loss labels to `net_profit` in Phase HK-A. |

---

## 10. Claude Review Log

### Round 1 Feedback (Claude, 2026-06-20)

Status: Must-fix before task
R2 recommended: Yes
Phase HK-A may enter implementation: No (proceed only after the scope correction below is folded in and re-confirmed)

The evidence-pack design itself is sound and close to ready. The blocker is not the HK
block extraction — it is a cross-file scope error: the design assumes adding HK evidence
blocks is sufficient for the stated acceptance criterion ("黑芝麻 revenue can anchor"),
but that criterion is provably unreachable under Non-Goal #4 (do not modify
`periodic_report_structured_facts.py`). The proof needs no implementation:

- `periodic_report_structured_facts._PHASE_A_METRICS` anchors on hard-coded A-share
  simplified labels: `营业收入`, `归属于上市公司股东的净利润`, `经营活动产生的现金流量净额`.
- `_anchor_cell_to_block` requires `label_compact in block_text_compact` AND the value in
  the same block. Whitespace is normalized (good, the Jina-spacing fix has landed), but
  simplified-vs-traditional is a *different axis* and is not normalized.
- Measured against the local 黑芝麻 HK cache (`/tmp/black_sesame_2025_annual_zh_jina.txt`,
  which is actually 繁体): `营业收入` = 0 hits, `归属于上市公司股东的净利润` = 0,
  `经营活动产生的现金流量净额` = 0. The report uses `收入` (94), `年內虧損` (2),
  `經營活動所用現金淨額` (5), under `綜合損益表` (1) / `綜合現金流量表` (4).

Therefore an implementer who touches only `periodic_report_evidence_pack.py` will produce
HK blocks that still anchor zero facts, and acceptance row 1 ("黑芝麻 revenue can anchor")
will fail. Phase HK-A must include the anchor-label work, or the acceptance criterion must
be moved out of this task.

Findings:

- [Must-fix] Non-Goal #4 + §6 scope are inconsistent with the §5 acceptance criterion.
  Phase HK-A must explicitly include: (a) `periodic_report_structured_facts._PHASE_A_METRICS`
  carrying HK label variants (revenue: `收入` / `來自客戶合同的收入`; OCF:
  `經營活動所用現金淨額` and `經營活動產生的現金流量淨額`), and (b) confirmation that
  `periodic_report_required_financial_metrics` keys HK revenue/operating_cash_flow under the
  `revenue` / `operating_cash_flow` keys structured_facts reads (it already does for
  revenue + OCF on this sample; net_profit is correctly absent). Add both files to §6
  "Files Expected To Change". Keep the changes helper-only: `source_credit` stays 75,
  `knowledge_eligible` stays False, no new confirmed source types — Phase A gating intact.

- [Must-fix] Bare `收入` is too generic to anchor on raw text (94 hits). It is only safe
  *inside* a dedicated `hk_income_statement_table` block. The design must state that HK
  revenue anchoring relies on the income-statement block scoping + priority ordering
  (income statement pri 0, first matching block wins), not on a raw-text label search. This
  is the strongest justification for new `hk_*` usages over reusing `financial_summary_table`.

- [Must-fix] Anti-five-year-summary rule must be deterministic, not "mark lower priority OR
  exclude". Pick: exclude any window containing `五年財務概要` / `五年财务概要` from
  `hk_income_statement_table` / `hk_cash_flow_table` primary usages; if retained, give it a
  distinct low-priority diagnostic usage id so it can never be the anchor. The five-year
  block holds multiple years' values in one window, so a current-year value can appear there
  too — priority + exclusion together are what prevent misanchor.

- [Nice-to-have] HK label set should keep both traditional and simplified variants, but note
  that on this sample `來自客戶合同的收入` = 0; bare `收入` (scoped to the statement block)
  is the realistic anchor. Don't over-rely on the `來自...` variant.

- [Nice-to-have] OCF label `經營活動所用現金淨額` ("所用" = cash used) implies an outflow;
  the metrics extractor already returns a negative value (-985,373 千元) for 黑芝麻, so the
  signed-cashflow logic is preserved. Worth an explicit fixture asserting the sign survives.

Open Questions — recommended decisions:

- Q1 (new usages vs reuse): Use new `hk_*` usages. Anchoring is by block text, not usage id,
  but new ids keep A-share extraction/priority/tests untouched and let the five-year
  exclusion and priority rules be tested independently. Reusing `financial_summary_table`
  risks HK content satisfying A-share-targeted gates by coincidence.

- Q2 (five-year summaries): Exclude from primary HK statement usages; optionally retain as a
  distinct low-priority diagnostic usage. Do not let them carry a primary usage id.

- Q3 (net_profit for loss-makers): Do NOT map `年內虧損` to `net_profit` in this task. Keep
  operating loss / adjusted loss as separate later facts. State the expected Phase HK-A
  outcome for 黑芝麻 explicitly: revenue anchored, operating_cash_flow anchored (negative),
  net_profit legitimately missing (`missing_net_profit_for_cashflow_ratio`), no derived
  ratio, no signal. The cashflow-ratio path is therefore not exercised by HK in this task,
  which is correct and conservative.

Test plan additions (beyond §5):

- End-to-end HK anchor test in `test_periodic_report_structured_facts.py`: 黑芝麻-style
  繁体 text (`綜合損益表` + `收入` + current-year value; `綜合現金流量表` +
  `經營活動所用現金淨額`) yields anchored `revenue` + `operating_cash_flow` with the
  expected `hk_*` block ids. This test fails before the anchor-label change — that failure is
  the in-code proof that evidence-pack changes alone are insufficient.
- Misanchor guard: many bare `收入` mentions present; assert revenue anchors to the
  income-statement block, not an unrelated mention.
- Five-year fail-closed: text with five-year summary but no current-year statement → facts
  skip, no placeholder refs, no anchor to five-year values.
- A-share non-regression: keep existing `test_periodic_report_evidence_pack.py` and required
  metrics tests green; assert HK additions do not change existing A-share block ids/priorities.

Scope/guardrail check (Q6): Good. §7 correctly fences fetcher, pipeline registration,
synthesis, Knowledge persistence, scoring, risk rendering, and data/raw/reports/knowledge.
Acceptance gates include `tools/ci_grep_gates.sh` + fulltext isolation tests. Add
`periodic_report_structured_facts.py` / `periodic_report_required_financial_metrics.py` to
§6 and keep them helper-only.

### Design Delta After Round 1

Accepted:
- Expanded Phase HK-A scope to include a small helper-only change in
  `periodic_report_structured_facts.py`: supported Phase A metrics may carry HK label
  variants while remaining scoped to evidence-pack blocks.
- Added explicit HK label variants for `revenue` and `operating_cash_flow`, including
  Traditional and Simplified forms.
- Made the Black Sesame expected outcome conservative and explicit: revenue anchored,
  operating cash flow anchored as negative when reported as cash used, net profit missing,
  no cash-flow ratio, and no typed cashflow signal.
- Added block-scoped anchoring rule for bare `收入`: it is valid only inside a dedicated
  `hk_income_statement_table` / `hk_financial_summary_table` selected by priority, never
  arbitrary raw text.
- Chose deterministic five-year-summary handling: exclude `五年財務概要` / `五年财务概要`
  from primary HK income statement and cash-flow statement usages; any later retention
  must use a separate diagnostic usage id.
- Expanded files expected to change and tests to include structured-facts HK anchor
  variants and required-financial-metrics key confirmation if needed.

Rejected:
- Rejected mapping HK loss labels such as `年內虧損` / `年内亏损` / `經調整虧損淨額` to
  `net_profit` in Phase HK-A. Loss metrics need their own later schema instead of
  pretending they are A-share-style positive profit facts.
- Rejected reusing existing A-share `financial_summary_table` semantics for HK statement
  anchors. New `hk_*` usages keep priority, diagnostics, and non-regression tests
  separable.

Deferred:
- Full HK financial model coverage, including operating loss, adjusted loss, segment-level
  HK metrics, and acquisition/placing/borrowings facts.
- Any HKEX fetcher/network change, pipeline registration, Knowledge persistence, scoring,
  or risk integration.
- Optional five-year-summary diagnostic blocks. Primary fact anchoring must fail closed
  when only five-year summaries are available.

R2 Required:
- Yes — re-confirm the scope correction (anchor-label variants in structured_facts +
  required_financial_metrics key mapping) and the revised acceptance criterion before
  implementation.

### Final Implementation Readiness

- Not yet. Phase HK-A is approved in principle but gated on the must-fix scope correction
  above. Once the design adds the anchor-label work and the consistent acceptance criterion,
  implement via TDD (HK anchor test red first).

### Round 2 Feedback (Claude, 2026-06-20)

Status: Ready to implement (with nice-to-have refinements)
R3 Needed: No
Phase HK-A implementation allowed: Yes

The Round 1 blocker is fully resolved in the revised design, and a source-level check
confirms the acceptance criterion is now reachable without touching any fenced subsystem.

Blockers:

- None. No fetcher/pipeline/Knowledge/synthesis/scoring/risk change is required to make
  黑芝麻 revenue/OCF anchor. The two production files in scope
  (`periodic_report_evidence_pack.py` for HK blocks,
  `periodic_report_structured_facts.py` for HK label variants) are sufficient, and both
  stay helper-only.

R1 blocker verification (all resolved):

- Non-Goal #4 now reads "Do not change `periodic_report_structured_facts.py` beyond HK
  label variants needed for evidence anchoring" (§2), removing the contradiction with §5.
- §4.1.1 + §6 explicitly authorize the HK label-variant change in structured_facts.
- `revenue` carries Traditional + Simplified variants (`收入` / `來自客戶合同的收入` /
  `来自客户合同的收入`); `operating_cash_flow` carries all four
  (`經營活動所用現金淨額` / `经营活动所用现金净额` / `經營活動產生的現金流量淨額` /
  `经营活动产生的现金流量净额`) — §4.1.1, §4.3.
- `年內虧損` / `經調整虧損淨額` are explicitly NOT mapped to `net_profit` (§4.1.1, §4.3
  net-loss row, Open Q3, Design Delta "Rejected"). Conservative outcome (net_profit
  missing, no ratio, no signal) is stated.
- Source confirmation: `periodic_report_required_financial_metrics._extract_hk_profit_quality`
  / `_extract_cash_flow_quality` already populate `revenue` and `operating_cash_flow` from
  HK 繁体 text under the exact keys `_PHASE_A_METRICS` reads, and leave `net_profit` absent
  for loss-makers. So §6's "Modify if needed" row for required_financial_metrics is really
  "confirm via test", not a code change — recommend the design say so to avoid an
  implementer editing it unnecessarily.

Bare `收入` scoping (§4.3): Stated correctly as principle — anchoring valid only inside a
dedicated HK statement block selected by priority, never raw-text-wide. See Nice-to-have
below on making the enforcement mechanism explicit.

Five-year summary (§4.2, Open Q2, Design Delta): Deterministic fail-closed. `五年財務概要`
/ `五年财务概要` windows are excluded from primary `hk_income_statement_table` /
`hk_cash_flow_table` usages; any future retention must use a distinct low-priority
diagnostic usage id. Good.

File scope (§6/§7): Correct and helper-only. §7 fences fetcher, pipeline registration,
synthesis, Knowledge persistence, scoring, risk rendering, and data/raw/reports/knowledge.
`source_credit` 75 / `knowledge_eligible` False / no new confirmed source types preserved.

Test plan (§5 + R1 additions): Covers HK income+cash-flow anchor (end-to-end, red-first),
many-bare-`收入` misanchor guard, five-year-only fail-closed (no placeholder refs), and
A-share non-regression on block ids/priorities. Sufficient to gate the change.

Must-fix:

- None.

Nice-to-have (can be folded in during TDD, not gating):

1. Spell out the `_PHASE_A_METRICS` data-structure change. The current entry carries a
   single `label` string and `_anchor_cell_to_block(blocks, label, cell)` matches one
   label. Supporting variants means either widening the label field to a sequence or
   looping labels in the anchor. Recommend: try the A-share label first, then HK variants,
   first match wins — so A-share behavior is bit-for-bit unchanged. Worth one sentence in
   §4.1.1 so the implementer doesn't reshape the anchor signature ad hoc.
2. Make the bare-`收入` block-scoping mechanism explicit. `_anchor_cell_to_block` returns
   the FIRST block (in pack order) whose text contains the label + value. The design relies
   on `hk_income_statement_table` being priority 0 so it sorts ahead of any incidental
   bare-`收入` block. That is correct given current ordering, but the guarantee is "priority
   ordering + first-match", not "label is only searched inside HK blocks". State this so the
   misanchor test asserts block id == `hk_income_statement_table`, and so nobody assumes the
   anchor itself filters by usage.
3. Value-substring robustness. HK figures are 千元-grouped (e.g. `822,328`); the anchor does
   `text_value in block_text` after comma/whitespace compaction. Add an assertion that the
   metrics `cell["text"]` preserves the as-reported HK figure that actually appears in the
   statement block, so the substring match holds. (The end-to-end anchor test already
   exercises this implicitly; making it explicit prevents a unit-mismatch regression.)
4. Sign-preservation fixture for `經營活動所用現金淨額` ("所用" = cash used → negative).
   Already noted in R1; keep it in the plan so the negative OCF is asserted at the
   filing-fact level even though the derived ratio is skipped for loss-makers.

Test results (read-only):

- `python3 -m pytest tests/utils/test_agent_workflow_docs.py tests/utils/test_ci_grep_gates.py
  tests/reporter/test_fulltext_material_isolation.py -q` → 13 passed.
- `bash tools/ci_grep_gates.sh` → all gates passed (fulltext material-layer isolation; source
  safety AST checks).
- `git diff --check` → clean.

Files changed by this review: only this design document
(`docs/agent_workflow/2026-06-20-hk-periodic-report-evidence-pack-design.md`). No source,
test, config, prompt, data/raw, reports, or knowledge changes. (`context_index.md` and the
R1/R2 review-prompt docs were already modified before this review.)

Recommendation: Begin Phase HK-A via TDD. Write the end-to-end HK anchor test first
(黑芝麻-style 繁体 income statement + cash-flow → anchored `revenue` and negative
`operating_cash_flow`, `net_profit` legitimately missing); confirm it is red against current
code; then add HK blocks in `periodic_report_evidence_pack.py` and HK label variants in
`periodic_report_structured_facts.py` to turn it green, keeping A-share tests untouched.
