# Claude Task — Periodic Report Fulltext As Synthesis Display Material

你是 Claude Code，在 `/Users/erichan/testsnow` 仓库里做小范围 TDD 实现。

## 目标

实现年报/半年报 fulltext material 可选进入最终报告展示叙事，但不能进入核心事实、风险评分、风险关键词观察、Knowledge 写入或 evidence notes。

设计文件：

- `docs/agent_workflow/2026-06-19-periodic-report-fulltext-synthesis-material-design.md`

重点遵守末尾：

- `## Design Delta After Round 2`

## 允许修改

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/synthesis_credit.py`
- `scripts/utils/reporter/sections/executive_summary_renderer.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/reporter/sections/html_dashboard_renderer.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_scoring_engine_risk.py` 或等价 existing risk test
- `tests/reporter/test_executive_summary_renderer.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_html_dashboard_renderer.py` 或等价 renderer test
- `tests/utils/test_synthesis_credit.py`（如不存在可新增）
- 可追加 notes 到 `docs/agent_workflow/2026-06-20-periodic-report-fulltext-synthesis-material-claude-notes.md`

## 禁止修改

- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- `scripts/utils/report_skills/knowledge_skills.py`
- `scripts/utils/knowledge_synthesizer.py` prompt / core facts prompt
- technical modules
- `claim_risk_signal_skill.py`
- `source_intake_merge_skill.py`
- `evidence_note_writer.py`
- `data/raw/`
- `reports/`
- `knowledge/`
- 与任务无关的重构或格式化

## 实现要求

1. 先写失败测试，再实现最小代码。
2. 新增 ctx switch：`include_periodic_report_fulltext_in_synthesis`，默认 False。
3. 当 switch 为 False：
   - `periodic_report_fulltext_items` 不进入 synthesis。
   - 行为与当前一致。
4. 当 switch 为 True 且存在合法 fulltext item：
   - baseline synthesis 使用普通 items。
   - enhanced/display synthesis 使用普通 items + fulltext items。
   - fulltext item 必须追加到末尾，保持普通来源编号稳定。
   - `ctx["synthesis"]` 必须是 baseline。
   - `ctx["core_facts"]` 必须来自 baseline。
   - `ctx["synthesis_text"]` 必须是 baseline flatten。
   - `ctx["synthesis_sources"]` 必须是 baseline sources。
   - `ctx["synthesis_display"]` 才是 enhanced。
   - `ctx["synthesis_display_sources"]` 是 enhanced sources。
   - `ctx["synthesis_text_with_periodic_report_fulltext"]` 可保存 enhanced flatten，但风险路径不得读取。
5. 三个展示 renderer 使用：
   - `ctx.get("synthesis_display") or ctx.get("synthesis")`
6. Knowledge 写入器不得修改，且由于 `ctx["synthesis"]` 是 baseline，不会写入 fulltext 叙事。
7. `synthesis_credit.derive_synthesis_usage()` 对 `source_type=="periodic_report_fulltext_analysis"` 返回：
   - `credit_tier="medium"`
   - `usage="annual_report_material"`
   - `display_label="中信用/annual_report_material"`
   - 不允许 `core_fact_allowed`
8. `format_synthesis_source_line()`：
   - 普通 source content cap 保持 500。
   - fulltext source content cap 为 1200。
   - cap 判断必须基于 `source_type=="periodic_report_fulltext_analysis"`。
9. `is_core_fact_supporting_source("定期报告全文", meta)` 必须仍为 False。

## 必测用例

至少覆盖：

- default off: fulltext items in ctx but synthesizer 只收到 ordinary items。
- switch on: synthesizer 先收到 ordinary items，再收到 ordinary + fulltext item。
- fulltext item appended last。
- canonical `ctx["synthesis"]` remains baseline。
- `ctx["synthesis_display"]` contains enhanced narrative。
- `ctx["synthesis_text"]` remains baseline even if enhanced contains “降价 / 毛利率承压 / 净流出”等关键词。
- `ctx["core_facts"]` remains baseline。
- risk scoring with `score_llm_keyword_risks=True` is invariant because it receives baseline synthesis_text。
- display renderers prefer `synthesis_display` and fall back to `synthesis`。
- Knowledge path receives baseline by construction（可用 monkeypatch/ctx assertion，不要写真实 knowledge）。
- fulltext usage/excerpt cap tests。

## 建议测试命令

```bash
python3 -m pytest \
  tests/reporter/test_synthesis_skills.py \
  tests/reporter/test_scoring_engine_risk.py \
  tests/reporter/test_executive_summary_renderer.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_html_dashboard_renderer.py \
  tests/utils/test_synthesis_credit.py -q

python3 -m pytest \
  tests/reporter/test_pipeline_integration.py \
  tests/reporter/test_source_intake_evidence_renderer.py \
  tests/utils/test_periodic_report_fulltext_intake.py -q

git diff --check
```

如果某个 test file 不存在，请说明，并跑最接近的 existing renderer test。

## 停止条件

立即停止并汇报，不要继续实现：

- 需要修改禁止文件。
- 需要修改 scoring/risk/technical/KnowledgeSynthesizer prompt。
- 发现 display renderer 无法通过 `synthesis_display` 安全接入，必须改 report assembly 大结构。
- 测试暴露出 unrelated 大范围失败。

## 完成后回复

- 改了哪些文件
- 新增/修改了哪些测试
- 关键不变量是否满足：
  - `ctx["synthesis"]` baseline
  - `ctx["synthesis_display"]` enhanced
  - `ctx["synthesis_text"]` baseline
  - no risk scoring leak
  - no Knowledge persistence leak
- 测试结果
- `git diff --check` 结果
- blocker / 偏离点
