# Source Evidence Visibility Sprint Implementation Notes

日期：2026-06-15

## 目标

一次性实现 Source Evidence Visibility Sprint：在单股 Markdown 报告中新增只读、分层信用的 Source Intake 证据观察章节，不影响评分、风险、EV、技术面、LLM synthesis、引用或最终建议。

## 改动文件

1. `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`（新增）
   - `SourceIntakeEvidenceRenderer`：纯展示层渲染器。
   - 仅在 `source_intake_enabled=True` 且 `source_intake_status` 不为 disabled/error/empty 时渲染。
   - 空 Source Intake 返回 `""`，避免报告噪声。
   - 动态生成来源分层概览表（官方公告 / 东方财富新闻 / 券商研报摘要 / 其他来源）。
   - 动态读取 `source_credit` 与 `verification_status`，新闻/券商研报永远归一化为 `professional_observation`。
   - 最多渲染 6 条代表性证据，优先级：官方公告 > 券商研报 > 新闻 > 未知。
   - 清理 `[^n]`、`[n]`、`AgentReach(...)`、长 URL、常见 Jina/PDF 元数据前缀。
   - 对 Markdown 表格竖线进行转义。
   - 不修改 `ctx` 或 `SynthesisItem` 对象。

2. `scripts/utils/report_skills/assembly_skills.py`
   - 在 `ReportAssemblySkill.RENDERERS` 中注册 `source_intake_evidence`：位于 `deep_analysis` 之后、`agent_reach_evidence` 和 `risk` 之前。

3. `tests/reporter/test_source_intake_evidence_renderer.py`（新增）
   - 覆盖：disabled/empty/error 返回空字符串、官方公告 high-credit、新闻/研报 professional_observation、malformed 元数据归一化、动态计数、6 条上限、优先级排序、citation/AgentReach/URL 清理、pipe 转义、未知来源回退、ctx/item 不可变性、merged keep fallback、信用范围、表格列头、Jina PDF 元数据剥离。

4. `tests/reporter/test_assembly_skills.py`
   - 新增 renderer 顺序测试、Source Intake 键缺失时报告仍可渲染、Agent-Reach-only 报告不出现 Source Intake 章节。

## 测试结果

### Focused tests

```bash
python3 -m pytest tests/reporter/test_source_intake_evidence_renderer.py tests/reporter/test_assembly_skills.py -q
# 33 passed
```

### 相关回归

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_deep_analysis_renderer.py -q
# 58 passed
```

### Reporter 全量

```bash
python3 -m pytest tests/reporter -q
# 675 passed, 6 skipped
```

### 全量回归

```bash
python3 -m pytest tests -q
# 972 passed, 6 skipped
```

## Runtime Validation

### 运行命令

```bash
cd scripts && python3 run_黑芝麻智能.py --fast-test
cd scripts && python3 run_中简科技.py --fast-test
cd scripts && python3 run_圣邦股份.py --fast-test
```

### 生成文件

| 股票 | Markdown | HTML | PDF | Agent-Reach audit JSON |
|---|---|---|---|---|
| 黑芝麻智能 | ✅ | ✅ | ✅ | ✅ |
| 中简科技 | ✅ | ✅ | ✅ | ❌（Agent-Reach 未启用） |
| 圣邦股份 | ✅ | ✅ | ✅ | ❌（Agent-Reach 未启用） |

### Quality Check

```bash
python3 scripts/check_report_quality.py reports/黑芝麻智能_20260615.md  # PASS
python3 scripts/check_report_quality.py reports/中简科技_20260615.md    # PASS
python3 scripts/check_report_quality.py reports/圣邦股份_20260615.md    # PASS
```

### Source Intake Section 出现情况

| 股票 | source_intake_enabled | Section 出现 | 行号 |
|---|---|---|---|
| 黑芝麻智能 | False | ❌ 未出现 | — |
| 中简科技 | True | ✅ 出现 | 236 |
| 圣邦股份 | True | ✅ 出现 | 295 |

### HTML Dashboard 是否包含 Section

**否。** `HTMLDashboardRenderer` 独立渲染 HTML dashboard，不基于 Markdown 转换，因此 HTML 中未出现 Source Intake 章节。Markdown 报告包含该章节。

### 三股报告关键指标

| 股票 | 综合评分 | EV | AI 综合推荐 | 风险等级 | 仓位建议 |
|---|---|---|---|---|---|
| 黑芝麻智能 | 4.1/10 | N/A% | N/A — 技术面偏弱 | 2.0/10 | 趋势破坏期，以观望或防守仓位为主，建议 0-5% |
| 中简科技 | 5.9/10 | N/A% | N/A — 估值健康度良好；技术面偏弱；社区情绪偏乐观 | 5.0/10 | 趋势破坏期，以观望或防守仓位为主，建议 0-5% |
| 圣邦股份 | 7.5/10 | +10.25% | **看多但等待入场** | 2.0/10 | 当前入场质量不足，建议等待回调或盈亏比改善，仓位 5-10% |

圣邦股份出现 7.5/+10.25% 而非此前某次运行的 6.5/+7.66%，原因是 LLM 质量门在该次运行中将唯一看涨 knowledge post 降级（keep=0），本次运行 keep=1；该波动来自 LLM 非确定性，与 Source Intake 展示层无关。Entry Quality Guardrail 仍在生效（"看多但等待入场"、入场约束、仓位降级）。

### 引用与隔离检查

- 黑芝麻智能：Agent-Reach 章节独立存在；未出现 Source Intake 章节。
- 中简科技 / 圣邦股份：Source Intake 章节内无 `[^n]` 编号引用。
- Source Intake 章节与 Agent-Reach 章节在 source_intake_enabled 的股票中同时出现时保持分离（中简科技/圣邦股份未启用 Agent-Reach）。
- 未发现 Source Intake 或 Agent-Reach 编号引用污染深度分析章节。

### Source Intake 分层概览（最终报告）

**中简科技**

| 来源类型 | 数量 | 信用等级 | 事实用途 | 状态 |
|---|---|---|---|---|
| 官方公告 | 8 | 95 | confirmed_fact | 可用于事实确认 |
| 券商研报摘要 | 8 | 65 | professional_observation | 专业观察 |
| 东方财富新闻 | 10 | 60 | professional_observation | 背景资讯 |

**圣邦股份**

| 来源类型 | 数量 | 信用等级 | 事实用途 | 状态 |
|---|---|---|---|---|
| 官方公告 | 11 | 95 | confirmed_fact | 可用于事实确认 |
| 券商研报摘要 | 8 | 65 | professional_observation | 专业观察 |
| 东方财富新闻 | 10 | 60 | professional_observation | 背景资讯 |

## 生成/修改的文件

- `reports/黑芝麻智能_20260615.md`
- `reports/黑芝麻智能_20260615.html`
- `reports/黑芝麻智能_20260615.pdf`
- `reports/黑芝麻智能_20260615_agent_reach.json`
- `reports/中简科技_20260615.md`
- `reports/中简科技_20260615.html`
- `reports/中简科技_20260615.pdf`
- `reports/圣邦股份_20260615.md`
- `reports/圣邦股份_20260615.html`
- `reports/圣邦股份_20260615.pdf`
- `data/raw/report_input_20260615_黑芝麻智能.json`
- `data/raw/report_input_20260615_中简科技.json`
- `data/raw/report_input_20260615_圣邦股份.json`
- `knowledge/10-Stocks/中简科技/evidence/`（evidence notes 更新）
- `knowledge/10-Stocks/圣邦股份/evidence/`（evidence notes 更新）
- `knowledge/10-Stocks/中简科技/MOC.md`（更新）
- `knowledge/10-Stocks/圣邦股份/MOC.md`（更新）
- `reports/黑芝麻智能_radar.png`（重新生成）
- `reports/中简科技_radar.png`（重新生成）
- `reports/圣邦股份_radar.png`（重新生成）

上述 reports/data/raw/evidence 缓存文件受 `.gitignore` 保护，未出现在 git status 的未跟踪列表中；`knowledge/**/MOC.md` 与 `*_radar.png` 会显示为已修改。

## 偏离点

1. **初始实现未剥离 Jina/PDF 元数据**：代表性证据摘录中一度出现 `Title: 1225....PDF URL Source: ...` 等元数据。已补充 `_clean_text` 中的元数据剥离逻辑，并通过 `test_jina_pdf_metadata_stripped_from_excerpt` 测试覆盖，随后重新生成了 中简科技 / 圣邦股份 报告。
2. **HTML dashboard 未包含新章节**：与 task 文件预期一致，Markdown 包含而 HTML dashboard 未自动继承；已在 notes 中明确说明。
3. **圣邦股份评分/EV 波动**：7.5/+10.25% 与此前某次 6.5/+7.66% 的差异来自 LLM 质量门非确定性，非 Source Intake 展示层导致。

## 网络 / 环境问题（非阻塞）

- akshare `stock_zh_a_hist` / `index_zh_a_hist` 多次因代理错误失败，技术数据仅返回 106 条（目标 120 条）。
- 百度资金流向获取失败。
- 这些属于运行环境网络问题，不影响 Source Intake 展示层验收。

## Blocker

无。

## 结论

Source Evidence Visibility Sprint 已实现并通过测试与三股 runtime 验收：

- 新 renderer 正确渲染在 中简科技 / 圣邦股份 报告中。
- 黑芝麻智能 保持 Agent-Reach 独立，未出现 Source Intake 章节。
- 评分、风险、EV、技术面、最终推荐逻辑未被修改。
- 未触发新的 quality check 问题。
- 未下载研报 PDF，未抓取雪球详情页，未使用 CDP，未刷新知乎，未修改 LLM prompt。
