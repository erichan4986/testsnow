# Claude Review Prompt Round 2: Fresh Social Low-Credit Intake

Use this prompt for a narrow R2 review. Do not write code.

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做 R2 设计快审，不要修改源码。

请阅读：
- docs/agent_workflow/2026-06-15-fresh-social-low-credit-intake-design.md

背景：
Round 1 的 blocker 是：
1. Jina Search 开放搜索作为 Provider 1 无界、低信噪、易引入 SEO/新闻垃圾。
2. Claim extraction gate 对网页片段反噪音不够强。

Codex 已修订设计：
- 删除 Jina Search / s.jina.ai open search。
- 改为 explicit URL list + Jina Reader / r.jina.ai。
- Bilibili / yt-dlp 移出 claim intake，推迟到 social inventory。
- 增加 community-like 正向过滤和 SEO/news/official 负向过滤。
- 明确 fresh claims 如果被高信用证据验证，可能通过 existing claim-risk bridge 进入 structured risk signals。
- fresh note 文件名改为 <YYYYMMDD>-新鲜外部社媒claims.md，避免覆盖缓存雪球 notes。

请只审查：
1. Round 1 两个 blocker 是否已解除。
2. 现在是否 Ready to implement。
3. 是否还有必须在 task 里写清楚的测试/约束。

请把反馈追加到 design 文件末尾，标题为：
## Round 2 Feedback

反馈格式：
- Status: Ready to implement / Must-fix before task
- Remaining blocker
- Required task adjustments
- Missing tests
- Final recommendation

禁止事项：
- 不要修改源码。
- 不要运行外部网络、报告生成、Chrome/CDP、雪球详情页。
- 不要改 config/knowledge/reports/data/raw。
```
```
