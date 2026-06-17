# Claude Review Prompt: Fresh Social Low-Credit Intake

Use this prompt for a fast design review. Do not write code.

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做设计快审，不要修改源码。

请阅读：
- docs/agent_workflow/2026-06-15-fresh-social-low-credit-intake-design.md
- scripts/utils/community_claim_note_writer.py
- scripts/smoke_cached_community_claims.py
- scripts/utils/claim_verification.py
- docs/agent_workflow/2026-06-15-social-source-inventory.md

目标：
审查 Fresh Social Low-Credit Intake 设计是否足够安全，可以作为一个合并 implementation task 推进。

重点检查：
1. 设计是否真正解决“不能只用已有过滤后雪球 JSON”的问题。
2. Jina Search / Jina Reader / yt-dlp 作为 fresh low-credit smoke 是否合理。
3. 是否会误接入评分、风险、EV、技术、LLM synthesis 或最终建议。
4. 是否有 Xueqiu detail/CDP/登录/反爬风险。
5. `source_credit: 30` / `unverified_claim` / `market_opinion` 契约是否足够保守。
6. claim extraction gate 是否足够防噪音。
7. 是否应该先只做 中简科技，而不是三股一起。
8. 缺失测试、失败模式、runtime 验收清单。

请把反馈追加到 design 文件末尾，标题为：
## Round 1 Feedback

反馈格式：
- Status: Ready to implement / Must-fix before task
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
