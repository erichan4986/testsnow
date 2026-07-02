# 2026-07-02 Peer Comparison Material Layer — Phase 3b Claude Task

## Goal

Implement the deterministic peer comparison material pack and quality gates, without changing LLM prompts or report prose generation.

Phase 3a is already committed:

- config-backed peers are wired through `run_stock_report.py -> PerStockReporter -> pipeline_input -> data_skills -> data_fetcher -> valuation_renderer`;
- `scripts/utils/reporter/peer_config.py` exists;
- Fudan Microelectronics has `industry`, `competitors`, `peer_codes`, and `peer_dimensions` in `config/stocks.json`;
- existing fallback to `COMPETITOR_MAP` still works.

This task is Phase 3b only.

## Scope

Allowed to modify/create:

- Create `scripts/utils/peer_comparison_material.py`
- Modify `scripts/utils/report_skills/synthesis_skills.py`
- Modify `scripts/utils/report_skills/assembly_skills.py`
- Modify `scripts/utils/report_quality.py`
- Add/update focused tests:
  - `tests/utils/test_peer_comparison_material.py`
  - `tests/reporter/test_assembly_skills.py`
  - `tests/reporter/test_report_quality.py`
  - small existing config/fetcher tests only if necessary

Do not modify:

- `scripts/utils/knowledge_synthesizer.py`
- any LLM prompt text
- deep analysis renderer behavior
- scoring/risk/technical algorithms
- Xueqiu/Chrome/CDP/Playwright/fetcher code
- generated `reports/*.md` by hand

Natural report output from a smoke run is allowed, but do not hand-edit it.

## Required Behavior

### 1. Peer material builder

Create `scripts/utils/peer_comparison_material.py`.

Public functions:

```python
def build_peer_comparison_material(
    stock_name: str,
    competitor_metrics: dict | None = None,
    source_items: list[dict] | None = None,
    stock_config: dict | None = None,
) -> dict:
    ...


def filter_peer_rows_for_prompt(material: dict) -> dict:
    ...
```

Output schema:

```json
{
  "schema": "peer_comparison_material.v1",
  "target": "复旦微电",
  "peers": ["紫光国微", "安路科技"],
  "rows": [
    {
      "dimension": "盈利能力",
      "target": "复旦微电",
      "peer": "紫光国微",
      "metric": "gross_margin",
      "target_value": 60.0,
      "peer_value": 65.0,
      "period": "latest",
      "unit": "%",
      "comparison": "毛利率低于紫光国微",
      "source_refs": ["指标:competitor_metrics:gross_margin"],
      "confidence": 0.85,
      "usage": "claim_eligible"
    }
  ],
  "warnings": []
}
```

Rules:

- Build rows from deterministic `competitor_metrics` first.
- At minimum support:
  - profitability: `gross_margin`
  - valuation: `pe_ttm`, `forward_pe`, `ps`
  - market cap: `mcap`
- Do not invent values. Missing target or peer value means no comparable metric row.
- Keep row count compact:
  - max 2 peers per metric;
  - max 8 total metric rows.
- Social/display-only sources must not enter this material pack.
- Source refs must use only allowed prefixes:
  - `公告:`
  - `年报:`
  - `研报:`
  - `指标:`
  - `行业研报:`
  - `行业资讯:`
  - `iwencai:`

### 2. Confidence formula

Implement deterministic confidence.

Base score:

- `0.85`: target and peer have the same metric, same period, same unit, from `competitor_metrics`.
- `0.75`: same metric, but one side is deterministic metrics and one side is a formal source row.
- `0.60`: formal/professional source mentions target and peer in the same dimension, but no comparable numeric metric exists.
- `0.40`: only title/snippet mentions the peer or dimension. This is audit/context only.
- no row: one side absent, social-only source, or comparison needs an inferred metric not present in input.

Adjustments:

- `-0.15` if periods differ.
- `-0.15` if units differ or cannot be normalized.
- `-0.10` if one source is mainstream industry news rather than announcement/broker research/deterministic metric.
- cap at `0.95`.
- floor at `0.0`.

Usage tiers:

- `confidence >= 0.70`: `usage="claim_eligible"`
- `0.50 <= confidence < 0.70`: `usage="context_only"`
- `confidence < 0.50`: `usage="audit_only"`

### 3. Prompt hard-filter helper, but no prompt integration

Implement `filter_peer_rows_for_prompt(material)`.

It should:

- drop rows with `confidence < 0.50`;
- for rows with `0.50 <= confidence < 0.70`, remove:
  - `comparison`
  - `target_value`
  - `peer_value`
  - numeric spread fields if any
- keep high-confidence rows unchanged.

Do not call this helper from `KnowledgeSynthesizer` in Phase 3b. It is for tests and Phase 3c.

### 4. Pipeline context + sidecar persistence

In `synthesis_skills.py`, after baseline source-intake material preparation has access to ctx, build the peer material from:

- `ctx.get("stock_name")`
- `ctx.get("competitor_metrics")`
- formal/canonical source-intake items already available in synthesis context, if easy to access
- `ctx.get("stock_config")`

Set:

```python
ctx.set("peer_comparison_material", material)
```

If no rows are produced, still set a valid material dict with empty `rows`.

In `assembly_skills.py`, persist non-empty material sidecar:

```text
reports/<stock>_<date>_peer_comparison_material.json
```

Only persist when `rows` is non-empty.

Set:

```python
ctx.set("peer_comparison_material_path", str(path))
```

Mirror the style of `_persist_industry_relevance_manifest`.

### 5. Quality gates

Modify `report_quality.py`.

Add auto-load sidecar:

```text
<report_stem>_peer_comparison_material.json
```

Extend `check_report_text(..., peer_comparison_material=None)`.

Add checks:

#### `peer_pack_social_leak`

Severity: error.

Trigger if peer material rows contain any source ref prefix:

- `雪球:`
- `知乎:`
- `微信:`
- `精选外部:`
- `社区:`

Allowed prefixes are the formal/professional prefixes listed above.

#### `unsupported_peer_superlative`

Severity: error.

Check only 4.1/4.2 text.

Strong terms:

- `行业第一`
- `唯一`
- `全面领先`
- `显著优于`
- `远强于`
- `优于`
- `领先`
- `远超`
- `全面占优`
- `更具优势`

Trigger when strong comparison wording appears but peer material has no row with:

- `confidence >= 0.70`
- non-empty `source_refs`

#### `peer_claim_without_peer_pack`

Severity: warning.

Check only 4.1/4.2 text.

Weak terms:

- `对标`
- `差距`
- `落后于`
- `不及`
- `接近`
- `略高于`
- `略低于`
- `窄于`
- `好于`
- `弱于`
- `行业平均`
- `同行平均`

Trigger when weak peer comparison wording appears but peer material is missing or has zero rows.

Important:

- Do not scan 4.4.
- Do not scan the source list.
- Avoid flagging generic headings like `竞争格局` by itself.

## Tests

Use TDD. Add failing tests first.

### `tests/utils/test_peer_comparison_material.py`

Required tests:

1. Builds high-confidence metric rows from `competitor_metrics`.
2. Drops rows when target value or peer value is missing.
3. Assigns usage tiers for 0.85 / 0.60 / 0.40 style cases.
4. Drops social source refs.
5. `filter_peer_rows_for_prompt()` removes low-confidence rows and strips comparison/numbers from context-only rows.

### `tests/reporter/test_assembly_skills.py`

Required test:

- writes `*_peer_comparison_material.json` sidecar when ctx contains rows;
- does not write when rows are empty.

### `tests/reporter/test_report_quality.py`

Required tests:

1. auto-loads peer material sidecar from report path;
2. flags `peer_pack_social_leak`;
3. flags strong unsupported comparison terms in 4.1/4.2;
4. warns on weak peer comparison without sidecar;
5. does not flag 4.4 display-only peer language;
6. high-confidence sidecar suppresses unsupported strong comparison error.

## Verification Commands

Run:

```bash
PYTHONPATH=/Users/erichan/testsnow/scripts:/Users/erichan/testsnow/scripts/utils python3 -m pytest tests/utils/test_peer_comparison_material.py tests/reporter/test_assembly_skills.py tests/reporter/test_report_quality.py -q
PYTHONPATH=/Users/erichan/testsnow/scripts:/Users/erichan/testsnow/scripts/utils python3 -m pytest tests/reporter/test_peer_config.py tests/reporter/test_data_fetcher_peers.py tests/reporter/test_data_skills.py tests/reporter/test_valuation_renderer.py tests/reporter/test_stock_reporter_source_intake_config.py -q
bash tools/ci_grep_gates.sh
git diff --check
```

Optional smoke only if the focused tests pass and time allows:

```bash
set -a; . ./.env; set +a
python3 scripts/run_stock_report.py --stock 复旦微电 --no-pdf
python3 scripts/check_report_quality.py reports/复旦微电_20260702.md
```

Do not run Xueqiu/CDP/Chrome.

## Stop Conditions

Stop and report instead of expanding scope if:

- implementation requires editing `KnowledgeSynthesizer` prompt;
- peer material needs social sources to pass tests;
- quality gate causes broad false positives in unrelated existing tests;
- you need to add new external data fetching;
- you need to change scoring/risk/technical code.

## Completion Report Format

After implementation, write notes to:

```text
docs/agent_workflow/2026-07-02-peer-comparison-material-layer-phase3b-claude-notes.md
```

Include:

- files changed;
- requirement-test matrix;
- test commands and exact results;
- whether sidecar is generated in any smoke;
- blocker/warning/deviation;
- final `git status --short`.
