# 复旦微电 Evidence Depth Pipeline - Codex Notes Batch A/C/E

Date: 2026-07-02

## Scope

本轮只处理 pipeline 能力，不手改 `reports/复旦微电_20260702.md`。

- Batch A: 年报经营解释材料包，供 4.2 使用。
- Batch C: 4.4 外部观点 reasoning cards 保真展示。
- Batch E: evidence depth warning gates，捕获“安全但空泛”的输出。

## Batch A - Formal Financial Explanation Pack

新增 `scripts/utils/periodic_report_explanation_pack.py`，从年报全文缓存中抽取经营解释而不是只复述财务数字。输出 schema 为 `formal_financial_explanation_pack.v1`。

覆盖主题：

- `revenue_change`
- `profit_change`
- `gross_margin_change`
- `expense_rnd`
- `inventory_cashflow`
- `orders_customers_guidance`

关键保护：

- 优先抽取 `营业收入变动原因说明`、`利润变动原因说明` 等明确解释段。
- 排除风险因素章节。
- `source_excerpt` 控制在 220 字以内。
- 对复旦微电 2025 年报缓存实测，`revenue_change` 抽到的是“安全与识别芯片、智能电表芯片及 FPGA 销售额增加所致”，没有误抓“研发投入占营业收入比例”表格噪声。

集成位置：

- `periodic_report_fulltext_intake_skill.py` 构建并写入 `ctx["periodic_report_explanation_pack"]`
- `synthesis_skills.py` 注入 `all_data["formal_financial_explanation_pack"]`
- `knowledge_synthesizer.py` 仅在 `fundamentals` 主题加入 4.2 prompt 附录

Prompt 样例：

```text
正式经营解释材料包（仅供4.2使用，非新增引用）
- 营业收入/revenue_change: 主要系报告期内公司的安全与识别芯片、智能电表芯片及FPGA销售额增加所致。

写作要求：
- 4.2 优先解释营收、利润、毛利率变化原因，不要把核心事实基座里的财务数字重复成表。
- 如果材料包已有订单、客户、管理层指引片段，不要写“未提供订单/客户/指引”。
```

## Batch C - 4.4 Reasoning Cards

4.4 narrative 现在可以携带 `reasoning_cards`，用于保留雪球/知乎好文中的推理链条、数字、假设和反方约束。

关键保护：

- 所有 cards 必须能映射到有效 citation，否则丢弃。
- `source_excerpt` 最长 200 字，超长截断并标记 `excerpt_truncated`。
- reasoning cards 仍只进入 4.4 display-only，不进入 4.1-4.3、评分、风险或目标价。

集成位置：

- `curated_external_viewpoint_narrative.py` 保留 composer 返回的 `reasoning_cards`
- `synthesis_skills.py` 归一化并写入 `_curated_external_reasoning_cards`
- `deep_analysis_renderer.py` 在 4.4 中渲染：
  - `观点`
  - `原文片段`
  - `推理步骤`
  - `关键数字`
  - `关键假设`
  - `反方约束`
  - `待验证项`

注意：当前已落盘的复旦 `data/curated_external/viewpoint_narratives/fudan_20260702.json` 如果仍是旧 schema、没有 `reasoning_cards`，正式报告不会自动出现 cards；需要后续重新跑 narrative composer 或补齐 narrative JSON。

## Batch E - Evidence Depth Warnings

`report_quality.py` 新增 warning-only 检查，不作为 blocker：

- `section_too_generic`: 4.1/4.2/4.3 出现模板化空话且缺少数字、日期、引用、产品名或公司名。
- `vague_supply_chain_position`: 供应链位置只有泛泛表述，没有供应商、客户、产能、库存、价格、交付等经营变量。
- `fundamentals_repeats_core_facts`: 4.2 只重复营收/利润/毛利率等数字，没有管理层解释。
- `external_viewpoint_overcompressed`: 4.4 有外部观点但缺少 reasoning card 标记，提示观点被过度压缩。

这些 warning 用来防止下一只股票又出现“看起来合规、但内容空”的报告。

## Verification

Focused regression:

```text
python3 -m pytest tests/utils/test_periodic_report_explanation_pack.py tests/reporter/test_periodic_report_fulltext_intake_skill.py tests/utils/test_curated_external_viewpoint_narrative.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_report_quality.py tests/utils/test_fundflow_material.py tests/reporter/test_technical_skills_contract.py tests/utils/test_source_adapter.py -q
```

Result: `238 passed`.

Gates:

```text
bash tools/ci_grep_gates.sh
git diff --check
```

Result: both clean.

## Runtime Caveat

在 Codex 沙箱里尝试正式跑：

```text
set -a; . ./.env; set +a; python3 scripts/run_stock_report.py --stock 复旦微电 --no-pdf
```

入口退出码为 0，但网络、DNS、LLM/API、行情接口和 Chrome/Kaleido 均出现连接失败，因此生成的 `reports/复旦微电_20260702.md` 是降级报告，不适合作为人工审稿版本。

质量检查结果：

- `check_report_quality.py`: FAIL，原因是 `missing_daily` / `missing_weekly` / `missing_volume` / `missing_volatility`
- `check_report_prose_quality.py`: PASS
- `check_report_source_boundary.py`: PASS

结论：代码级 Batch A/C/E 已通过 focused tests 和 gates；正式复旦报告需要在本地有网络/API/LLM/Chrome 环境下重新生成后再验收。

## Remaining Pipeline Work

- Batch B: 更强的同行业务/产品基本面对比材料包，还未完成。本轮只保证已有 peer metric 与 4.4 reasoning card 能被更好地使用。
- 复旦 4.4 reasoning cards 需要重新生成 narrative JSON，才能从“观点摘要”升级到“推理链条保真展示”。
- 复旦正式报告需本地重跑，避免使用本轮沙箱网络失败覆盖出来的降级 Markdown。
