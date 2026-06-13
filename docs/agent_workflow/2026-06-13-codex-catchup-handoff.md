# Codex Catch-Up Handoff — 2026-06-13

> 本文件用于 Codex 额度恢复后快速恢复上下文。阅读顺序：本 handoff → 对应 `claude-notes.md` / `codex-review.md` → 代码 diff → 测试。

---

## 1. 当前分支与基线

- **当前分支**：`codex-report-quality-upgrade`
- **HEAD**：`af962d4 baseline before Codex report quality upgrade`
- **基线分支**：`master`（仓库主分支）
- **状态**：大量未提交改动和未跟踪文件堆积在工作区，等待整理提交。
- **最后完整测试**：
  ```bash
  cd /Users/erichan/testsnow && python3 -m pytest tests -q
  # 668 passed, 6 skipped in 172.78s
  ```

---

## 2. 6/11–6/13 完成的主要模块

### 2.1 Agent-Reach 证据层（已完成，已本地验证）

| 阶段 | 文件 | 状态 |
|------|------|------|
| 设计 | `2026-06-11-agent-reach-fundamental-research-design.md` | ✅ 已闭环 |
| Connector 重构 | `2026-06-11-agent-reach-connector-refactor-*` | ✅ 已闭环 |
| 质量门 | `2026-06-11-agent-reach-quality-gate-*` | ✅ 已闭环 |
| 证据渲染 | `2026-06-11-agent-reach-evidence-renderer-*` | ✅ 已闭环 |
| 主题化证据 | `2026-06-11-agent-reach-themed-evidence-*` | ✅ 已闭环 |
| Seed URL 配置 | `2026-06-11-agent-reach-config-seed-urls-*` | ✅ 已闭环 |
| 校准 | `2026-06-11-agent-reach-phase0b-calibration-*` | ✅ 已闭环 |
| Audit + 官方源校准 | `2026-06-13-agent-reach-audit-official-source-calibration-*` | ✅ 已闭环 |
| 单股 source expansion | `2026-06-13-agent-reach-source-expansion-*` | ✅ 已闭环 |

**关键代码产物**（未跟踪文件）：
- `scripts/utils/report_skills/agent_reach_query_skill.py`
- `scripts/utils/report_skills/agent_reach_skill.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/report_skills/evidence_note_skill.py`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- `scripts/utils/report_quality.py`
- `scripts/utils/source_credit.py`
- `scripts/utils/wind_kline_loader.py`
- `scripts/smoke_agent_reach.py`
- `scripts/utils/reporter/report_manager.py`

**配置变更**：
- `config/stocks.json`：为 黑芝麻智能 增加 `agent_reach` 块，包含 6 个 `blacksesame.com` 官方 URL 和 `official_domains`。
- 其他股票未启用 `agent_reach`。

**测试产物**：
- `tests/reporter/test_agent_reach_*.py`（多个）
- `tests/reporter/test_evidence_note_skill.py`
- `tests/reporter/test_report_quality.py`
- `tests/reporter/test_stock_reporter_agent_reach_config.py`
- `tests/reporter/test_run_black_sesame_entry.py`
- `tests/reporter/test_technical_skills_contract.py`
- `tests/reporter/test_wind_kline_loader.py`
- `tests/utils/test_claim_verification.py`
- `tests/utils/test_evidence_note_writer.py`
- `tests/utils/test_extract_detail_cli.py`
- `tests/utils/test_pdf_exporter.py`
- `tests/utils/test_source_credit.py`

### 2.2 Claim Verification 证据笔记链（已完成，已本地验证）

| 阶段 | 文件 | 状态 |
|------|------|------|
| 设计 | `2026-06-13-claim-verification-design.md` | ✅ 已闭环 |
| Phase 4 实现 | `2026-06-13-claim-verification-implementation-*` | ✅ 已闭环 |
| Phase 4B runtime | `2026-06-13-claim-verification-phase4b-runtime-validation-*` | ✅ 已闭环 |
| Phase 4C real legacy | `2026-06-13-claim-verification-phase4c-real-legacy-validation-*` | ✅ 已闭环 |
| Phase 4D body extraction | `2026-06-13-claim-extraction-phase4d-*` | ✅ 已闭环 |
| Phase 5 synthesis 集成 | `2026-06-13-claim-verification-phase5-synthesis-integration-*` | ✅ 已闭环 |

**关键代码产物**（未跟踪文件）：
- `scripts/utils/claim_verification.py`
- `scripts/utils/evidence_note_writer.py`

**集成点**：
- `scripts/utils/report_skills/synthesis_skills.py` 已修改，支持 `enable_claim_verification_context`（默认关闭）。
- `scripts/utils/knowledge_synthesizer.py` 已修改，接收 `claim_verification_context` 并附加 guarded prompt appendix。
- `scripts/utils/stock_reporter.py` 已修改，支持 per-stock `claim_verification` 配置透传。

### 2.3 其他修改的已有文件

- `AGENTS.md`：新增 Codex 协作规则（Level 0/2/3 workflow、prompt 模板、验收责任）。
- `docs/codex_handoff/runbook.md`：更新运行命令、目录约定、入口演进方向。
- `README.md`：小幅更新架构图和 Agent-Reach 描述。
- `scripts/run_黑芝麻智能.py`、`scripts/utils/stock_reporter.py` 等：接入 Agent-Reach 和 claim verification。
- 多个 `scripts/utils/report_skills/*.py` 和 `reporter/sections/*.py`：配合新能力微调。
- 大量现有测试更新以适配新 schema 和配置。

---

## 3. 当前工作区状态

### 3.1 未提交但应提交的代码/配置

```text
M  AGENTS.md
M  README.md
M  config/stocks.json
M  docs/codex_handoff/runbook.md
M  knowledge/10-Stocks/圣邦股份/MOC.md
M  scripts/extract_detail.py
M  scripts/extract_detail_via_cdp.py
M  scripts/run_黑芝麻智能.py
M  scripts/utils/data_collector.py
M  scripts/utils/detail_page_fetcher.py
M  scripts/utils/knowledge_synthesizer.py
M  scripts/utils/pdf_exporter.py
M  scripts/utils/report_skills/__init__.py
M  scripts/utils/report_skills/assembly_skills.py
M  scripts/utils/report_skills/chart_skills.py
M  scripts/utils/report_skills/data_skills.py
M  scripts/utils/report_skills/synthesis_skills.py
M  scripts/utils/report_skills/technical_skills.py
M  scripts/utils/reporter/__init__.py
M  scripts/utils/reporter/scoring_engine.py
M  scripts/utils/reporter/sections/__init__.py
M  scripts/utils/reporter/sections/composite_score_renderer.py
M  scripts/utils/reporter/sections/risk_renderer.py
M  scripts/utils/reporter/sections/technical_renderer.py
M  scripts/utils/reporter/sections/valuation_renderer.py
M  scripts/utils/reporter/technical_analyzer.py
M  scripts/utils/source_adapter.py
M  scripts/utils/stock_reporter.py
M  scripts/xueqiu_monitor_v2.py
M  tests/reporter/test_assembly_skills.py
M  tests/reporter/test_chart_skills.py
M  tests/reporter/test_composite_score_renderer.py
M  tests/reporter/test_data_skills.py
M  tests/reporter/test_pipeline_integration.py
M  tests/reporter/test_risk_renderer.py
M  tests/reporter/test_stock_reporter_charts.py
M  tests/reporter/test_synthesis_skills.py
M  tests/reporter/test_technical_renderer.py
M  tests/reporter/test_valuation_renderer.py
M  tests/utils/test_detail_page_fetcher.py
M  tests/utils/test_knowledge_synthesizer.py
M  tests/utils/test_source_adapter.py

?? scripts/check_report_quality.py
?? scripts/smoke_agent_reach.py
?? scripts/utils/claim_verification.py
?? scripts/utils/evidence_note_writer.py
?? scripts/utils/report_quality.py
?? scripts/utils/report_skills/agent_reach_quality_skill.py
?? scripts/utils/report_skills/agent_reach_query_skill.py
?? scripts/utils/report_skills/agent_reach_skill.py
?? scripts/utils/report_skills/evidence_note_skill.py
?? scripts/utils/reporter/report_manager.py
?? scripts/utils/reporter/sections/agent_reach_evidence_renderer.py
?? scripts/utils/source_credit.py
?? scripts/utils/wind_kline_loader.py
?? tests/reporter/test_agent_reach_connector.py
?? tests/reporter/test_agent_reach_evidence_renderer.py
?? tests/reporter/test_agent_reach_quality_skill.py
?? tests/reporter/test_agent_reach_skills.py
?? tests/reporter/test_agent_reach_smoke_script.py
?? tests/reporter/test_agent_reach_source_config.py
?? tests/reporter/test_evidence_note_skill.py
?? tests/reporter/test_report_quality.py
?? tests/reporter/test_run_black_sesame_entry.py
?? tests/reporter/test_scoring_engine_contract.py
?? tests/reporter/test_stock_reporter_agent_reach_config.py
?? tests/reporter/test_technical_skills_contract.py
?? tests/reporter/test_wind_kline_loader.py
?? tests/utils/test_claim_verification.py
?? tests/utils/test_evidence_note_writer.py
?? tests/utils/test_extract_detail_cli.py
?? tests/utils/test_pdf_exporter.py
?? tests/utils/test_source_credit.py
```

### 3.2 建议清理的生成物/缓存（不要提交）

```text
.cache/
.playwright-mcp/
data/raw/20260612/
knowledge/10-Stocks/*/20260612-*.md  # 自动生成的知识库笔记
reports/*.md
reports/*.html
reports/*.pdf
reports/*.png
reports/agent_reach_page_*.png
reports/黑芝麻智能_20260613_agent_reach.json
reports/黑芝麻智能_20260613_agent_reach_smoke.json
reports/黑芝麻智能_20260613_technical.png
```

建议把 `.cache/` 和 `.playwright-mcp/` 加入 `.gitignore`。

---

## 4. Codex 恢复后的标准路径

```bash
# 1. 确认分支和基线
cd /Users/erichan/testsnow
git branch
git log --oneline -5

# 2. 读 handoff
cat docs/agent_workflow/2026-06-13-codex-catchup-handoff.md

# 3. 运行完整测试
python3 -m pytest tests -q
# 预期：668 passed, 6 skipped

# 4. 查看当前未提交改动
git status --short
```

---

## 5. 已验证的 focused smoke 命令

```bash
# Agent-Reach 单股 smoke（已验证通过）
python3 scripts/smoke_agent_reach.py --stock 黑芝麻智能 --write-audit --output-dir reports

# Agent-Reach focused tests（已验证通过）
python3 -m pytest tests/reporter/test_agent_reach_*.py tests/reporter/test_stock_reporter_agent_reach_config.py tests/reporter/test_run_black_sesame_entry.py tests/reporter/test_assembly_skills.py -q
# 136 passed

# Claim verification focused tests（已验证通过）
python3 -m pytest tests/utils/test_claim_verification.py tests/utils/test_evidence_note_writer.py tests/reporter/test_evidence_note_skill.py -q
# 92 passed
```

---

## 6. 待决策 / 下一步工作

| 优先级 | 事项 | 说明 |
|--------|------|------|
| **P0** | 提交当前工作区 | 把代码/测试/文档按逻辑拆成 3-4 个 commit；清理缓存和生成物。 |
| **P1** | 跑单股完整报告验收 | `cd scripts && python3 run_黑芝麻智能.py --fast-test`，检查 Markdown/HTML/PDF 是否正常，Agent-Reach evidence section 是否渲染。 |
| **P1** | 决定是否启用 claim verification in synthesis | 已实现但默认关闭；下一步是手动 sample prompt/output review。 |
| **P2** | Agent-Reach 扩展到其他股票 | 当前仅 黑芝麻智能 启用；每只股票需要独立的 source inventory。 |
| **P2** | 整理 `.gitignore` | 把 `.cache/`、`.playwright-mcp/`、`data/raw/2026*/` 等运行时目录加入。 |
| **P3** | 合并到 `master` | 当前分支领先 master 约 30+ commits；需先 commit、rebase/merge、再验证。 |

---

## 7. 关键约束（不要违反）

- **不要自动抓雪球详情页**：除非用户已登录 Chrome CDP。
- **不要把 Agent-Reach 喂进 LLM synthesis / 评分 / 最终建议**：Agent-Reach 只进证据层。
- **不要在 audit JSON 里保存完整网页 content**：`agent_reach_run_summary` 是 compact 的。
- **不要修改 scoring_engine、technical analyzer、KnowledgeSynthesizer 核心逻辑** unless 明确任务要求。
- **单股验证优先用** `scripts/run_黑芝麻智能.py --fast-test`；不要默认跑 `xueqiu_monitor_v2.py`。

---

## 8. 联系人

- 本地 Claude Code 已执行过本次 source expansion 和 smoke 验证。
- Codex 有额度后，按本 handoff 第 4 节路径恢复即可。

---

*Last updated: 2026-06-13 by Claude Code (local).*
