# Annual + Broker Memo V1 — Batch 0 笔记

Date: 2026-07-05  
Branch: `codex-report-quality-upgrade`

## 本次范围

Batch 0 目标：
1. 执行 4.1-4.4 相关代码瘦身审计（只读，不大规模删除）。
2. 修复执行摘要中的 PE spread 错配问题。
3. 不实现年报 memo / 研报 memo，不改评分、目标价、推荐、技术面。

## PE Sanitizer 修复

### 修改文件

- `scripts/utils/reporter/sections/executive_summary_renderer.py`
  - 新增 `_build_pe_spread_facts`：从结构化 `peer_comparison_material` 提取 `pe_ttm` 行，计算 `target_pe`、`peer_pe`、`spread_abs`。
  - 新增 `_format_pe`：格式化 PE 数值，最多两位小数并去尾零。
  - 新增 `_rewrite_pe_spread_clause`：当文本中的数字更接近 spread 而非 peer PE 时，把 `PE(TTM)X倍高于<peer>Y倍` 改写成 `<公司> PE(TTM) 为 X 倍，<peer>为 Y 倍，高出约 Z 个 PE 倍数点。`。
  - 新增 `_sanitize_pe_spread_in_text`：遍历 fact 改写；无结构化 metrics 时删除可疑 spread 压缩句。
  - 在 `render()` 中对看多/看空论点及一句话结论调用 sanitizer。
- `tests/reporter/test_executive_summary_renderer.py`
  - 新增 4 个聚焦测试：结构化 metrics 存在时改写、缺失时删除、合法 peer PE 不被改写、原句带股票名前缀时不吞掉股票名。

### 为什么修复位置在 executive_summary_renderer.py

- `peer_comparison_material.py` 已经正确存储了 `target_value`、`peer_value` 和 `comparison`（如 `PE(TTM)高于新易盛15.0倍`）。
- 错配发生在 LLM 压缩执行摘要时：LLM 把 comparison 中的 spread 数字（15）当成 peer PE 写进论点。
- 因此 bug 是**渲染/摘要压缩阶段**引入的，源头数据结构无需修改；在 `executive_summary_renderer.py` 做确定性 sanitizer 最符合设计文档 "Location" 要求，也避免影响其他使用 peer material 的模块。

### 结构化 peer metrics 来源

- `scripts/utils/report_skills/synthesis_skills.py` 调用 `build_peer_comparison_material` 生成 `peer_comparison_material` 并存入 `SkillContext`。
- `scripts/utils/report_skills/assembly_skills.py` 在组装报告时把完整 `ctx` 传给每个 renderer，因此 `ExecutiveSummaryRenderer.render(ctx)` 可直接读取 `ctx.get("peer_comparison_material")`。
- sanitizer 只读取 `rows` 中 `metric == "pe_ttm"` 的行，不修改原始数据结构。

## 4.1-4.4 瘦身审计（rg 只读）

| 候选 | 审计结果 | 依据 |
|------|---------|------|
| visible reasoning-card report rendering path | **需 Batch 3 再判断** | `**观点卡片：**` 可见块已确认不渲染（`deep_analysis_renderer.py:658-659` 注释），但 reasoning_cards 元数据仍被 4.2 外部观点地图、4.3 验证清单、 synthesis stats 使用。gate `_check_external_viewpoint_reasoning_card_templates` 仍作为回归保护存在。 |
| `_curated_external_addendum` / `_curated_external_narrative_addendum` / grouped addendum | **暂不可删** | `_curated_external_addendum` 仍是 4.4 `精选外部观察（Preview）` 的入口；narrative 与 grouped 两条分支均被 `deep_analysis_renderer.py` 和 `assembly_skills.py` 调用，并有对应测试。 |
| `external_viewpoint_reasoning_cards_templated` gate | **需 Batch 3 再判断** | 代码与测试均活跃（`report_quality.py:670/983-1010`、`test_report_quality.py:421/1162`）。设计文档要求等外部地图 gate 完全覆盖 display-only isolation、unverified-claim framing、citation refs 后再删除。 |
| duplicate citation/text normalization helpers | **暂不可删 / 需 Batch 3 再判断** | `sanitize_citation_markers`（`synthesis_credit.py`）与 `_sanitize_citation_markers`（`scoring_engine.py`）功能不同：前者保留 `[^n]` 仅删非法 marker，后者删除所有数字 citation。各 `_normalize_*` 大多领域特定，不能简单合并。 |
| formal-thin temporary fallback branches | **本次未发现可删临时分支** | `rg 'formal_thin.*fallback\|thin.*fallback\|temporary.*thin'` 无命中。当前 `formal_thin_external_rich` 分支是正式路由（`synthesis_skills.py:467-480`、`deep_analysis_renderer.py:250`），非临时 fallback。 |

结论：Batch 0 不满足安全删除条件，瘦身留在 Batch 3 执行。

## Runtime 行数估算

```text
git diff --stat scripts/utils/reporter/sections/executive_summary_renderer.py tests/reporter/test_executive_summary_renderer.py
 .../sections/executive_summary_renderer.py         |  77 ++++
 tests/reporter/test_executive_summary_renderer.py  | 153 ++++
```

- Runtime 净增：**77 行**（`executive_summary_renderer.py`）。
- Tests 净增：**153 行**。
- 未删除 runtime 代码（Batch 0 审计结论是暂不可删）。
- 满足用户 Batch 0 停止条件 `runtime 净增 <= 80 行`；也满足设计文档 V1 预算 `<= 180 行`。

## 测试结果

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_executive_summary_renderer.py tests/reporter/test_deep_analysis_renderer.py tests/reporter/test_report_quality.py -q -p no:cacheprovider
```

结果：`120 passed`

```bash
bash tools/ci_grep_gates.sh
```

结果：all gates passed

```bash
git diff --check
```

结果：clean（无输出）

## Blocker / Warning / Deviation

- **Blocker**：无。
- **Warning**：
  - runtime 净增 77 行，已贴近 80 行上限；后续 Batch 1/2 新增 memo 模块必须通过瘦身或等效删除控制预算。
  - 无结构化 metrics 时 sanitizer 直接删除可疑 PE spread 句，可能导致该论点变短；当前测试已覆盖不保留误导句。
- **Deviation**：
  - 未实现年报 memo / 研报 memo（符合 Batch 0 范围）。
  - 未修改 `peer_comparison_material.py` 数据结构。
  - 未改评分、目标价、推荐、技术面算法。
  - 未运行正式报告入口，未修改 `reports/`、`data/raw/`、`knowledge/`。

## 后续建议

- Batch 1 实现年报 memo 时，优先复用 `periodic_report_evidence_pack` / `periodic_report_narrative_evidence_cards` / `annual_report_material_pack`，并把 memo 状态写入现有 `deep_analysis_evidence_profile`。
- Batch 2 实现研报 memo 时，复用 `broker_research_digest.py` 与 `broker_research_digest_synthesis_items.py`，并应用 design 中的 admission rule。
- Batch 3 再评估 visible reasoning-card 路径与 `external_viewpoint_reasoning_cards_templated` gate 的删除/合并。
