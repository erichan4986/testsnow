# Agent-Reach 多平台可用性与反爬风险审计

## 审计范围

- 仅审计代码层配置与公开平台风控现状，**不执行任何真实抓取**、**不登录任何账号**、**不修改源代码**。
- 审计对象：`scripts/utils/report_skills/agent_reach_skill.py` 中配置的 5 个平台，以及用户额外关注的雪球、抖音。

## 本地 agent-reach CLI 状态

```bash
$ which agent-reach
NOT FOUND in PATH

$ find /Users/erichan -name "agent-reach" 2>/dev/null
(无结果)
```

**结论**：`agent-reach` 二进制当前未安装，本地无法执行任何 `agent-reach search <platform>` 命令。即使代码层 pipeline 已就绪，实际采集能力取决于该 CLI 的存在性与平台适配深度。

---

## 当前代码层平台配置

`agent_reach_skill.py:25-31` 映射表：

| 平台 | CLI 子命令 |
|------|-----------|
| twitter | `agent-reach search twitter` |
| reddit | `agent-reach search reddit` |
| bilibili | `agent-reach search bilibili` |
| wechat | `agent-reach search wechat` |
| xiaohongshu | `agent-reach search xiaohongshu` |

`agent_reach_query_skill.py:46` 中，所有基础查询都会向这 5 个平台同时发起搜索；竞争对手对比查询只向 `twitter, reddit, xiaohongshu` 发起。

**注意**：雪球和抖音**不在**当前 `agent-reach` 平台列表中。

---

## 平台风险矩阵

| 平台 | 可用性 | 是否需登录/cookie | 反爬风险 | 封号风险 | 推荐接入级别 | 备注 |
|------|--------|-------------------|----------|----------|--------------|------|
| Twitter/X | 低 | **必须**（未登录访问已大幅收紧） | **极高** | **高** | **Research only** | Elon Musk 收购后取消免费 API，搜索/时间线大量要求登录；批量搜索极易触发 429/账号锁定。 |
| Reddit | 中 | 部分需要（搜索/子版浏览通常需登录，只读偶尔可用） | 中 | 中 | **Manual only** | 有官方 API 但搜索功能受限；未登录搜索被限制；频率过高会触发 shadowban。 |
| Bilibili | 中 | 否（站内搜索和评论区可未登录访问，但有签名验证） | **中高** | 中 | **Manual only** | 有 WBI 签名反爬；未登录有请求频率限制；web 端信息密度足够做舆情扫描。 |
| 微信公众号 | 极低 | **必须**（搜狗微信搜索已失效，需微信生态登录态） | **极高** | **高** | **Do not automate** | 微信生态封闭；批量抓取公众号文章极易触发风控；内容主要在 App 内。 |
| 小红书 | 低 | **必须**（web 端搜索基本要求登录，且内容有限） | **极高** | **高** | **Do not automate** | 强反爬+设备指纹；web 端内容远少于 App；批量搜索账号存活时间短。 |
| 雪球 | 低 | **详情页必须**（列表页可有限不登录访问） | **极高** | **高** | **Manual only** | 已有独立 CDP 采集方案；AGENTS.md/CLAUDE.md 明确限制：禁止批量详情页、需用户登录 Chrome、间隔 3-5 秒。 |
| 抖音 | 极低 | **必须**（内容主要在 App 内，web 端极有限） | **极高** | **极高** | **Do not automate** | 不在当前 agent-reach 列表中；web 端几乎无法搜索到有效股票讨论内容。 |

---

## 分级建议

### Safe now
- **无**

当前 7 个平台均不适合在无人值守、无登录态、无用户授权的情况下全自动接入报告 pipeline。Bilibili 是唯一一个技术上勉强可行的，但仍需解决 WBI 签名和频率控制。

### Manual only
- **Reddit**：可用，但需要登录态和低频控制；适合作为用户手动补充信源，不适合每周自动跑 6 只股票的批量搜索。
- **Bilibili**：站内搜索可用，但需处理 WBI 反爬签名；如果 agent-reach CLI 内部已解决签名问题，可作为低频补充来源，但仍建议人工复核后再入 pipeline。
- **雪球**：项目已有成熟 CDP 采集方案（`fetcher.py` + `xueqiu_monitor_v2.py --xueqiu`），不应通过 agent-reach 重复接入。如必须走 agent-reach，需复用现有 CDP 登录态和 3-5 秒间隔策略，否则违反 AGENTS.md 限制。

### Research only
- **Twitter/X**：官方 API 已收费（Basic  tier $100/月，Pro tier $5000/月），第三方抓取存活时间短。如果未来有预算购买官方 API，可重新评估。当前只建议在研究阶段小规模验证，不接入生产 pipeline。

### Do not automate
- **微信公众号**：生态封闭，无稳定免费抓取通道。搜狗微信搜索已失效，任何自动化方案都高概率触发微信风控。放弃自动化接入。
- **小红书**：强设备指纹 + 登录墙 + 内容 App 化。web 端能抓取到的股票讨论质量低、数量少，不值得投入开发和账号维护成本。
- **抖音**：与小红书类似，股票讨论内容极少，且反爬机制极强。不值得接入。

---

## 雪球特别审计

### 当前状态
- 雪球**不在** `agent_reach_skill.py` 的 `_AGENT_REACH_COMMANDS` 中。
- 项目已有独立的雪球采集方案：`scripts/utils/fetcher.py`（Playwright 列表页采集）和 CDP 详情页采集。

### AGENTS.md / CLAUDE.md 约束
1. **禁止自动抓取详情页**：不得在无用户手动登录的情况下批量访问雪球帖子详情页。
2. **触发预警**：过高频率会触发反爬预警。
3. **正确做法**：用户手动登录 → 已登录 Chrome CDP → 每次请求间隔 3-5 秒 → 优先使用列表页摘要，避免不必要的详情页访问。
4. **数据来源优先级**：雪球列表页摘要（已缓存）> 东方财富（备用）> 雪球详情页（仅限用户授权且已登录时）。

### 结论
- **不要通过 agent-reach 接入雪球**。现有 CDP 方案已满足需求，重复接入会增加被封号风险。
- 如果未来一定要把雪球塞进 agent-reach CLI，必须复用现有 CDP 连接（`http://localhost:9222`）和用户已登录的 Chrome 实例，且严格遵守 3-5 秒间隔。否则违反项目硬规则。

---

## 综合建议

1. **agent-reach CLI 未安装**：在接入任何平台之前，首先需要确认 `agent-reach` 二进制是否存在、支持哪些平台、内部如何反反爬（签名、TLS、浏览器指纹等）。当前代码中假设 CLI 存在并直接调用 `subprocess.run`，但本地未找到该二进制。

2. **不要一次性开放 5 个平台**：即使 agent-reach CLI 存在，也不建议在 `agent_reach_query_skill.py:46` 中向全部 5 个平台同时搜索。应分批验证、按平台质量逐步放开。推荐优先级：Bilibili（如果反爬已解决）> Reddit > Twitter/X（仅在有 API 预算时）。微信和小红书不建议接入。

3. **增加平台可用性探测**：在 `agent_reach_fetch_skill` 中增加平台级健康检查（ping/轻量搜索），如果某平台连续失败或返回 `missing_binary`，自动降级并标记 `warnings`，而不是让整支股票的搜索全部失败。

4. **雪球的处理**：保持现有 CDP 采集方案不变，不要把雪球加入 agent-reach 平台列表。这是避免重复采集和封号的最安全做法。

5. **接入 pipeline 的前提条件**：
   - agent-reach CLI 已安装且可用
   - 至少有一个平台通过小规模人工测试（10-20 次搜索，观察是否触发风控）
   - 用户明确授权并提供必要的登录态/cookie
   - 有平台级降级机制（单平台失败不影响其他平台）

**当前结论**：Agent-Reach 渲染层（Phase 3/3B）已就绪，但采集层在生产环境落地前，需要先解决 CLI 可用性和平台风控问题。不建议在未验证平台可用性的情况下直接启用 `enable_agent_reach=True`。
