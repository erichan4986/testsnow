# Annual Producer v2 Admission Repair: Codex Notes

## Verdict

`needs_revision`

Producer v2 的 source-only admission、usage-primary 路由和 seed/continuation bundling 已完成并通过代码测试；但八股本地缓存 recovery gate 仍未归零，因此本轮不允许删除 v1 adapter，也不生成正式报告。

## Implementation

- `periodic_report_narrative_evidence_cards.py`
  - 使用共享 `canonical_family_for_usage`、`has_concrete_annual_anchor` 和 whitespace normalization。
  - 采用 usage-primary + 强财务解释 override。
  - 将 source unit 分为 seed / continuation / noise，按同 family、相邻原文顺序合并。
  - 加入 A 股 checkbox 因果尾句、港股隐含主体和明确 technology-product anchor 规则。
  - 删除旧的 signal-only continuation selector、usage fallback 表和未使用 bundle signal 状态。
  - 对 `hk_market_outlook` 保留一个窄的港股商业化首句路由，避免后续客户/量产句被拆散。
- `annual_argument_schema.py`、`periodic_report_evidence_pack.py`、`annual_report_material_pack.py`
  - 继续使用上一批共享 schema、SourceUnit 和 v1 coverage proof 实现。
- tests
  - 新增港股 market bundle 回归测试和五支受影响股票的 source-only fixture。

## Verification

- annual/schema/evidence/producer/material-pack tests: `264 passed`
- reporter renderer/quality/source-boundary tests: `187 passed`
- `bash tools/ci_grep_gates.sh`: passed
- `git diff --check`: passed
- Runtime delta relative to `aa7bdd9`: `+270` lines, exactly at the absolute hard limit; no budget increase。

八股刷新只使用本机缓存 `/Users/erichan/testsnow/data/raw/periodic_reports`，未联网：

| 股票 | exact shadowed | unit covered | needs recovery | adapter use |
| --- | ---: | ---: | ---: | ---: |
| 黑芝麻智能 | 4 | 17 | 7 | 7 |
| 长春高新 | 0 | 0 | 0 | 0 |
| 三花智控 | 0 | 0 | 0 | 0 |
| 中简科技 | 2 | 13 | 8 | 8 |
| 圣邦股份 | 4 | 15 | 7 | 7 |
| 乐鑫科技 | 2 | 10 | 14 | 14 |
| 中际旭创 | 4 | 6 | 3 | 3 |
| 复旦微电 | 0 | 0 | 0 | 0 |

## Stop Condition

`v1_needs_recovery_count` 对五支股票仍大于零。缺口包括港股商业化/毛利率中间句、A 股现金流 checkbox 前缀、研发人员表格和部分风险/平台论证段落。它们尚未被当前 v2 SourceUnit 精确覆盖，不能把 v1 adapter 当作已安全删除。

- Batch B: `no`
- 正式报告生成: skipped
- v1 note 归档/删除: skipped
- 评分、目标价、风险、技术面、推荐、LLM prompt、采集逻辑: 未修改
