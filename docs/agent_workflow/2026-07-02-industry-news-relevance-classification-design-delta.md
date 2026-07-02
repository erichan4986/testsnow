# Design Delta — Industry News Relevance Classification

## Accepted

- 采纳 MF1：4.3 synthesis input 必须硬过滤，只保留 `allowed_sections` 包含 `4.3` 的条目；不再把 `sector_background/noise` 交给 LLM 后靠 prompt 要求它不用。
- 采纳 MF2：增加 chain match validation。设计改为报告生成时输出 industry relevance sidecar manifest，`check_report_quality.py` 可用 manifest 对 4.3 因果链做 canonical chain 匹配。
- 采纳 MF3：补充强确认词列表和链条/审慎词列表，作为 quality gate 的稳定输入。
- 采纳 MF4：补充置信度阈值策略：`>=0.70` 正常进入 4.3，`0.40-0.70` 只能审慎表达，`<0.40` 降级为 `sector_background`。
- 采纳 N1/N2：`relevance_chain` 改为 `chain_id + hops`，chain_rules 改为支持 N-hop 的 `hops` 序列，不再限制为 `from/through/to` 三段。

## Deferred

- 不在本轮验证产业链经济合理性，只验证“4.3 文本是否越过 helper/config/news 支撑链条”。
- 不新增 LLM 分类调用；如 deterministic helper 置信度不足，则降级，不让 LLM 补链。
- `sector_background` 进入 4.1 的长度约束保留为后续 prose/topic ownership 优化，不作为 Batch 2b P0。

## Rejected

- 无。

## R2 Required

No.

原因：Round 1 没有 blocker；四个 must-fix 均已转成明确可测试的设计约束。下一步可先实现 helper + fixture tests，再接入 synthesis hard filter 与 chain validator。
