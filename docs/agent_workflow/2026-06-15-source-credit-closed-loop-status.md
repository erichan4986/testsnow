# Source Credit Closed-Loop Status

日期：2026-06-15

## 当前结论

中简科技已经跑通一条可验收的单股证据闭环：

`Source Intake / 社区低信用 claims -> evidence notes / low-credit notes -> claim verification -> structured risk signals -> report risk section`

当前闭环是保守可用状态：

- 高信用官方公告可验证低信用社区 claim。
- 中信用新闻/券商研报只作为专业观察和背景线索，不直接变成官方事实。
- 低信用雪球/股吧 claim 不互相验证；未被高信用证据验证前不进入风险因子表。
- Source Intake 章节和 Agent-Reach 章节仍是只读展示层，不直接参与评分、技术面、EV 或最终建议。

## 中简科技当前证据状态

最近一次只读 claim audit：

- 文件：`docs/agent_workflow/2026-06-15-中简科技-closed-loop-claim-audit.md`
- high_credit_claims：11
- low_credit_claims：13
- verified：3
- supported：0
- unverified：10
- needs_review：0

Verified 的 3 条均来自低信用社区 claims，并由高信用 `2026年第一季度业绩预告` 验证：

1. 研发费用 1.18 亿元，同比增长 37.02%
2. 产品需求阶段性减少导致发货暂时减少，收入下降约 50%-60%
3. 研发费用同比增长约 175%-185%

Fresh 东财股吧两条新鲜 claim 仍保持 unverified：

- `股吧帖子：中简科技中简护城河还是比较深的...`
- `股吧帖子：中简科技中复神鹰9亿股本...`

这两条没有进入风险因子表、综合推荐、核心事实或编号引用。

## 报告层当前状态

参考报告：`reports/中简科技_20260615.md`

报告中的 Source Intake 章节：

- 位置：`## Source Intake 分层证据观察`
- 声明：不参与综合评分、风险评分、技术面判断或最终建议
- 分层：
  - 官方公告：8 条，信用 95，`confirmed_fact`
  - 券商研报摘要：8 条，信用 65，`professional_observation`
  - 东方财富新闻：10 条，信用 60，`professional_observation`

报告中的风险因子表：

- 情绪过热：+1.5
- 技术破位：+1.0
- 业绩预期下调：+1.5，来源 `claim_verification / verified`
- 盈利压力：+1.0，来源 `claim_verification / verified`

关键一致性：

- 技术面：下降趋势 / 破坏期，趋势健康度 29/100
- 风险等级：5.0/10，中等风险
- 仓位建议：趋势破坏期，以观望或防守仓位为主，建议 0-5%
- AI 综合推荐：N/A，未给出强推

当前未发现明显“技术弱但建议强买”的矛盾。

## 已完成能力

### 高信用来源

- 巨潮公告 / 官方公告通过 Source Intake 写入 evidence notes。
- 可作为 `confirmed_fact`。
- 可验证低信用社区 claims。

### 中信用来源

- 东方财富新闻、券商研报摘要进入 Source Intake 观察层。
- 统一作为 `professional_observation`。
- 不直接变成官方事实。

### 低信用来源

- 已有雪球缓存社区 claims。
- Fresh Eastmoney Guba 直连 smoke 已实现，默认 dry-run，显式 `--write` 才写入。
- 低信用 source_credit 维持在 30-35。
- claim_status 强制为 `unverified_claim`。

### 风险闭环

- 只有 `verified` / `supported` 且符合 phrase table 的 claim verification 结果才会生成 structured risk signals。
- `unverified` fresh claims 不进入风险评分。
- LLM 自由文本关键词已降级为“风险观察（不计分）”。

## 仍未完成 / 暂不做

### 不继续扩第四只股票

三只股票已经覆盖：

- 黑芝麻智能：Agent-Reach 官方 URL / 港股场景
- 中简科技：Source Intake + fresh social + claim-risk 闭环
- 圣邦股份：Source Intake 第三只 A 股试点

继续扩第四只股票收益不高，优先收敛质量门和闭环稳定性。

### RSS 暂不作为主路径

RSS 暂时保留为可选来源，不作为当前主路径。当前更可靠的是：

- 官方公告
- 东财新闻/研报摘要
- 明确 URL 或明确 provider 的社区来源

### Social media 大平台仍是 inventory 阶段

微博/B站/小红书/YouTube 等社媒源后续应先做 capability inventory，不直接接 pipeline。

## 下一步建议

优先做一个小质量门，而不是继续扩数据源：

**Claim Pollution Quality Guard**

目标：

- 自动检查低信用 fresh/social claim 是否直接出现在核心事实、综合推荐、编号引用或风险因子表中。
- 允许 verified/supported 后通过 `claim_verification` 进入风险因子表。
- 禁止 unverified fresh/social claim 直接污染报告正文关键结论。

建议范围：

- `scripts/check_report_quality.py`
- `tests/reporter/test_report_quality.py` 或现有质量检查测试
- 只读检查，不改 pipeline、不改评分、不改 LLM prompt

验收：

- 中简科技报告应 PASS。
- 人工构造包含 unverified fresh claim 泄漏的报告片段应 FAIL/WARNING。

## 本次操作

本次仅做只读审计和状态文档：

```text
python3 scripts/smoke_claim_verification_audit.py --stock 中简科技 --output docs/agent_workflow/2026-06-15-中简科技-closed-loop-claim-audit.md
```

未运行完整报告，未访问外部网络，未刷新知乎，未抓雪球详情页，未启动 Chrome/CDP。
