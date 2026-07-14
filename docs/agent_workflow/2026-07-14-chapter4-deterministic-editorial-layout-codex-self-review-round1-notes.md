# Chapter 4 Deterministic Editorial Projection Codex Self-Review Round 1

日期：2026-07-14

verdict: ok_after_revision

## Summary

方向成立，但初稿有八项实现契约缺口。已全部修回 design 与 Claude Round 1 review task；未修改 runtime、tests、data、knowledge 或 reports。

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
- resolution：只有 exact normalized title 被两个不同 attribution 支持时才称共识，否则用“机构关注重点”；forecast range 强制 `研报预计` attribution。

### SR-04 External dedupe contract

- issue：现有 `_dedupe_row_refs_by_citation_identity()` 只去重单 row refs，不能保证两条 profile 路径使用同一 row dedupe 规则。
- resolution：新增唯一 shared key `(normalized_exact_body, sorted_unique_citation_identities)`；只删除完整 key 相同 rows，并移除 formal-medium/formal-thin renderer hard slices。

### SR-05 4.4 repetition

- issue：当前 `_formal_medium_price_path_section()` 会把 4.1–4.3 长 body 再次展开，并可能优先选择 portrait，延续人工验收中的复读问题。
- resolution：固定 annual/broker/external role priority，排除 portrait；4.4 只展示来源层级、变量 label、inline citation 与验证条件，不复写完整 body。

### SR-06 Source Intake restore path

- issue：初稿只有顶层 flag，正式 config 无传递路径；默认 False 还会破坏 `periodic_report_fulltext_preview.py --source-intake-section`。
- evidence：`stock_reporter.py` 已把完整 `source_intake_config` 放入 ctx；preview 当前只设置 `source_intake_enabled=True`。
- resolution：顶层 override 优先，否则读取 `source_intake_config.render_section`；preview 显式设置顶层 True，并加入 preview regression test。

### SR-07 External alternate projections

- issue：MaterialSnapshot 同时保留 narrative、reasoning 和 topic-group rows；若简单取消 cap，formal-medium 会把三套替代视图全部展示。
- resolution：snapshot 保持完整；display 固定使用 narrative → reasoning → topic 的单一路径优先级，再执行 exact key dedupe，不把替代投影视为独立材料。

### SR-08 External citation gate after local-list removal

- issue：现有 `_check_curated_external_inline_footnotes()` 只有在 external section 含“本节引用来源”时才检查 inline footnote。新版删除局部来源表后，漏挂脚注可能和全局来源一起被 `_visible_citations_only()` 删除并错误 PASS。
- resolution：将 `report_quality.py` 纳入窄范围；新布局按 `**变量标题**` + 下一观点段落 pair 检查 inline footnote，同时保留 legacy 检查和 fallback 豁免。

## Scope Review

- 新增允许 runtime：`scripts/previews/periodic_report_fulltext_preview.py`，仅一处显式 flag plumbing。
- 仍禁止修改 producer、memo、profile、citation allocator、report quality、scoring、target、risk、technical、recommendation 和 LLM prompt。
- runtime `+80` 目标 / `+140` hard stop 仍可信，前提是删除 renderer portrait selector、hard slices 和 local citation list，而不是叠加实现。

## Remaining Status

- blockers: []
- must_fix: []
- implementation_ready: no
- reason：按 Level 3 流程仍需独立 Claude Round 1 只读审查；若无 blocker/未关闭 must-fix，再写 implementation task。
