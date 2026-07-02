# Phase 3b 同行比较 Material Layer — Claude 实现笔记

**日期**: 2026-07-02
**Branch**: `codex-report-quality-upgrade`
**实现类型**: 实现（TDD + 代码修改）

---

## 文件变更

| 文件 | 状态 | 行数 +/- | 作用 |
|------|------|----------|------|
| `scripts/utils/peer_comparison_material.py` | **新建** | 199 行 | 确定性同行比较 material pack 构建 + prompt 过滤 |
| `scripts/utils/report_skills/synthesis_skills.py` | 修改 | +9/-0 | 在 pipeline 上下文中构建 peer material |
| `scripts/utils/report_skills/assembly_skills.py` | 修改 | +20/-0 | 持久化 peer material sidecar JSON |
| `scripts/utils/report_quality.py` | 修改 | +152/-1 | 三个质量门：social_leak、unsupported_superlative、claim_without_pack |
| `tests/utils/test_peer_comparison_material.py` | **新建** | 173 行 | peer_comparison_material 的 11 个测试 |
| `tests/reporter/test_assembly_skills.py` | 修改 | +76/-0 | 2 个 sidecar 持久化测试 |
| `tests/reporter/test_report_quality.py` | 修改 | +299/-0 | 10 个质量门测试（含 8 个 peer 门） |

Total: **+555/-1 行变更**（5 个修改文件 + 2 个新建文件）

---

## Requirements-Test Matrix

### peer_comparison_material.py

| 需求 | 测试方法 | 通过 |
|------|----------|:----:|
| 从 competitor_metrics 构建 metric rows | `test_builds_high_confidence_metric_rows_from_competitor_metrics` | ✅ |
| 缺失值时跳过（不编造） | `test_drops_rows_when_target_or_peer_value_missing` | ✅ |
| 置信度 0.85 分配 correct usage tier | `test_assigns_usage_tiers_correctly` | ✅ |
| 只允许 formal source refs | `test_drops_social_source_refs` | ✅ |
| 每 metric 最多 2 个 peer，总量 ≤8 | `test_compact_row_count_limits` | ✅ |
| 空输入返回空行 | `test_returns_empty_rows_when_no_data` | ✅ |
| peers 列表保持 config 顺序 | `test_peers_list_in_config_order` | ✅ |
| filter_peer_rows_for_prompt 移除 <0.50 行 | `test_removes_low_confidence_rows` | ✅ |
| filter 从 context_only 行剥离 comparison/values | `test_strips_comparison_from_context_only_rows` | ✅ |
| filter 保留 ≥0.70 行不变 | `test_high_confidence_rows_unchanged` | ✅ |
| filter 空行不变 | `test_preserves_empty_rows` | ✅ |

### assembly_skills.py — sidecar 持久化

| 需求 | 测试方法 | 通过 |
|------|----------|:----:|
| 有 rows 时写入 `*_peer_comparison_material.json` | `test_assembly_writes_peer_comparison_material_sidecar` | ✅ |
| rows 为空时不写入 | `test_assembly_does_not_write_peer_comparison_material_when_rows_empty` | ✅ |

### report_quality.py — 质量门

| 需求 | 测试方法 | 通过 |
|------|----------|:----:|
| social source refs 报 error | `test_peer_pack_social_leak_is_error` | ✅ |
| allowed refs 通过 | `test_peer_pack_allowed_refs_pass` | ✅ |
| 强比较词无 high-confidence pack 报 error | `test_unsupported_peer_superlative_is_error` | ✅ |
| pack 有高置信行时不报 | `test_high_confidence_sidecar_suppresses_superlative_error` | ✅ |
| 弱比较词无 pack 报 warning | `test_peer_claim_without_peer_pack_warns` | ✅ |
| pack 有行时不报 | `test_peer_claim_without_peer_pack_no_false_positive_with_sidecar` | ✅ |
| 4.4 display-only 同行语言不触发 | `test_no_peer_gate_false_positive_on_44_display_only` | ✅ |
| check_report_file 自动加载 sidecar | `test_check_report_file_loads_peer_comparison_material_sidecar` | ✅ |

---

## 测试结果

```
# Phase 3b focused tests
$ pytest tests/utils/test_peer_comparison_material.py tests/reporter/test_assembly_skills.py tests/reporter/test_report_quality.py -q
............................................. 51 passed

# Phase 3a regression tests  
$ pytest tests/reporter/test_peer_config.py tests/reporter/test_data_fetcher_peers.py tests/reporter/test_data_skills.py tests/reporter/test_valuation_renderer.py tests/reporter/test_stock_reporter_source_intake_config.py -q
............................................ 44 passed

合计: 95 passed ✅
```

```
$ bash tools/ci_grep_gates.sh
[gate a] ... ok
[gate b] ... ok
[gate c] ... ok
ci_grep_gates: all gates passed ✅

$ git diff --check
(无输出) ✅
```

---

## Sidecar 生成

Sidecar 命名格式: `reports/<stock>_<date>_peer_comparison_material.json`

- 由 `assembly_skills.py:run()` → `_persist_peer_comparison_material()` 持久化
- 行为: 仅当 `rows` 非空时写入
- 模式: 复制 `_persist_industry_relevance_manifest` 的设计
- 路径: 设置到 `ctx["peer_comparison_material_path"]`
- 未 smoke 运行（无 Chrome/CDP/Playwright，无雪球）

---

## Blocker / Warning / Deviation

### Blocker: 无

### Warning: 无

### Deviation: 无

所有实现严格遵循 Phase 3b 边界：
- ❌ 未修改 `knowledge_synthesizer.py`
- ❌ 未修改任何 LLM prompt 文本
- ❌ 未修改 deep_analysis renderer 行为
- ❌ 未修改 scoring/risk/technical 算法
- ❌ 未使用 Chrome/CDP/Playwright/雪球
- ❌ 未手工修改 `reports/*.md`

---

## 设计决策

### 1. `source_items` 参数当前未使用

`build_peer_comparison_material()` 签名接受 `source_items` 参数，但 Phase 3b 仅从 `competitor_metrics` 构建 rows。这是有意的：
- `competitor_metrics` 是确定性、格式化、可直接比较的数据
- `source_items`（formal source titles/snippets）需要额外的 NLP 或模式匹配来提取 peer 引用
- Phase 3c 或后续迭代可以在不改变 API 签名的情况下为 full source_items 填充提供空间

### 2. Confidence formula 简化

由于 competitor_metrics 不携带 period/unit 元数据，所有 metric-based rows 的基础置信度为 0.85。如果后续阶段添加 period 差异检测或 source_items 比较，`_compute_confidence()` 已接受 `periods_differ` 等调整参数。

### 3. Quality gate 扫描范围

- `stronter_peer_superlative` 和 `peer_claim_without_peer_pack` 仅扫描 4.1 和 4.2 章节
- `peer_pack_social_leak` 扫描 sidecar JSON（不扫描报告文本）
- 4.4 display-only 章节排除（`test_no_peer_gate_false_positive_on_44_display_only` 已验证）

### 4. Section 提取方式

复用现有的 `_extract_deep_analysis_subsection()` 函数来提取 4.1 和 4.2 章节——这一函数原为 4.3 编写，现已证明在 4.1/4.2 上也能稳健工作。

---

## Git Status

```
 M scripts/utils/report_quality.py
 M scripts/utils/report_skills/assembly_skills.py
 M scripts/utils/report_skills/synthesis_skills.py
 M tests/reporter/test_assembly_skills.py
 M tests/reporter/test_report_quality.py
?? scripts/utils/peer_comparison_material.py
?? tests/utils/test_peer_comparison_material.py
```

无计划外的修改或文件。

---

## Codex 验收补充

Codex 复核时补了一个窄范围 quality gate 缺口：

- `peer_pack_social_leak` 现在不仅拦截 `雪球:` / `知乎:` / `微信:` / `精选外部:` / `社区:`，也会拦截不在允许列表中的未知来源前缀。
- 新增测试 `test_peer_pack_unknown_source_prefix_is_error`。
- 将 `test_peer_claim_without_peer_pack_warns` 改为纯弱比较词场景，避免用 strong error 间接覆盖 weak warning。

最终验证：

```text
PYTHONPATH=/Users/erichan/testsnow/scripts:/Users/erichan/testsnow/scripts/utils python3 -m pytest tests/utils/test_peer_comparison_material.py tests/reporter/test_assembly_skills.py tests/reporter/test_report_quality.py tests/reporter/test_peer_config.py tests/reporter/test_data_fetcher_peers.py tests/reporter/test_data_skills.py tests/reporter/test_valuation_renderer.py tests/reporter/test_stock_reporter_source_intake_config.py -q
# 96 passed

bash tools/ci_grep_gates.sh
# all gates passed

git diff --check
# clean
```

额外观察：

- 当前已有的 `reports/复旦微电_20260702.md` 是 Phase 3b 前生成的旧报告，没有 `*_peer_comparison_material.json` sidecar；因此 `check_report_quality.py` 会因 4.1/4.2 同行比较表达缺少 peer material 支撑而失败。
- 这属于旧报告/新质量门的不匹配。正式验收应重新跑一次复旦报告入口，让 pipeline 自然生成 peer material sidecar 后再检查报告。
