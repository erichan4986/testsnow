# Claude Implementation Task — Fudan Trial Quality Fix Batch 1.5 + D

You are Claude Code implementing the first safe slice in `/Users/erichan/testsnow`.

Read first:

1. `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design.md`
2. `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design-delta.md`
3. `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-claude-review-round2-notes.md`

## Goal

Implement only Batch 1.5 and Batch D:

1. Complete stock-level config needed by Direct-Only future work.
2. Make the report header config-first with constants fallback.
3. Make `DeepAnalysisRenderer` always render 4.1 / 4.2 / 4.3 with controlled fallback text instead of silently omitting sections.

This task does **not** implement Direct-Only filtering, financial fact pack, unit normalization, or new quality gates.

## Allowed Files

You may modify:

- `config/stocks.json`
- `scripts/utils/report_skills/assembly_skills.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `tests/reporter/test_stock_reporter_source_intake_config.py`
- `tests/reporter/test_assembly_skills.py`
- `tests/reporter/test_deep_analysis_renderer.py`

You may create:

- `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-claude-notes-batch1_5-d.md`

## Forbidden Files / Areas

Do not modify:

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_quality.py`
- `scripts/utils/industry_news_relevance.py`
- `scripts/utils/periodic_report_*`
- `scripts/utils/reporter/scoring_engine.py`
- technical analysis modules
- Xueqiu / Playwright / CDP / browser fetching code
- `reports/`, `data/raw/`, `knowledge/`
- unrelated docs or formatting-only changes

If you need any forbidden file, stop and report why.

## Implementation Requirements

### 1. Config completion

Update `config/stocks.json` for these three stocks:

#### 复旦微电

Keep existing `industry`, `competitors`, `peer_codes`, and `peer_dimensions`.

Add `product_exposure_terms` containing direct products only:

- `FPGA`
- `FPAI`
- `RF-FPGA`
- `RFSoC`
- `PSoC`
- `MCU`
- `智能电表芯片`
- `车规MCU`
- `安全与识别芯片`
- `RFID`
- `非挥发存储器`
- `非易失存储`
- `EEPROM`
- `NOR Flash`
- `SLC NAND`

Do **not** include generic sector words such as `半导体`, `芯片`, `国产替代`, `AI`, `汽车电子`, `集成电路`, `MLCC`.

#### 中际旭创

Add:

- `industry`: `光通信 / 光模块 / CPO / 硅光`
- `competitors`: `新易盛`, `天孚通信`, `光迅科技`, `剑桥科技`, `华工科技`
- `peer_codes`:
  - `新易盛`: `300502`
  - `天孚通信`: `300394`
  - `光迅科技`: `002281`
  - `剑桥科技`: `603083`
  - `华工科技`: `000988`
- `product_exposure_terms`:
  - `CPO`
  - `光模块`
  - `光通信`
  - `硅光`
  - `数通`
  - `800G`
  - `1.6T`
  - `LPO`
  - `NPO`
  - `XPO`
  - `光引擎`
  - `光连接`
  - `数据中心光模块`

#### 圣邦股份

Add:

- `industry`: `模拟芯片 / 电源管理 / 信号链`
- `competitors`: `思瑞浦`, `杰华特`, `纳芯微`, `艾为电子`
- `peer_codes`:
  - `思瑞浦`: `688536`
  - `杰华特`: `688141`
  - `纳芯微`: `688052`
  - `艾为电子`: `688798`
- `product_exposure_terms`:
  - `模拟芯片`
  - `模拟IC`
  - `电源管理`
  - `电源管理芯片`
  - `PMIC`
  - `信号链`
  - `运放`
  - `ADC`
  - `DAC`
  - `接口芯片`
  - `车规模拟芯片`

### 2. Header config-first fallback

In `ReportAssemblySkill._header()`:

1. Read `stock_config = ctx.get("stock_config", {}) or {}`.
2. `industry` should prefer `stock_config["industry"]`, then fallback to `INDUSTRY_MAP.get(stock_name, "—")`.
3. `competitors` should prefer `stock_config["competitors"]` if it is a non-empty list, then fallback to `COMPETITOR_MAP.get(stock_name, [])`.
4. Render competitors using `、`. Do not show Python list syntax.
5. Preserve existing data source behavior.

### 3. DeepAnalysisRenderer controlled fallback

In `DeepAnalysisRenderer._deep_analysis()`:

1. Always render headings:
   - `### 4.1 产业逻辑与竞争格局`
   - `### 4.2 业绩路径与多空分歧`
   - `### 4.3 资金面与催化剂时间线`
2. If 4.1 has no `industry_logic`, render a controlled fallback sentence similar to:
   - `当前正式材料不足以形成可验证的产业逻辑与竞争格局判断；本节不使用泛行业材料补链条。`
3. If 4.2 has no `fundamentals` and no `valuation_debate`, render:
   - `当前正式材料不足以形成可验证的业绩路径或估值分歧判断；本节不使用外部观点补充财务结论。`
4. For 4.3:
   - If both `funding_sentiment` and `events_catalysts` exist: render both normally.
   - If only `funding_sentiment` exists: render it, then add `当前正式材料未形成可验证的催化剂时间线。`
   - If only `events_catalysts` exists: render it, then add `当前正式材料未提供足够资金面数据。`
   - If neither exists: render `当前正式材料未形成可验证的资金面或催化剂时间线；本节不使用泛行业新闻补链条。`
5. Do not add fake citations to fallback text.
6. Existing citation source lists should still render only when actual section body contains `[^n]`.
7. Preserve 4.4 display-only behavior exactly.

## Required Tests

Write or update tests before implementation where practical.

### Config tests

Update `tests/reporter/test_stock_reporter_source_intake_config.py`:

- Assert 复旦微电 has `product_exposure_terms` and does not include `MLCC`.
- Assert 中际旭创 has `industry`, `competitors`, `peer_codes`, and product exposure terms including `光模块` and `CPO`.
- Assert 圣邦股份 has `industry`, `competitors`, `peer_codes`, and product exposure terms including `模拟芯片` and `电源管理芯片`.

### Header tests

Update `tests/reporter/test_assembly_skills.py`:

- Test `stock_config` wins over constants:
  - Create `SkillContext` for `圣邦股份` with `stock_config.industry = "测试行业"` and `competitors = ["测试对手"]`.
  - `_header()` should contain `测试行业` and `测试对手`.
- Test constants fallback:
  - Create `SkillContext` for `圣邦股份` with no `stock_config`.
  - `_header()` should contain existing constant fallback, e.g. `模拟芯片/半导体` and `思瑞浦`.
- Test double-missing fallback:
  - Unknown stock with no config should render `所属赛道**: —` and `可比公司**: —` or equivalent existing header format.

### Renderer tests

Update `tests/reporter/test_deep_analysis_renderer.py`:

- `funding_sentiment` and `events_catalysts` both empty still renders `### 4.3` and the controlled fallback.
- Only `funding_sentiment` renders funding content plus catalyst-missing sentence.
- Only `events_catalysts` renders event content plus funding-missing sentence.
- Empty `industry_logic` still renders `### 4.1` controlled fallback.
- Empty `fundamentals` and `valuation_debate` still renders `### 4.2` controlled fallback.
- Existing curated external 4.4 tests must continue to pass.

## Test Commands

Run:

```bash
python3 -m pytest \
  tests/reporter/test_stock_reporter_source_intake_config.py \
  tests/reporter/test_assembly_skills.py \
  tests/reporter/test_deep_analysis_renderer.py \
  -q
```

Then run:

```bash
bash tools/ci_grep_gates.sh
git diff --check
```

Do not run the full report entry in this task unless explicitly asked after implementation.

## Completion Notes

Write notes to:

`docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-claude-notes-batch1_5-d.md`

Include:

- Files changed.
- Requirement-test matrix.
- Test commands and results.
- Whether 4.4 behavior was left unchanged.
- Any blocker or deviation.
- `git status --short`.

## Stop Conditions

Stop and report instead of continuing if:

- You need to edit forbidden files.
- Header logic requires changing constants or broader assembly flow.
- Renderer fallback would require LLM prompt changes.
- Any test failure points to Direct-Only filtering, financial fact pack, unit normalization, source collection, scoring, or technical analysis.
- You need external network, Chrome, CDP, Playwright, Xueqiu, Zhihu, or WeChat.
