# Curated External Full-Body Viewpoint Design Delta

Date: 2026-06-29

Status: accepted implementation delta after Phase 2.8 / Phase 2.9 validation

## 1. Why This Delta Exists

The original long-term synthesis plan proposed:

```text
source -> evidence cards + excerpt packs -> topic buckets -> claim candidates -> cited narrative
```

That direction remains correct, but the curated-external implementation found
that short evidence cards were too lossy for WeChat / industry-media longform
articles.  The useful information was often not a new fact, but an external
interpretation of an already-known fact: operating-quality signals, timing
risks, strategic tradeoffs, or downstream/upstream verification variables.

The primary curated-external path is therefore revised to:

```text
full-body source packet
  -> LLM multipass viewpoint extraction
  -> quote/hash fidelity validation
  -> novelty guard with interpretive-claim allowance
  -> semantic near-duplicate merge
  -> validated viewpoint digest
  -> LLM narrative composer
  -> cited 4.4 display-only narrative
```

Evidence cards remain useful as preview/audit material and as a fallback, but
they are no longer the preferred primary material layer for external longform
viewpoints.

## 2. What Stays From The Original Design

The source boundary is unchanged:

- no Knowledge write;
- no core fact upgrade;
- no scoring, risk scoring, EV, target price, or final recommendation impact;
- no use of raw discovery JSONL directly in report generation;
- no Xueqiu detail scraping, Chrome/CDP, Playwright, or new crawler behavior;
- curated external material only enters `ctx["deep_analysis_display"]`.

The citation and safety gates also remain mandatory:

- every displayed claim must resolve to a source packet;
- `source_quote` must be a normalized substring of the referenced source;
- quote hash and source block hash must match;
- display-only flags must remain false for Knowledge/scoring/risk eligibility;
- final rendered text must pass citation-aware overclaim lint.

## 3. Revised Claim Semantics

The earlier novelty guard was too strict: if a source quote contained a
baseline fact such as revenue, loss, or fundraising amount, the whole claim
could be dropped even when the actual claim added interpretation.

The revised rule is:

- pure repeated baseline facts are still rejected;
- explicit `baseline_overlap == "duplicate"` is still rejected;
- if the repeated fact appears only inside `source_quote`, and the claim text /
  `why_incremental` clearly adds interpretation, the claim may pass.

Additional allowed claim types:

- `business_quality_signal`
- `interpretive_frame`
- `strategic_tradeoff`

These types are still display-only observations, not fact confirmations.

## 4. Semantic Near-Duplicate Merge

Full-body extraction intentionally asks for more candidate viewpoints.  This
improves recall, but creates repeated variants of the same external argument.

The digest now performs a conservative semantic merge after exact quote-hash
dedupe:

- merge only within the same source;
- merge only when keyword buckets match a known near-duplicate theme;
- keep the more informative claim;
- preserve distinct subthemes inside the same broad area.

For example:

- merge repeated "费用收缩 / 节衣缩食 / 投入收缩" claims;
- keep "具身智能商业化周期" separate from "具身智能竞争与资源分散";
- keep "A2000 审查通过" separate from "A2000 高阶窗口滞后".

## 5. Current Implementation State

Implemented and validated:

- full-body source packet preview CLI;
- LLM multipass extractor with API retry and failed-pass stats;
- quote repair / quote hash / source hash validation;
- deterministic baseline fact fingerprint;
- interpretive-claim novelty allowance;
- semantic near-duplicate merge;
- viewpoint digest JSON / Markdown preview;
- narrative composer JSON / Markdown preview;
- cached narrative display in report `### 4.4 精选外部观察（Preview）`;
- `DeepAnalysisRenderer` rendering as paragraph narrative with local citations;
- CI gate protecting scoring/risk/Knowledge from curated external tokens.

Validated report samples:

- 中际旭创: external 4.4 adds supply-chain, 800G, NPO/XPO/CPO, and demand-cycle
  variables while keeping display-only isolation.
- 黑芝麻智能: external 4.4 adds operating-quality, benchmark-model conversion,
  high-end chip timing, embodied-AI tradeoff, and fundraising-allocation
  viewpoints without repeating 4.1-4.3 financial facts.

## 6. What Is Still Not Done

This is not a full canonical synthesis rewrite.

Still unchanged:

- 4.1-4.3 continue to use the existing canonical synthesis path;
- `KnowledgeSynthesizer` prompt and core fact extraction are not changed by
  this delta;
- official / high-credit fact upgrade remains future work;
- curated external claims are not used in scoring, risk, target price, or final
  recommendation.

Open work:

- broaden full-body source availability for stocks with weak WeChat longform
  coverage;
- reduce repeated source references in the rendered citation list where the
  same article supports multiple claims;
- define a follow-up plan for whether Zhihu / broker research should migrate to
  the same source-packet -> digest -> narrative interface;
- decide whether 4.4 should remain per-stock opt-in or gain a quality-gated
  automatic enablement path.

## 7. Implementation Boundary Going Forward

Future changes should keep the layers separate:

- **Extraction layer**: source packets, LLM multipass extraction, quote/hash
  validation, novelty/duplicate gates.
- **Digest layer**: claim schema, semantic dedupe, stats, preview Markdown.
- **Narrative layer**: LLM paragraph composer, paragraph claim refs, citations,
  overclaim lint.
- **Report layer**: cached JSON loading and display-only `deep_analysis_display`
  rendering.

Do not put raw WeChat text directly into the report renderer or canonical
synthesis prompt.  Do not let display-only materials bypass the digest and
narrative gates.
