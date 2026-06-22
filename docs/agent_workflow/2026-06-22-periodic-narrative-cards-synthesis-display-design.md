# Periodic Narrative Cards Synthesis Display Design

Date: 2026-06-22

Status: Draft for review

## 1. Goal

Use persisted annual-report narrative cards as high-quality report context without changing the canonical synthesis, risk scoring, scoring, core facts, or Knowledge persistence paths.

The intended behavior is display-only:

- `ctx["synthesis"]` remains baseline.
- `ctx["synthesis_text"]` remains baseline.
- `ctx["core_facts"]` remain baseline.
- `ctx["synthesis_display"]` may include annual-report narrative cards.
- final report renderers may prefer `synthesis_display`.
- risk/scoring/Knowledge persistence must not consume `synthesis_display`.

## 2. Current State

Annual-report material now has several paths:

| Path | Current role | Knowledge | Scoring/risk |
| --- | --- | --- | --- |
| `periodic_report_fulltext_analysis` | fulltext LLM summary / material layer | no | no |
| Ground Truth numeric block | constrains fulltext LLM numbers | no | no |
| `periodic_report_narrative_evidence` | short annual-report text evidence cards | yes, under `periodic_narrative_cards/` | no |
| `periodic_report_filing_fact` | structured financial facts, writer-only | helper-only / gated | no |

Narrative cards are the primary path for useful annual-report text entering Knowledge. They contain business model, product progress, market outlook, margin/competitiveness, technology platform, operation update, and financial-note excerpts.

## 3. Proposed Data Flow

### 3.1 Read

Add a small helper that reads existing narrative card notes for the current stock from:

```text
knowledge/10-Stocks/<stock>/periodic_narrative_cards/*.md
```

It should parse only the structured note fields needed to build display material:

- `card_type`
- `title`
- `source_excerpt` from the note body blockquote under `## Narrative Evidence`
- `source_block_id`
- `card_id`
- `source_type`
- `source_credit`
- `report_year`
- `report_type`

Important reader contract:

- `source_excerpt` is not a frontmatter field in current narrative-card notes.
- The writer stores the excerpt in the Markdown body as `> {excerpt}`.
- The reader must parse that body blockquote, mirroring the legacy excerpt extraction shape used by `scripts/periodic_report_narrative_cards_preview.py`.
- If the body excerpt is missing or empty, skip the note instead of inventing a placeholder.
- Ignore notes that are malformed or not `source_type=periodic_report_narrative_evidence`.

### 3.2 Convert

Convert each valid card into a `SynthesisItem`-compatible display source.

Required metadata:

```python
extra = {
    "source_type": "periodic_report_narrative_evidence",
    "source_credit": 75,
    "verification_status": "professional_analysis",
    "claim_status": "professional_analysis",
    "knowledge_eligible": False,
    "report_eligible": False,
    "synthesis_display_only": True,
    "experimental": True,
    "card_type": card_type,
    "card_id": card_id,
    "source_block_id": source_block_id,
}
```

Important:

- The display item must use `knowledge_eligible=False` even though the original card note is already persisted. This prevents a second Knowledge write through synthesis.
- `report_eligible=False` intentionally matches the fulltext material-layer convention. These items do not flow through `source_intake_merge`; they are injected directly into display synthesis.
- `synthesis_display_only=True` is advisory metadata unless implementation code explicitly checks it. The hard gate is that these items are only passed to the display synthesis call.

### 3.3 Inject

Extend `SynthesisSkill.run()` by composing all display-only annual-report extras in one place. This must include the existing fulltext display path and the new narrative-card display path so the shared `ctx["synthesis_display"]` key is written once.

```text
baseline = synthesize(existing normal items)
ctx["synthesis"] = baseline
ctx["synthesis_text"] = flatten(baseline)
ctx["core_facts"] = baseline.core_facts

display_extra_items = []

if include_periodic_report_fulltext_in_synthesis:
    display_extra_items += eligible fulltext material items

if include_periodic_narrative_cards_in_synthesis_display:
    display_extra_items += eligible narrative-card display items

if display_extra_items:
    display = synthesize(existing normal items + display_extra_items)
    ctx["synthesis_display"] = display
    ctx["synthesis_display_sources"] = display._sources
    ctx["synthesis_text_with_periodic_display_materials"] = flatten(display)

    if fulltext material was included:
        ctx["synthesis_text_with_periodic_report_fulltext"] = flatten(display)

    if narrative cards were included:
        ctx["synthesis_text_with_periodic_narrative_cards"] = flatten(display)
```

Ordering must be deterministic:

```text
normal synthesis items first, then fulltext material items, then narrative-card items
```

This preserves ordinary source numbering and avoids the both-on bug where fulltext and narrative cards overwrite each other's `synthesis_display`.

This mirrors the existing fulltext display-only pattern while making the shared display key explicit.

### 3.4 Render

No renderer changes should be required if the existing renderers already use:

```python
ctx.get("synthesis_display") or ctx.get("synthesis")
```

The display-enhanced result should be visible in:

- executive summary
- deep analysis
- HTML dashboard

It must not be visible to paths that read only `ctx["synthesis"]` or `ctx["synthesis_text"]`.

## 4. Source Policy

Narrative cards are stronger than raw fulltext LLM summaries because they are short, deterministic, evidence-bound excerpts. They are still not confirmed facts.

Policy:

- credit stays `75`.
- status stays `professional_analysis`.
- source type stays `periodic_report_narrative_evidence`.
- cards can be used as report context.
- cards cannot support `confirmed_fact` / `fact_candidate` through synthesis.
- cards cannot change `synthesis_text`.
- cards cannot change risk keyword scoring.
- cards cannot be written again by `knowledge_skills`.

## 5. Allowed Files For Implementation

Recommended minimum:

- `scripts/utils/report_skills/synthesis_skills.py`
- a new small helper if needed, e.g. `scripts/utils/periodic_report_narrative_card_synthesis_items.py`
- tests under `tests/reporter/` or `tests/utils/`
- `tools/ci_grep_gates.sh`
- `tests/utils/test_ci_grep_gates.py`

No `scripts/utils/synthesis_credit.py` change should be needed: `source_credit=75` is below the high-credit threshold and `periodic_report_narrative_evidence` is not a confirmed source type.

Do not modify:

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/knowledge_skills.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- `scripts/utils/report_skills/claim_risk_signal_skill.py`
- `scripts/utils/synthesis_credit.py`
- `scripts/utils/periodic_report_narrative_evidence_cards.py`
- `scripts/utils/periodic_report_narrative_card_note_writer.py`
- report entry scripts

## 6. Configuration

Add an explicit default-off switch.

Suggested context key:

```text
include_periodic_narrative_cards_in_synthesis_display
```

Default:

```text
False
```

This should be enabled only for report trials where narrative-card Knowledge has already been generated.

## 7. Failure Modes

### 7.1 Risk scoring leakage

Failure: display-enhanced narrative enters `ctx["synthesis_text"]`, and `risk_renderer` / `scoring_engine` keyword scans change.

Required guard:

- `ctx["synthesis_text"]` remains byte-for-byte baseline when display cards are enabled.
- only `ctx["synthesis_text_with_periodic_narrative_cards"]` contains display cards.

### 7.2 Knowledge persistence leakage

Failure: `knowledge_skills` writes display-enhanced synthesis into Knowledge, causing annual-report card content to backflow through deep analysis notes.

Required guard:

- `ctx["synthesis"]` remains baseline.
- `knowledge_skills` continues reading only `ctx["synthesis"]`.
- no change to `knowledge_skills.py`.

### 7.3 Core fact promotion

Failure: narrative cards indirectly support `core_facts` or citation-derived `confirmed_fact` / `fact_candidate`.

Required guard:

- `ctx["core_facts"]` remains baseline.
- source type `periodic_report_narrative_evidence` is not added to confirmed-source allowlists.

### 7.4 Bad or stale card notes

Failure: stale or malformed note files create low-quality synthesis context.

Required guard:

- reader skips malformed notes.
- reader admits only `source_type=periodic_report_narrative_evidence`.
- reader can cap by `max_cards` and prefer recent/valid notes.

### 7.5 Citation confusion

Failure: display citations look like official confirmed evidence.

Required guard:

- citation metadata keeps `source_type=periodic_report_narrative_evidence`.
- source credit remains `75`.
- source platform/title should make annual-report material clear.

### 7.6 Fulltext and narrative-card display collision

Failure: fulltext display synthesis and narrative-card display synthesis both write `ctx["synthesis_display"]`, so the later path overwrites the earlier one.

Required guard:

- collect all display-only extra items first;
- compute `ctx["synthesis_display"]` once;
- test the both-on case contains both `periodic_report_fulltext_analysis` and `periodic_report_narrative_evidence` sources.

## 8. Test Plan

Minimum tests:

1. Default-off: narrative-card notes do not affect `synthesis_display`.
2. Reader allowlist: only `periodic_report_narrative_evidence` notes are loaded.
3. Reader body parsing: `source_excerpt` is read from the `## Narrative Evidence` blockquote, not from frontmatter.
4. Reader read-only: loading cards never writes, refreshes, or deletes `knowledge/` notes.
5. Baseline invariant: enabling display cards leaves `ctx["synthesis"]`, `ctx["synthesis_text"]`, and `ctx["core_facts"]` byte-for-byte unchanged.
6. Narrative-card leak fixture: invariants must use `source_type=periodic_report_narrative_evidence`, not only `periodic_report_fulltext_analysis`.
7. Display enhancement: enabling display cards creates `ctx["synthesis_display"]` containing card-derived material.
8. Both-on composition: enabling fulltext display and narrative-card display produces one `synthesis_display` containing both source types, ordered normal -> fulltext -> cards.
9. Risk invariant: with risk keywords inside a card, `ctx["synthesis_text"]` still does not contain those keywords.
10. Knowledge invariant: simulated `knowledge_skills` input sees baseline `ctx["synthesis"]`, not display-enhanced synthesis.
11. Citation metadata: display citations include `source_type=periodic_report_narrative_evidence`, `source_credit=75`, `verification_status=professional_analysis`.
12. Malformed note skip: invalid notes do not crash synthesis.
13. Cap/order: reader deterministically caps cards by stable ordering.
14. Gate A: `periodic_report_narrative_evidence` is rejected if it appears in scoring/risk/Knowledge persistence files.

Suggested focused commands:

```bash
python3 -m pytest tests/reporter/test_synthesis_skills.py tests/reporter/test_fulltext_material_isolation.py -q
python3 -m pytest tests/utils/test_ci_grep_gates.py -q
bash tools/ci_grep_gates.sh
git diff --check
```

## 8.1 CI Gate Update

Extend Gate A in `tools/ci_grep_gates.sh` so the forbidden regex covers:

```text
periodic_report_fulltext|periodic_report_narrative_evidence|synthesis_display
```

The existing protected file list should remain narrow: scoring, risk renderer, Knowledge persistence, and periodic-report note writers/helpers where display material must not leak.

Add a negative test in `tests/utils/test_ci_grep_gates.py` proving the gate fails when `periodic_report_narrative_evidence` appears in a protected scoring/risk/Knowledge file.

## 9. Stop Conditions

Stop and report instead of implementing if the task requires:

- modifying scoring or risk scoring;
- modifying `KnowledgeSynthesizer` prompts;
- changing `knowledge_skills.py`;
- adding `periodic_report_narrative_evidence` to confirmed source types;
- writing or refreshing real `knowledge/` notes during tests;
- network, LLM, Chrome, CDP, or report runs.

## 10. Review Prompt

Use this prompt for Claude Code review before implementation:

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做只读设计审查。

目标：
审查 docs/agent_workflow/2026-06-22-periodic-narrative-cards-synthesis-display-design.md，判断“annual-report narrative cards 只进入 synthesis_display，不进入 canonical synthesis / synthesis_text / core_facts / scoring / risk / Knowledge persistence”的设计是否安全、可测、边界清楚。

禁止事项：
- 不要修改源码、测试、配置、prompt。
- 不要运行报告入口。
- 不要访问网络，不要调用 LLM，不要启动 Chrome/CDP。
- 不要写 data/raw、reports、knowledge。
- 唯一允许写操作：把审查结论追加到该设计文档末尾的 “## 11. Claude Review Log”。

重点检查：
1. display-only 数据流是否真的避开 risk_renderer/scoring_engine/knowledge_skills/core_facts。
2. source_type policy 是否与 fulltext material-layer 和 narrative cards Knowledge writer 现状冲突。
3. 是否应该复用 fulltext display-only 路径，还是需要独立 ctx key。
4. 允许修改文件是否过宽或过窄。
5. 测试计划是否足以捕获 risk scoring leak、Knowledge persistence leak、core fact promotion。

输出格式：
- Status: Ready / Needs fixes / Blocked
- Blockers
- Must-fix
- Nice-to-have
- 是否需要二轮审查（R2）
- 是否建议进入实现
- 你本轮实际读取/修改了哪些文件
```

## 11. Claude Review Log

### R1 — Claude Code (read-only design review, 2026-06-22)

**Status: Needs fixes** (design is fundamentally sound and mirrors a proven pattern; not blocked, but several concrete must-fix items before implementation).

#### Verification basis (what was checked in code)

- `scripts/utils/report_skills/synthesis_skills.py:60-79` — the fulltext display-only path already exists. It computes `baseline = _synthesize(...)` first, sets baseline `synthesis` / `core_facts` / `synthesis_text` / `synthesis_sources`, then, gated by `ctx.get("include_periodic_report_fulltext_in_synthesis")`, computes a separate `display = _synthesize(..., extra_items=fulltext_items)` and sets `synthesis_display`, `synthesis_display_sources`, `synthesis_text_with_periodic_report_fulltext`. `_synthesize` appends `extra_items` LAST (`synthesis_skills.py:214-215`) so ordinary source numbering stays stable.
- Consumers verified: `risk_renderer.py:23` reads `ctx.get("synthesis_text")` only; `scoring_engine.py` reads no synthesis ctx keys (receives `synthesis_text` as a function arg); `knowledge_skills.py:61` reads `ctx.get("synthesis", {})` only. None fall back to `synthesis_display`. ✅ The display-only isolation claim holds for risk/scoring/knowledge/core_facts.
- Renderers `executive_summary_renderer.py:245`, `deep_analysis_renderer.py:34`, `html_dashboard_renderer.py:125` already use `ctx.get("synthesis_display") or ctx.get("synthesis") or {}`. ✅ No renderer change needed (§3.4 correct).
- `synthesis_credit.py:40-52,129-145` — `_CONFIRMED_SOURCE_TYPES` / `_CONFIRMED_VERIFICATION_STATUSES` do not contain `periodic_report_narrative_evidence` or `professional_analysis`, and `_HIGH_CREDIT_THRESHOLD = 80`. A card at `source_credit=75` + `verification_status=professional_analysis` cannot be promoted to confirmed_fact/fact_candidate. ✅ §4 source policy is safe against promotion.
- `tools/ci_grep_gates.sh:22-45` (Gate A) forbids the regex `periodic_report_fulltext|synthesis_display` in 6 files (scoring_engine, risk_renderer, knowledge_skills, filing_fact_note_writer, narrative_evidence_cards, narrative_card_note_writer). It does **not** mention `periodic_report_narrative_evidence`.
- `tests/reporter/test_fulltext_material_isolation.py` — its fixtures use `source_type="periodic_report_fulltext_analysis"`; the dual-synthesizer only treats fulltext items as display material, so these tests would still pass even if narrative cards leaked into a forbidden path.

#### Blockers

- None. The design does not require touching any stop-condition file; the proven fulltext pattern transfers.

#### Must-fix (before implementation)

1. **Shared `synthesis_display` key collision with the existing fulltext path.** Both the existing fulltext path and this design write the *same* `ctx["synthesis_display"]` key. §3.3 pseudocode builds `display = synthesize(normal items + cards)` — if `include_periodic_report_fulltext_in_synthesis` is also on, whichever skill runs last clobbers the other, and the card display would *drop* fulltext items (or vice-versa). Define the composition explicitly: when both flags are on, the display synthesis must be `synthesize(normal + fulltext_items + card_items)`, computed in one place, with deterministic ordering. Add a test for the both-on case.
2. **`source_excerpt` is not a frontmatter field.** `periodic_report_narrative_card_note_writer.py:172-191` writes `source_excerpt` only into the note *body* as a `> {excerpt}` blockquote (frontmatter has `source_excerpt_hash`, not `source_excerpt`). §3.1 lists `source_excerpt` as a "structured note field" to parse — the reader must parse the body blockquote (mirror `periodic_report_narrative_cards_preview.py:_extract_legacy_note_excerpt`), not frontmatter. Correct §3.1 and add a malformed/legacy-body parse test.
3. **Extend Gate A to cover the new material identifier.** Gate A's regex does not include `periodic_report_narrative_evidence`, so a future leak of card material into scoring/risk/knowledge would pass CI silently. Add `periodic_report_narrative_evidence` (and the new helper module name) to the Gate A regex, and add the new helper to the protected scan list semantics. This requires `tools/ci_grep_gates.sh` + `tests/utils/test_ci_grep_gates.py` to be in the allowed-files list — they currently are not (see Must-fix 4).
4. **Allowed-files list (§5) is too narrow on guardrails, and slightly ambiguous on source policy.** Add `tools/ci_grep_gates.sh` and `tests/utils/test_ci_grep_gates.py` (needed for Must-fix 3). The `synthesis_credit.py` "allowed only if…" caveat is fine, but the verified fact is that no `synthesis_credit.py` change is needed for safety (75 < 80 threshold already blocks promotion) — state that explicitly so an implementer does not "preemptively" edit it.
5. **Test plan gaps (re: leak detection).** Current `test_fulltext_material_isolation.py` will NOT catch a narrative-card leak because it keys on the fulltext source_type. The §8 tests must be authored with `source_type="periodic_report_narrative_evidence"` fixtures specifically, and must add: (a) byte-for-byte `synthesis`/`synthesis_text`/`core_facts` baseline-invariant when card flag is on (item 3 — make it byte-for-byte, not just "unchanged"); (b) risk keyword inside a card must not appear in `synthesis_text` (item 5 — good, keep); (c) a simulated `knowledge_skills` read sees baseline `synthesis` only (item 6 — good, keep); (d) the new Gate A regex test; (e) the both-flags-on composition test from Must-fix 1.

#### Nice-to-have

- **Metadata consistency.** Live card metadata (`periodic_report_narrative_evidence_cards.py:1544-1565`) does NOT set `verification_status`/`claim_status` (it sets `synthesis_eligible=False`). The design's display item adds `verification_status`/`claim_status="professional_analysis"` and `synthesis_display_only=True`. These additions are harmless (no consumer enforces them; not in confirmed allowlists) but `synthesis_display_only` has no enforcement behind it today — either wire a guard that reads it, or document it as advisory-only so it is not mistaken for a hard gate.
- **`report_eligible` divergence.** Design sets `report_eligible=True`; fulltext material sets `report_eligible=False` (`periodic_report_fulltext_llm_analysis.py:471-477`). Confirm what consumes `report_eligible` and justify the divergence in the doc, or align it.
- **Reader read-only assertion.** Add an explicit test that the §3.1 reader never writes/refreshes `knowledge/` notes (pairs with §9 stop conditions).

#### R2 needed?

**Yes — a short R2** to confirm the resolved composition semantics (Must-fix 1), the body-parse reader contract (Must-fix 2), and the extended Gate A (Must-fix 3). R2 can be doc-only if those three are addressed in the design text.

#### Proceed to implementation?

**Not yet.** Address Must-fix 1–5 in the design (they are mostly doc/spec corrections, not deep redesign), then a quick R2 sign-off; after that the implementation is low-risk and tracks the existing fulltext pattern closely.

#### Files read / modified this round

- Read: `docs/agent_workflow/2026-06-22-periodic-narrative-cards-synthesis-display-design.md`, `docs/agent_workflow/context_index.md`, `scripts/periodic_report_narrative_cards_preview.py`, and (via read-only sub-investigation) `scripts/utils/report_skills/synthesis_skills.py`, `scripts/utils/reporter/sections/risk_renderer.py`, `scripts/utils/reporter/scoring_engine.py`, `scripts/utils/report_skills/knowledge_skills.py`, `scripts/utils/report_skills/claim_risk_signal_skill.py`, `scripts/utils/knowledge_synthesizer.py`, `scripts/utils/synthesis_credit.py`, `scripts/utils/periodic_report_narrative_card_note_writer.py`, `scripts/utils/periodic_report_narrative_evidence_cards.py`, `scripts/utils/periodic_report_fulltext_llm_analysis.py`, `tools/ci_grep_gates.sh`, `tests/utils/test_ci_grep_gates.py`, `tests/reporter/test_fulltext_material_isolation.py`, the relevant renderers.
- Modified: only this file (§11 Claude Review Log).

### Design Delta After R1

Accepted:

- §3.1 now states that `source_excerpt` must be parsed from the note body blockquote under `## Narrative Evidence`, not from frontmatter.
- §3.2 now sets `report_eligible=False` and documents `synthesis_display_only=True` as advisory metadata unless implementation code checks it.
- §3.3 now composes fulltext and narrative-card display extras together and writes `ctx["synthesis_display"]` once. Both-on ordering is normal items -> fulltext material -> narrative cards.
- §5 now allows `tools/ci_grep_gates.sh` and `tests/utils/test_ci_grep_gates.py`, and explicitly says `synthesis_credit.py` should not need changes.
- §7.6 adds the fulltext/narrative-card `synthesis_display` collision failure mode.
- §8 expands the test plan with narrative-card-specific leak fixtures, byte-for-byte baseline invariants, body parsing, read-only reader behavior, both-on composition, and Gate A coverage.
- §8.1 specifies the Gate A regex extension to include `periodic_report_narrative_evidence`.

Rejected:

- None.

Deferred:

- No implementation yet. R2 should be a short doc-only review focused on composition semantics, body parsing, and Gate A.

R2 required: yes.

### Implementation Log — Codex (2026-06-22)

Implemented the R2-approved display-only path with TDD.

Files changed:

- `scripts/utils/periodic_report_narrative_card_synthesis_items.py` — new read-only helper that loads `periodic_narrative_cards/*.md`, parses frontmatter metadata, parses `source_excerpt` from the `## Narrative Evidence` blockquote, and returns display-only `SynthesisItem` objects.
- `scripts/utils/report_skills/synthesis_skills.py` — composes all display-only annual-report extras in one place. When both fulltext and narrative cards are enabled, it synthesizes once with normal items -> fulltext items -> narrative-card items and writes one `ctx["synthesis_display"]`.
- `tools/ci_grep_gates.sh` — Gate A now rejects `periodic_report_narrative_evidence` in core scoring/risk/Knowledge persistence files while avoiding false positives in the narrative-card helper/writer that legitimately define the source type.
- `tests/utils/test_periodic_report_narrative_card_synthesis_items.py` — new reader tests for body blockquote parsing, source-type allowlist, read-only behavior, and deterministic caps.
- `tests/reporter/test_synthesis_skills.py` — display-only tests for default-off behavior, baseline invariants, risk keyword isolation, Knowledge baseline behavior, and fulltext+narrative both-on composition.
- `tests/utils/test_ci_grep_gates.py` — negative gate test for narrative-card leakage into scoring.

Verification:

- `python3 -m pytest tests/reporter/test_synthesis_skills.py tests/reporter/test_fulltext_material_isolation.py tests/utils/test_periodic_report_narrative_card_synthesis_items.py tests/utils/test_ci_grep_gates.py -q` -> 63 passed.
- `bash tools/ci_grep_gates.sh` -> all gates passed.
- `git diff --check` -> clean.

No report runs, no LLM, no network, no Chrome/CDP, no writes to `data/raw`, `reports`, or `knowledge`.

### R2 — Claude Code (read-only design review, 2026-06-22)

**Status: Ready** (R1 Must-fix 1–5 resolved in design text; no residual risk of leakage into risk/scoring/Knowledge/core_facts; implementation may proceed with standard TDD and CI gate updates).

#### R1 Must-fix 逐项复核

1. **Shared `synthesis_display` key collision** — ✅ 已解决。§3.3 明确要求在 `SynthesisSkill.run()` 内统一收集所有 display-only extra items，计算一次 `ctx["synthesis_display"]`，顺序为 normal → fulltext → narrative cards；§7.6 新增碰撞失败模式；§8 测试 8 覆盖 both-on 合成。
2. **`source_excerpt` body-blockquote 解析** — ✅ 已解决。§3.1 明确 `source_excerpt` 不是 frontmatter，必须从 `## Narrative Evidence` 下的 `> {excerpt}` 解析，并引用 `preview.py` 的 legacy 提取形状；§8 测试 3 覆盖正文解析。
3. **Gate A 扩展** — ✅ 已解决。§8.1 把 Gate A 正则改为 `periodic_report_fulltext|periodic_report_narrative_evidence|synthesis_display`；§5 把 `tools/ci_grep_gates.sh` 和 `tests/utils/test_ci_grep_gates.py` 加入允许修改文件；§8 测试 14 覆盖 Gate A 负样本。
4. **允许文件 + source policy 明确性** — ✅ 已解决。§5 新增 CI gate 文件，并明确声明 `synthesis_credit.py` 不需要修改（75 < 80 阈值已天然阻止晋升）。
5. **测试计划补缺** — ✅ 已解决。§8 测试 5 要求 baseline byte-for-byte 不变；测试 6 要求使用 `source_type=periodic_report_narrative_evidence` 的夹具；测试 4 要求 reader read-only；测试 9/10/11/12/13 覆盖 risk/Knowledge/metadata/malformed/cap；测试 14 覆盖 Gate A。

#### 残余风险检查

- **risk/scoring leak**：风险渲染器只读 `synthesis_text`（已验证 `risk_renderer.py:23`），评分引擎从参数接收 `synthesis_text` 且不读 synthesis ctx keys。设计保持 `synthesis_text` baseline byte-for-byte，故无泄漏。✅
- **Knowledge persistence leak**：`knowledge_skills.py:61` 只读 `ctx["synthesis"]`；设计保持 `synthesis` baseline；display items 带 `knowledge_eligible=False`。✅
- **core_fact promotion**：`core_facts` 来自 baseline；`periodic_report_narrative_evidence` 不在 `synthesis_credit.py` 的 confirmed source types / verification statuses 中，且 credit 75 < 80 阈值。✅
- **source_type policy 冲突**：无冲突。display item 的 `source_type=periodic_report_narrative_evidence` 与 note writer 一致；`verification_status=professional_analysis` 与 fulltext material 层一致；`report_eligible=False` 也与 fulltext 层对齐。✅

#### Blockers

- 无。

#### Must-fix

- 无（设计层面已就绪；实现阶段应遵循 §8 测试计划和 §9 stop conditions）。

#### Nice-to-have（实现阶段可顺手处理，非阻塞）

- 在 §3.2 的代码块里把 `synthesis_eligible=False` 也显式加入 extra 元数据，与现有 `_build_card` 一致（当前缺该字段，但无消费者强制要求）。
- 实现 reader 时，把 `_extract_legacy_note_excerpt` 的解析逻辑复用到新 helper，避免两份 parser 漂移。
- 考虑把 `synthesis_text_with_periodic_narrative_cards` 的命名与 §3.3 中 `synthesis_text_with_periodic_display_materials` 的关系写得更直白：后者是 both-on 时的统一 flattened text，前者是仅卡片开启时的别名/回退。

#### 是否建议进入实现

**建议进入实现。** 设计边界清楚、安全可测、与现有 fulltext display-only 路径一致。实现时应：
- 严格遵循 §5 允许文件列表；
- 先写 §8 列出的测试并 watch fail；
- 同步更新 `tools/ci_grep_gates.sh` 与 `tests/utils/test_ci_grep_gates.py`；
- 跑 `python3 -m pytest tests/reporter/test_synthesis_skills.py tests/reporter/test_fulltext_material_isolation.py tests/utils/test_ci_grep_gates.py -q` + `bash tools/ci_grep_gates.sh` + `git diff --check` 后再收尾。

#### 本轮实际读取/修改的文件

- **读取（只读）**：`docs/agent_workflow/2026-06-22-periodic-narrative-cards-synthesis-display-design.md`（完整重读 §1–§10 与 §11 R1 log）。
- **修改**：仅本设计文档 `## 11. Claude Review Log` 末尾追加 R2 结论（唯一允许的写操作）。

未联网、未调用 LLM、未运行报告入口、未启动 Chrome/CDP、未写 data/raw·reports·knowledge、未改源码/测试/配置/prompt。
