# Agent-Reach Curated URL Expansion — Claude Notes

**日期**: 2026-06-12  
**任务**: 在 `config/stocks.json` 中扩展黑芝麻智能的 Agent-Reach 官网 URL 信息源，仅做低风险扩源，并用 fast-test 单股入口验证。

## 1. 实际新增 URL

`config/stocks.json` 中 “黑芝麻智能” 的 `agent_reach.web_urls` 从 1 条扩展为 6 条：

| # | URL | 主题 |
|---|-----|------|
| 1 | https://www.blacksesame.com/zh/list_10/972.html | 华山A2000U/A2000X 获 ISO 26262 ASIL-D 认证（保留） |
| 2 | https://www.blacksesame.com/zh/list_9/977.html | 与上实科技战略合作，具身智能/机器人平台 |
| 3 | https://www.blacksesame.com/zh/list_9/966.html | 加入理想星环OS开源生态 |
| 4 | https://www.blacksesame.com/zh/list_9/964.html | 与东风汽车平台级合作，武当C1296 |
| 5 | https://www.blacksesame.com/zh/list_9/961.html | 与如祺出行战略合作，L4无人驾驶 |
| 6 | https://www.blacksesame.com/zh/list_10/912.html | 华山A1000获“中国芯”整车芯应用奖 |

未接入任何需要登录/cookie/反爬的平台（无 Twitter/X、小红书、抖音、雪球、微信、微博、Exa 等）。

## 2. 验证流程

### 2.1 Focused tests

```bash
cd /Users/erichan/testsnow
python3 -m pytest tests/reporter/test_run_black_sesame_entry.py \
  tests/reporter/test_stock_reporter_agent_reach_config.py \
  tests/reporter/test_agent_reach_evidence_renderer.py -q
```

结果：**36 passed**

（`test_run_black_sesame_entry.py` 已同步更新预期 URL 列表。）

### 2.2 单股 fast-test 报告入口

```bash
cd /Users/erichan/testsnow/scripts
python3 run_黑芝麻智能.py --fast-test
```

结果：成功完成。
- 未刷新知乎内容。
- 未运行 ZhihuCurator / DeepSeek curator。
- 未运行 `xueqiu_monitor_v2.py`。

### 2.3 生成的报告文件

| 文件 | 路径 | 大小 |
|------|------|------|
| Markdown | `/Users/erichan/testsnow/reports/黑芝麻智能_20260612.md` | 30 KB |
| HTML Dashboard | `/Users/erichan/testsnow/reports/黑芝麻智能_20260612.html` | 11 KB |
| PDF | `/Users/erichan/testsnow/reports/黑芝麻智能_20260612.pdf` | 1.7 MB |

PDF 共 **18 页**。

## 3. 报告质量检查

```bash
cd /Users/erichan/testsnow
python3 scripts/check_report_quality.py reports/黑芝麻智能_20260612.md
```

结果：**PASS — No quality issues found.**

## 4. Agent-Reach 章节验证

### 4.1 章节存在

✅ Markdown 中存在 `## Agent-Reach 外部证据观察`。  
✅ PDF 第 13 页开始展示该章节。

### 4.2 证据数量与动作

- 高优先级证据：**6 条**
- 低优先级观察：**0 条**
- 已过滤：**0 条**
- 检索状态：ok
- 质量门：ok

所有 6 条 URL 均通过质量门，动作全部为 **keep**。

### 4.3 每条 URL 的评分/原因

| URL | 评分 | 主要评分原因 |
|-----|------|--------------|
| 972.html | 51 | 包含股票名称；含 4 个业务关键词；有URL；含 2 类数据指标；含 10 个日期；标题充实；内容较长；标题+内容完整；疑似门户/导航页，内容价值低 |
| 977.html | 55 | 包含股票名称；含 7 个业务关键词；有URL；含 3 类数据指标；含 11 个日期；标题充实；内容较长；标题+内容完整；疑似门户/导航页，内容价值低 |
| 966.html | 50 | 包含股票名称；含 7 个业务关键词；有URL；含 2 类数据指标；含 10 个日期；标题充实；内容较长；标题+内容完整；含 1 个炒作信号；疑似门户/导航页，内容价值低 |
| 964.html | 55 | 包含股票名称；含 8 个业务关键词；有URL；含 3 类数据指标；含 10 个日期；标题充实；内容较长；标题+内容完整；疑似门户/导航页，内容价值低 |
| 961.html | 55 | 包含股票名称；含 7 个业务关键词；有URL；含 3 类数据指标；含 11 个日期；标题充实；内容较长；标题+内容完整；疑似门户/导航页，内容价值低 |
| 912.html | 53 | 包含股票名称；含 4 个业务关键词；有URL；含 3 类数据指标；含 11 个日期；标题充实；内容较长；标题+内容完整；疑似门户/导航页，内容价值低 |

### 4.4 Jina 元数据清理

✅ 报告中**未出现** `Title:`、`URL Source:`、`Markdown Content:` 字符串。

⚠️ 但发现新的视觉噪音：部分新增 URL（特别是 `/zh/list_9/` 页面）在证据摘要中仍出现：
- 重复的 Markdown H1：`# 黑芝麻智能与上实科技达成战略合作...`
- 导航文本：`联系我们 商务合作加入我们媒体资讯 选择语言 中文English [](https://www.blacksesame.com/zh)`

原因是这些 `/list_9/` 页面没有 `/list_10/` 获奖页面那种 `![Image N: 获奖]` 锚点，renderer 的正则未能提取正文，回退到整页内容后 H1/导航前缀未被完全清理。这属于 renderer 清理范围，但本次任务禁止修改 renderer，因此在 notes 中记录。

## 5. PDF 排版检查

✅ **无明显溢出**。Agent-Reach 表格跨 PDF 第 14–16 页，6 条证据均在表格单元格内正确换行/截断，没有出现单元格内容溢出到表格外或破坏页面布局的情况。

## 6. 是否修改代码

- ✅ 只修改了 `config/stocks.json`（配置扩源）。
- ✅ 同步更新了 `tests/reporter/test_run_black_sesame_entry.py` 的预期 URL 列表（使 focused test 通过）。
- ❌ 未修改任何 pipeline、Agent-Reach skill、renderer、评分、技术分析、LLM prompt、报告模板或入口脚本。
- ❌ 未运行 `xueqiu_monitor_v2.py`。
- ❌ 未抓取雪球详情页，未启动或控制已登录 Chrome/CDP。

## 7. Git Status 摘要

```bash
git status --short | grep -E "config/stocks|test_run_black_sesame"
```

变更：
- `M config/stocks.json`
- `?? tests/reporter/test_run_black_sesame_entry.py`（新文件，未跟踪）

生成的 `reports/黑芝麻智能_20260612.*` 和 `data/raw/report_input_20260612_黑芝麻智能.json` 已被 `.gitignore` 忽略，未出现在 git status 中。

`.cache/zhihu_curator/` 下有新的缓存 json 文件，是 fast-test 复用/运行过程中自然生成的知乎缓存，不属于代码改动。

## 8. 结论

- ✅ 6 条官网 URL 全部成功抓取并进入 keep。
- ✅ Markdown/PDF 中 Agent-Reach 章节展示多 URL 证据。
- ✅ 无 `Title:` / `URL Source:` / `Markdown Content:` 残留。
- ✅ PDF 表格无明显溢出。
- ✅ 报告质量检查 PASS。
- ✅ Focused tests 36/36 通过。
- ⚠️ 新增 `/list_9/` 页面存在 H1 重复和导航文本噪音，需后续在 renderer 层增强清理（本次未改代码）。
