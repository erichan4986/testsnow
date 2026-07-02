# Phase 3c 同行比较 Material → KnowledgeSynthesizer Prompt 集成 — Claude 实现笔记

**日期**: 2026-07-02
**Branch**: `codex-report-quality-upgrade`
**实现类型**: 实现（TDD + 代码修改）

---

## 文件变更

| 文件 | 状态 | 行数 +/- | 作用 |
|------|------|----------|------|
| `scripts/utils/knowledge_synthesizer.py` | 修改 | +62/-8 | 新增 `_format_peer_appendix()`，将 `peer_comparison_material` 串入 synthesize → _build_prompt 调用链 |
| `scripts/utils/report_skills/synthesis_skills.py` | 修改 | +12/-8 | 将 peer material 构建提前至 baseline synthesis 之前；在 _synthesize 中将 peer_material 传入 all_data |
| `tests/utils/test_knowledge_synthesizer.py` | 修改 | +181/-1 | 新增 6 个 Phase 3c 测试 + 修复现有 spy 函数签名 |

Total: **+255/-17 行变更**（3 个修改文件）

---

## Requirements-Test Matrix

### KnowledgeSynthesizer 集成

| 需求 | 测试 | 通过 |
|------|------|:----:|
| `_build_prompt` 接受 `peer_comparison_material` | `test_peer_appendix_included_for_industry_logic` | ✅ |
| industry_logic prompt 包含同行对比 heading | `test_peer_appendix_included_for_industry_logic` | ✅ |
| 高置信行 comparison/source_refs 出现在 prompt | `test_peer_appendix_included_for_industry_logic` | ✅ |
| 使用规则出现在 prompt | `test_peer_appendix_included_for_industry_logic` | ✅ |
| Appendix 仅限 fundamentals/valuation_debate，不在 funding_sentiment/events_catalysts | `test_peer_appendix_included_for_fundamentals_and_valuation_only` | ✅ |
| Low-confidence 行（<0.50）被过滤 | `test_peer_appendix_hard_filters_low_confidence_rows` | ✅ |
| Context-only 行（0.50-0.70）剥离 comparison/values | `test_peer_appendix_strips_context_only_comparisons` | ✅ |
| peer_material 从 synthesize 传递到 _build_prompt | `test_synthesize_passes_peer_material_to_build_prompt` | ✅ |
| 核心事实提取 prompt 不含同行对比 heading | `test_core_fact_extraction_prompt_does_not_include_peer_appendix` | ✅ |
| 向后兼容：无 peer_material 时正常运行 | (existing 54 tests pass) | ✅ |

### synthesis_skills.py

| 需求 | 验证方式 | 通过 |
|------|----------|:----:|
| peer material 在 baseline synthesis 前构建 | 代码结构验证 | ✅ |
| peer material 传入 KnowledgeSynthesizer all_data | 代码验证 + smoke 侧边栏 | ✅ |
| 不修改 legacy _build_prompt / core facts 路径 | git diff --check | ✅ |

### Regression

| Suite | Tests | 通过 |
|-------|-------|:----:|
| Phase 3c focused (knowledge_synthesizer + peer_comparison_material + report_quality) | 70 | ✅ |
| Phase 3a regression (peer_config + data_fetcher + data_skills + etc.) | 44 | ✅ |
| CI grep gates | 3/3 | ✅ |
| git diff --check | — | ✅ |

---

## 测试结果

```
# Phase 3c focused tests
$ PYTHONPATH=... python3 -m pytest tests/utils/test_knowledge_synthesizer.py tests/utils/test_peer_comparison_material.py tests/reporter/test_report_quality.py -q
# 70 passed ✅

# Phase 3a regression
$ PYTHONPATH=... python3 -m pytest tests/reporter/test_peer_config.py tests/reporter/test_data_fetcher_peers.py tests/reporter/test_data_skills.py tests/reporter/test_valuation_renderer.py tests/reporter/test_stock_reporter_source_intake_config.py -q
# 44 passed ✅

# CI gates
$ bash tools/ci_grep_gates.sh
# all gates passed ✅

# git diff --check
# clean ✅
```

---

## Smoke 验证结果 — 复旦微电

### 入口

```bash
python3 scripts/run_stock_report.py --stock 复旦微电 --no-pdf
```

退出码: **0**

### Quality Checkers

| Checker | 结果 |
|---------|:----:|
| `check_report_quality.py` | **PASS** |
| `check_report_prose_quality.py` | **PASS**（仅有已有 theme_reexpanded 警告） |
| `check_report_source_boundary.py` | **PASS** |

### 4.1/4.2 同行材料使用

**4.1 产业逻辑与竞争格局**:
- 包含同行对比表格：毛利率/PE TTM/Forward PE/PS vs 紫光国微，来源标注为"同行对比材料"
- 表格格式：| 指标 | 复旦微电值 | 对手值 | 比较 | 同行对比材料 |
- 与正式源（公告/行业资讯）并存

**4.2 业绩路径与多空分歧**:
- 多处使用同行对比数据：
  - "同行对比显示，复旦微电毛利率（55.27%）高于紫光国微（52.58%）约2.7个百分点"
  - "当前PE(TTM)高达220.36倍，显著高于紫光国微的42.97倍"
  - "公司Forward PE仍达48.99倍，高于紫光国微的21.25倍"
  - "PS（市销率）低于紫光国微3.3倍"
- "唯一"在"被部分外部观点视为A股唯一能量产亿门级高端FPGA的企业"中出现（外部视角，非 report 自身 claim）

### 4.3/4.4/scoring/risk/core facts 是否排除

| 区域 | 同行材料 | 验证 |
|------|----------|:----:|
| 4.3 资金面与催化剂 | **排除** ✅ | 仅 1 行，无 peer 提及 |
| 4.4 精选外部观察 | **排除** ✅ | 独立路径，不接收 peer appendix |
| Scoring/Risk | **排除** ✅ | baseline synthesis 原始路径 |
| Core facts 提取 | **排除** ✅ | extract_core_facts 不走 _build_prompt |

### Sidecar 状态

- 报告正常生成：`reports/复旦微电_20260702.md`（31KB）
- Sidecar 正常持久化：`reports/复旦微电_20260702_peer_comparison_material.json`（8 行高置信数据）

---

## 设计决策

### 1. Peer material 构建时间前移

将 `build_peer_comparison_material()` 调用从 baseline synthesis 之后移至之前。这样 baseline synthesis 的 KnowledgeSynthesizer 也能接收 peer material，在 4.1/4.2 prompt 中加入同行对比附录。

```python
# Before Phase 3c: peer material built AFTER baseline
baseline = self._synthesize(...)
ctx.set("peer_comparison_material", build_peer_comparison_material(...))

# After Phase 3c: peer material built BEFORE baseline  
peer_material = build_peer_comparison_material(...)
ctx.set("peer_comparison_material", peer_material)
baseline = self._synthesize(...)
```

### 2. `_format_peer_appendix` 方法

新增的静态方法位于 `KnowledgeSynthesizer` 类中：
- 调用 `filter_peer_rows_for_prompt()` 执行 hard filter
- 按 theme 设置 row cap：industry_logic=4, fundamentals=3, valuation_debate=3
- 对 valuation_debate 优先展示"估值水平"维度行
- claim_eligible 行保留 comparison/values，context_only 行剥离
- 输出格式化的非引用附录文本

### 3. 向后兼容

所有现有参数保持 optional（默认 None）：
- `_build_prompt(..., peer_comparison_material=None)`
- `_synthesize_theme(..., peer_comparison_material=None)`
- `synthesize` 从 `all_data.get("peer_comparison_material")` 读取

### 4. 附录格式

```
同行对比材料（正式/指标来源，非新增引用）

使用规则：
- 只能基于 claim_eligible 行写"高于/低于/接近/优于/弱于"等相对判断。
- context_only 行只能写成"后续可跟踪的对比线索"，不能写成已确认优劣。
- 不得把同行材料写入 4.3 资金面/催化剂。
- 不得引用雪球/知乎/微信/精选外部来支撑 4.1/4.2 同行结论。

- 盈利能力 | 复旦微电 vs 紫光国微 | gross_margin: 55.3% vs 52.6% | 毛利率高于紫光国微约2.7% | confidence=0.85 | 来源: 指标:competitor_metrics
```

---

## Blocker / Warning / Deviation

### Blocker: 无

### Warning: 无

### Deviation: 无

所有实现严格遵循 Phase 3c 边界：
- ❌ 未修改 `peer_comparison_material.py`（API 保持 Phase 3b 一致）
- ❌ 未修改 `deep_analysis_renderer.py`
- ❌ 未修改 `report_quality.py`
- ❌ 未修改 scoring/risk/technical 算法
- ❌ 未使用 Chrome/CDP/Playwright/雪球
- ❌ 未手工修改 `reports/*.md`

---

## Git Status

```
 M scripts/utils/knowledge_synthesizer.py
 M scripts/utils/report_skills/synthesis_skills.py
 M tests/utils/test_knowledge_synthesizer.py
?? docs/agent_workflow/2026-07-02-peer-comparison-material-layer-claude-task-phase3c.md
?? reports/
```

无计划外的修改或文件。

---

## Codex 验收补充

Codex 复核 diff 后补了两处窄范围保护：

- `KnowledgeSynthesizer._format_peer_appendix()` 的使用规则中明确：同行材料不是新的引用来源，不得生成新的 `[^n]` 引用编号。
- 新增 `test_peer_appendix_order_before_claim_verification_and_previous_ledger`，锁定 prompt 顺序为：编号来源 → 同行对比材料 → claim verification context → previous topic ledger。

复验结果：

```text
PYTHONPATH=/Users/erichan/testsnow/scripts:/Users/erichan/testsnow/scripts/utils \
python3 -m pytest tests/utils/test_knowledge_synthesizer.py tests/utils/test_peer_comparison_material.py tests/reporter/test_report_quality.py -q
# 71 passed

PYTHONPATH=/Users/erichan/testsnow/scripts:/Users/erichan/testsnow/scripts/utils \
python3 -m pytest tests/reporter/test_peer_config.py tests/reporter/test_data_fetcher_peers.py tests/reporter/test_data_skills.py tests/reporter/test_valuation_renderer.py tests/reporter/test_stock_reporter_source_intake_config.py tests/reporter/test_run_stock_report_entry.py tests/reporter/test_stock_reporter_charts.py -q
# 56 passed

python3 scripts/check_report_quality.py reports/复旦微电_20260702.md
# PASS

python3 scripts/check_report_prose_quality.py reports/复旦微电_20260702.md
# PASS, 2 existing theme_reexpanded warnings

python3 scripts/check_report_source_boundary.py reports/复旦微电_20260702.md
# PASS

bash tools/ci_grep_gates.sh
# all gates passed

git diff --check
# clean
```
