# Formal-Medium Chapter 4.4 Retirement: Codex Self-Review Round 1

日期：2026-07-22  
Verdict：`ok`

## Findings Closed

### R1. “4.4” ownership was ambiguous

仓库中存在两种 4.4：formal-medium 的固定 price-path 模板，以及 formal-rich 的 legacy external addendum。设计已明确只删除前者；formal-rich 有来源正文和 inline citations，不在本批范围。

### R2. Shared title helper could be deleted by mistake

`is_informative_variable_title()` 虽为 price-path 选择使用，也被 4.2 的机构关注重点复用。设计明确保留该 helper 和 deny-list，只删除三个 price-path-only selectors。

### R3. `argument_complete` is not dead schema

删除 price path 后，`argument_complete` 仍属于 annual producer/material contract，并参与 `_rank_annual_rows()`。设计明确不删字段、不改 producer。

### R4. Hidden view-model consumers

全仓 call-site audit 显示 `section("4.4")` 的 runtime consumer 只有 `DeepAnalysisRenderer`；其余调用均为直接覆盖 price-path 行为的测试。移除 section 后不存在未迁移 runtime caller。

### R5. Citation loss risk

当前 4.4 rows 全部从已可见 4.1--4.3 rows 中再次选择，因此 4.4 不拥有唯一 source row 或 citation。删除 projection 不删除 snapshot rows，也不应减少前三节引用。设计增加 view-model/citation equality 和正式报告 missing/unused-ref gates。

### R6. Future reintroduction could recreate generic prose

设计新增结构化 trigger 准入合同，要求指标、方向、确认条件、反证条件、期限和引用齐全。renderer 不得从 prose 猜测缺失字段。

## Scope and Budget

- Runtime scope: two existing files.
- Tests: two corresponding focused files.
- Expected runtime change is deletion-only, approximately `-70` to `-90` lines.
- No profile routing, quality rule, scoring, target, risk, technical, recommendation, producer, canonical or LLM changes.

## Remaining Blockers

None found in Codex self-review. Because this changes report structure, an independent read-only Round 1 design review is still required before implementation.
