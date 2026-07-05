请对我上传/粘贴的设计做一次只读设计审查。

审查对象：

- `docs/agent_workflow/2026-07-03-evidence-adaptive-deep-analysis-design.md`

背景：

这是一个中文 A股/港股股票深度报告生成 pipeline。近期复旦微电正式报告暴露出：

1. 高信用正式材料不足时，pipeline 仍强行生成 `4.1 产业 / 4.2 业绩 / 4.3 资金`，导致空泛、重复、填表和错误推断。
2. 低信用但信息密度高的知乎/雪球好文被放在 4.4，但当前“观点卡片”可读性很差。
3. 用户希望结构跟着材料质量走：材料丰富时保留 4.1/4.2/4.3；材料薄但外部观点丰富时，改成“正式材料要点 + 外部观点地图 + 待验证清单”。
4. 低信用源可以影响置信度、仓位上限、风险提示和推荐措辞，但不能直接成为正式事实、目标价或评分输入。
5. 实现应尽量瘦身，复用已有模块，删除/合并无用 helper，不要继续膨胀。

请重点审：

1. `formal_rich / formal_thin_external_rich / thin_all` 的路由是否合理；
2. 是否会破坏材料丰富股票（如中际旭创）的 4.1/4.2/4.3 效果；
3. 外部观点地图是否足够有信息密度，同时不把低信用源伪装成确认事实；
4. “低信用外部信号只影响 confidence/position cap/risk wording/recommendation wording” 是否安全；
5. 删除 visible reasoning cards 是否会损失必要审计能力；
6. core facts pruning 是否会误删有用事实；
7. quality gates 是否足够，是否太粗或误杀；
8. 设计是否真的能减少代码膨胀，还是会新增另一套复杂系统。

请输出结构：

```yaml
verdict: ok | needs_revision | blocked
summary: "一句话总评"
blockers:
  - id:
    issue:
    why_it_matters:
    suggested_fix:
must_fix:
  - id:
    issue:
    why_it_matters:
    suggested_fix:
nice_to_have:
  - id:
    issue:
    suggested_fix:
answers_to_review_questions:
  routing:
  formal_rich_regression:
  external_viewpoint_map:
  low_credit_signal_layer:
  reasoning_cards_removal:
  core_fact_pruning:
  quality_gates:
  code_bloat:
implementation_risk:
  highest_risk:
  recommended_first_batch:
  stop_conditions:
```

不要改代码。不要泛泛而谈。请基于设计文本给出 blocker / must-fix / nice-to-have。
