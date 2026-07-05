# Theme Material Budget Review Round 1

Verdict: **proceed**（可实施，有 3 个 must-fix 和 1 个风险点需确认）

## Summary

设计在根本原理上正确：当前 `KnowledgeSynthesizer._build_prompt()`（line 297）重复调用 `_filter_items_for_theme()`，且用局部编号 `enumerate(i + 1)` 给每个主题的 items 重新编号（line 298-299），而 `SynthesisSkill._fill_citation_metadata()`（synthesis_skills.py line 904）用 `items[ref_id - 1]` 直接从全局 items 列表查找——编号错位是真实bug，不是理论风险。

全局 source-id material budget 通过一次构建（`_build_theme_material_budget()`）、`_build_prompt()` 消费预计算数据（不再重新过滤）、全局编号（`ref_id` 直接等于 items 列表中的下标）解决了这组耦合问题。

实现范围控制在 3 个文件（`knowledge_synthesizer.py`、`synthesis_skills.py`、`curated_external_viewpoint_narrative.py`），不作新文件、不碰 renderer、不碰 quality gates，符合最小替换原则。

**确认 bug：双重过滤 + 局部重编号**
- `synthesize()` line 202: `theme_items = self._filter_items_for_theme(...)` → 过滤后遍历
- 同一 `theme_items` 传入 `_synthesize_theme()` → `_build_prompt()` line 297: `self._filter_items_for_theme()` **再次过滤**→ 结果可能不同（`_filter_items_for_theme` 不是纯函数，依赖 `stock_config` 和 `theme_key`，两次调用的 `items` 长度不同）
- Line 298-299: `for i, item in enumerate(theme_items): source_lines.append(format_synthesis_source_line(i + 1, item))` → 编号是 1-based 的局部编号
- `_fill_citation_metadata()`（synthesis_skills.py line 904）: `item = items[ref_id - 1]` → 用局部编号查找全局列表 → **错位**

**确认 fundflow 数据丢弃**：`synthesis_skills.py` line 867 当 `fundflow_material_pack` 存在时 `fundflow=[]`，所有原始 fundflow 数据被丢弃，4.3 prompting 中没有任何可引用的实际资金流向 items。

## Must-Fix

### MF1: budget 的 `source_refs` 必须严格按 theme 隔离 fundflow items

**Evidence**: `_build_theme_material_budget()` 的 `source_refs` dict 按 theme_key 分配 items IDs。设计说 "if the only eligible funding materials are missing, funding_sentiment should be skipped"，但没说明当 fundflow items 存在时如何防止它们漏入 `events_catalysts` 或其他 theme。

**Why it matters**: 当前 `_filter_items_for_theme()` 对 `events_catalysts`（line 484-505）没有 `_is_funding_sentiment_item()` 式过滤——只有 `allowed_sections` 检查和 `is_industry_news` 阻断。Fundflow items 的 `source_platform="资金流向"` 既不触发 `is_industry_news = True`（不是"行业资讯"/mainstream_media），如果没有 `allowed_sections` 约束就会透传到 `events_catalysts` prompt。

**Required change**: 在 `_build_theme_material_budget()` 中，fundflow items 必须被显式分配给 `funding_sentiment` 或从其他所有 theme 的 `source_refs` 中排除。不能在 budget 中留空让下游 `_filter_items_for_theme` 兜底——因为 budget 的目标就是**替换**下游过滤。

### MF2: supply_chain_state (`has_operating_variable`) 的判断标准要与报告质量门的 `_OPERATING_VARIABLE_TERMS` 一致

**Evidence**: 设计引入了 `supply_chain_state.has_operating_variable` 字段，但没定义 `matched_terms` 从哪里来。`report_quality.py` line 631-645 已有 `_OPERATING_VARIABLE_TERMS`（供应商、客户、产能、供需、库存、存货、订单、价格、交期、采购、备货、交付、产量）。`_check_vague_supply_chain_position()`（line 693-711）会用这些 term 检测 4.1 供应链位置表达是否空泛。

**Why it matters**: 如果 budget 用不同的 term 集合检测 operating variables，会出现 budget 认为 "有操作变量" 但 quality gate 认为 "没有" 的矛盾。或者反之：budget 说 "无变量" 所以 LLM prompt 被限制，但 quality gate 仍然用同样的标准检查一遍（重复劳动或冲突）。

**Required change**: 要么在 `_build_theme_material_budget()` 中直接复用 `_OPERATING_VARIABLE_TERMS`（跨模块导入或提取到共享常量），要么在实现任务中明确注明两组 term 的关系和同步要求。

### MF3: explanation pack 的 appendix 顺序设计没有确保 4.2 优先使用经营解释

**Evidence**: 设计说 pack ordering 为 `[explanation_pack, fact_pack, peer_metrics]`，但这仅在 budget 的 `appendices` 字段中标记。实际 appendix 的插入顺序由 `_build_prompt()` line 315-325 控制，当前顺序是 `peer_appendix` (line 310) → `fact_pack` (line 315) → `explanation_pack` (line 320)。

**Why it matters**: 如果 `_build_prompt()` 仍然保留自己的逻辑顺序（不读取 budget 的 `appendices`），就会出现 budget 说 "先 explanation 后 fact" 但实际 prompt 中 fact_pack 出现在 explanation_pack 之前。LLM 看到数字在前、解释在后，可能优先重复数字而不是优先使用解释。

**Required change**: `_build_prompt()` 中 appendix 的插入逻辑（lines 309-330）必须改为读取 budget 的 `appendices` 字段顺序，而不是硬编码的 theme_key 判断顺序。或者退一步：在当前 `_build_prompt()` 中手动把 explanation_pack 的插入移到 fact_pack 之前，并在注释和设计文档中明确此顺序。

## Nice-To-Have

### N1: 硬编码 `_PEER_STRONG_TERMS` / `_PEER_WEAK_TERMS` 检查也应该考虑 budget 中的 supply_chain_state

**Why**: 当前 `report_quality.py` lines 832-856 的 `_check_peer_comparison_quality()` 独立于 KnowledgeSynthesizer 运行。如果 budget 已经约束了 LLM 不写强同行比较表达（因为缺少高 confidence 的 peer rows），但 quality gate 仍然因为同样的并行问题发出 warning，就会造成 confusion。这不是阻塞问题，因为 quality gate 的 warning 比 budget 的 prompt 约束更保守（宁可多报警）。

### N2: `funding_sentiment` 的 `requires` 字段应定义完整的 SKIP 信号链

**Why**: 设计用 `requires: "fundflow_or_position_or_trading_sentiment"` 和 `skip_reason` 表示跳过。应该明确这个字段的值如何与 `min_items=3` 协作：
- `requires` 不满足 → 无论 item count 多少都跳过 → budget 层面阻断
- `requires` 满足但 items < 3 → min_items 跳过后备
两者应该都是 skip，但 `requires` 的 skip 更快（不等到 LLM call 阶段）。
最好实现一个统一的 `_should_skip_theme(budget, theme_key, items)` 方法。

### N3: `_legacy_llm_synthesize()` 应显式标记为 frozen 并添加弃用 warning

**Why**: `synthesis_skills.py` line 828-840 的 legacy 路径完全绕过 KnowledgeSynthesizer budget，使用自己的 `self.llm_client.chat()`。如果不处理，后面修改 budget 的开发者可能不知道这条路径。在函数开头加 `logger.warning("legacy_llm_synthesize is deprecated, use KnowledgeSynthesizer with budget")` 即可。

## Blocker

### B1: 无（设计不阻塞实施）

设计原理正确，核心 bug（双重过滤 + 局部重编号）确实存在且能通过 budget 一次性修复。无架构性阻止因素。

## Replacement / Freeze Assessment

| Old path | Proposed handling | Verdict | Notes |
| --- | --- | --- | --- |
| `KnowledgeSynthesizer._filter_items_for_theme()` called twice | Budget builds once → `_build_prompt()` receives `source_rows`, not `items` | ✅ Replace | **关键变更** — 必须确保 `_build_prompt()` 不再调 `_filter_items_for_theme()` |
| `_build_prompt()` local `enumerate(i + 1)` numbering | Use global `ref_id` from budget's `source_refs` | ✅ Replace | LLM prompt 中显示 `[5]` 而不是 `[1]`（当 global index 是 5 时） |
| `_build_prompt()` hardcoded appendix order | Read `appendices` from budget (or keep current order but verify match) | 🔶 Conditional replace | MF3 已提示 |
| `synthesis_skills.py` line 867 `fundflow=[]` | Keep raw fundflow when pack exists, route via budget per-theme | ✅ Replace | Must fix MF1 isolation |
| `_fill_citation_metadata()` global `items[ref_id-1]` | Ref_id matches global index → works correctly | ✅ Implicitly fixed | 无需额外代码修改 |
| `_legacy_llm_synthesize()` | Do not modify | 🔶 Freeze | N3 建议加弃用 warning |
| `heuristic_narrative_composer()` no reasoning_cards | Add reasoning_cards to output schema | ✅ Replace | 35-50 lines change |
| `_default_prompt()` paragraph-only output | Require both `paragraphs` and `reasoning_cards` | ✅ Replace | Producer schema change only |

## Test Gaps

Current test coverage for proposed changes: **❌ No tests exist** for any of the 8 defined failure modes.

| Failure Mode | Test Name (from design) | Needed | Priority |
| --- | --- | --- | --- |
| FM1: Local numbering remains | `test_theme_budget_uses_global_source_refs` | New | P0 |
| FM2: Double filtering still exists | `test_build_prompt_uses_precomputed_source_rows_without_refiltering` | New | P0 |
| FM3: Fundflow pack but no citable sources | `test_fundflow_pack_keeps_citable_fundflow_sources` | New | P0 |
| FM4: Financial anns enter funding prompt | `test_no_fundflow_no_funding_sentiment_even_with_financial_announcements` | New | P0 |
| FM5: Events/catalysts vanish with funding missing | `test_events_catalysts_can_render_when_funding_missing` | New | P0 |
| FM6: Explanation pack loses priority | `test_fundamentals_prompt_orders_explanation_before_fact_pack` | New | P1 |
| FM7: Supply-chain prose invents specifics | `test_supply_chain_state_blocks_generic_position_without_operating_variables` | New | P1 |
| FM8: Paragraph-only 4.4 JSON | `test_default_viewpoint_narrative_prompt_requires_reasoning_cards` + `test_heuristic_narrative_composer_emits_reasoning_cards` | New | P1 |

Additional missing tests:

- **Budget-theme isolation**（来自 MF1）: `test_budget_routes_fundflow_items_only_to_funding_sentiment`
- **Budget-fallback interaction**（来自 N2）: `test_requires_flag_skips_before_min_items_check`
- **Appendix ordering from budget**（来自 MF3）: `test_budget_appendices_control_prompt_order`
- **Regression: existing tests must still pass** — 现有 40+ 个 test in `test_knowledge_synthesizer.py` 和 50+ 个 in `test_synthesis_skills.py` 必须全部通过。特别需要关注那些直接调用 `_build_prompt()` 的测试（约 30 个），因为 `_build_prompt()` 的签名会变化（添加 `source_rows` 参数或改变 `items` 语义）。

## Line Budget Risk

**预计增量：105-140 lines（runtime），安全。**

| File | Design target | Estimated actual | Risk |
| --- | --- | --- | --- |
| `knowledge_synthesizer.py` | +70 to +120 | +66 to +80 | Low — 核心方法 ~45行，修改 synthesizer + _build_prompt ~25行，supply_chain 检测 ~15行 |
| `synthesis_skills.py` | +5 to +20 | +4 to +10 | Low — 只需改 line 867 和加 fundflow 条件 |
| `curated_external_viewpoint_narrative.py` | +35 to +60 | +35 to +50 | Medium — 需改 `_default_prompt()` 和 `heuristic_narrative_composer()` 的 output schema，还要加 `reasoning_cards` 字段验证 |
| `deep_analysis_renderer.py` | 0 | 0 | ✅ 不需改 |
| `report_quality.py` | 0 | 0 | ✅ 不需改 |

**风险最高的条目**: `curated_external_viewpoint_narrative.py` +35-60。`LLM` narrative composer 的 `response_format={"type": "json_object"}` (line 212) 强制 LLM 输出 JSON，但 schema 约束靠 prompt 而非 `response_format` 的 JSON Schema 参数。要求同时输出 `paragraphs` 和 `reasoning_cards` 会让 LLM 输出更复杂的 JSON，增加 parse failure 概率 (已经被 `_extract_json()` 包装为 `NarrativeComposerError`)。建议测试时覆盖 LLM 省略 `reasoning_cards` 的场景。

**Hard stop 可行性**：设计定义的 8 个 stop condition — `section_materials.py`、section-material sidecar、social-to-canonical、new peer pack、renderer-inferred cards、new quality rules、local renumbering、+250 line — 全部可实现且必要。其中 "local per-theme source renumbering" stop condition 是设计的核心约束，实现过程中需反复检查。

## Recommendation

**Proceed.** 设计正确且必要。3 个 must-fix（MF1-MF3）是实施细节，不改变架构方向。

建议实施顺序：
1. **改 `_build_prompt()` 签名 + 加 budget 方法** — 最核心变更，优先做
2. **改 `synthesize()` 循环** — 消费 budget，不再传 raw items
3. **改 `synthesis_skills.py` fundflow 保留** — 简单行内变更
4. **改 `curated_external_viewpoint_narrative.py` 的 composer** — Producer schema 修改
5. **加 8 个 FM 测试** — P0 的 FM1-FM5 必须写，P1 的 FM6-FM8 建议写
6. **跑 `tests/run-all.js`** — 确认现有测试全部通过，特别是 `test_knowledge_synthesizer.py` 中 30+ 个直接调用 `_build_prompt()` 的测试

不建议在本批次额外做的事：
- 多跳产业链推理（design 已明确 non-goal）
- `report_quality.py` 的 warning 家族（non-goal）
- `_legacy_llm_synthesize()` 路径重构（仅加 freeze label）
