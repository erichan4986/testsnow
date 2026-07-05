# Claude Review Round 1 — Theme Material Budget With Global Source IDs

请在 `/Users/erichan/testsnow` 仓库里做一次只读设计审查。

读取：

- `docs/agent_workflow/2026-07-03-theme-material-budget-global-source-ids-design.md`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/curated_external_viewpoint_narrative.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/report_quality.py`
- 相关测试：
  - `tests/utils/test_knowledge_synthesizer.py`
  - `tests/reporter/test_synthesis_skills.py`
  - `tests/utils/test_curated_external_viewpoint_narrative.py`
  - `tests/reporter/test_deep_analysis_renderer.py`
  - `tests/reporter/test_report_quality.py`

目标：

审查这个 V2 是否真的能以最小代码增量替换旧路径：

1. `KnowledgeSynthesizer` 内部全局 source-id material budget 是否是正确的唯一 routing owner？
2. 这个设计是否能消除双重 theme filter 和局部重编号造成的 citation metadata 错配？
3. 是否能避免继续膨胀 `synthesis_skills.py`？
4. fundflow raw source 保留方案是否足够，是否会重新引入伪资金材料？
5. 4.4 只修 producer schema、不中途从 renderer 反推 cards 是否合理？
6. 是否有遗漏的旧路径需要冻结或替换？
7. 是否有必须补充的测试或 stop condition？
8. runtime 净增 <250 行是否现实？

禁止事项：

- 不要改代码。
- 不要运行报告入口。
- 不要访问外部网站。
- 不要启动 Chrome/CDP/Playwright。
- 不要生成或修改 reports。

输出文件：

`docs/agent_workflow/2026-07-03-theme-material-budget-global-source-ids-claude-review-round1-notes.md`

输出格式：

```markdown
# Theme Material Budget Review Round 1

Verdict: ok | needs_revision | risky

## Summary

...

## Blocker

- B1: ...

## Must-Fix

- MF1: ...

## Nice-To-Have

- N1: ...

## Replacement / Freeze Assessment

| Old path | Proposed handling | Verdict | Notes |
| --- | --- | --- | --- |

## Test Gaps

...

## Line Budget Risk

...

## Recommendation

Proceed / revise first / do not proceed.
```

请给出具体 evidence，引用文件和函数名。不要泛泛而谈。
