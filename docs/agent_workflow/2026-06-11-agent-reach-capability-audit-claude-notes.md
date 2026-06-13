# Agent-Reach 本地能力与命令契约审计

## 审计方法

- 本地安装 Agent-Reach v1.4.0（`pip install -e .` 从源码安装）
- 运行只读诊断命令：`agent-reach --help`、`agent-reach doctor`
- 阅读 channel 源码和 SKILL.md 文档，确认实际命令形式
- **未执行任何真实搜索，未登录任何平台**

---

## 重大发现：当前代码的命令映射是错的

`agent-reach` CLI **没有 `search` 子命令**。

```bash
$ agent-reach --help
Available commands: setup, install, configure, doctor, uninstall, skill, format, check-update, watch, version
```

这意味着当前 `agent_reach_skill.py:25-31` 中的映射：

```python
_AGENT_REACH_COMMANDS = {
    "twitter": ["agent-reach", "search", "twitter"],
    "reddit":  ["agent-reach", "search", "reddit"],
    ...
}
```

**这些命令完全不存在**。如果代码实际执行，会返回 `FileNotFoundError` 或 `returncode != 0`。

### Agent-Reach 的真实工作方式

Agent-Reach 是一个**脚手架（scaffolding）**，不是搜索引擎网关。它的作用是：
1. 安装上游工具（twitter-cli、yt-dlp、rdt-cli 等）
2. 配置环境（MCP、cookie、代理等）
3. 提供 `doctor` 诊断各平台可用性
4. Agent **直接调用上游工具**完成搜索/读取

例如：
- Twitter 搜索：`twitter search "query" -n 10`（不是 `agent-reach search twitter`）
- YouTube 字幕：`yt-dlp --write-sub --skip-download URL`（不是 `agent-reach search youtube`）
- Reddit 搜索：`rdt search "query" --limit 10`

---

## 平台能力矩阵

| 平台 | README 声称 | doctor 状态 | 实际命令 | 是否需 cookie/登录 | 账号/反爬风险 | 股票研究价值 | 推荐动作 |
|------|-------------|-------------|----------|-------------------|--------------|-------------|----------|
| **RSS** | 无需配置 | **✅ 可用** | `feedparser.parse('URL')` | 否 | 无 | 中 | **接入** |
| **网页读取** | 无需配置 | **✅ 可用** | `curl -s https://r.jina.ai/URL` | 否 | 低 | 中 | **接入** |
| **YouTube** | 无需配置 | ⚠️ 需配置 JS runtime | `yt-dlp --dump-json "ytsearch5:query"` | 否 | 低 | **中高** | **接入** |
| **V2EX** | 无需配置 | ⚠️ SSL 证书失败 | `curl -s https://www.v2ex.com/api/topics/hot.json` | 否 | 低 | 低 | 观望 |
| **GitHub** | 公开仓库可用 | ⚠️ gh CLI 未安装 | `gh search repos "query"` | 公开：否 | 低 | 中低 | **接入（公开）** |
| **Reddit** | 需登录 | **❌ 未安装 rdt-cli** | `rdt search "query" --limit 10` | **是** (rdt login) | 中 | 低 | Manual only |
| **微信公众号** | 无需配置 | **❌ 未安装 mcporter+Exa** | `mcporter call 'exa.web_search_exa(...)'` | 否 | 中 | **极高** | **接入（先装 Exa）** |
| **全网搜索(Exa)** | 自动配置 | **❌ 未安装 mcporter+Exa** | `mcporter call 'exa.web_search_exa(...)'` | 否 | 低 | **中高** | **接入（先装 Exa）** |
| **雪球** | 需配置 | 未直接检测（tier 1） | Python API 调用（urllib + cookie） | **是** (xq_a_token) | **高** | **极高** | Manual only |
| **微博** | 无需配置 | 未直接检测（tier 1） | `curl -s https://r.jina.ai/https://weibo.com/...` | 否 | 低 | 中 | **接入** |
| **Bilibili** | 本地可用 | 未直接检测（tier 1） | `bili search "query" -n 5` / `yt-dlp URL` | 可选（服务器需） | 中 | 中 | **接入** |
| **Twitter/X** | 需配置 | 未直接检测（tier 1） | `twitter search "query" -n 10` | **是** (TWITTER_AUTH_TOKEN) | **高** | 中 | Manual only |
| **小红书** | 需配置 | 未直接检测（tier 1） | `xhs search "query"` | **是** (xhs login) | **高** | 低 | Do not automate |
| **抖音** | 需配置 | 未直接检测（tier 1） | `mcporter call 'douyin.parse...'` | 否 | 中 | 低 | Do not automate |
| **LinkedIn** | 公开页可用 | 未直接检测（tier 1） | `mcporter call 'linkedin.read...'` | **是** | 中 | 低 | Do not automate |
| **小宇宙播客** | 需配置 | 未直接检测（tier 1） | `transcribe.sh "URL"` | **是** (Groq Key) | 低 | 低 | Do not automate |

> **tier 说明**：tier 0 = doctor 直接检测；tier 1 = 需要用户配置后才检测（安装额外 CLI/MCP）

---

## 特别确认项

### 1. 是否真的有 wechat / weibo？

**wechat（微信公众号）**：
- ✅ 真实存在，`agent_reach/channels/wechat.py`
- 底层使用 **Exa MCP**（`mcporter call 'exa.web_search_exa(...)'`），不是直接爬微信
- 搜索时通过 `includeDomains: ["mp.weixin.qq.com"]` 限定微信公众号域名
- **不需要微信登录**，因为 Exa 是第三方 AI 搜索引擎，已经爬好了内容
- doctor 状态：❌ 未安装 mcporter + Exa MCP

**weibo（微博）**：
- ✅ 真实存在，`agent_reach/channels/weibo.py`
- 但 SKILL.md 中的命令非常简陋：`curl -s "https://r.jina.ai/https://weibo.com/USER_ID/POST_ID"`
- 也就是说，微博**没有搜索能力**，只能通过 Jina Reader 读取已知 URL 的内容
- 无法像雪球那样搜索关键词获取帖子列表
- 股票研究价值大打折扣

### 2. 是否真的支持 `agent-reach search <platform>`？

**❌ 完全不支持。**

CLI 源码中没有任何 `search` 子命令的定义。实际搜索命令是：
- `twitter search "query"`（调用 twitter-cli）
- `rdt search "query"`（调用 rdt-cli）
- `xhs search "query"`（调用 xiaohongshu-cli）
- `bili search "query"`（调用 bilibili-cli）
- `gh search repos "query"`（调用 gh CLI）
- `yt-dlp --dump-json "ytsearch5:query"`（yt-dlp 原生搜索）
- `mcporter call 'exa.web_search_exa(...)'`（Exa MCP 搜索）

### 3. 雪球底层是否需要 cookie/登录？

**是，需要 Cookie。**

`xueqiu.py` 源码明确：
- 使用 `http.cookiejar` 管理 cookie
- 优先从 `~/.agent-reach/config.yaml` 读取 `xueqiu_cookie`
- 其次尝试从 Chrome 浏览器提取 `xq_a_token`
- 最后是 homepage 访问获取反 DDoS cookie（acw_tc），但这**不足以访问股票 API**
- `get_stock_quote()`、`get_hot_posts()` 等都需要有效登录态

**关键限制**：
- 与现有 CDP 方案一样，需要用户先登录雪球
- Agent-Reach 的雪球 channel 只是封装了 API 调用，没有绕过反爬
- 如果不配置 cookie，`doctor` 返回 `warn`（API 连接失败）

### 4. YouTube / RSS / Web / GitHub 是否可零配置使用？

| 平台 | 零配置？ | 实际条件 |
|------|----------|----------|
| **YouTube** | 部分 | yt-dlp 已安装，但需配置 JS runtime（Node.js 或 deno）。当前 doctor 报 `warn`：缺少 `--js-runtimes` 配置 |
| **RSS** | ✅ 是 | feedparser 随 agent-reach 一起安装（依赖项），直接可用 |
| **Web** | ✅ 是 | Jina Reader 通过 `curl https://r.jina.ai/URL` 访问，无需任何配置 |
| **GitHub** | 部分 | gh CLI 未安装。公开仓库搜索理论上可以免认证，但需要先装 gh CLI |

---

## 当前 doctor 实际输出

```
Agent Reach 状态
========================================

✅ 装好即用：
  [!]  GitHub 仓库和代码 — gh CLI 未安装
  [!]  YouTube 视频和字幕 — yt-dlp 已安装但未配置 JS runtime
  [X]  Reddit 帖子和评论 — 需要安装 rdt-cli
  [X]  微信公众号文章 — 需要 mcporter + Exa MCP
  [X]  V2EX 节点、主题与回复 — V2EX API 连接失败（SSL 证书问题）
  ✅ RSS/Atom 订阅源 — 可读取 RSS/Atom 源
  [X]  全网语义搜索 — 需要 mcporter + Exa MCP
  ✅ 任意网页 — 通过 Jina Reader 读取任意网页

状态：2/16 个渠道可用
还有 8 个可选渠道可以解锁（Twitter/X 推文、B站视频、字幕和搜索、小红书笔记、微博动态与热搜、小宇宙播客转文字、雪球股票行情与社区动态、抖音短视频、LinkedIn 职业社交）
```

---

## 对当前股票报告 pipeline 的影响

### 当前代码的问题

1. **命令不存在**：`agent_reach_skill.py` 中所有 `_AGENT_REACH_COMMANDS` 映射的命令都是虚构的
2. **_parse_records 兼容性**：即使命令形式修正了，各上游工具的输出格式差异巨大（twitter-cli 输出 YAML/JSON、yt-dlp 输出 JSON、rdt 输出 Markdown 等），当前 `_parse_records()` 只处理简单 JSON，无法兼容
3. **质量评分假设**：`agent_reach_quality_skill.py` 的评分逻辑基于 `SynthesisItem`（title/content/author/url），但 YouTube 字幕、RSS 摘要、网页全文的内容结构完全不同

### 修正方向

当前代码需要**重写 `agent_reach_skill.py`**，核心变化：

1. **移除 `_AGENT_REACH_COMMANDS`**：不再通过 `agent-reach` 子命令搜索
2. **按平台直接调用上游工具**：
   ```python
   # Twitter
   subprocess.run(["twitter", "search", query, "-n", "10", "--json"], ...)
   # YouTube
   subprocess.run(["yt-dlp", "--dump-json", f"ytsearch5:{query}"], ...)
   # Reddit
   subprocess.run(["rdt", "search", query, "--limit", "10", "--json"], ...)
   # Exa 全网搜索
   subprocess.run(["mcporter", "call", f"exa.web_search_exa(query: '{query}')"], ...)
   ```
3. **平台级输出解析**：每个平台需要独立的解析器（`_parse_twitter_output`、`_parse_youtube_output` 等）
4. **先安装上游工具**：在接入任何平台前，必须先 `pipx install twitter-cli`、`npm install -g mcporter` 等

---

## 分级建议

### Safe now（可直接接入）
- **RSS**：feedparser 已安装，直接可用
- **网页读取**：Jina Reader 通过 curl 可用，零配置

### Ready after install（安装后即可接入，无需登录）
- **YouTube**：安装 Node.js/deno + 配置 yt-dlp JS runtime
- **GitHub**：安装 gh CLI（公开仓库无需登录）
- **全网搜索(Exa)**：安装 mcporter + 配置 Exa MCP（免 Key）
- **微信公众号**：与 Exa 共用同一套 mcporter 配置

### Manual only（需要登录/Cookie，建议人工控制）
- **雪球**：需要 xq_a_token Cookie，与现有 CDP 方案等价
- **Twitter/X**：需要 TWITTER_AUTH_TOKEN + TWITTER_CT0，建议小号
- **Reddit**：需要 rdt login，中文股票内容极少
- **Bilibili**：可选登录（服务器 IP 需要 Cookie）

### Do not automate
- **小红书**：需要 Cookie + xsec_token 限制，股票内容质量低
- **抖音**：需要分享链接才能解析，无法搜索
- **LinkedIn**：需要登录，港股公司信息有限
- **V2EX**：SSL 证书问题未解决，股票讨论极少
- **微博**：没有搜索 API，只能读取已知 URL
- **小宇宙播客**：需要 Groq API Key，股票相关内容极少

---

## 推荐接入路线图

| 阶段 | 平台 | 工作量 | 前提条件 |
|------|------|--------|----------|
| **Phase 0（修复）** | 重写 `agent_reach_skill.py`，移除虚构命令，直接调用上游工具 | 3-4 天 | 理解各上游工具的 CLI 接口 |
| **Phase 1** | RSS + 网页读取 + YouTube | 2-3 天 | 安装 Node.js，配置 yt-dlp |
| **Phase 2** | Exa 全网搜索 + 微信公众号 | 2-3 天 | 安装 mcporter，配置 Exa MCP |
| **Phase 3** | GitHub + Bilibili | 2 天 | 安装 gh CLI、bili-cli（可选） |
| **Phase 4** | 雪球（与 CDP 对比评估） | 3-4 天 | 配置 xq_a_token Cookie |
| **Phase 5** | Twitter/X（小号） | 2-3 天 | 配置 TWITTER_AUTH_TOKEN |

---

## 结论

1. **当前代码无法工作**：`agent_reach_skill.py` 中的 `_AGENT_REACH_COMMANDS` 映射的命令在 Agent-Reach v1.4.0 中**完全不存在**
2. **Agent-Reach 不是搜索引擎**：它是一个脚手架，安装完成后 Agent 直接调用上游工具（twitter-cli、yt-dlp、rdt-cli、mcporter 等）
3. **真正零配置可用的只有 3 个**：RSS、网页读取、（部分）YouTube
4. **高价值的平台大多需要前置安装**：微信公众号/全网搜索需要 mcporter+Exa，雪球需要 Cookie，Twitter 需要 Cookie
5. **建议 Phase 0 先修复命令契约**，再按路线图逐步接入

---

## 来源

- [Agent-Reach GitHub](https://github.com/Panniantong/Agent-Reach)
- [Agent-Reach README](https://github.com/Panniantong/Agent-Reach/blob/main/README.md)
- [Agent-Reach SKILL.md](https://github.com/Panniantong/Agent-Reach/blob/main/agent_reach/skill/SKILL.md)
- 本地安装：Agent-Reach v1.4.0（源码安装）
- 本地诊断：`agent-reach doctor`（2025-06-11）
