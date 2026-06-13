# 黑芝麻智能单股入口试跑笔记

**日期**: 2026-06-12  
**入口**: `scripts/run_黑芝麻智能.py`  
**目标**: 验证单股深度报告 pipeline、Agent-Reach 官网证据、Markdown/HTML/PDF 输出和报告质量。

## 1. 运行入口

```bash
cd /Users/erichan/testsnow/scripts
python3 run_黑芝麻智能.py
```

运行结果：成功完成，未要求外部登录或危险采集。

数据使用情况：
- 雪球缓存：`data/raw/xueqiu_data_20260602_黑芝麻智能.json`（299 条帖子）
- 知乎采集：搜索关键词并经过质量门
- Agent-Reach：自动读取 `config/stocks.json` 中的官网 URL

## 2. 生成文件

| 文件 | 路径 | 大小 |
|------|------|------|
| Markdown 报告 | `/Users/erichan/testsnow/reports/黑芝麻智能_20260612.md` | 28 KB |
| HTML Dashboard | `/Users/erichan/testsnow/reports/黑芝麻智能_20260612.html` | 11 KB |
| PDF 报告 | `/Users/erichan/testsnow/reports/黑芝麻智能_20260612.pdf` | 1.7 MB |
| 原始输入数据 | `/Users/erichan/testsnow/data/raw/report_input_20260612_黑芝麻智能.json` | — |

PDF 共 **17 页**。

## 3. Agent-Reach 章节验证

### 3.1 是否出现

✅ 出现。Markdown 中章节标题为 `## Agent-Reach 外部证据观察`，PDF 中位于第 13–14 页。

### 3.2 官网证据内容

来源：`AgentReach(web)`  
URL：`https://www.blacksesame.com/zh/list_10/972.html`  
质量评分：**51**  
质量动作：**keep（高优先级证据）**

证据摘要包含：
- 黑芝麻智能华山 A2000U、A2000X
- ISO 26262 ASIL-D 最高功能安全认证
- 车规级最高安全标准、系统设计、硬件架构、安全机制

### 3.3 Jina 元数据清理

✅ 已清理。Markdown 表格行中：
- 无 `Title:` 前缀
- 无 `URL Source:`
- 无 `Markdown Content:`
- 表格单元格单行，无原始换行

渲染后的证据摘要示例：

```markdown
| — | 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证-黑芝麻智能科技有限公司 — 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证，标志着其在系统设计、硬件架构及安全机制等方面均已达到车规级最高安全标准。 近日，智能汽车计算芯片引领者黑芝麻智能宣布，旗下面向全场景通识智驾的华山A... | AgentReach(web) | 51 / 包含股票名称; 含 4 个业务关键词; 有URL; 含 2 类数据指标; 含 10 个日期; 标题充实; 内容较长; 标题+内容完整; 疑似门户/导航页，内容价值低 | [原文](https://www.blacksesame.com/zh/list_10/972.html) |
```

### 3.4 PDF 是否溢出

✅ 无溢出。PDF 第 14 页 Agent-Reach 表格内容在单元格内正确换行/截断，未出现单元格内容溢出到表格外的情况。

## 4. 报告质量检查

```bash
python3 /Users/erichan/testsnow/scripts/check_report_quality.py /Users/erichan/testsnow/reports/黑芝麻智能_20260612.md
```

结果：**PASS — No quality issues found.**

## 5. 报告关键章节检查

| 检查项 | 状态 |
|--------|------|
| 执行摘要 | ✅ |
| 综合评分与推荐 | ✅ |
| 估值与财务快照 | ✅ |
| 技术面分析 | ✅ |
| 趋势背景 | ✅ |
| 日线结构 | ✅ |
| 周线结构 | ✅ |
| 成交量确认 | ✅ |
| 波动率条件 | ✅ |
| 综合评分 | ✅ |
| 分析可信度 | ✅ |
| 风险提示与关注要点 | ✅ |
| Agent-Reach 外部证据观察 | ✅ |
| 行业特有风险因子评估 | ✅ |

## 6. Focused Tests

```bash
cd /Users/erichan/testsnow
python3 -m pytest tests/reporter/test_run_black_sesame_entry.py \
  tests/reporter/test_stock_reporter_agent_reach_config.py \
  tests/reporter/test_agent_reach_evidence_renderer.py -q
```

结果：**36 passed**。

## 7. 问题与阻塞

- **无网络问题**：知乎 API 和 DeepSeek API 均正常返回。
- **无 LLM 问题**：所有 LLM 调用均返回 200 OK。
- **无 PDF 问题**：PDF 成功生成，17 页，无渲染错误。
- **无 CDP/Chrome 问题**：未启动或控制已登录 Chrome；PDF 导出使用的是 Playwright/Kaleido 内置的无头 Chromium，非用户登录浏览器。

## 8. Git Status 检查

运行 `git status --short` 后：

- `reports/黑芝麻智能_20260612.*` 和 `data/raw/report_input_20260612_黑芝麻智能.json` 已被 `.gitignore` 忽略，未出现在 git status 中。
- 新增未跟踪文件：`.cache/zhihu_curator/*.json`（知乎采集缓存，运行入口自然生成）。
- 未出现源代码或配置文件的非预期改动。

## 9. 总体结论

- ✅ `run_黑芝麻智能.py` 入口运行成功。
- ✅ Markdown / HTML / PDF 全部生成。
- ✅ Agent-Reach 官网证据被正确读取、质量门 keep、渲染到报告。
- ✅ Jina 元数据前缀已清理，表格单行无溢出。
- ✅ 报告质量检查通过。
- ✅ 所有关键章节完整。
- ✅ Focused tests 36/36 通过。
- ✅ 未修改任何代码。
- ✅ 未抓取雪球详情页，未使用 CDP/已登录 Chrome。
