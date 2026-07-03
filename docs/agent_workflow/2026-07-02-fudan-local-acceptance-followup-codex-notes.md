# Fudan Local Acceptance Follow-up Notes

Date: 2026-07-02

## Context

本地 Claude Code 验收报告：

```text
/tmp/fudan_local_pipeline_acceptance_20260702.md
```

本地正式入口成功：

- `python3 scripts/run_stock_report.py --stock 复旦微电 --no-pdf`
- exit code: 0
- 16 次 DeepSeek 调用均 200
- `check_report_quality`: PASS, 1 warning
- `check_report_prose_quality`: PASS, 5 warnings
- `check_report_source_boundary`: PASS

已验证通过的 P0/P1：

- MLCC 不再污染 4.1
- 核心事实单位从 `万元` 修正为 `亿元`
- 4.3 不再静默缺失
- 4.2 “未提供营收/利润”矛盾消失
- header 行业/同行不再是 `—`

## New Blocker

`4.3` 出现“财务数据冒充资金面”：

```text
主力资金 | 2026年Q1营收7.82亿元，环比下降 | 可能压制主动买盘
```

这是跨维度 LLM 推断。根因不是单份报告，而是 pipeline 缺少两层保护：

1. `funding_sentiment` prompt 仍能看到公告/财务类 item。
2. `report_quality` 只拦截“净流入/净流出 + 万元”的资金流向句，漏掉“营收/利润 -> 主力资金/买盘”的推断。

## Fix

### Prompt/Input Guard

File:

```text
scripts/utils/knowledge_synthesizer.py
```

Changes:

- `funding_sentiment` prompt 新增硬约束：
  - 缺少资金流向、融资余额、持仓结构或交易情绪数据时，只能写资金面数据缺失。
  - 不得用营收、利润、毛利率等财务数据推测主力资金、买盘、卖盘或资金流入流出。
- `_filter_items_for_theme()` 对 `funding_sentiment` 增加资金/持仓/交易情绪白名单。
- 财务公告如一季报营收/净利不再进入资金面 prompt。
- 回购/增持/减持/融资/北向/成交/龙虎榜等仍允许进入资金面。

### Quality Gate

File:

```text
scripts/utils/report_quality.py
```

Changes:

- `_check_fundflow_claims()` 不只检查“净流入/净流出 + 万元”。
- 新增对以下模式的拦截：
  - 主力资金/资金面/买盘/卖盘 + 压制/支撑/推升/流入/流出
  - 营收/收入/利润/毛利率/订单 + 主力资金/买盘/卖盘/资金面
- 若没有 `fundflow_material_pack` sidecar rows，则报：
  - `fundflow_claim_without_fundflow_pack`

## Regression Tests

Added:

```text
tests/utils/test_knowledge_synthesizer.py::test_funding_sentiment_prompt_excludes_financial_announcement_without_fundflow_pack
tests/reporter/test_report_quality.py::test_fundflow_claim_without_sidecar_catches_financial_data_inferred_buying_pressure
```

The two tests failed before the fix and pass after the fix.

## Verification

```text
python3 -m pytest tests/utils/test_knowledge_synthesizer.py tests/reporter/test_report_quality.py tests/reporter/test_synthesis_skills.py tests/utils/test_fundflow_material.py tests/utils/test_source_adapter.py -q
# 170 passed

python3 -m pytest tests/utils/test_periodic_report_explanation_pack.py tests/reporter/test_periodic_report_fulltext_intake_skill.py tests/utils/test_curated_external_viewpoint_narrative.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_report_quality.py tests/utils/test_fundflow_material.py tests/reporter/test_technical_skills_contract.py tests/utils/test_source_adapter.py -q
# 240 passed

bash tools/ci_grep_gates.sh
# all gates passed

git diff --check
# clean
```

## Remaining Non-blocking Findings From Local Acceptance

- 4.2 年报经营解释没有明显进入正文，需要下一轮本地报告确认 prompt 是否真正生效，或检查 annual report explanation pack 是否有 rows。
- 4.1 产品/同行对比仍偏数字化，Batch B peer business comparison pack 仍待做。
- 4.4 reasoning cards 仍未显示，可能是 narrative JSON 尚未包含 `reasoning_cards`。
- 4.1 供应链变量有部分改善，但仍偏泛。

## Recommendation

修复这个 blocker 后，建议再由本地 Claude Code 重跑一次复旦报告验收。若 `4.3` 不再用财务数据推断买盘/主力资金，可进入按包拆 commit；否则继续修 `funding_sentiment` 过滤或 renderer fallback。
