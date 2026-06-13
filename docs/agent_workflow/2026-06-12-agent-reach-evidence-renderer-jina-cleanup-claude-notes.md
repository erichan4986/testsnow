# Agent-Reach Evidence Renderer Jina Cleanup — Claude Notes

**日期**: 2026-06-12  
**任务**: 清理 Agent-Reach 证据表格中的 Jina Reader 元数据前缀与换行，避免 Markdown 表格变形和 PDF 单元格溢出。  
**约束**: 只修改 `AgentReachEvidenceRenderer` 和对应测试；不动 WebConnector、质量门、pipeline、评分、技术分析、Xueqiu/CDP/Playwright 或入口脚本。

## 1. 改动文件

| 文件 | 变更摘要 |
|------|----------|
| `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` | 新增 `_clean_jina_content()` 和 `_clean_jina_title()`；`_make_excerpt()` 和 `_render_table()` 调用清理逻辑 |
| `tests/reporter/test_agent_reach_evidence_renderer.py` | 新增 3 个测试：Jina 元数据清理、标题去重、pipe 转义 |

## 2. 修复内容

### 2.1 清理 Jina 元数据前缀

- 从 `content` 中移除：
  - `Title: ...` 行
  - `URL Source: <url>` 行
  - `Markdown Content:` 行
- 从 `title` 字段移除 `Title: ` 前缀（WebConnector 把 Jina 首行原样存进 `title`）。

### 2.2 单行化表格单元格

- 把 `\r\n` / `\r` 统一为 `\n`。
- 清理后用 `[\s]+` 折叠为单个空格。
- 表格行中不再包含原始换行。

### 2.3 标题去重

- 如果 `content` 开头包含与 `title` 相同或前缀相同的 Markdown H1，则删除该 H1，避免渲染成 `title — title...`。

### 2.4 提取正文、丢弃导航噪音

- 针对 Black Sesame 官网这种 Jina 返回整页 HTML→Markdown 的情况，用正则匹配 `![Image N: 获奖](...)` + `YYYY/MM/DD` 日期锚点到 `上一篇/下一篇/热门新闻/热门标签/关注我们` 之间的内容作为正文。
- 移除 Markdown 图片语法，并把链接语法折叠为链接文本。

## 3. 测试

运行命令：

```bash
cd /Users/erichan/testsnow
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_assembly_skills.py -q
```

结果：**36 passed**。

全量测试：

```bash
python3 -m pytest tests/ -q
```

结果：**461 passed, 6 skipped, 1 failed**。

失败用例仍是 `tests/reporter/test_lexin_phase3_report.py::test_negative_bias_advisor_no_chasing`（BIAS 顾问逻辑，与本次 renderer 改动无关）。

## 4. 验证前后对比

### 4.1 修复前 Markdown 行（来自 `reports/黑芝麻智能_20260612.md`）

```markdown
| — | Title: 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证-黑芝麻智能科技有限公司 — 
# 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证-黑芝麻智能科技有限公司 [联系我们](javascript:;) [商务合作](mailto:mkt@bst.ai)[加入我们](mailto:... | AgentReach(web) | 51 / ... |
```

问题：
- 包含 `Title:`、`URL Source:`、`Markdown Content:` 前缀。
- 行内原始换行破坏 Markdown 表格。
- 标题与 H1 重复。
- PDF 第 8 页单元格溢出。

### 4.2 修复后 Markdown 行

```markdown
| — | 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证-黑芝麻智能科技有限公司 — 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证，标志着其在系统设计、硬件架构及安全机制等方面均已达到车规级最高安全标准。 近日，智能汽车计算芯片引领者黑芝麻智能宣布，旗下面向全场景通识智驾的华山A... | AgentReach(web) | 51 / 包含股票名称; 含 4 个业务关键词; 有URL; 含 2 类数据指标; 含 10 个日期; 标题充实; 内容较长; 标题+内容完整; 疑似门户/导航页，内容价值低 | [原文](https://www.blacksesame.com/zh/list_10/972.html) |
```

改进：
- 无 `Title:` / `URL Source:` / `Markdown Content:`。
- 单行表格单元格。
- 标题只出现一次。
- 摘要保留 ASIL-D / A2000U / A2000X 正文内容。

### 4.3 修复后 PDF 第 8 页

已保存截图：`/tmp/黑芝麻智能_agent_reach_page8_final.png`

观察：
- Agent-Reach 章节标题、概览、主题表格完整呈现。
- 表格单元格内容被正确截断/换行，未溢出到表格外。
- 整个页面排版整齐，无破坏性溢出。

## 5. 偏差与未解决问题

- **无偏差**：所有改动集中在 renderer 层，未触碰 WebConnector、质量门、pipeline 等约束范围外的文件。
- **未发现新阻塞**。

## 6. 总体结论

- ✅ Jina 元数据前缀已清理。
- ✅ Markdown 表格单元格已单行化。
- ✅ 标题重复已避免。
- ✅ 有用正文内容被保留。
- ✅ pipe 转义行为保留。
- ✅ renderer 章节顺序和主题分类未变。
- ✅ PDF 第 8 页不再出现单元格溢出。
