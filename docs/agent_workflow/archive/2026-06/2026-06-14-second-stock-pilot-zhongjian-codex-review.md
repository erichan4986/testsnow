# Second Stock Pilot: 中简科技 Claim Risk Bridge

Date: 2026-06-14

## Scope

Use 中简科技 as a second-stock pilot for the claim verification / structured risk signal path.

Non-goals:

- no Xueqiu detail fetch
- no Chrome/CDP
- no external Agent-Reach search
- no report pipeline changes
- no config persistence for 中简科技 yet

## Local Material Inventory

Existing local files:

- `knowledge/10-Stocks/中简科技/20260526-公司公告.md`
- `knowledge/10-Stocks/中简科技/20260526-技术指标.md`
- `knowledge/10-Stocks/中简科技/20260526-深度分析.md`
- `knowledge/10-Stocks/中简科技/20260612-公司公告.md`
- `knowledge/10-Stocks/中简科技/20260612-技术指标.md`
- `knowledge/10-Stocks/中简科技/20260612-深度分析.md`
- `knowledge/10-Stocks/中简科技/posts/*.md`

No local `data/raw/xueqiu_data_*_中简科技.json` was found.

## Implementation

Codex extended the local cached-community claim smoke script so it can read Markdown posts from a knowledge `posts/` directory:

- `scripts/smoke_cached_community_claims.py`
  - new `load_markdown_posts(posts_dir)`
  - new `--posts-dir`
  - if `--posts-dir` is provided, the script reads local Markdown posts instead of `data/raw/xueqiu_data_*`
- `tests/reporter/test_cached_community_claim_smoke_script.py`
  - coverage for Markdown post loading
  - coverage that `posts_dir` takes precedence over raw JSON loading

Codex generated a low-credit claim note from local posts:

- `knowledge/10-Stocks/中简科技/20260614-雪球缓存社区claims.md`
- `claim_count=6`
- source: `knowledge/10-Stocks/中简科技/posts`
- no external network

Codex added a local high-credit evidence note from existing confirmed local notes:

- `knowledge/10-Stocks/中简科技/evidence/20260614-local-confirmed-facts.md`
- `source_credit=85`
- source files:
  - `20260526-公司公告.md`
  - `20260526-技术指标.md`
  - `20260526-深度分析.md`
- this does not promote the `posts/` community notes to high credit

Codex also expanded conservative risk phrase coverage:

- `收入.*下降`
- `营收.*下降`
- `需求量.*减少`
- `发货.*减少`

These map to `业绩预期下调`. Positive revenue phrases such as `收入增长` and `营收增长` remain excluded by tests.

## Verification

Focused tests:

```bash
python3 -m pytest tests/reporter/test_cached_community_claim_smoke_script.py tests/utils/test_community_claim_note_writer.py -q
# 13 passed

python3 -m pytest tests/utils/test_claim_risk_signals.py -q
# 76 passed

python3 -m pytest tests/reporter/test_agent_reach_claim_bridge_smoke_script.py tests/reporter/test_cached_community_claim_smoke_script.py tests/utils/test_community_claim_note_writer.py tests/utils/test_claim_verification.py tests/utils/test_claim_risk_signals.py tests/reporter/test_claim_risk_signal_skill.py -q
# 149 passed
```

Lightweight bridge smoke:

```bash
python3 scripts/smoke_agent_reach_claim_bridge.py --stock 中简科技 --json
```

Result:

- Agent-Reach enabled: `false`
- fetch status: `disabled`
- high-credit claims: 6
- low-credit claims: 12
- verifications: 12
- skipped files: 5
- structured risk signals: 2

Structured risk observations:

```text
业绩预期下调 | claim_verification | unverified | 0
盈利压力     | claim_verification | unverified | 0
```

Evidence snippets:

- `客户对公司部分产品的需求量阶段性减少导致发货暂时减少，其中收入下降约50%-60%`
- `公司持续加大研发投入，研发费用同比增长约175%-185%`

## Interpretation

The second-stock pilot confirms:

- the low-credit claim pool can be created from local Markdown posts, not only raw JSON cache
- claim verification can run with local high/low material
- structured risk observations work for a different risk profile than Black Sesame
- unverified community claims remain non-scoring

Current limitation:

- 中简科技 does not yet have Agent-Reach official source config
- 中简科技 does not yet have a single-stock deep report entry equivalent to `run_黑芝麻智能.py`
- full report runtime validation was therefore not performed in this pilot

Recommended next step:

1. Add an official-source inventory for 中简科技.
2. Add only stable official URLs or local high-credit notes.
3. Decide whether to create a single-stock report entry for 中简科技 or keep it as technical-only for now.
