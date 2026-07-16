# Claude Review Prompt: Knowledge Persistence 6B Completion, Round 1

在 `/Users/erichan/testsnow/.worktrees/annual-producer-v2` 对以下设计做**只读**审查：

`docs/agent_workflow/2026-07-16-knowledge-persistence-6b-completion-design.md`

背景：当前分支 `codex/annual-producer-v2` 已在 commit `c20af7f` 完成 pack-first 机器读取：
annual material loader 从 validated JSON pack/manifest 读取 v2 cards；报告不再把 v2 单卡
Markdown 当机器输入。此前清理逐卡 v2 Markdown 是有意的，因为它重复保存 source excerpt、
frontmatter 和模板。当前仍缺一条 human-readable projection，同时两个正常写入入口仍会调用
legacy card-note writer，可能重新制造 N 个冗余文件。

本批目标：

1. 正常 `--write-knowledge` 写一个 JSON pack 与一个 Markdown view，而不是 N 个 card notes；
2. view 只读取 validated persisted pack，不能成为 material loader 输入；
3. 保留 v1 compatibility/recovery；不恢复已清理的 v2 notes；
4. 不改 producer、memo、snapshot、renderer、引用、profile、评分、目标价、风险、技术、推荐、
   采集或 LLM prompt；
5. 本批只写设计和 task，不实现、不联网、不生成报告。

请先阅读：

- `docs/agent_workflow/2026-07-16-knowledge-persistence-6b-completion-design.md`
- `docs/agent_workflow/2026-07-15-knowledge-persistence-slimming-design.md`
- `scripts/utils/periodic_report_narrative_pack_store.py`
- `scripts/utils/annual_report_material_pack.py`
- `scripts/prepare_annual_report_materials.py`
- `scripts/previews/periodic_report_narrative_cards_preview.py`
- `scripts/previews/periodic_report_narrative_cards_acceptance.py`
- 对应 tests（尤其 prepare/preview/acceptance/pack-store/material-pack）。

重点审查：

1. 新 view 是否真的从唯一的 validated machine truth 派生，而没有重建第二套 parser/validator；
2. `prepare`、preview 和 CLI 兼容策略是否足够明确，特别是 legacy refresh flags；
3. pack-first reset 后，新的 acceptance 是否足够证明材料保全与 loader 隔离，而非错误要求已删除
   v2 notes 的 parity；
4. view 的 family cap、排序、exact hash 去重是否会误伤完整材料（仅限展示层）；
5. atomicity、错误传播、manifest/period 边界、v1 recovery 和 formal-thin citation 是否有回归风险；
6. 是否有隐藏 scope 扩张、重复逻辑或不必要的大实现；
7. target `+110`/hard stop `+150` runtime line budget 是否可信。

不要修改任何源码、测试、配置、knowledge、data 或 reports；不要联网、不要生成报告、不要提交。

把审查写入：

`docs/agent_workflow/2026-07-16-knowledge-persistence-6b-completion-claude-review-round1-notes.md`

请使用以下格式：

```markdown
# Knowledge Persistence 6B Completion - Claude Review Round 1

verdict: ok | needs_revision | blocked

## Scope Audit

## Findings

### Blockers
- id:
  issue:
  evidence:
  required_design_change:

### Must Fix
- id:
  issue:
  evidence:
  required_design_change:

### Nice To Have
- id:
  issue:
  rationale:

## Requirement-Test Matrix
| Design requirement | Proposed implementation owner | Required test |
| --- | --- | --- |

## Budget Review

## Recommendation
```

最后只回复：`review notes 路径`、`verdict`、`blocker/must-fix 数量`。
