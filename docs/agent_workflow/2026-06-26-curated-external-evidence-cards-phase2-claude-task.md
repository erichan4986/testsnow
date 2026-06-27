# Claude Task — Curated External Evidence Cards Phase 2

你是 Claude Code，在 `/Users/erichan/testsnow` 仓库中实现 Phase 2。

## Goal

让 enriched curated external evidence cards 以 **deep-analysis-only /
display-only** 方式进入 `## 四、深度分析`，并确保不进入核心事实、
Knowledge、评分、风险、执行摘要、HTML dashboard 或最终建议。

## Required Reading

先读完：

- `docs/agent_workflow/2026-06-26-curated-external-evidence-cards-phase2-design.md`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/stock_reporter.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `tools/ci_grep_gates.sh`
- `tests/reporter/test_synthesis_skills.py`
- `tests/utils/test_ci_grep_gates.py`

## Allowed Files

可以修改 / 新增：

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/stock_reporter.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/curated_external_evidence_card_synthesis_items.py`
- `scripts/utils/curated_external_display_lint.py`
- `tools/ci_grep_gates.sh`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_deep_analysis_renderer.py` 或现有 renderer 测试文件
- `tests/utils/test_curated_external_evidence_card_synthesis_items.py`
- `tests/utils/test_curated_external_display_lint.py`
- `tests/utils/test_ci_grep_gates.py`

如确实需要新增 focused test 文件，可以新增在 `tests/reporter/` 或
`tests/utils/` 下，但不要扩大到无关模块。

## Forbidden

- 不要修改 `scripts/utils/knowledge_synthesizer.py`。
- 不要修改 `scripts/utils/report_skills/knowledge_skills.py`。
- 不要修改 `scripts/utils/reporter/scoring_engine.py`。
- 不要修改 `scripts/utils/reporter/sections/risk_renderer.py`。
- 不要修改技术分析、EV、目标价、仓位建议模块。
- 不要修改外部采集、WeChat exporter、雪球、Playwright、Chrome/CDP 逻辑。
- 不要写 `knowledge/`、`reports/`、`data/raw/`。
- 不要运行 LLM，不要访问外部网络。
- 不要打印 `.env` 或任何 API key。

## Implementation Requirements

### 1. Helper: evidence cards → SynthesisItem

新增 `scripts/utils/curated_external_evidence_card_synthesis_items.py`。

实现一个可测试入口，例如：

```python
def load_curated_external_evidence_card_synthesis_items(
    cards_json_path: str | Path,
    *,
    max_items: int = 8,
    min_cards: int = 3,
    min_total_excerpt_chars: int = 1200,
) -> tuple[list[SynthesisItem], dict]:
    ...
```

返回：

- eligible `SynthesisItem` 列表；
- stats/status dict，至少包含：
  - `status`
  - `cards_seen`
  - `cards_eligible`
  - `cards_rejected`
  - `total_excerpt_chars`
  - `rejection_reasons`

必须执行 card gate：

- summary `schema_version == "curated_external_evidence_cards.v1"`
- summary `wrote_knowledge is False`
- summary `connected_synthesis is False`
- card `schema_version == "periodic_report_narrative_evidence_card.v1"`
- card `source_type == "curated_external_analysis_evidence"`
- card `quality_action == "preview_only"`
- card `knowledge_eligible is False`
- card `synthesis_eligible is True`
- card `synthesis_display_only is True`
- card `scoring_eligible is False`
- card `risk_score_eligible is False`
- card `verification_status == "professional_observation"`
- card `source_credit <= 65`
- card `source_ref` 是 URL 或本地路径，不是 source_kind fallback
- excerpt `normalized_substring_verified is True`
- normalized excerpt length >= 300 chars
- Chinese chars >= 80
- Chinese char density >= 5%
- topic in whitelist:
  - `industry_logic`
  - `commercialization`
  - `earnings_context`
  - `cycle_price`
  - `certification_policy`
  - `capital_market_context`
- reject `product_roadmap`
- `capital_market_context` only passes if title/excerpt contains substance terms:
  - 财报 / 业绩 / 盈利 / 亏损 / 毛利率 / 现金流
  - 募资用途 / 研发投入 / 产能建设 / 资本开支
  - 上市进展 / 递表 / 聆讯 / 发行 / 招股书
  - 行业影响 / 产业链 / 客户 / 订单 / 量产
- stock-level gate:
  - eligible cards >= `min_cards`
  - total eligible excerpt chars >= `min_total_excerpt_chars`

SynthesisItem requirements:

- `source_platform = "微信公众号精选观察"`
- `title = card title`
- `content` includes title, topic/source_kind note, and source excerpt
- `url = source_ref` if source_ref is URL
- `extra` includes:
  - `source_type = "curated_external_analysis_evidence"`
  - `source_credit = card source_credit or 55`
  - `verification_status = "professional_observation"`
  - `claim_status = "professional_observation"`
  - `quality_action = "preview_only"`
  - `knowledge_eligible = False`
  - `synthesis_display_only = True`
  - `scoring_eligible = False`
  - `risk_score_eligible = False`
  - `card_id`
  - `source_ref`
  - `source_excerpt_hash`
  - `source_block_hash`
  - `topic`

Sort deterministically:

```text
topic priority, longer excerpt first, publish_time descending, card_id
```

### 2. Helper: citation-aware overclaim lint

新增 `scripts/utils/curated_external_display_lint.py`。

实现一个可测试入口，例如：

```python
def lint_curated_external_display_text(
    synthesis: dict,
    *,
    curated_source_type: str = "curated_external_analysis_evidence",
    max_curated_source_credit: int = 65,
) -> dict:
    ...
```

行为：

- 只检查 synthesis 的叙事字段：
  - `industry_logic`
  - `fundamentals`
  - `valuation_debate`
  - `funding_sentiment`
  - `events_catalysts`
- 按中文/英文句号、分号、换行切句。
- 从句子中抽取数字引用 `[^n]`。
- citation 是 curated external 当且仅当：
  - `source_type == "curated_external_analysis_evidence"`
  - `source_credit <= 65`
- 如果句子包含强确认词，且句子里的所有引用都是 curated external，则 fail。
- 如果句子包含强确认词，但至少引用一个高信用公告/官方来源，则 pass。
- 如果句子无引用但包含强确认词，不因 curated external lint fail。

强确认词：

- `确认`
- `证实`
- `已验证`
- `必然`
- `确定`
- `公司披露`
- `公告显示`
- `已落地`
- `锁定`

返回 dict：

- `ok: bool`
- `violations: list`

### 3. SynthesisSkill integration

修改 `scripts/utils/report_skills/synthesis_skills.py`。

要求：

- 新增 curated external 分支，独立于现有 `synthesis_display` 分支。
- 不把 curated external items append 到现有 fulltext / narrative / broker
  display branch。
- 成功时只设置：
  - `deep_analysis_display`
  - `deep_analysis_display_sources`
  - `synthesis_text_with_curated_external_evidence_cards`
  - `curated_external_evidence_cards_status`
  - `curated_external_evidence_cards_stats`
  - `curated_external_evidence_cards_lint`
- 失败或 gate 不满足时：
  - 不设置 `deep_analysis_display`
  - 保持 `synthesis`、`core_facts`、`synthesis_text`、
    `synthesis_sources`、`synthesis_display` 不变
  - 设置 status/stats 说明原因
- 复用 `dedupe_synthesis_display_items()` 处理 normal items + curated items。
- 扩展 `_fill_citation_metadata()`，把以下 `item.extra` 字段转发到
  citations 顶层：
  - `card_id`
  - `source_ref`
  - `source_excerpt_hash`
  - `source_block_hash`
  - `topic`
  - `synthesis_display_only`
  - `quality_action`
  - `scoring_eligible`
  - `risk_score_eligible`

### 4. Pipeline / config wiring

修改 `scripts/utils/report_skills/__init__.py`。

`build_stock_report_pipeline()` 显式增加参数：

```python
include_curated_external_evidence_cards_in_synthesis_display: bool = False
curated_external_evidence_cards_json: str = ""
curated_external_evidence_cards_max_display_items: int = 8
curated_external_evidence_cards_min_cards: int = 3
curated_external_evidence_cards_min_total_excerpt_chars: int = 1200
```

并把这些值传入 `SynthesisSkill`，或以其他显式、可测试的方式传给它。
不要使用未声明的 `**kwargs`。

修改 `scripts/utils/stock_reporter.py`。

读取：

```text
source_intake_configs.<stock>.curated_external_evidence_cards_synthesis_display
```

仅当：

- `source_intake_enabled is True`
- subsection `enabled is True`

才启用该功能。

配置字段：

- `cards_json`
- `max_display_items`
- `min_cards`
- `min_total_excerpt_chars`

### 5. Renderer integration

修改 `scripts/utils/reporter/sections/deep_analysis_renderer.py`。

`render()` 应优先读取：

```python
ctx.get("deep_analysis_display") or ctx.get("synthesis_display") or ctx.get("synthesis") or {}
```

不要让 `ExecutiveSummaryRenderer` 或 `HtmlDashboardRenderer` 读取
`deep_analysis_display`。

### 6. CI gates

修改 `tools/ci_grep_gates.sh` 和 `tests/utils/test_ci_grep_gates.py`。

要求：

- 把新 helper 加入 helper leak check：
  - `scripts/utils/curated_external_evidence_card_synthesis_items.py`
  - `scripts/utils/curated_external_display_lint.py`
- 新增 curated external leak gate，禁止以下 token 出现在核心文件：
  - `curated_external_analysis_evidence`
  - `deep_analysis_display_sources`
  - `synthesis_text_with_curated_external_evidence_cards`
- 核心文件：
  - `scripts/utils/reporter/scoring_engine.py`
  - `scripts/utils/reporter/sections/risk_renderer.py`
  - `scripts/utils/report_skills/knowledge_skills.py`
  - `scripts/utils/knowledge_synthesizer.py`

## Required Tests

Use TDD: write failing tests before implementation.

Minimum tests:

1. `tests/utils/test_curated_external_evidence_card_synthesis_items.py`
   - accepts valid enriched cards;
   - rejects excerpt <300 chars;
   - rejects Chinese chars <80;
   - rejects Chinese density <5%;
   - rejects product_roadmap;
   - rejects capital_market_context without substance;
   - rejects source_credit >65;
   - enforces stock-level gates;
   - sorts deterministically;
   - emits SynthesisItem extra traceability fields.

2. `tests/utils/test_curated_external_display_lint.py`
   - curated-only sentence with strong confirmation fails;
   - official/announcement citation with strong confirmation passes;
   - mixed official + curated citation passes;
   - cautious wording passes;
   - non-numeric citations do not crash.

3. `tests/reporter/test_synthesis_skills.py`
   - default-off excludes curated external cards;
   - enabled with valid 中际旭创-style cards sets `deep_analysis_display`;
   - 圣邦-style one-card sample does not set `deep_analysis_display`;
   - `synthesis`, `core_facts`, `synthesis_text`, `synthesis_sources`,
     and `synthesis_display` remain baseline;
   - `synthesis_text_with_curated_external_evidence_cards` is set only when
     deep-analysis display succeeds;
   - citation metadata includes `card_id`, `source_ref`,
     `source_excerpt_hash`, `source_block_hash`, `topic`;
   - overclaim lint failure avoids setting `deep_analysis_display`.

4. Renderer test:
   - `DeepAnalysisRenderer` prefers `deep_analysis_display`;
   - existing fallback to `synthesis_display` and `synthesis` still works.

5. Config wiring test:
   - `stock_reporter.py` maps the source_intake config subsection into
     pipeline kwargs only when source intake and subsection are enabled.

6. CI gate tests:
   - leak tokens in scoring/risk/knowledge files fail;
   - helper files are covered by helper leak check.

## Verification Commands

Run focused tests:

```bash
python3 -m pytest \
  tests/utils/test_curated_external_evidence_card_synthesis_items.py \
  tests/utils/test_curated_external_display_lint.py \
  tests/reporter/test_synthesis_skills.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/utils/test_ci_grep_gates.py -q
```

Run compile:

```bash
python3 -m compileall \
  scripts/utils/curated_external_evidence_card_synthesis_items.py \
  scripts/utils/curated_external_display_lint.py \
  scripts/utils/report_skills/synthesis_skills.py \
  scripts/utils/report_skills/__init__.py \
  scripts/utils/stock_reporter.py \
  scripts/utils/reporter/sections/deep_analysis_renderer.py
```

Run gates:

```bash
bash tools/ci_grep_gates.sh
git diff --check
```

If full `pytest` is too slow, report that and include focused tests above.

## Optional Smoke

If `/tmp/zhongjixuchuang_curated_external_body_enriched_evidence_cards.json`
and `/tmp/shengbang_curated_external_body_enriched_evidence_cards.json` exist,
run a no-report synthetic context smoke or focused unit fixture:

- 中际旭创 enriched cards should set `deep_analysis_display`;
- 圣邦股份 one-card sample should stay baseline.

Do not generate reports unless explicitly necessary.

## Notes Output

Write implementation notes to:

```text
docs/agent_workflow/2026-06-26-curated-external-evidence-cards-phase2-claude-notes.md
```

Notes must include:

- files changed;
- requirement-test matrix;
- focused tests and outputs;
- whether any allowed-scope expansion was needed;
- whether `deep_analysis_display` stayed isolated from
  `synthesis_display`, scoring, risk, and Knowledge;
- blocker / warning / deviation;
- `git status --short`.

## Stop Conditions

Stop and report instead of implementing if:

- you need to modify forbidden files;
- you need to modify `KnowledgeSynthesizer` prompt;
- you need to touch scoring/risk/technical/EV/final recommendation code;
- tests reveal existing unrelated large failures;
- you need network, LLM, Chrome/CDP, Playwright, or external collection;
- the design contract cannot be implemented without changing report semantics
  beyond `DeepAnalysisRenderer`.
