# Chapter 4 Deterministic Editorial Projection Codex Self-Review Round 1

日期：2026-07-14

verdict: ok_after_revision

## Summary

方向成立，但三轮自审共发现十三项实现契约缺口。已全部修回 design 与 Claude Round 1 review task；未修改 runtime、tests、data、knowledge 或 reports。

## Closed Findings

### SR-01 Portrait ownership

- issue：annual role budget 没有保证画像槽位，renderer 仍会通过 `_select_annual_portrait_row()` 二次选择。
- evidence：`deep_analysis_renderer.py` 当前在 4.1 分组后再次搜索 portrait。
- resolution：shared annual selector 先保留最高分 portrait，写入 `editorial_slot="portrait"`；renderer 只消费 slot 并删除二次 selector。

### SR-02 Diagnostics compatibility

- issue：若直接把 `annual_selected_count` 改成 budget 后数量，会静默改变已有测试与诊断语义。
- resolution：保留旧 key 为 admission + dedupe 数量，新增 display/hidden diagnostics。

### SR-03 Broker consensus and attribution

- issue：当前 `_broker_consensus_sentence()` 只拼标题，单一机构也可能被展示为“机构共识”；formal-thin `forecast_ranges` 未经过 attribution normalizer。
- resolution：最终方案由 SR-12 收紧为完全删除 title-only“机构共识”，只保留“机构关注重点”；forecast range 仍强制 `研报预计` attribution。

### SR-04 External dedupe contract

- issue：现有 `_dedupe_row_refs_by_citation_identity()` 只去重单 row refs，不能保证两条 profile 路径使用同一 row dedupe 规则。
- resolution：新增唯一 shared key `(normalized_exact_body, sorted_unique_citation_identities)`；只删除完整 key 相同 rows，并移除 formal-medium/formal-thin renderer hard slices。

### SR-05 4.4 repetition and generic labels

- issue：当前 `_formal_medium_price_path_section()` 会把 4.1–4.3 长 body 再次展开，并可能优先选择 portrait，延续人工验收中的复读问题。
- resolution：固定 annual/broker/external role priority，排除 portrait；4.4 只展示来源层级、有效变量标题、inline citation 与验证条件，不复写完整 body。`业务覆盖 / 产品线` 等 deterministic role fallback 不得凑段；没有非泛化 title 的层级直接省略，因此 4.4 可少于三段。

### SR-06 Source Intake restore path

- issue：初稿只有顶层 flag，正式 config 无传递路径；默认 False 还会破坏 `periodic_report_fulltext_preview.py --source-intake-section`。
- evidence：`stock_reporter.py` 已把完整 `source_intake_config` 放入 ctx；preview 当前只设置 `source_intake_enabled=True`。
- resolution：顶层 override 优先，否则读取 `source_intake_config.render_section`；preview 显式设置顶层 True，并加入 preview regression test。

### SR-07 External alternate projections

- issue：MaterialSnapshot 同时保留 narrative、reasoning 和 topic-group rows；若简单取消 cap，formal-medium 会把三套替代视图全部展示。
- resolution：snapshot 保持完整；display 固定使用 narrative → reasoning → topic 的单一路径优先级，再执行 exact key dedupe，不把替代投影视为独立材料。

### SR-08 External citation gate after local-list removal

- issue：现有 `_check_curated_external_inline_footnotes()` 只有在 external section 含“本节引用来源”时才检查 inline footnote。新版删除局部来源表后，漏挂脚注可能和全局来源一起被 `_visible_citations_only()` 删除并错误 PASS。
- resolution：将 `report_quality.py` 纳入窄范围；新布局逐一扫描 4.3 Preview 中所有 standalone `**变量标题**` + 下一普通观点段落 pair。每个 pair 必须有完整 inline footnote，且不得以 bullet/table/heading 代替段落；同时保留 legacy 检查和 fallback 豁免。

### SR-09 Scope and gate grammar consistency

- issue：Scope 明确允许修改 `report_quality.py`，但自审 Scope Review 又把 report quality 列为禁止项；新 title/body gate 也未明确逐条扫描的 Markdown grammar。
- resolution：`report_quality.py` 仅可修改 external inline-footnote gate，其他 quality rules 仍禁止；新 layout 明确只扫描 4.3 Preview body、不含全局引用表，逐 pair 检查普通段落和 `[^n]`，并覆盖后续 pair 与多位数 citation 测试。

### SR-10 Deterministic 4.4 variable titles

- issue：设计用“有信息量”和“等泛标签”描述 4.4 title 准入，但真实默认值还包括 `外部变量`、`机构核心观点`、`产业与产品判断`、`盈利预测` 和 `反方约束`，实现者仍需主观补规则。
- resolution：新增唯一 `_is_informative_variable_title()` 契约和完整 exact deny-list；只允许原 row title，禁止从 evidence body 造标题。4.4 改为最多三段，全部 title 被拒绝时使用无事实、无引用的固定 fallback。

### SR-11 Eligible external projection fallback

- issue：formal-thin 当前只要 raw narrative list 非空就不会进入 reasoning 分支，即使 narrative 全部缺正文或有效 citation，也会错误得到空 external map。
- resolution：三套 projection 先分别执行正文/citation eligibility 与 shared-key dedupe，再通过同一 helper 选择首个非空 projection。测试锁定“raw narrative 存在但不可展示，reasoning 有效”必须 fallback reasoning，且不得混合 projection。

### SR-12 Title-only broker consensus

- issue：broker title 来自固定 family map；不同机构都叫“产业与产品判断”或“盈利预测与估值假设”，不能证明观点方向和论据一致。正文 display dedupe 还会让 attribution 支持数取决于去重顺序。
- resolution：删除 `_broker_consensus_sentence()` 与“机构共识”输出。本批只保留“机构关注重点”：从已选 display rows 提取非通用 title，按 source order 去重；全是通用 title 时省略摘要块，逐机构 attribution 段落保持不变。

### SR-13 4.4 filter/priority order

- issue：若先按 role/source order 取第一条，再检查 informative title，泛标题 row 会让整个来源层消失，即使后续 visible row 已有具体变量。
- resolution：固定为 `visible rows → informative-title filter → role/source-order priority → one row per layer`。annual/broker/external 各加“泛标题在前、具体标题在后”测试；仍禁止读取 snapshot hidden rows。

## Scope Review

- 新增允许 runtime：`scripts/previews/periodic_report_fulltext_preview.py`，仅一处显式 flag plumbing。
- 仍禁止修改 producer、memo、profile、citation allocator、除 external inline-footnote gate 外的 report quality、scoring、target、risk、technical、recommendation 和 LLM prompt。
- runtime `+80` 目标 / `+140` hard stop 仍可信，前提是删除 renderer portrait selector、hard slices 和 local citation list，而不是叠加实现。

## Remaining Status

- blockers: []
- must_fix: []
- implementation_ready: no
- reason：按 Level 3 流程仍需独立 Claude Round 1 只读审查；若无 blocker/未关闭 must-fix，再写 implementation task。
