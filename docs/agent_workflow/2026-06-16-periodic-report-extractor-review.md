# 定期报告摘录器 Code Review — 2026-06-16

**Review target**: Codex 新增的独立年报/半年报摘录器第一版
**Files reviewed**:
- `scripts/utils/periodic_report_extractor.py`
- `scripts/periodic_report_extractor.py`
- `tests/utils/test_periodic_report_extractor.py`

**Scope**: 不修改任何文件；不运行网络、Chrome/CDP、雪球详情页、完整报告；仅做只读审查与一次本地 Jina 文本运行观察。

---

## Status

**Needs minor fixes** before being recommended as a stable base for Source Intake evidence notes.
当前版本在受控单元测试与真实 Jina 年报文本上均未崩溃，但存在审计状态误识别、财务数字解析范围过窄、章节切片去重不足等可复现问题。修复后适合作为 **仅 evidence note** 的输入源。

---

## Findings（按 severity 排序）

### 1. 半年报审计状态识别遗漏标准表述变体 — Severity: Medium-High
- **Location**: `scripts/utils/periodic_report_extractor.py::_detect_audit_status()` line 165
- **Issue**: 代码匹配 `"标准无保留意见"`，但巨潮/Jina 文本实际使用 `"标准的无保留意见"`（带"的"）。对中简科技 2025 年报运行结果返回 `audited_attention_required`，而实际是标准无保留意见。
- **Impact**: 年报被错误标记为"需关注"，误导下游使用者。
- **Suggested fix**: 同时匹配 `"标准无保留意见"`、`"标准的无保留意见"`、`"无保留意见"`，并排除 `"非标准"`、`"保留意见"`、`"无法表示意见"` 等否定/保留字样。

### 2. `_metric_value()` 只取标签后 25 字符内第一个数字 — Severity: Medium-High
- **Location**: `scripts/utils/periodic_report_extractor.py::_metric_value()` line 329
- **Issue**: 正则 `re.escape(label) + r"[^-\d]{0,25}(-?[\d,]+(?:\.\d+)?)"` 一旦在 25 字符内没有数字就会失败；即使成功，也可能把行首"期末数"、"占比%"等无关数字当成指标值。真实文本中 `"归属于上市公司股东的净利润  3.15  亿元"` 可以命中，但 `"扣除非经常性损益后的净利润三者孰低为负值"` 这类法律/说明性片段会抢先匹配，导致真正数值被跳过。
- **Impact**: 扣非净利润、研发、存货跌价准备等关键指标可能漏读或误读，进而让 `financial_forensics` 的预警规则失效或误报。
- **Suggested fix**: 放宽扫描窗口到 200–400 字符；要求数字后紧跟金额单位（元、亿元、万元）或百分比；对同一标签多次匹配并选择最合理的数值（有单位、非表头）。

### 3. `_metric_with_growth()` 对真实 PDF/Jina 表格数字拼接后的文本鲁棒性不足 — Severity: Medium
- **Location**: `scripts/utils/periodic_report_extractor.py::_metric_with_growth()` lines 336–352
- **Issue**:
  - `_clean_text()` 会把数字间空格删除（`"846,092,620.66 812,470,190.54" → "846,092,620.66812,470,190.54"`），导致 `_plain_numbers()` 可能把两个数字解析成一个非法大数。
  - 占比列（如 `7.93%`）与同比列（如 `-10.06%`）混在同一行时，`growth_match` 只匹配第一个 `同比/增长/变动` 后的数字，容易把 "占营业收入比例" 的同比变动当成指标本身的增长。
  - 当 `growth_match` 为空时，fallback 用 `number_matches[0]` 与 `number_matches[1]` 计算同比，这在多列表格里几乎一定错误。
- **Evidence**: 中简科技年报应收账款行 `400,706,972.46 7.93% 835,058,483.10 17.99% -10.06%` 中，真实同比是 -10.06%，但当前 fallback 逻辑很可能取前两个数 `400,706,972.46 / 7.93%` 导致异常。所幸应收账款同比为负，未触发 `ar.growth > revenue.growth * 1.8`，避免了误报；但结构本身不可靠。
- **Suggested fix**: 优先用显式 `同比/增减/变动...%` 提取增长率；对缺失增长率的情况，只在明确两列标注"本期/上期"或"期末/期初"时才 fallback 计算；对百分比数字不要作为 base value。

### 4. 章节切片重复/碎片化 — Severity: Medium
- **Location**: `scripts/utils/periodic_report_extractor.py::_split_sections()` lines 173–183
- **Issue**: `SECTION_HEADING_RE` 同时匹配目录行和正式章节标题。对中简科技年报输出 `sections_found` 出现 20 个条目，包括：
  - `'第三节中“十一、公司未来发展的'`（句子内碎片）
  - `'第三节管理层讨论与分析............................'`（目录行）
  - `'第三节管理层讨论与分析'`（正式标题）
  - `'第五节十八、公司子公司重大事项”'`（句子内碎片）
- **Impact**: `_find_section()` 可能取到目录碎片或句子碎片，`_management_fallback_section()` 会被迫兜底；虽然目前观察到的 management_view 质量尚可，但存在抽到无关内容的隐患。
- **Suggested fix**: 切片后按 heading 去重；过滤带 `...`、`…………`、`............` 的目录行；优先使用没有省略号的 heading；对长度 < 6 或 > 40 的 heading 降低优先级。

### 5. `risk_disclosure` 抽取过粗且容易截断 — Severity: Medium
- **Location**: `scripts/utils/periodic_report_extractor.py::_extract_front_risks()` lines 186–201
- **Issue**: 取 `"重要提示"`、`"重大风险"`、`"释义"` 第一节或全文前 8000 字符，按关键词打分后截断 180 字符。中简科技实际只抽出 1 条，且证据是一句被截断的风险总述，没有具体到"客户集中"、"产品价格下降"等子风险。
- **Impact**: 风险披露标题永远相同（"公司披露的重大风险"），粒度太粗。
- **Suggested fix**: 在风险章节内部按子条目（常见格式 `1、...风险`、`（一）...风险`）拆分；为每个子风险生成独立 item。

### 6. `capital_action` 抽到公司治理/股权激励表格噪音 — Severity: Low-Medium
- **Location**: `scripts/utils/periodic_report_extractor.py::_extract_capex_and_events()` lines 223–234
- **Issue**: CAPEX 关键词包含 `"股权激励"`、`"员工持股"`，但全文扫描会抽到第四节/第五节的公司治理、持股计划表格内容，证据中出现大量 `□适用 不适用` 等格式噪音。
- **Impact**: 有用信号（回购、募投、重大合同）被稀释。
- **Suggested fix**: 优先在 `"第五节 重要事项"`、 `"募集资金"`、 `"重大合同"` 等章节扫描；对公司治理章节降权；过滤包含大量 `□//适用/不适用` 的表格碎片。

### 7. 财报排雷规则覆盖不足 — Severity: Low-Medium
- **Location**: `scripts/utils/periodic_report_extractor.py::_extract_financial_forensics()` lines 237–323
- **Current rules**: 应收增速>营收、扣非弱于净利润、经营现金流弱于利润、研发资本化率>30%、存货增速>营收、在建工程增速>50%。
- **Missing rules**（对军工/新材料/硬科技尤为重要）：
  - 应收票据（含商业承兑汇票）增速与结构
  - 合同资产/合同负债异动
  - 政府补助金额及占利润比
  - 研发人员数量/人均薪酬/学历结构变化
  - 商誉减值（并购类公司）
  - 受限资产/质押/冻结资产
  - 客户集中度（前五大客户占比）
  - 应收账款账龄结构（1 年以上占比）
  - 关联交易占比
  - 存货周转天数/应收周转天数趋势
- **Suggested fix**: 第一版不必全部实现，但应把上述缺失项列为 `forensics_signals` 中的 `"not_extracted"` 占位，或增加 `notes` 字段提醒人工复核；避免下游误把"未检出"当成"无风险"。

### 8. `_management_fallback_section()` 的结束边界可能包含第四节/公司治理噪音 — Severity: Low
- **Location**: `scripts/utils/periodic_report_extractor.py::_management_fallback_section()` lines 363–381
- **Issue**: fallback 以 `("第四节", "第五节", "重要事项", "公司治理")` 作为结束标记，但如果这些词在主营业务章节内部出现（如"详见第四节"），可能提前截断；如果没有找到结束标记，则固定取 20000 字符。
- **Evidence**: 中简科技运行输出中 management_view 未出现目录噪音，但结束边界仍可能过宽。
- **Suggested fix**: 采用章节切片后的 `"主营业务分析"` / `"核心竞争力分析"` / `"经营情况讨论与分析"` 区间，而不是字符串查找。

### 9. `_parse_number()` 不处理括号/全角数字/中文数字 — Severity: Low
- **Location**: `scripts/utils/periodic_report_extractor.py::_parse_number()` line 471
- **Issue**: 年报中负值可能写成 `(123,456.78)` 或 `−123.45`，当前正则只识别 `-`；全角数字、中文"一万"等虽不常见但可能出现在附注中。
- **Suggested fix**: 统一处理 `(num)` 为负数；保留全角数字映射（可选）。

### 10. CLI 路径合理但缺少 shebang 可执行性与入口注册 — Severity: Low
- **Location**: `scripts/periodic_report_extractor.py` lines 1–77
- **Issue**:
  - 文件顶部有 `#!/usr/bin/env python3`，但没有 `__main__` 之外的入口函数暴露。
  - 依赖 `sys.path.insert` 引入 `utils/`，在作为模块被导入时会修改全局路径。
  - 用户问及是否应放 `tools/`，目前 `scripts/` 是仓库约定（Node 规则要求脚本放 `scripts/`），但这是一个 Python 工具；若保持 `scripts/`，应与仓库其他 CLI 风格一致。
- **Suggested fix**: 保留 `scripts/periodic_report_extractor.py` 作为 CLI；将核心逻辑 `scripts/utils/periodic_report_extractor.py` 重命名为更内聚的模块名；避免在 import 时修改 `sys.path`（可把路径处理放到 `if __name__ == "__main__"` 块内）。

### 11. Markdown 输出缺少空状态说明 — Severity: Low
- **Location**: `scripts/utils/periodic_report_extractor.py::render_markdown()` lines 137–139
- **Issue**: 当没有高信号条目时只打印 `"未抽取到高信号条目。"`，未说明可能原因（输入为空/格式不支持/所有指标正常）。
- **Suggested fix**: 增加 `sections_found` 计数与审计状态，帮助判断是"无风险"还是"解析失败"。

---

## Must-fix before Source Intake integration

1. **修复审计状态识别**：匹配 `"标准的无保留意见"` 等变体，避免把正常年报标为 `audited_attention_required`。
2. **修复 `_metric_value()` 扫描窗口与表头误匹配**：放宽到 200–400 字符并要求金额单位；多候选时取最合理的值。
3. **修复 `_metric_with_growth()` 表格列混排问题**：显式优先提取 `同比/变动...%`；无显式增长率时不 fallback 用相邻数字硬算。
4. **章节切片去重/过滤目录碎片**：避免 `"...................."` 目录行进入 `sections`。
5. **增加 `financial_forensics` 缺失项占位或 notes**：明确告知哪些信号"未检查"，而不是"未检出"。

---

## Nice-to-have

1. 风险披露按子条目拆分，提升粒度。
2. `capital_action` 按章节加权，降低公司治理噪音。
3. 支持 `(num)` 负数格式与全角数字。
4. Markdown 输出增加审计状态、章节数、条目数等元信息。
5. 将 `sys.path.insert` 移入 `__main__` 块，避免污染全局导入路径。
6. 为 `--report-type` 增加 `--output` 目录批量处理模式（当前一次只处理一个文件）。

---

## Missing tests

以下 regression tests 建议补充，再接入 Source Intake：

1. **审计意见变体**: `test_detects_standard_unqualified_opinion_with_de()` 验证 `"标准的无保留意见"` 返回 `audited`。
2. **真实 Jina/PDF 文本**: 用 `/tmp/zhongjian_2025_annual_jina.txt` 做一个 fixture-free 的回归测试，断言不抛出、返回 `annual_report`、至少提取到 N 条 management_view。
3. **表格列混排不误报**: 已有 `test_balance_sheet_percentage_columns_do_not_create_fake_growth_signals`，建议再补一条确认 `营业收入 100 200 50%` 中 growth 识别为 `50%` 而非 `(200-100)/100`。
4. **`_metric_value()` 多候选选择**: 验证 `"扣除非经常性损益后的净利润三者孰低为负值 ... 扣非净利润 -2,000,000 元"` 能拿到 `-2000000` 而非 None。
5. **章节去重**: 输入同时包含目录和正式标题时，`sections_found` 不应包含带 `...` 的目录条目。
6. **空输入/非报告输入**: 验证空字符串、随机文本返回 `report_type: unknown`、`audit_status: unknown`、`items: []`。
7. **研发资本化率边界**: 当前只测 >=30%，补充 29.9% 不触发、30% 触发的边界用例。
8. **`_fmt_amount()` 负数与极小值**: 验证 `-1000`、`-1.5` 输出符合预期。
9. **PDF 输入路径 mock**: 当前 `test_cli_outputs_json_and_markdown` 只测 txt；用 `unittest.mock` mock `PdfReader` 或 `PyPDF2` 验证 `--pdf` 分支。

---

## 是否建议接入 Source Intake

**建议接入，但仅作为 evidence note，且必须修复 Must-fix 后再接入。**

- **适合的角色**: 输出 `risk_disclosure`、`management_view`、`capital_action`、`financial_forensics` 四类结构化观察，全部标记为 `source_type: periodic_report_excerpt`、`source_credit: 75`（年报/半年报本身信用高，但摘录器规则化提取可能出错，需降档）。
- **不适合的角色**: 不直接进入核心事实、评分或风险评分；`management_view` 明确不是 confirmed fact；`financial_forensics` 规则触发项只能作为"需复核信号"，不能作为结论。
- **接入方式**: 将 extractor 输出写入 Source Intake 的 candidate pool，经过与研报/公告同等的 claim verification 流程后，才可被 deep analysis / risk 模块引用。

---

## 是否发现越界行为

**未发现越界行为。**

- ✅ 不访问网络
- ✅ 不调用 LLM
- ✅ 不接入评分/风险/核心事实生成
- ✅ 不接入主报告 pipeline
- ✅ 不生成最终报告
- ✅ CLI 仅读取本地 txt/pdf/stdin，输出 markdown/json

唯一需要提醒的是：CLI 的 `--pdf` 分支依赖可选包 `pypdf`/`PyPDF2`，当前未安装时会给用户清晰报错，属于预期行为。

---

## 运行记录

```bash
python3 -m pytest tests/utils/test_periodic_report_extractor.py -q
# 8 passed in 0.20s

python3 scripts/periodic_report_extractor.py --help
# 输出正常，支持 --txt/--pdf/--report-type/--industry/--format/--output

python3 scripts/periodic_report_extractor.py \
  --txt /tmp/zhongjian_2025_annual_jina.txt \
  --industry hardtech --report-type annual_report --format json \
  --output /tmp/periodic_report_review_out.json
# items: 17, sections: 20, audit: audited_attention_required, report_type: annual_report
```

> 注意：上述 `audit: audited_attention_required` 正是 finding #1 所述的误识别；实际年报审计意见为"标准的无保留意见"。
