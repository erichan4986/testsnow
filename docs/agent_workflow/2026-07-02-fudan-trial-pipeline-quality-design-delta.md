# Design Delta — 复旦微电 Trial Pipeline Quality

## Accepted

- 采纳 MF1：4.4 citation 修复不只补 `citation_refs`，还必须放宽/标准化 `_normalize_viewpoint_narrative_citations()` 对外部观察 citation source_type 的过滤。设计已补充雪球专栏、雪球评论、知乎精选等 display-only 细分类型的兼容要求。
- 采纳 MF2：market cap sanity 明确采用方案 A，在 `data_fetcher.py` quote 归一化层处理；renderer 只消费归一化结果。
- 采纳 MF3：行业新闻 relevance class 使用 hybrid 策略。intake 层做确定性初筛，synthesis/后处理层只允许有明确“行业事件 -> 公司暴露 -> 待验证变量”链路的新闻进入 4.3。
- 采纳 MF4：`weak_trend` 推荐标签缺分支，Batch 1 直接补测试和实现。
- 采纳 N2：formal financial metrics pack 不依赖年报全文单一路径，显式纳入 `fetch_financial_abstract()` 这类东财/akshare 财务接口作为后备正式源。
- 采纳 N3：Batch 3 移除 `peer_source_queries`，先做 config-driven industry/competitors 和同行材料层基础。

## Deferred

- 行业新闻复杂语义分类不在 Batch 1 实现；放入 Batch 2b。
- 同行研究 Agent、自动生成 peer source queries 不在本轮实现；放入后续同行材料层设计。
- 4.3 是否保留全量 sector_background 给 LLM 作为上下文，将在 Batch 2b 的实现设计中具体约束，避免本轮扩大 prompt/LLM 风险。

## Rejected

- 无。Claude Round 1 的 must-fix 均采纳。

## R2 Required

No.

原因：Round 1 没有 blocker；must-fix 均为设计歧义或已确认小边界 bug，已在设计文档中明确，不改变 high-risk 架构方向。可进入 Batch 1 实现。
