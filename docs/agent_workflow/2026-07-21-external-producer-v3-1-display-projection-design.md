# External Producer v3.1 Display Projection Design

日期：2026-07-21  
分支：`codex/pipeline-stabilization`  
状态：Draft for user review

## 1. Problem

External Producer v3 和 External Topic Narrative Memo 已稳定保留 exact SourceUnit、引用身份、
target/peer 边界及可选段落编排，但正式报告仍暴露两类上游质量问题：

1. SourceUnit 同时包含编辑元话语和有效事实，例如“这里做一张清晰的对比表：……”或
   “资料来源：……”。当前 renderer 只能完整展示原文，不能安全删除开头噪声。
2. 省略目标公司名的后续事实可能被判为 `peer_or_industry`。典型场景是前一单元明确目标公司
   与机构/产品，后一单元继续描述同一机构/产品，但只写“中心”“该产品”或重复机构名。

这些问题不能继续在 renderer 里用字符串清洗解决。renderer 缺少原始 unit offset、同源顺序和
scope anchor，容易产生第二套文本/主体 owner。

## 2. Goals

1. 保留 immutable raw SourceUnit、hash、citation identity 和 canonical cards。
2. 为报告提供经过验证的 exact contiguous display span，而不是改写文本。
3. 为 target/peer scope 提供可审计 provenance，而不是根据最终段落猜主体。
4. 无法安全形成 display span 的 unit 保留在 pack，但不进入 Chapter 4.3 display。
5. 不增加 LLM 调用，不修改评分、目标价、风险、技术分析、推荐或 Chapter 4.1/4.2/4.4。
6. 先以中际旭创、复旦微电、黑芝麻智能做 pilot；通过后一次性完成配置股票迁移并删除过渡
   fallback。

## 3. Non-Goals

- 不让 LLM 改写、摘要或补写 SourceUnit。
- 不重新定义 External Producer v3 的 family taxonomy。
- 不用 embedding、fuzzy matching 或股票/行业专用 hardcode 判断主体。
- 不删除 canonical cards、citations、source fingerprints 或 rejected diagnostics。
- 不在 renderer 或 report quality gate 中维护第二套元话语清洗规则。
- 不解决外部材料本身的事实可信度；所有内容仍为 Preview / display-only。

## 4. Options Considered

### 4.1 Validated projection inside SourceUnit metadata (selected)

Raw unit remains authoritative. A validated projection records the exact displayed substring and scope provenance.
Consumers use only validated metadata. This keeps one evidence owner and makes stale/invalid projection fail closed.

### 4.2 Separate display sidecar (rejected)

A sidecar would leave the core pack untouched, but creates a second unit identity/freshness owner and additional
path/config lifecycle. It is more likely to become stale than optional metadata in the canonical pack.

### 4.3 Rewrite SourceUnit and recompute hashes (rejected)

This is smaller code, but changes the quoted evidence, unit hash and citation identity. It weakens auditability and
forces an unnecessary evidence migration.

## 5. Data Contract

Each selected `evidence_unit` gains two validated, display-only objects. Existing fields are unchanged.

```json
{
  "schema_version": "curated_external_source_unit.v1",
  "unit_id": "external-unit:...",
  "text": "immutable raw source unit",
  "unit_hash": "sha256(raw text)",
  "display_projection": {
    "schema_version": "curated_external_display_span.v1",
    "status": "exact",
    "text": "exact contiguous substring",
    "start": 12,
    "end": 86,
    "reason": "leading_editorial_context_removed"
  },
  "scope_provenance": {
    "schema_version": "curated_external_scope_provenance.v1",
    "origin": "adjacent_target_context",
    "anchor_unit_id": "external-unit:..."
  }
}
```

### 5.1 Display span states

- `exact`: `raw_text[start:end] == text`; only this state is display-eligible.
- `unsafe`: no trustworthy projection exists. `text` is empty and offsets are `null`; the unit remains canonical
  but is hidden from report projection.

Allowed reasons are a closed vocabulary owned by the projection module:

- `raw_complete`
- `leading_editorial_context_removed`
- `leading_source_label_removed`
- `structural_noise_only`
- `tail_not_argument_complete`
- `ambiguous_boundary`
- `unsafe_anchor_context`

Offsets are zero-based, start-inclusive and end-exclusive Python string indices over the stored Unicode `text`.
Whitespace may be omitted only when it lies outside those recorded bounds; projected text is always reconstructed by
the literal `raw_text[start:end]` slice.

### 5.2 Scope provenance states

- `explicit_target`: display span or raw unit explicitly names the configured stock; `anchor_unit_id` is self.
- `adjacent_target_context`: inherited from a prior explicit target anchor in the same source; anchor ID is required.
- `peer_or_industry`: no proven target anchor; anchor ID is empty.

Card-level `entity_scope` remains the consumer-facing scope, but must be derivable from its units' provenance.

### 5.3 Pack projection version

The pack gains `display_projection_version: external_display_projection.v1`. This version tracks the deterministic
span/provenance contract independently. Producer-native scope admission does change, so canonical regeneration also
bumps the existing selector version. The reader validates both versions before exposing display text.

During Phase A, existing non-pilot reports may temporarily keep the current raw display path. A pilot pack is never
eligible for acceptance through that fallback: it must carry the projection version and report
`projection_status=ready`. The reader exposes `legacy_unprojected` distinctly so raw and projected output cannot be
mixed in one acceptance result. After all configured canonical packs pass migration gates, the fallback is deleted
and a missing version becomes `display_projection_missing` for the display path. Core pack validity remains
independent so data is never destroyed by projection failure.

## 6. Projection Algorithm

`curated_external_display_projection.py` is the only owner of span and scope projection.

### 6.1 Span generation

For each raw unit, generate deterministic candidates in source order:

1. Full raw text.
2. Suffix after the first structural separator (`：`, `:`, or a line boundary) only when the prefix is classified
   as editorial direction or source-label context.

The prefix classifier uses generic document-language patterns such as display instructions, table introductions,
source labels and navigation labels. It must not contain stock names, stock codes, product names or industry names.

A suffix is admitted only when all checks pass:

- it is a single contiguous substring of raw text;
- it contains a non-structural family signal already recognized by the canonical family resolver;
- it forms an argument-complete clause or sentence rather than a title fragment;
- it does not begin or end with truncation punctuation;
- it is not itself a source label, table header, navigation label or disclaimer.

Selection order is deterministic: clean full text first; otherwise the earliest safe suffix. No candidate is joined
with another substring. If none pass, status is `unsafe`.

### 6.2 Scope provenance

Units are processed by `(source_id, source_ordinal)`.

1. A unit explicitly naming the configured stock becomes `explicit_target`.
2. A following unit may become `adjacent_target_context` only when:
   - it has the same `source_id`;
   - its ordinal is within the next two source units;
   - the anchor is `explicit_target`;
   - it begins with a bounded continuation subject (`公司`, `其`, `该产品`, `上述产品`, `该平台`, `该中心`),
     or shares an exact named organization/product anchor with the explicit unit;
   - it does not introduce a different named company or an independent industry/market subject.
3. A new heading, structural label, different source, explicit peer company, independent subject or more than two
   units of distance ends inheritance.
4. Inherited scope is never transitive: an inherited unit cannot anchor another inherited unit.

Named shared anchors are exact phrases extracted by structural rules: quoted/bracketed names and phrases ending in
`中心/平台/产品/芯片/模块/系统/项目`. No fuzzy matching is allowed.

“Different named company” detection does not depend on a finite company-name suffix list. It reuses the producer's
generic named-subject/action grammar: when a continuation introduces a non-anchor subject before an action such as
`发布/推出/量产/交付/扩产/合作/收购`, inheritance stops. Relation phrases such as `竞争对手/同行/供应商/合作方`
also stop inheritance when followed by a non-anchor named subject. This specifically prevents a phrase such as
“其竞争对手英伟达发布……” from inheriting the target scope without adding company-specific tokens.

An inherited unit is display-eligible only when its explicit anchor also has an `exact` display projection and is
available earlier in the same projected scope group. Otherwise it remains canonical but is hidden as
`unsafe_anchor_context`; the report must not expose a dangling “其/该产品/该中心” clause.

### 6.3 Unsafe fallback

An unsafe unit:

- remains in the canonical card and citation graph;
- is counted in diagnostics;
- is excluded from display rows and topic-narrative prompt coverage;
- cannot be restored by memo, renderer or a fallback card path.

If a card contains both exact and unsafe units, only exact units are displayed and visible citations are rebuilt from
those units. If all units are unsafe, the card has no display row but remains in the pack.

The display copy derives `entity_scope` from exact visible unit provenance only. It may preserve or conservatively
downgrade the canonical scope, but may never elevate peer/industry material to target scope. A target display copy
therefore requires at least one visible `explicit_target` unit or a visible `adjacent_target_context` unit whose exact
anchor is also available earlier in the projected group. Existing family resolution is rerun over exact visible
text; a copy with no remaining family signal is hidden instead of borrowing a family from an unsafe unit.

Projection can run in two contexts through the same pure API:

- producer-native projection sees the complete newly materialized source-unit stream before admission;
- one-time migration projects only units already stored in a canonical pack.

Migration never invents a missing neighboring anchor. If an explicit anchor is absent from the stored pack, the
affected unit cannot inherit target scope and remains peer/industry or unsafe. Pilot diagnostics must make that loss
visible; there is no migration-only inference rule.

## 7. Integration

### 7.1 Producer

1. `materialize_external_source_units()` continues to create immutable raw units.
2. Projection runs once after materialization and before mandatory/optional admission.
3. `prepare_external_argument_material()` consumes scope provenance instead of recomputing scope from final text.
4. `_build_v3_card()` preserves projection objects without changing raw unit identity.
5. Pack diagnostics add exact/unsafe counts, rejection reasons and inherited-scope counts.

### 7.2 Validator and reader

The stored-card validator checks:

- exact span offsets and text reconstruction;
- closed status/reason vocabulary;
- no text/offset payload for `unsafe`;
- inherited target provenance has a same-source explicit anchor within the allowed ordinal distance;
- card scope agrees with unit provenance;
- display projection version is recognized.

Validation builds one pack-wide `(source_id, source_ordinal, unit_id)` index. Unit IDs must be unique across cards;
an inherited anchor must exist in that index, be earlier in the same source, be within distance two, be
`explicit_target`, and have an exact display projection. This is a pack invariant, not a card-local lookup.

Projection failure does not invalidate raw evidence. The reader returns core `status=ok` plus a separate projection
status. Display consumers fail closed when projection is missing or invalid.

### 7.3 Topic narrative memo

- The memo prompt includes only exact display spans.
- Unit ownership remains `(argument_key, unit_id)`; the memo does not own span or scope.
- The source fingerprint includes projection version, status, offsets and projected text, so a changed projection
  makes an old memo stale.
- Complete memo coverage is measured against display-eligible units, not all raw units.
- Quote validation uses the projected span as its source string. Existing “quote must be an exact complete prefix”
  semantics remain, but the prefix is taken from `display_projection.text`, not immutable raw `unit.text`; this is
  required for a safely selected suffix to participate without being rewritten.

### 7.4 Display, snapshot and renderer

- `curated_external_display` creates display-card copies. Each copy retains card/unit identity and immutable hashes,
  replaces only the copy's visible `text` with the exact span, drops unsafe units, and rebuilds card refs/source
  identity from the remaining units. Canonical cards in the pack are never mutated.
- The existing `_curated_external_argument_cards` display field contains those projected copies so downstream code
  has one card path; no consumer branches between raw and projected cards.
- `MaterialSnapshot` receives only display-card copies. Formal-thin citation numbering continues to allocate over
  the complete display snapshot in the existing order (annual, broker, external); hidden units allocate no visible
  reference and therefore cannot create unused refs or alter the offset formula.
- The renderer receives already-clean text and proven scope; it adds no cleaning or inheritance logic.
- Chapter 4.4 remains row-only, consumes the same projected rows, and does not read memo or hidden units.

## 8. Migration and Rollout

### Phase A: Pure projection and pilot

1. Add pure projection contracts and tests.
2. Keep a temporary raw fallback only for non-pilot legacy reports; mark it `legacy_unprojected`.
3. Produce `/tmp` pilot packs for 中际旭创、复旦微电、黑芝麻智能 without changing canonical files.
4. Generate fresh no-PDF reports through temporary config.

Pilot gates:

- all exact spans reconstruct from raw offsets;
- no unsafe unit leaks to report or memo;
- every inherited target unit has a valid explicit anchor;
- no target facts newly move to peer scope;
- raw unit/hash/citation/source fingerprints are unchanged;
- displayed external-unit count decline is reported by stock and family;
- quality/source/prose/CI gates pass;
- representative paragraphs receive user confirmation.

Coverage stop gates are deterministic: stop for review when any previously visible target card becomes fully hidden,
any previously populated target family becomes empty, or more than 20% of pilot evidence units are unsafe. These are
review triggers rather than permanent display caps; accepted high-quality content remains uncapped.

### Phase B: Canonical cutover

1. Rebuild all configured canonical argument packs from their local source packets under the bumped selector version;
   do not treat metadata-only migration of old selected cards as canonical regeneration.
2. Verify every configured pack reports recognized projection version.
3. Remove the temporary raw fallback and fixtures.
4. Re-run formal-medium, formal-thin-external-rich and 港股 report fixtures.

No long-lived dual reader or sidecar remains after Phase B.

## 9. Required Tests

### Pure span tests

- clean factual unit uses full-range exact span;
- generic editorial prefix plus complete factual tail selects the exact suffix;
- source label with no provably complete tail becomes unsafe;
- offset mismatch, non-contiguous text and ellipsis ending are rejected;
- no stock/industry-specific token appears in the projection rules.

### Scope tests

- explicit stock mention produces self-anchored target provenance;
- same-source adjacent pronoun or exact shared organization inherits target;
- a different named company, independent industry subject, heading or distance >2 blocks inheritance;
- inherited units cannot act as transitive anchors;
- A-share and HK stock fixtures use the same rules.

### Pack/reader tests

- raw text/hash/citation identity remains unchanged after projection;
- mixed exact/unsafe cards expose only exact refs;
- mixed cards derive display scope/family only from exact units and never inherit them from hidden units;
- display-card copies rebuild refs/source identity and never mutate canonical cards;
- invalid projection fails closed without invalidating core evidence;
- pilot packs cannot pass through `legacy_unprojected` raw fallback;
- duplicate unit IDs and missing/non-exact inherited anchors are rejected pack-wide;
- memo fingerprint changes when projection changes;
- old memo cannot restore hidden unsafe units.

### Report tests

- no unsafe text appears in 4.3;
- target/peer rendering follows provenance;
- formal-thin citation offset remains correct;
- 4.4 remains isolated;
- all visible refs are defined and no unused/malformed refs appear.

## 10. Failure Modes

| Failure | User-visible symptom | Detection | Response |
| --- | --- | --- | --- |
| Span is not exact | displayed wording cannot be traced to source | offset reconstruction test/reader | projection invalid; hide unit |
| Meta prefix falsely removed | fact begins mid-clause | argument-complete tests and pilot excerpts | mark unsafe; do not display |
| Useful noisy unit hidden | display coverage drops | per-stock/family diagnostics | stop pilot if unexplained/material |
| Scope inheritance crosses source | peer fact shown as target | provenance validator | reject inherited scope |
| New company introduced | wrong target binding | named-company break tests | classify peer/industry |
| Projection changes without memo refresh | stale narrative text | projection-aware fingerprint | reject memo as stale |
| Mixed card leaks unsafe refs | citation points to hidden text | visible-ref subset tests | rebuild refs from exact units |
| Hidden anchor leaves a dangling pronoun | paragraph starts with “其/该产品” without target context | anchor-display invariant | hide inherited unit |
| Pilot silently uses legacy raw text | false-positive acceptance | explicit projection status assertion | reject pilot run |
| Old pack silently bypasses projection | meta noise persists after cutover | projection-version gate | Phase B cannot complete |

## 11. Scope and Budget

Expected runtime files:

- new `scripts/utils/curated_external_display_projection.py`
- `scripts/utils/curated_external_argument_cards.py`
- `scripts/utils/curated_external_full_body_viewpoint_claims.py`
- `scripts/utils/curated_external_topic_narrative.py`
- `scripts/utils/curated_external_display.py`
- `scripts/utils/deep_analysis_material_snapshot.py`
- one preview/migration entry under `scripts/previews/`

No renderer change is expected. `report_quality.py` changes only if a new fail-closed projection error needs a report
gate; it must not duplicate projection rules.

Runtime target is net `+160` lines, hard stop `+220`. Implementation must replace existing scope derivation and raw
display branches rather than layer a second selector. Exceeding the hard stop returns to design review.

## 12. Stop Conditions

- A span cannot be proven by exact offsets.
- Scope inheritance needs fuzzy matching, embeddings or stock/industry hardcode.
- Core unit text/hash/citation identity changes.
- Display coverage drops materially without an explicit unsafe reason.
- Any low-credit external fact enters scoring, target, risk or official-confirmation sections.
- Formal-thin citation offset, 4.4 isolation or existing quality gates regress.
- Phase B would require an indefinite compatibility branch.
- Runtime net increase exceeds `+220` lines.

## 13. Acceptance

The batch is complete only when all three pilot stocks and all configured canonical packs pass projection validation,
fresh report gates and user review; the temporary raw fallback is then removed. A green unit test suite without the
pilot/cutover evidence is not sufficient.

## 14. Self-Review Delta

- Accepted: separated core pack validity from display projection validity so evidence is retained while display
  fails closed.
- Accepted: made pilot status explicit; a legacy raw fallback can no longer masquerade as projected output.
- Accepted: changed downstream integration to projected card copies, closing the current snapshot raw-text leak.
- Accepted: bound memo quote validation to the exact span and included projection metadata in freshness.
- Accepted: required a visible exact anchor for inherited clauses and a pack-wide provenance index.
- Rejected: a display sidecar and renderer cleaning because both create a second evidence/text owner.
- Deferred: external source-credit improvement and LLM summarization quality; neither belongs to deterministic
  source-unit hygiene.
- External Round 1 review required: yes. This changes citation-bearing display projection and producer/reader/memo
  coordination across more than three runtime files, so repository Level 3 review remains mandatory before planning.
