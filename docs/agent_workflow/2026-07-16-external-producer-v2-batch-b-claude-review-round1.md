# External Producer v2 Batch B Round 1 Review

请对以下设计做一次只读审查：

`docs/agent_workflow/2026-07-16-external-producer-v2-batch-b-cutover-design.md`

## Review Focus

1. extractor-only + canonical persisted pack 是否能安全替代 digest/narrative 双路径；
2. candidate 与 pack schema 是否足以证明 entity、claim、逐字 evidence、citation identity；
3. pack 的 missing/stale/invalid fail-closed 契约是否完整；
4. freshness、display-only risk 和 profile 的迁移是否遗漏 legacy consumer；
5. §7.5 profile 顺序能否保持中际 formal_medium、复旦 formal_thin_external_rich、
   黑芝麻不因 external-only 被错误升级；
6. 1--3 evidence units、无总 card 上限是否会引入不可控重复或 payload 风险；
7. 删除 composer、preview、digest/narrative caches/config 是否存在隐藏调用；
8. 三股样例确认 gate 是否足以满足 LLM 无编造要求；
9. 删除股票/主题专用 extractor profiles、固定 multipass 与 fuzzy quote repair 后，通用
   extractor 是否仍能完整且确定地生产 candidates；
10. B1 暂存新路径、B2 用户确认后原子 cutover 的时序是否避免半切换状态；
11. pack API、SynthesisSkill context status、snapshot-only citation offset 与 4.4 canonical
    row 消费是否存在第二 owner；
12. curated-viewpoint risk 的迁移是否不会误删 `display_only_external_risks` /
    `curated_external_analysis_items` 这两个非-viewpoint 显式输入；
13. `social_viewpoint_digest_preview.py`、测试注册和 layout/README 是否也已纳入 deletion
    ledger；
14. required tests、failure modes、stop conditions 是否可执行；
15. runtime 净增 +120 hard stop 是否可信，是否有明确 replacement ledger。

## Constraints

- 只读，不修改源码、测试、配置、data、knowledge 或 reports。
- 不联网，不运行 LLM，不生成报告。
- 必须读取真实代码确认 consumer 和删除范围，不能只复述设计。
- 反馈按 `blocker / must-fix / nice-to-have` 分级。
- 如提出保留 legacy compatibility，必须指出无法迁移的真实 consumer 和证据。
- 不建议让 external 进入评分、风险分数、目标价、推荐或技术路径。

## Output

写入：

`docs/agent_workflow/2026-07-16-external-producer-v2-batch-b-claude-review-round1-notes.md`

格式：

```text
verdict: ok | needs_revision | blocked

summary:

blockers:
  - id:
    issue:
    evidence:
    suggested_fix:

must_fix:
  - id:
    issue:
    evidence:
    suggested_fix:

nice_to_have:
  - id:
    issue:
    evidence:

consumer_and_deletion_audit:

schema_and_validation_review:

profile_routing_review:

requirement_test_gaps:

budget_assessment:

implementation_ready: yes | no
```
