# 2026-07-02 Peer Comparison Material Layer Design

## Background

The Fudan Microelectronics trial exposed a recurring gap in 4.1/4.2:

- reports can describe the industry cycle, company products, and valuation debate;
- but peer comparison remains shallow or hard-coded;
- conclusions such as "industry enters a dividend cycle, this stock has opportunity" need a closed loop:
  industry trend -> peer/industry benchmark -> company exposure -> relative strength/weakness -> watch variable.

This must be fixed at the pipeline level, not by rewriting one report.

## Scope

This is Batch 3 after Batch 2b industry-news relevance classification.

In scope:

1. Move peer identity from hard-coded maps toward `config/stocks.json`.
2. Build a deterministic peer material layer from existing formal/professional materials.
3. Feed peer comparison into 4.1/4.2 only.
4. Add quality gates for unsupported peer/superlative claims.

Out of scope:

1. No autonomous peer research agent.
2. No new broad `peer_source_queries` field in this batch.
3. No social-media peer claims in 4.1-4.3.
4. No new Xueqiu/Chrome/CDP/Playwright behavior.
5. No LLM-only peer conclusion without source-backed rows.

## Design Principles

### Formal-First Boundary

Peer comparison used by 4.1/4.2 must come from:

- company announcements and annual reports;
- broker research;
- iwencai industry research already collected by source intake;
- mainstream industry news only when classified as relevant to 4.1;
- deterministic market/financial metrics already fetched by `data_fetcher`.

Social sources may still discuss peers in 4.4 display-only, but must not support core peer claims in 4.1-4.3.

### No Query Explosion

Batch 3 should not add a field like `peer_source_queries` that asks future agents to go search the internet.

Instead, it should derive peer terms from:

- `competitors`;
- `peer_codes`;
- existing stock keywords;
- existing source-intake materials already fetched for the target stock.

If future work needs a peer research agent, it should be designed separately with its own rate limits, cache policy, and quality gates.

## Config Shape

Add stock-level fields:

```json
{
  "industry": "集成电路设计 / FPGA / MCU / 非易失存储",
  "competitors": ["紫光国微", "安路科技", "兆易创新", "普冉股份", "聚辰股份"],
  "peer_codes": {
    "紫光国微": "002049",
    "安路科技": "688107",
    "兆易创新": "603986",
    "普冉股份": "688766",
    "聚辰股份": "688123"
  },
  "peer_dimensions": [
    "盈利能力",
    "估值水平",
    "产品线重叠",
    "毛利率与研发投入",
    "行业景气暴露"
  ]
}
```

Rules:

- `competitors` is the canonical display order.
- `peer_codes` is optional but recommended. If missing, existing `stock_codes` and constants remain fallback.
- `peer_dimensions` is optional and only constrains summaries; it must not create unsupported facts.
- Existing `COMPETITOR_MAP` / `COMPETITOR_CODES` remain fallback during migration.

## Data Flow

### Step 1: Peer Identity

Create a helper:

`scripts/utils/reporter/peer_config.py`

Responsibilities:

- `get_peer_names(stock_name, stock_config=None)`;
- `get_peer_codes(stock_name, stock_codes, stock_config=None)`;
- preserve fallback to current constants;
- normalize duplicates and remove target stock itself.

### Step 2: Peer Metrics

Update:

`scripts/utils/reporter/data_fetcher.py`

`fetch_competitor_metrics()` should prefer config peers and peer codes.

It should still return the same shape currently consumed by renderers/charts.

No scoring formula changes in this batch.

### Step 3: Peer Material Pack

Add:

`scripts/utils/peer_comparison_material.py`

Input:

- target stock name;
- `competitor_metrics`;
- source-intake items and formal display items;
- stock config peer metadata.

Output:

```json
{
  "schema": "peer_comparison_material.v1",
  "target": "复旦微电",
  "peers": ["紫光国微", "安路科技"],
  "rows": [
    {
      "dimension": "盈利能力",
      "target_observation": "2025净利同比承压",
      "peer_observation": "紫光国微盈利规模更高",
      "comparison": "弱于核心军工IC同行",
      "source_refs": ["公告:复旦微电2025年报", "指标:competitor_metrics"],
      "confidence": 0.8
    }
  ],
  "warnings": []
}
```

Rules:

- It may extract simple numeric comparisons from metrics.
- It may use formal source titles/snippets when they mention a peer.
- It must not invent peer metrics absent from input.
- It must mark rows as `low_confidence` when the peer basis is only a title/snippet.
- It should output no row rather than weak filler.

### Peer Row Confidence Formula

`rows[].confidence` is deterministic, not LLM-assigned.

Base score:

- `0.85`: target and peer both have the same metric, same period, same unit, and the same deterministic source family such as `competitor_metrics`.
- `0.75`: target and peer both have the same metric, but one side comes from a formal source row while the other comes from deterministic metrics. The row may support cautious relative wording.
- `0.60`: formal source refs mention both target and peer in the same dimension, but no fully comparable numeric metric exists.
- `0.40`: only a formal title/snippet mentions the peer or dimension. This is context only.
- no score / no row: one side is absent, source family is social-only, or the comparison needs an inferred metric not present in input.

Adjustments:

- `-0.15` if periods differ.
- `-0.15` if units differ or cannot be normalized.
- `-0.10` if one source is mainstream industry news rather than announcement / broker research / deterministic metric.
- cap at `0.95`.
- floor at `0.0`.

Thresholds:

- `>= 0.70`: eligible for 4.1/4.2 as a usable peer comparison row.
- `0.50 <= confidence < 0.70`: context-only row; may be included in sidecar, but not in prompt as a comparison claim.
- `< 0.50`: sidecar audit only or omitted; never shown to LLM.

### Step 4: Synthesis Integration

Pass peer pack as a guarded appendix to `KnowledgeSynthesizer` for:

- `industry_logic` / final 4.1;
- `fundamentals` and `valuation_debate` / final 4.2.

Do not pass it to:

- `funding_sentiment`;
- `events_catalysts`;
- 4.4 narrative composer;
- scoring/risk engine.

Prompt rule:

- peer pack may support "优于/弱于/接近同行" only when the relevant row has source refs and confidence >= 0.7;
- low-confidence rows must be written as "可作为后续对比线索" or omitted.

Input hard filter:

- before building 4.1/4.2 prompt appendices, rows with `confidence < 0.50` are removed;
- rows with `0.50 <= confidence < 0.70` are reduced to dimension labels and source labels only, with no comparison wording or numeric spread;
- only rows with `confidence >= 0.70` may include `comparison`, target metric, peer metric, and relative conclusion;
- this filtering happens before LLM prompt construction, not as an instruction inside the prompt.

### Step 5: Rendering

Do not add a new major report section.

4.1 may include a compact "同行对比" table if at least two peer rows exist.

4.2 may reference peer valuation/profitability only when the peer pack includes valuation/profit rows.

Avoid table bloat:

- max 4 peer rows in 4.1;
- max 3 peer rows in 4.2;
- no nested headings;
- use inline bold labels rather than extra `####` subheadings.

## Quality Gates

Add deterministic checks in `report_quality.py` or `report_prose_quality.py`:

1. `unsupported_peer_superlative`
   - Trigger when 4.1/4.2 contains strong comparison terms without peer pack source support.
   - Strong terms include: "行业第一", "唯一", "全面领先", "显著优于", "远强于", "优于", "领先", "远超", "全面占优", "更具优势".
2. `peer_claim_without_peer_pack`
   - Trigger when 4.1/4.2 contains peer comparison wording but no peer pack sidecar exists.
   - Weak comparison terms include: "对标", "差距", "落后于", "不及", "接近", "略高于", "略低于", "窄于", "好于", "弱于", "行业平均", "同行平均".
3. `peer_pack_social_leak`
   - Peer pack source refs must not contain Xueqiu/Zhihu/WeChat/social-only labels for 4.1-4.3.
   - Allowed `source_refs` prefixes: `公告:`, `年报:`, `研报:`, `指标:`, `行业研报:`, `行业资讯:`, `iwencai:`.
   - Any `雪球:`, `知乎:`, `微信:`, `精选外部:` ref is an error for peer pack rows feeding 4.1/4.2.

Sidecar:

`reports/<stock>_<date>_peer_comparison_material.json`

The quality checker should auto-load this sidecar like the industry relevance manifest.

## Failure Modes

### Wrong Peer Set

Symptom:

- report compares Fudan Microelectronics with unrelated analog-chip companies.

Prevention:

- config-driven `competitors`;
- test stock-specific peer list;
- fallback only when config is absent.
- Phase 3a is releasable only when one config-backed stock and one fallback stock both pass peer lookup tests.

### Social Leakage

Symptom:

- 4.1 says "雪球观点认为紫光国微更强".

Prevention:

- peer pack only accepts formal/professional/canonical items;
- source-boundary test covers social labels.

### Unsupported Superlative

Symptom:

- report says "国内唯一/行业第一" without official or high-credit source.

Prevention:

- quality gate for peer/superlative language;
- prompt restricts superlatives to high-confidence rows.

### Table Bloat

Symptom:

- 4.1 becomes a giant peer table and loses narrative.

Prevention:

- row caps;
- prose quality checks;
- topic ownership rules remain active.
- 4.1 peer table is qualitative positioning only. It must not duplicate the numeric `competitor_metrics_table` already rendered in valuation/financial snapshot.
- Numeric valuation/profitability comparison stays in the existing valuation table unless 4.2 needs a one-sentence interpretation.

### Stale Metrics

Symptom:

- peer valuation uses old quote while target quote is current.

Prevention:

- mark metric timestamp/source in peer pack;
- do not compare if metric missing or stale/conflicting.

## Tests

Focused tests:

- `tests/reporter/test_peer_config.py`
  - config peers override constants;
  - fallback constants still work.
- `tests/reporter/test_data_fetcher_peers.py`
  - `fetch_competitor_metrics` uses config peer codes.
  - `competitor_metrics_table` uses the same peer order for config-backed and fallback stocks.
- `tests/utils/test_peer_comparison_material.py`
  - builds rows from metrics;
  - drops social sources;
  - marks low-confidence rows.
  - confidence formula handles same-metric/same-period, mixed-source, title-only, and missing-side cases.
- `tests/utils/test_knowledge_synthesizer.py`
  - peer appendix appears only in 4.1/4.2 prompts;
  - not in 4.3 prompts.
  - rows below `0.50` are not present in prompts;
  - rows `0.50-0.70` are present only as context labels without comparison claims.
- `tests/reporter/test_report_quality.py`
  - unsupported peer superlative is error;
  - weak peer comparison without sidecar is warning/error according to term strength;
  - peer sidecar allows supported relative claims.
  - social ref prefixes in peer sidecar are errors.

Validation:

- focused tests;
- `check_report_quality.py`;
- `check_report_prose_quality.py`;
- `check_report_source_boundary.py`;
- `ci_grep_gates.sh`;
- `git diff --check`;
- one Fudan formal report rerun.

## Implementation Phases

### Phase 3a: Config Migration + Metrics

- add peer config helper;
- migrate Fudan config;
- update data_fetcher peer lookup;
- tests only, no new LLM behavior;
- prove fallback for at least one existing hard-coded stock, such as 圣邦股份 or 中际旭创.

### Phase 3b: Peer Material Pack

- build deterministic peer pack;
- implement the confidence formula above;
- persist sidecar;
- add quality gates;
- still no prompt changes until tests prove pack shape.

### Phase 3c: Synthesis Prompt Integration

- pass peer pack appendix to 4.1/4.2 only;
- apply confidence hard filtering before prompt construction;
- run Fudan report;
- inspect whether 4.1/4.2 now form a coherent peer comparison without over-table formatting;
- run Zhongji or Shengbang regression to ensure existing competitor table behavior does not drift.

## Stop Conditions

Stop and redesign if:

- implementation needs new external crawling/query fields;
- peer pack requires social sources for 4.1-4.3;
- `fetch_competitor_metrics` needs scoring changes;
- report output becomes dominated by peer tables;
- quality gate causes false positives on existing Zhongji/Shengbang reports.
