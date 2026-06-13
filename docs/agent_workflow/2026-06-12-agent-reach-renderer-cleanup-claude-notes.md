# Agent-Reach Renderer Cleanup — Black Sesame Official Site Noise

**日期**: 2026-06-12  
**任务**: 修复 Agent-Reach 证据摘要中黑芝麻官网 `/zh/list_9/` 页面的导航噪音与重复 H1，仅做 renderer 清理。  
**约束**: 只修改 `agent_reach_evidence_renderer.py`、对应测试与本文档；不动采集、质量门、pipeline、评分、技术分析、LLM 合成、报告模板、入口脚本或配置。

## 1. 改动文件

| 文件 | 变更摘要 |
|------|----------|
| `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` | 在 `_make_excerpt()` 中先对 `title` 调用 `_clean_jina_title()` 再传给 `_clean_jina_content()`，确保带 `Title:` 前缀的标题也能正确去重 H1；保留并复用已有的 Jina 元数据剥离、导航词清理、正文提取、单行化逻辑。 |
| `tests/reporter/test_agent_reach_evidence_renderer.py` | 新增 `test_renderer_supports_six_black_sesame_keep_items()`：传入 6 条黑芝麻官网 URL 的 keep 项，验证 renderer 能同时展示 6 条，且摘要中无导航噪音、无重复 H1、无原始换行。 |

## 2. 修复内容

### 2.1 标题前缀导致 H1 去重失效

之前 `_make_excerpt()` 把 item 的原始 `title`（常带有 Jina 的 `Title: ` 前缀）直接传给 `_clean_jina_content()` 做 H1 去重。当 content 中的 H1 没有 `Title: ` 前缀时，正则无法匹配，导致摘要出现 `title — # 标题...` 的重复。

修复：先在 `_make_excerpt()` 中对 `title` 调用 `_clean_jina_title()` 去掉前缀，再传入正文清理函数。

```python
title = getattr(item, "title", "") or ""
title = self._clean_jina_title(title)  # 新增
cleaned = self._clean_jina_content(content, title)
```

### 2.2 导航噪音清理（复用已有逻辑）

renderer 中已有的 `nav_phrases` 集合已覆盖黑芝麻官网常见导航词：

- 联系/合作类：`联系我们`、`商务合作`、`加入我们`、`媒体资讯`
- 语言/站点类：`选择语言`、`中文`、`English`、`首页`
- 公司信息类：`公司信息`、`基本介绍`、`概况`、`团队`、`DNA`、`认证`、`发展历程` 等
- 产品/解决方案/投资者关系菜单项

`_drop_nav_tokens()` 以空格分词后精确匹配删除，保留正文中的合作方、芯片型号、平台名称等关键信息。

### 2.3 Markdown 表格单元格单行化

清理流程最后用 `re.sub(r"[\s]+", " ", text)` 把换行、制表符、连续空格折叠为单个空格，避免 Markdown/PDF 表格单元格出现原始换行或溢出。

## 3. 测试

运行命令：

```bash
cd /Users/erichan/testsnow
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py \
  tests/reporter/test_assembly_skills.py \
  tests/reporter/test_run_black_sesame_entry.py -q
```

结果：**41 passed**。

本次新增的测试：

- `test_renderer_supports_six_black_sesame_keep_items`
  - 构造 6 条黑芝麻官网 URL keep 项
  - 断言 6 条 URL 均出现在输出中
  - 断言 `| — |` 表格行数量为 6
  - 断言无 `联系我们`、`首页`、`# 黑芝麻智能` 等噪音

已有的相关测试仍通过：

- `test_jina_metadata_cleaned_in_table_row`
- `test_title_not_duplicated_when_h1_matches_title`
- `test_black_sesame_list9_nav_noise_removed`
- `test_black_sesame_list9_body_keeps_key_info`

## 4. fast-test 报告

运行命令：

```bash
cd scripts
python3 run_黑芝麻智能.py --fast-test
```

结果：成功生成。

生成文件：

- Markdown: `reports/黑芝麻智能_20260612.md`
- HTML: `reports/黑芝麻智能_20260612.html`
- PDF: `reports/黑芝麻智能_20260612.pdf`

`python3 scripts/check_report_quality.py reports/黑芝麻智能_20260612.md`：**PASS**。

## 5. 清理前后摘要变化

### 修复前（典型问题行）

```markdown
| — | Title: 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证-黑芝麻智能科技有限公司 — 
# 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证-黑芝麻智能科技有限公司 [联系我们](javascript:;) [商务合作](mailto:mkt@bst.ai)[加入我们](mailto:...) | AgentReach(web) | ... |
```

问题：

- 残留 `Title:` 前缀。
- 行内重复 H1 `# 黑芝麻智能...`。
- 包含 `联系我们`、`商务合作` 等导航文本。
- 原始换行破坏 Markdown 表格结构。

### 修复后（本次 fast-test 实际输出示例）

```markdown
| — | 黑芝麻智能加入理想星环OS开源生态，共建智能汽车底层技术底座-黑芝麻智能科技有限公司 — 黑芝麻智能正式宣布加入理想星环OS开源生态。双方将围绕开源共建展开深度合作，基于黑芝麻智能全系列芯片平台，对星环OS进行深度适配与性能优化，携手推动智能汽车底层技术的开放协同与产业创新，加速整车操作系统的规模化落地。 理想星环OS是理想汽车... | AgentReach(web) | 50 / 包含股票名称; 含 7 个业务关键词; 有URL; 含 2 类数据指标; 含 10 个日期; 标题充实; 内容较长; 标题+内容完整; 含 1 个炒作信号; 疑似门户/导航页，内容价值低 | [原文](https://www.blacksesame.com/zh/list_9/966.html) |
```

改进：

- 无 `Title:` / `URL Source:` / `Markdown Content:`。
- 无 `# 黑芝麻智能...` 重复 H1。
- 无 `联系我们`、`商务合作`、`加入我们`、`媒体资讯`、`选择语言`、`首页`、`公司信息` 等导航词。
- Markdown 表格单元格为单行，PDF 表格无溢出。
- 保留关键信息：`理想星环OS`、`全系列芯片平台`、`如祺出行`、`L4`、`Robotaxi`、`华山 A1000`、`产融芯链行动` 等。

## 6. 关于“6 条 URL 全部 keep”的说明

`config/stocks.json` 中黑芝麻智能确实配置了 6 条官网 URL，renderer 的 `MAX_KEEP_ITEMS = 6` 也支持最多展示 6 条。本次新增的测试也验证了 renderer 在收到 6 条 keep 项时能全部展示。

但实际 fast-test 报告中展示的高优先级证据数量由上游 **Agent-Reach 质量门** 决定（不在本次修改范围内）。本次两次 fast-test 运行分别观察到 5 条和 3 条 keep 项，说明质量门根据实时抓取内容动态过滤。renderer 仅负责**把被 keep 的项干净地展示出来**，不修改质量评分结果，也不强制提升 keep 数量。

因此：

- ✅ renderer 具备展示 6 条 URL 的能力（测试覆盖）。
- ✅ renderer 正确清理了被 keep 项的导航噪音、重复 H1 与原始换行。
- ⚠️ 实际报告中 keep 数量取决于质量门，不在 renderer 层控制。

## 7. 人工检查结果

- ✅ Agent-Reach 章节仍存在（`reports/黑芝麻智能_20260612.md` 第 294 行）。
- ✅ 渲染后的摘要中不再出现 `Title:` / `URL Source:` / `Markdown Content:`。
- ✅ 渲染后的摘要中不再出现 “联系我们 商务合作 加入我们 媒体资讯 选择语言”。
- ✅ 渲染后的摘要中不再出现重复的 `# 黑芝麻智能...`。
- ✅ Markdown 表格单元格无原始换行。
- ✅ PDF 表格无明显溢出（已检查 `reports/agent_reach_page_13.png`、`reports/agent_reach_page_14.png`）。

## 8. 总体结论

- ✅ 仅修改了 renderer 与测试，未触碰采集、质量门、pipeline、评分、技术分析、LLM 合成、配置或入口脚本。
- ✅ Jina 元数据前缀已清理。
- ✅ 重复 H1 已避免（包括 title 带 `Title:` 前缀的情况）。
- ✅ 黑芝麻官网导航噪音已移除。
- ✅ 关键正文信息保留。
- ✅ Markdown/PDF 表格无溢出。
