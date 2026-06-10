# Claude Code 扩展清单与 Codex 迁移评估

> **审计日期**: 2026-06-10
> **审计范围**: 用户目录 `~/.claude/` + 仓库 `testsnow/.claude/`
> **目的**: 为 Codex 接管评估哪些 Claude Code 专属配置/扩展值得迁移

---

## 1. 清单总览

| 类别 | 数量 | 位置 | 是否涉及敏感信息 |
|------|------|------|-----------------|
| Skills (用户级) | 3 | `~/.claude/skills/` | 否 |
| Skills (仓库级) | 1 | `testsnow/.claude/skills/` | 否 |
| Commands | 3 | `~/.claude/commands/` | 否 |
| Rules | 2 | `~/.claude/rules/` | 否 |
| Plugins | 5 | `~/.claude/plugins/` | 否 |
| MCP Servers | 1 (Playwright) | 插件内置 | 否 |
| Settings | 2 | `~/.claude/settings.json` + `testsnow/.claude/settings.local.json` | **是（含 API Key）** |

---

## 2. Skills 详细清单

### 2.1 用户级 Skills (`~/.claude/skills/`)

#### a-stock-data
- **路径**: `~/.claude/skills/a-stock-data/SKILL.md`
- **用途**: A股全栈数据工具包 — 行情(mootdx+腾讯)、研报(东财+iwencai)、信号(同花顺热点/北向/百度PAE/龙虎榜/解禁/行业)、新闻(akshare)、基础数据(mootdx财务/F10)、公告(巨潮)六层数据源
- **触发场景**: 用户查询 A 股个股估值、研报检索、题材归因、龙虎榜跟踪、解禁预警、行业轮动等
- **依赖**: `mootdx`, `akshare`, `requests`, `pandas`, `stockstats`
- **脚本**: 无（纯 Markdown skill，内嵌 Python 调用代码示例）
- **迁移评估**: **必须迁移** — 本项目核心功能依赖 A 股数据采集，该 skill 是项目数据层的重要参考文档
- **迁移目标**: `~/.agents/skills/a-stock-data/SKILL.md`（Codex 全局 skill）或仓库级 `.agents/skills/a-stock-data/SKILL.md`
- **注意事项**: 内嵌代码可直接复制使用，无需额外安装；iwencai 语义搜索需 `IWENCAI_API_KEY`

#### global-stock-data
- **路径**: `~/.claude/skills/global-stock-data/SKILL.md`
- **用途**: 美股港股全栈数据工具包 — 行情(新浪+腾讯+东财)、K线(新浪+Yahoo)、技术指标、基本面(东财+Yahoo+SEC XBRL)、资金面、期权、SEC Filing、搜索工具八层数据源
- **触发场景**: 美股/港股个股分析、全市场筛选、财报解读、SEC 文件检索
- **依赖**: 同 a-stock-data + Yahoo/SEC 相关库
- **脚本**: 无（纯 Markdown skill）
- **迁移评估**: **可选迁移** — 本项目虽有港股标的（黑芝麻智能），但主流程中对港股 `is_hk` 直接跳过技术/资金/新闻采集，港股通路不完整。如后续加强港股支持则需迁移
- **迁移目标**: `~/.agents/skills/global-stock-data/SKILL.md`（全局）或保留在用户目录不迁移

#### everything-claude-code
- **路径**: `~/.claude/skills/everything-claude-code/SKILL.md`
- **用途**: `everything-claude-code` 项目的开发规范与提交约定（JavaScript 项目，conventional commits）
- **触发场景**: 仅当在 `everything-claude-code` 仓库中工作时激活
- **依赖**: 无
- **脚本**: 无
- **迁移评估**: **不建议迁移** — 这是另一个独立项目的开发规范（JavaScript 项目），与本 Python 项目完全无关
- **迁移目标**: 不迁移

### 2.2 仓库级 Skills (`testsnow/.claude/skills/`)

#### grill-me
- **路径**: `testsnow/.claude/skills/grill-me/SKILL.md`
- **用途**: 面试式设计审查 — 在写代码前 relentlessly 质问用户计划中的每个决策分支
- **触发场景**: 用户输入 `/grill-me` 或对话中触发
- **依赖**: 无
- **脚本**: 无（纯文本 skill）
- **迁移评估**: **可选迁移** — 通用设计审查 skill，不特定于本项目，但质量门控思想对本项目有益
- **迁移目标**: 保留在仓库 `.claude/skills/` 中即可（Claude Code 和 Codex 均可读取），或迁移到 `.agents/skills/grill-me/SKILL.md`
- **备注**: 该 skill 同时存在于 superpowers 插件中（`plugins/cache/.../grill-me/`），内容相同

---

## 3. Commands 详细清单 (`~/.claude/commands/`)

| 名称 | 路径 | 用途 | 触发场景 | 迁移评估 | 迁移目标 |
|------|------|------|----------|----------|----------|
| database-migration | `~/.claude/commands/database-migration.md` | 数据库迁移工作流 scaffold | `/database-migration` | **不建议迁移** | 不迁移 — 本项目无数据库 |
| add-language-rules | `~/.claude/commands/add-language-rules.md` | 新增编程语言规则系统 | `/add-language-rules` | **不建议迁移** | 不迁移 — 针对 everything-claude-code 项目 |
| feature-development | `~/.claude/commands/feature-development.md` | 标准功能实现工作流 | `/feature-development` | **不建议迁移** | 不迁移 — 针对 everything-claude-code 项目 |

> **结论**: 所有 3 个 commands 都是 `everything-claude-code` 项目的 workflow scaffolds，与本项目无关。

---

## 4. Rules 详细清单 (`~/.claude/rules/`)

| 名称 | 路径 | 用途 | 迁移评估 | 迁移目标 |
|------|------|------|----------|----------|
| node.md | `~/.claude/rules/node.md` | Node.js 项目规则（CommonJS、ESLint、c8、测试命名等） | **不建议迁移** | 不迁移 — 本项目是 Python |
| everything-claude-code-guardrails.md | `~/.claude/rules/everything-claude-code-guardrails.md` | everything-claude-code 项目的架构/提交/代码风格规则 | **不建议迁移** | 不迁移 — 针对另一个项目 |

---

## 5. Plugins 详细清单

### 5.1 已安装 Plugins (`~/.claude/plugins/`)

| 名称 | 来源 | 版本 | 用途 | 迁移评估 |
|------|------|------|------|----------|
| superpowers | claude-plugins-official | 5.1.0 | 提供 brainstorming、writing-plans、subagent-driven-development、executing-plans、using-git-worktrees、TDD 等 15+ 个 workflow skills | **可选迁移** — Codex 有自己的 planning/execution 能力，但这些 workflow skills 的质量很高，可作为参考 |
| playwright | claude-plugins-official | 1fb8ee762823 | 提供浏览器自动化 MCP server (`npx @playwright/mcp@latest`) | **必须保留** — 项目中雪球采集使用 Playwright |
| frontend-design | claude-plugins-official | 1fb8ee762823 | 前端设计辅助 skill | **不建议迁移** — 本项目无前端开发 |
| planning-with-files | planning-with-files | 2.42.0 | 将计划写入文件并跟踪的技能 | **可选迁移** — 本项目已自建 plans/specs 目录体系 |
| ralph-loop | claude-plugins-official | 1.0.0 | 循环工作流 skill | **不建议迁移** — 通用工具，非项目特定 |

### 5.2 MCP Server 配置

**Playwright MCP**:
- **配置位置**: `~/.claude/plugins/cache/claude-plugins-official/playwright/1fb8ee762823/.mcp.json`
- **启动命令**: `npx @playwright/mcp@latest`
- **用途**: 浏览器自动化（访问网页、截图、点击、填表、执行 JS）
- **在本项目中的使用**: 雪球网列表页采集（`fetcher.py` 中的 Playwright）、详情页 CDP 提取
- **Codex 兼容性**: Codex 支持 MCP servers，配置方式可能不同但功能等价
- **迁移评估**: **必须保留功能** — 雪球采集依赖浏览器自动化

---

## 6. Settings 详细清单

### 6.1 用户级 Settings (`~/.claude/settings.json`)

| 配置项 | 值 | 说明 | 迁移评估 |
|--------|-----|------|----------|
| `env.ANTHROPIC_BASE_URL` | `https://api.kimi.com/coding/` | Kimi API 代理地址 | **敏感 — 不迁移到仓库** |
| `env.ANTHROPIC_AUTH_TOKEN` | `sk-kimi-...` | Kimi API Key | **敏感 — 绝不迁移** |
| `model` | `moonshotai/kimi-k2.6` | 当前使用的模型 | **可选记录** — 可在 AGENTS.md 中注明 |
| `enabledPlugins` | 5 个插件 | 见上方插件清单 | **可选记录** — 在迁移文档中列出 |
| `extraKnownMarketplaces` | planning-with-files | 额外插件市场 | **不迁移** |

### 6.2 仓库级 Settings (`testsnow/.claude/settings.local.json`)

**⚠️ 重要发现**: 该文件包含大量敏感信息和历史权限记录，但**不是 hooks 配置**。

**内容分类**:

| 类别 | 数量 | 示例 | 风险等级 |
|------|------|------|----------|
| MCP Playwright 权限 | 9 | `mcp__plugin_playwright__browser_evaluate`, `browser_navigate`, `browser_click` 等 | 低 |
| Bash 命令权限 | ~80 | `python3 *`, `git *`, `pytest *`, `curl *`, `pip install *` 等 | **中** |
| API Key 硬编码 | 4 | `DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY`, `ZHIHU_API_KEY` | **高** |
| WebSearch/WebFetch 权限 | 2 | `WebSearch`, `WebFetch(domain:docs.tikhub.io)` | 低 |
| Read 权限 | 2 | `Read(//Users/erichan/.claude/skills/a-stock-data/**)`, `Read(//Users/erichan/**)` | 低 |

**敏感信息列表**（已脱敏）:
- `DEEPSEEK_API_KEY="sk-REDACTED-DEEPSEEK"`
- `MOONSHOT_API_KEY="sk-REDACTED-DEEPSEEK"`
- `ZHIHU_API_KEY="7d19ad2b8e7c5c0859b48b389674a24a54e88735"`
- `Authorization: Bearer 7d19ad2b8e7c5c0859b48b389674a24a54e88735` (TikHub API)

**迁移评估**:
- **不建议将此文件整体迁移给 Codex** — 它是 Claude Code 的权限缓存，Codex 有自己的权限模型
- **但必须告知 Codex 需要哪些环境变量** — 见下方「迁移建议」
- **应从 git 中排除此文件** — 已在 `.gitignore` 中忽略 `.claude/`（确认 `.gitignore` 第 2 行有 `.env`，但 `.claude/` 未被显式忽略，需检查）

---

## 7. Hooks 检查

**结果**: 未发现显式的 hooks 配置。

- `~/.claude/settings.json` 中无 `hooks` 键
- `testsnow/.claude/settings.local.json` 中无 `hooks` 键
- 仓库中无 `.claude/hooks/` 目录
- `scripts/` 目录下无 hook 脚本

> 注：`settings.local.json` 中的 `permissions.allow` 列表**不是 hooks**，它是 Claude Code 的权限审批缓存。

---

## 8. 迁移建议汇总

### 8.1 必须迁移

| 内容 | 当前位置 | 目标位置 | 原因 |
|------|----------|----------|------|
| a-stock-data skill | `~/.claude/skills/a-stock-data/SKILL.md` | `~/.agents/skills/a-stock-data/SKILL.md` 或 `.agents/skills/a-stock-data/SKILL.md` | 项目核心数据层参考 |
| Playwright MCP 功能 | 插件配置 | Codex MCP 配置 | 雪球采集依赖浏览器自动化 |
| 环境变量清单 | `settings.local.json` (硬编码) | AGENTS.md 或 `.env.example` | Codex 需要知道需要哪些 API Key |

### 8.2 可选迁移

| 内容 | 当前位置 | 目标位置 | 原因 |
|------|----------|----------|------|
| global-stock-data skill | `~/.claude/skills/global-stock-data/SKILL.md` | `~/.agents/skills/global-stock-data/SKILL.md` | 如加强港股支持则需 |
| grill-me skill | `testsnow/.claude/skills/grill-me/SKILL.md` | `.agents/skills/grill-me/SKILL.md` | 设计审查通用 skill |
| superpowers plugin skills | `~/.claude/plugins/cache/.../superpowers/5.1.0/skills/` | 作为参考阅读 | 高质量 workflow，但 Codex 有内置能力 |
| planning-with-files plugin | `~/.claude/plugins/cache/.../planning-with-files/` | 不迁移 | 本项目已自建 plans 体系 |

### 8.3 不建议迁移

| 内容 | 原因 |
|------|------|
| everything-claude-code skill | 另一个项目的 JavaScript 规范 |
| 所有 3 个 commands | 全部针对 everything-claude-code 项目 |
| 2 个 rules 文件 | 全部针对 everything-claude-code / Node.js 项目 |
| frontend-design plugin | 本项目无前端开发 |
| ralph-loop plugin | 通用循环工具，非项目特定 |
| settings.local.json 整体 | 含大量敏感信息 + 历史权限垃圾，Codex 不需要 |

---

## 9. 安全与敏感信息处理建议

### 9.1 立即行动

1. **从 settings.local.json 中清除历史 API Key**
   - 该文件第 22、52、56、65 等行硬编码了多个 API Key
   - 虽然文件在 `.claude/` 目录下，但**不在 `.gitignore` 中**
   - 建议运行: `echo ".claude/settings.local.json" >> .gitignore`

2. **创建 `.env.example`**（供 Codex 参考）
   ```bash
   # 必需
   DEEPSEEK_API_KEY=your_deepseek_key
   MOONSHOT_API_KEY=your_moonshot_key

   # 可选
   DEEPSEEK_MODEL=deepseek-chat
   IWENCAI_API_KEY=your_iwencai_key
   IWENCAI_BASE_URL=https://openapi.iwencai.com
   ```

3. **确认 `.gitignore` 已排除敏感文件**
   - `.env` ✓（已在第 2 行）
   - `cookies.txt` ✓（已在第 3 行）
   - `.claude/settings.local.json` ✗（**未排除**）

### 9.2 不要执行的脚本

本次审计中未发现需要执行的未知脚本。所有 skill 均为纯 Markdown 文档，无附带可执行脚本。

---

## 10. 附录：Superpowers Plugin Skills 子目录

`~/.claude/plugins/cache/claude-plugins-official/superpowers/5.1.0/skills/` 下包含 15 个 workflow skills：

```
brainstorming/
dispatching-parallel-agents/
executing-plans/
finishing-a-development-branch/
grill-me/
receiving-code-review/
requesting-code-review/
subagent-driven-development/
systematic-debugging/
test-driven-development/
using-git-worktrees/
using-superpowers/
verification-before-completion/
writing-plans/
writing-skills/
```

这些 skills 是 Claude Code 生态的高质量 workflow 模板。Codex 不直接兼容此格式，但可作为 AGENTS.md 中「工作流规范」章节的参考来源。

---

*本文档由 Claude 审计生成，供 Codex 迁移参考。不修改业务代码。*
