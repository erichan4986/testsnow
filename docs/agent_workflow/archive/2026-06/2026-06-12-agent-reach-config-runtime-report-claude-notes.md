# Agent-Reach 配置运行时报告验证笔记

**日期**: 2026-06-12  
**目标**: 验证 `config/stocks.json` 中 `黑芝麻智能` 的 Agent-Reach seed URL 在正常报告生成流程中被正确加载、抓取、质量门处理并渲染到 Markdown/PDF。  
**验证范围**: 仅使用正常入口 `xueqiu_monitor_v2.py`（不启用 `--xueqiu` / CDP / Playwright 详情页自动化）。

## 1. 初始阻塞与修复

### 1.1 ReportManager 导入失败

#### 命令

```bash
cd /Users/erichan/testsnow/scripts
python xueqiu_monitor_v2.py 2>&1 | tee /tmp/xueqiu_monitor_v2_20260612.log
```

#### 错误

```
Traceback (most recent call last):
  File "/Users/erichan/testsnow/scripts/xueqiu_monitor_v2.py", line 40, in <module>
    from utils.reporter import ReportManager
ImportError: cannot import name 'ReportManager' from 'utils.reporter' (/Users/erichan/testsnow/scripts/utils/reporter/__init__.py)
```

#### 根因

- `scripts/utils/reporter.py`（模块）中定义了 `ReportManager`。
- `scripts/utils/reporter/__init__.py`（同名包）未导出 `ReportManager`。
- `xueqiu_monitor_v2.py` 的 `from utils.reporter import ReportManager` 实际命中的是包，而非模块，导致导入失败。

#### 修复

新建 `scripts/utils/reporter/report_manager.py`，将 `ReportManager` 类移入包内；在 `scripts/utils/reporter/__init__.py` 中改为：

```python
from .report_manager import ReportManager
```

### 1.2 numpy 类型 JSON 序列化失败

#### 错误

在修复导入后继续运行，采集 `长春高新` 技术指标时遇到：

```
TypeError: Object of type bool_ is not JSON serializable
```

位置：`xueqiu_monitor_v2.py` 中 `json.dumps(tech_data, ...)` 调用。

#### 修复

在 `xueqiu_monitor_v2.py` 的 5 处 `json.dumps(...)` 调用中统一追加 `default=str`：

- `tech_data`
- `reports`
- `anns`
- `fund`
- `news`

这是最小改动，使 numpy 标量（如 `numpy.bool_`）可序列化为字符串，避免主流程中断。

---

## 2. 验证运行

### 命令

```bash
cd /Users/erichan/testsnow/scripts
python xueqiu_monitor_v2.py 2>&1 | tee /tmp/xueqiu_monitor_v2_20260612.log
```

> 未加 `--xueqiu`，未使用 CDP / Playwright 详情页自动化；数据来自东财列表页。

### 生成文件

- Markdown 报告：`/Users/erichan/testsnow/reports/黑芝麻智能_20260612.md`
- HTML Dashboard：`/Users/erichan/testsnow/reports/黑芝麻智能_20260612.html`
- PDF 报告：`/Users/erichan/testsnow/reports/黑芝麻智能_20260612.pdf`

### 配置确认

`config/stocks.json` 中 `黑芝麻智能` 配置：

```json
{
  "name": "黑芝麻智能",
  "code": "02533",
  "xueqiu_code": "HK02533",
  "gid": "hk02533",
  "agent_reach": {
    "enabled": true,
    "web_urls": [
      "https://www.blacksesame.com/zh/list_10/972.html"
    ]
  }
}
```

---

## 3. 验证项结果

### 3.1 正常流程是否读取配置

✅ **通过**。`xueqiu_monitor_v2.py` 读取 `stocks.json` 后构造：

```python
agent_reach_configs = {
    s["name"]: s["agent_reach"]
    for s in stocks
    if s.get("agent_reach")
}
```

`PerStockReporter` 对 `黑芝麻智能` 解析出 `agent_reach_enabled = True`，并传入 `agent_reach_urls`。

### 3.2 build_stock_report_pipeline 是否启用 Agent-Reach

✅ **通过**。`PerStockReporter.generate_stock_report()` 调用：

```python
pipeline = build_stock_report_pipeline(enable_agent_reach=agent_reach_enabled)
```

日志中可看到 Agent-Reach 三个技能均被执行：

```
Skill 'agent_reach_query' completed in 0.0000s
Skill 'agent_reach_fetch' completed in 3.2392s
Skill 'agent_reach_quality' completed in 0.0124s
```

### 3.3 Web/Jina fetch 是否对官方 URL 执行

✅ **通过**。Agent-Reach fetch 通过 `WebConnector` 调用 Jina Reader：

```
https://r.jina.ai/https://www.blacksesame.com/zh/list_10/972.html
```

抓取到的内容标题为：

> 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证-黑芝麻智能科技有限公司

### 3.4 质量门动作（keep / demote / discard）

✅ **通过 — 结果为 keep**。

| 项目 | 值 |
|------|-----|
| 来源平台 | AgentReach(web) |
| 质量评分 | **51** |
| 动作 | **keep** |
| 评分原因 | 包含股票名称；含 4 个业务关键词；有URL；含 2 类数据指标；含 10 个日期；标题充实；内容较长；标题+内容完整；疑似门户/导航页，内容价值低 |

说明：
- Web 配置 `keep_threshold=50`，`demote_threshold=30`，51 分刚好越过 keep 线。
- 虽然触发“疑似门户/导航页”惩罚，但因 `user_provided_url=True`，未强制降级到 discard。
- 未出现 discard。

### 3.5 Agent-Reach 证据节是否出现在 Markdown

✅ **通过**。报告数据来源行已包含 `Agent-Reach外部检索`，并出现独立章节：

```markdown
## Agent-Reach 外部证据观察

> 本节仅展示外部检索证据，不参与综合评分、风险评分或 LLM 深度分析结论。

### 本期外部证据概览

- 高优先级证据：1 条；低优先级观察：0 条；已过滤：0 条
- 主要主题：产品/量产进展
- 检索状态：ok；质量门：ok

### 主题化证据观察

#### 产品/量产进展

| 时间 | 证据摘要 | 来源 | 质量 | 链接 |
|------|----------|------|------|------|
| — | Title: 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证-黑芝麻智能科技有限公司 — 
URL Source: https://www.blacksesame.com/zh/list_10/972.html

Markdown Content:
# 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最... | AgentReach(web) | 51 / ... | [原文](https://www.blacksesame.com/zh/list_10/972.html) |
```

### 3.6 可读性与视觉干扰

⚠️ **基本可读，但存在视觉噪音和表格溢出**。

Markdown/PDF 中证据摘要直接保留了 Jina Reader 的原始前缀：

- `Title:`
- `URL Source:`
- `Markdown Content:`

这些前缀在表格单单元格内占用了大量空间，使“证据摘要”列显得臃肿。PDF 第 8 页可见表格单元格内容溢出到表格外，实际正文内容被截断/推至表格下方，影响阅读体验。

**建议（非本次修复范围）**: 在 `WebConnector` 或渲染层对 Jina 返回的元数据前缀做清理，仅保留标题 + 正文摘要。

### 3.7 未使用 Xueqiu/CDP/Playwright 详情页自动化

✅ **通过**。运行命令未加 `--xueqiu`，环境变量 `USE_XUEQIU` 未设置，流程使用东财列表页，未触发雪球详情页/CDP/Playwright 详情页自动化。

### 3.8 PDF 导出与溢出检查

✅ **PDF 成功生成**：`/Users/erichan/testsnow/reports/黑芝麻智能_20260612.pdf`（共 11 页，约 1.5 MB）。

Agent-Reach 章节位于 **第 8 页**。截图显示：
- 章节标题、概览、主题化表格均正常呈现。
- 表格“证据摘要”单元格因包含完整 Jina 原始输出而出现内容溢出，导致 `URL Source:` 和 `Markdown Content:` 被挤到表格线之外。

结论：**PDF 未因 Agent-Reach 章节导致整体分页崩溃或大面积截断，但单单元格内容溢出影响美观**。

---

## 4. 源码修改清单

| 文件 | 修改内容 | 原因 |
|------|----------|------|
| `scripts/utils/reporter/__init__.py` | 新增 `from .report_manager import ReportManager` | 修复 ReportManager 导入失败 |
| `scripts/utils/reporter/report_manager.py` | 新建文件，放入 `ReportManager` 类 | 避免模块/包同名冲突导致的循环导入 |
| `scripts/xueqiu_monitor_v2.py` | 5 处 `json.dumps(...)` 追加 `default=str` | 修复 numpy 类型 JSON 序列化失败 |

---

## 5. 回归测试

运行与 Agent-Reach 和报告组装相关的测试：

```bash
python -m pytest tests/reporter/test_agent_reach_connector.py \
  tests/reporter/test_agent_reach_quality_skill.py \
  tests/reporter/test_agent_reach_evidence_renderer.py \
  tests/reporter/test_pipeline_integration.py \
  tests/reporter/test_assembly_skills.py -q
```

结果：**89 passed**。

全量测试：

```bash
python -m pytest tests/ -q
```

结果：**458 passed, 6 skipped, 1 failed**。

失败用例：`tests/reporter/test_lexin_phase3_report.py::test_negative_bias_advisor_no_chasing`，与本次修改无关（涉及 `technical_analyzer` 的 BIAS 顾问逻辑）。

## 6. 总体结论

- **配置生效**：`config/stocks.json` 中 `黑芝麻智能` 的 Agent-Reach seed URL 已被正常报告流程读取。
- **Pipeline 启用**：`build_stock_report_pipeline` 对 `黑芝麻智能` 启用了 Agent-Reach，三个技能顺序执行。
- **Web/Jina 抓取成功**：官方 URL 内容被成功获取并进入质量门。
- **质量门结果**：评分为 51，动作 **keep**，未 discard。
- **Markdown 渲染**：`Agent-Reach 外部证据观察` 章节已出现，数据来源标注正确。
- **PDF 导出成功**：Agent-Reach 章节位于第 8 页，未造成整页丢失，但表格单单元格存在内容溢出。
- **修复 2 处 plumbing bug** 后完成全流程验证。
