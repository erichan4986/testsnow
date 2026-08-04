# Executive Summary Completeness Design

日期：2026-07-13
分支：`codex/annual-producer-v2`

## 1. Problem

`ExecutiveSummaryRenderer` 当前依赖 `synthesis` 文本中的看多/看空抽取。LLM 返回空、提取失败或所有观点被信用过滤后，renderer 仍输出“执行摘要”“核心投资论点”和图表标题，却没有正文。质量门只校验评分与推荐一致性，没有阻止空壳摘要进入正式报告。

此外，renderer 当前把 `synthesis` 列为 required key，并在空字典时直接返回空字符串。该入口契约本身必须收窄为只要求 `stock_name`，否则固定摘要无法覆盖“LLM 完全没有产出”的场景。

中际旭创与复旦微电 2026-07-13 报告均出现该问题。技术、估值、风险和 RecommendationDecision 已有结构化结果，因此执行摘要不应依赖 LLM 才能成立。

## 2. Goal

每份具备 RecommendationDecision 或基础评分数据的报告，必须确定性输出：

1. 基本面判断；
2. 估值与业绩预期；
3. 交易状态与风险；
4. 一句话结论。

LLM 看多/看空提取保留为补充。LLM 失败、返回空或观点被信用门全部过滤时，不影响四部分正文。

## 3. Non-goals

- 不修改 `KnowledgeSynthesizer` prompt 或 LLM 合成逻辑；
- 不修改技术状态机、技术指标、评分、目标价或风险评分；
- 不修改 Chapter 4、MaterialSnapshot 或 citation allocator；
- 不在本批接入 4.3 外部待验证变量；
- 不重新计算 RecommendationDecision 已拥有的推荐、EV、仓位或风险结论。

Technical Analysis v2、Chapter 4 Editorial Memo 和 Evidence Freshness Adaptation 记录在总路线图中，分别实施。

## 4. Output Contract

### 4.1 Fixed deterministic body

`ExecutiveSummaryRenderer.render()` 在评分标题后始终输出以下正文标签：

- `**基本面判断**`；
- `**估值与业绩预期**`；
- `**交易状态与风险**`；
- `> **一句话结论**`。

四部分不得依赖 `_llm_extract_thesis()` 成功。已有“看多/看空”列表继续放在固定正文之后，图表继续作为最后的补充展示。

`required_keys()` 只返回 `stock_name`。`synthesis_display` 与 `synthesis` 均缺失或为空时按空字典处理，固定正文仍需生成；只有 `stock_name` 缺失时允许返回空字符串。

### 4.2 Input precedence

#### 基本面判断

1. 优先使用 `core_facts` 中已有高信用、可展示的正式事实；
2. 无可展示 core fact 时，使用 `pillar.fundamental` 描述模型当前基本面强弱，并明确“尚未形成可由高信用来源支撑的核心事实基座”；
3. 不从未验证 claim、外部观点或自由文本中补数字；
4. 不因证据不足省略该部分。

#### 估值与业绩预期

1. 使用已有 `quote`、`consensus` 和 `pillar.valuation`；
2. 可展示 Forward PE、预期 EPS 增速或“缺少一致预期”的保守说明；
3. 只做显示层格式化，不重新计算目标价或 EV；
4. 缺少一致预期时明确写“估值判断证据不足”，不得省略。

#### 交易状态与风险

1. 优先使用 `RecommendationDecision.entry_constraint.display_note`、`position_cap_note` 和 `risk`；
2. 本批不直接拼接 `primary_state`、`stage`、技术健康度等可能冲突的技术状态字段；
3. 若 decision 不存在，则使用已有 pillar technical/risk 数据形成保守说明；
4. 不从 Chapter 4 外部材料生成风险评分结论。

#### 一句话结论

1. RecommendationDecision 存在时，直接使用 `recommendation_sentence`；
2. decision 不存在时，使用当前 renderer 已有的评分 fallback，输出“数据不足/保持观望”等确定性保守结论；
3. 不调用新的 LLM；
4. 不允许空字符串。

### 4.3 LLM thesis supplement

- `_extract_thesis_points()` 和现有 formal-thin 信用过滤逻辑保持；
- 有合格观点时继续输出看多/看空列表；
- 无合格观点时不输出空的看多/看空标题；
- LLM 异常必须降级，不能中断固定摘要；
- 外部待验证观点暂不进入摘要。后续只有在能复用完整引用编号时，才允许最多一条明确降级的外部变量进入摘要。

## 5. Quality Gate

在 `report_quality.py` 新增确定性空摘要检查：

1. 仅对包含 `## 一、综合评分与推荐` 的深度报告启用，保留旧轻量技术报告 fixture 的兼容性；
2. 提取 `## 执行摘要` 到下一个二级标题；
3. 忽略评分标题、空标题、图片和图表标题；
4. 至少需要一个在同一行标签冒号后带非空内容的固定正文块，空标签不得借下一行标题误通过；
5. 如果执行摘要只有评分、标题或图片，报告 `empty_executive_summary_body`，severity 为 `error`；
6. 既有 summary/section1 评分、EV 与推荐一致性 gate 保持不变。

该 gate 不判断投资观点质量，不复制信用过滤逻辑，只保证成品不是空壳。

## 6. Files and Responsibilities

允许修改：

- `scripts/utils/reporter/sections/executive_summary_renderer.py`
  - 生成固定摘要正文；
  - 保留 LLM 多空补充和信用过滤；
  - 对缺失输入做确定性保守降级。
- `scripts/utils/report_quality.py`
  - 增加空执行摘要正文 gate。
- `tests/reporter/test_executive_summary_renderer.py`
  - 覆盖固定正文、LLM 降级、formal-thin 过滤和输入缺失。
- `tests/reporter/test_report_quality.py`
  - 覆盖空壳摘要 error 与正常摘要通过。

本批不新增 runtime 模块，不修改 assembly、synthesis、technical、scoring、price target、risk、Chapter 4 或引用模块。

## 7. Failure Modes

| Failure mode | Visible symptom | Test / gate |
|---|---|---|
| LLM 返回空 | 摘要只剩标题 | renderer empty-LLM fixture + quality gate |
| `synthesis` 键缺失 | assembly 跳过 renderer | required-keys + missing-synthesis fixture |
| LLM 抛异常 | 报告生成中断或摘要为空 | renderer exception fixture |
| formal-thin 观点全部被过滤 | 无正文 | formal-thin no-core-facts fixture |
| core facts 缺失 | 编造基本面事实或空白 | no-core-facts fixture |
| consensus 缺失 | 估值部分消失 | no-consensus fixture |
| decision 存在但结论漂移 | 摘要与第一章推荐不一致 | RecommendationDecision integration fixture |
| 图片被误认作正文 | 空摘要通过 gate | image-only quality fixture |
| 轻量技术报告被新 gate 误伤 | 既有 minimal fixture 失败 | legacy-lightweight compatibility test |
| 旧信用过滤回归 | 外部/未验证看多事实进入摘要 | existing formal-thin tests |

## 8. Requirement-Test Matrix

| Requirement | Implementation location | Verification |
|---|---|---|
| 四部分固定正文始终存在 | `ExecutiveSummaryRenderer.render()` | renderer basic / empty-LLM tests |
| 空 synthesis 仍进入 renderer | `required_keys()` + empty-dict fallback | missing-synthesis test |
| 无 core facts 不编造 | deterministic fundamentals helper | no-core-facts test |
| 无 consensus 仍有估值说明 | deterministic valuation helper | no-consensus test |
| decision 结论唯一 | deterministic conclusion helper | decision integration test |
| LLM 只作补充 | existing thesis extraction path after fixed body | empty/exception LLM tests |
| formal-thin 信用边界保持 | existing filters | existing + focused regression tests |
| 空壳摘要阻塞验收 | `report_quality.py` | image-only/title-only error tests |
| 正常摘要不误报 | `report_quality.py` | complete-summary pass test |
| 旧轻量报告不误报 | deep-report scope guard | existing minimal fixture test |

## 9. Test Plan

Focused tests：

```text
tests/reporter/test_executive_summary_renderer.py
tests/reporter/test_report_quality.py
tests/reporter/test_recommendation_decision.py
```

Downstream regression：

```text
tests/reporter/test_html_dashboard_renderer.py
tests/reporter/test_fulltext_material_isolation.py
tests/reporter/test_report_source_boundary.py
```

完成代码级测试后，由正式入口重新生成中际旭创与复旦微电报告，确认：

- 执行摘要四部分均有正文；
- 推荐、EV 和仓位约束与第一章一致；
- formal-thin 未出现无来源看多事实；
- quality/source/prose/citation/CI gates 通过；
- 报告 mtime 晚于源码修改时间。

## 10. Runtime Budget and Stop Conditions

运行时代码目标净增不超过 `+60` 行，硬停止 `+100` 行，tests/docs 不计入。

立即停止并返回设计的条件：

- 需要修改允许范围之外的 runtime 文件；
- 需要修改 assembly、synthesis、technical、scoring、price target、risk 或 citation allocator；
- 需要新增 LLM prompt 或外部请求；
- 需要从低信用观点生成固定摘要事实；
- focused tests 暴露与本批无关的大范围失败；
- runtime 净增超过硬停止预算。

## 11. Decisions Recorded

- accepted：执行摘要固定四部分，LLM 只作补充；
- accepted：真正空摘要为阻塞 error；
- accepted：技术面大改延期到独立 Technical Analysis v2；
- accepted：外部近期变量未来可进入摘要，但必须明确降级且绑定完整引用；
- deferred：freshness-aware 外部材料扩充与 editorial memo；
- rejected：在本批用临时 renderer 文案修补技术状态机冲突。
