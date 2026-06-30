# Claude Review Round 1: Claim Verification Phase 4

请审查 Phase 4 设计，不要写代码，不要修改源码。

Design file:

`docs/agent_workflow/2026-06-13-claim-verification-design.md`

背景：

我们已经完成：

1. Source Credit Framework
   - Agent-Reach item 会带 `source_credit`, `source_type`, `verification_status`, `knowledge_eligible`, `report_eligible`。

2. Evidence Note Writer
   - 高/中/低信用信息可以写成 evidence notes。
   - Phase 3 已接入 pipeline，但默认 dry-run。

3. Legacy social notes
   - 当前 `knowledge/10-Stocks/**` 里保留了一批雪球/知乎来源信息。
   - 已打标为：
     - `source_type: social_discussion`
     - `source_platforms: ["雪球", "知乎"]`
     - `source_credit: 35`
     - `verification_status: market_opinion`
     - `report_eligible: false`
   - 这些内容只能作为待验证观点，不能直接进入 `KnowledgeSynthesizer`。

Phase 4 目标：

新增一个纯模块 claim verification framework，用高信用 evidence notes 验证低信用社区观点，先只产出 dry-run plan，不写回 knowledge，不接 pipeline，不调用 LLM。

请重点审查：

1. 边界是否正确：
   - 不修改 `KnowledgeSynthesizer`
   - 不修改 `SynthesisSkill`
   - 不接 pipeline
   - 不写真实 `knowledge/`
   - 不调用网络/浏览器/LLM/subprocess

2. `scripts/utils/claim_verification.py` 作为纯模块是否合理。

3. legacy social notes 的处理是否安全：
   - `MOC.md` 是否应跳过
   - 无 explicit claims 时是否应创建 coarse stub
   - 旧正文里的 `confirmed_facts` 是否必须忽略为事实

4. verification 规则是否过于粗糙或足够保守：
   - high-credit -> verified
   - medium-credit -> supported
   - social -> never verifies
   - unrelated -> unverified

5. 是否需要写回功能：
   - 设计建议 Phase 4 不写回，只返回 plan。

6. 测试计划是否足够：
   - YAML evidence note
   - JSON legacy social frontmatter
   - MOC skip
   - malformed frontmatter skip
   - trust direction
   - plan to dict
   - tmp_path only

请把审查结果写入：

`docs/agent_workflow/2026-06-13-claim-verification-claude-notes.md`

输出格式：

```markdown
# Claim Verification Phase 4 Review Round 1

## Status

Ready to implement / Ready with changes / Blocked

## Findings

### High
- None if no high-severity findings.

### Medium
- None if no medium-severity findings.

### Low
- None if no low-severity findings.

## Required Changes Before Implementation

- None if no required changes.

## Nice To Have

- None if no nice-to-have suggestions.

## Files Reviewed

- List reviewed files.
```

约束：

- 不写代码。
- 不修改任何 `.py` 文件。
- 不运行报告生成。
- 不调用网络、浏览器、LLM、subprocess。
- 可以读取相关代码、测试和 `knowledge/10-Stocks` 样例文件。

