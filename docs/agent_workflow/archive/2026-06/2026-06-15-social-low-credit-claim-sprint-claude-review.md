# Claude Review Prompt: Social / Low-Credit Claim Sprint

Use this prompt for a fast design review. Do not write code.

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做设计快审，不要修改源码。

请阅读：
- docs/agent_workflow/2026-06-15-social-low-credit-claim-sprint-design.md
- scripts/utils/community_claim_note_writer.py
- scripts/smoke_cached_community_claims.py
- scripts/utils/claim_verification.py
- tests/utils/test_community_claim_note_writer.py
- tests/utils/test_claim_verification.py

目标：
审查 Social / Low-Credit Claim Sprint 设计是否足够安全，可以作为一个合并 sprint 推进。

重点检查：
1. 是否复用现有 cached community claim writer，而不是重复造轮子。
2. 是否严格避免 Xueqiu detail/CDP/登录 Chrome/知乎刷新/LLM prompt 改动。
3. 社媒/社区内容是否始终保持 low-credit、unverified，不会污染 confirmed_fact。
4. claim verification 是否已经能支持 high-credit 验证 low-credit claim。
5. Agent-Reach social inventory 是否应只做能力盘点，不接报告 pipeline。
6. 是否需要泛化 community_claim_note_writer，还是先不改代码只跑现有 smoke。
7. 缺失的测试、失败模式、runtime 验收清单。

请把反馈追加到 design 文件末尾，标题为：
## Round 1 Feedback

反馈格式：
- Status: Ready to implement / Must-fix before task / Run existing smoke first
- R2 Needed: Yes/No
- Findings: 按 severity 排序
- Required task adjustments
- Missing tests
- Recommended execution order
- Blocker

禁止事项：
- 不要修改源码。
- 不要运行外部网络、报告生成、Chrome/CDP、雪球详情页。
- 不要改 config/knowledge/reports/data/raw。
```
```
