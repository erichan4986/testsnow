# 圣邦股份 Source Intake 第三只股票试点笔记

日期：2026-06-15

## 目标

为「圣邦股份」推进单股深度报告试点，检查/新增 `run_圣邦股份.py --fast-test` 入口，接入 Source Intake 配置，先 smoke，再 fast-test 生成报告，验证 evidence notes、claim verification、structured risk 是否正常工作。

## 改动文件

1. `scripts/run_圣邦股份.py`
   - 新增 `--fast-test` 参数解析
   - `--fast-test` 跳过知乎采集与 LLM curator，复用 `data/raw/report_input_*_圣邦股份.json` 中的知乎缓存
   - 无雪球缓存时回退到 `knowledge/10-Stocks/圣邦股份/posts/`
   - 新增 `_load_source_intake_config()` 与 `_load_agent_reach_config()`
   - 将 `source_intake_configs` 传入 `PerStockReporter`
   - 统一使用 `STOCK["code"]`（300661）避免硬编码

2. `config/stocks.json`
   - 仅在「圣邦股份」条目下新增 `source_intake` 配置：
     - `cninfo_announcements.enabled=true`, `lookback_days=365`, `max_items=12`
     - `read_detail_content=true`，但 `detail_content_categories` 仅包含短公告类别（业绩预告/季度报告/一季度报告/三季度报告/风险提示），避免读取长年报正文
     - `eastmoney_stock_news.enabled=true`, `max_items=10`
     - `eastmoney_research_reports.enabled=true`, `max_items=8`
     - `evidence_notes.enabled=true`, `dry_run=false`
     - `claim_verification.enabled=true`, `risk_signals=true`

3. `scripts/smoke_source_intake.py`
   - 在 `STOCK_CODES` 中增加 `"圣邦股份": "300661"`

4. `tests/reporter/test_run_shengbang_entry.py`（新增）
   - 验证 Source Intake 配置透传到 `PerStockReporter`
   - 验证 `--fast-test` 跳过 `ZhihuCollector`
   - 验证复用缓存知乎数据
   - 验证 knowledge posts 解析与外部 fetch 不被调用

5. `docs/agent_workflow/2026-06-15-shengbang-source-intake-pilot-claude-notes.md`（本文件）

## 运行命令与结果

### Focused tests

```bash
python3 -m pytest tests/reporter/test_run_shengbang_entry.py -q
# 5 passed in 1.05s

python3 -m pytest tests/reporter/test_agent_reach_source_config.py \
    tests/reporter/test_run_black_sesame_entry.py \
    tests/reporter/test_run_zhongjian_entry.py \
    tests/reporter/test_source_intake_smoke_script.py -q
# 20 passed in 1.08s
```

### Source Intake smoke

```bash
python3 scripts/smoke_source_intake.py --stock 圣邦股份 --json
```

结果：

```json
{
  "stock_name": "圣邦股份",
  "stock_code": "300661",
  "status": "ok",
  "total_items": 21,
  "source_statuses": {
    "cninfo_announcements": { "status": "ok", "count": 11 },
    "eastmoney_stock_news": { "status": "ok", "count": 10 },
    "eastmoney_research_reports": { "status": "empty", "count": 0 },
    "eastmoney_global_news": { "status": "disabled", "count": 0 }
  },
  "credit_breakdown": {
    "exchange_announcement:95": 11,
    "news:60": 10
  }
}
```

### 单股 fast-test 报告

```bash
cd scripts && python3 run_圣邦股份.py --fast-test
```

关键日志：

- 雪球缓存回退到 `xueqiu_data_20260605_圣邦股份.json`，0 条
- 从 `knowledge/10-Stocks/圣邦股份/posts/` 加载 5 条 knowledge posts
- 复用知乎缓存 `report_input_20260615_圣邦股份.json`，总计 85 条，质量门 keep=20/demote=13/discard=13
- `[a_stock_source_intake] status=ok items=21`
- `[source_intake_merge] keep=21 demote=0 discard=0`
- `[evidence_note_writer] status=written reason=written`
- `[claim_risk_signal] status=empty count=0`
- 报告生成：`reports/圣邦股份_20260615.md`、`reports/圣邦股份_20260615.html`
- PDF 导出成功：`reports/圣邦股份_20260615.pdf`

### 质量检查

```bash
python3 scripts/check_report_quality.py reports/圣邦股份_20260615.md
# PASS: reports/圣邦股份_20260615.md
# No quality issues found.
```

### 全量回归

```bash
python3 -m pytest tests -q
# 934 passed, 6 skipped in 204.49s
```

## Source Intake 抓取结果

| 来源 | 数量 | 状态 | 备注 |
|---|---|---|---|
| cninfo 公告 | 11 | ok | 含季度报告披露提示性公告等；仅短公告类别读取正文 |
| 东财个股新闻 | 10 | ok | 多为行业/概念类快讯 |
| 东财研报 | 0 | empty | 与 中简科技 试点现象一致，akshare 研报接口按代码过滤后无匹配 |
| 东财全球资讯 | 0 | disabled | 配置关闭 |
| **合计** | **21** | ok | 官方公告 11 + 新闻 10 |

## Evidence Notes

- 写入目录：`knowledge/10-Stocks/圣邦股份/evidence/`
- 写入数量：**21** 条
- 构成：11 条 `exchange_announcement`（source_credit=95） + 10 条 `news`（source_credit=60）
- 每条 evidence note 包含 YAML frontmatter（stock/code/source_type/source_credit/verification_status/claims 等）与原始摘录、初步 claims
- 无编号引用污染：evidence note 内部未出现 Agent-Reach/Source Intake 的编号引用残影

## Claim Verification / Structured Risk

- `claim_risk_signal` 技能状态：`empty`，结构化风险信号数量：**0**
- 原因：本次抓取的 evidence claims（如季度报告披露提示、行业概念下跌）未命中 `claim_risk_signals.py` 中预置的风险正则（业绩预期下调/竞争格局恶化/盈利压力/资金流出/技术路线风险）
- 但报告仍出现 **LLM 文本风险观察（不计分）**：命中 2 条
  - 竞争格局恶化（价格战）
  - 技术路线风险（不确定性、替代）
- 因此「结构化风险观察」整体存在，只是并非来自 claim verification 链路

## 报告中观察到的内容

1. **Source Intake evidence notes**：未在报告正文中以独立章节呈现，而是作为 knowledge base 沉淀写入 `evidence/` 目录。
2. **官方事实核验摘要**：报告中「三、核心事实基座」的事实来源仍标注为 知乎/雪球 (community)，未出现独立的「官方事实核验摘要」章节；Source Intake 的高信用证据尚未被报告装配模块显式引用。
3. **结构化风险观察**：存在「LLM文本风险观察（不计分）」与「综合风险评分」章节；claim verification 结构化信号为 0。
4. **编号引用污染**：未发现 Agent-Reach / Source Intake 的编号引用污染，引用列表仅包含 6 条社区/新闻来源。
5. **风险评分与技术面一致性**：
   - 综合风险评分 2.0/10（低风险），仓位建议「积极配置，最大仓位 20%」
   - 技术面：趋势健康度 58/100（转弱观察）、BIAS 严重正偏离（90% 极端分位）、MACD 柱线翻绿、单一背离预警（轻度），结论为「关注/不操作（盈亏比不足）」
   - **存在轻微矛盾**：低风险评分建议积极配置，而技术面给出偏谨慎的「观望/不操作」信号。

## 网络 / LLM / PDF 问题

- **akshare 技术数据代理错误**：`stock_zh_a_hist`、`index_zh_a_hist` 多次因 `ProxyError` 失败，导致 K 线/指数数据不完整（仅返回 106 条，不足目标 120 条）。
- **百度资金流向获取失败**：`Expecting value: line 1 column 1 (char 0)`。
- **LLM 调用**： DeepSeek API 正常返回，未出现失败。
- **PDF 导出**：成功生成 `reports/圣邦股份_20260615.pdf`。
- **未使用雪球详情页 / CDP / 知乎刷新**：`--fast-test` 模式下知乎使用缓存，未启动 ZhihuCollector；未访问雪球详情页；未启动 Chrome/CDP。

## 偏离点

1. **东财研报返回 empty**：与 中简科技 试点一致，`eastmoney_research_reports` 按 `300661` 过滤后无匹配，属于非阻塞空结果。
2. **Claim verification 结构化信号为 0**：本次抓取的证据文本未命中风险正则，不代表功能故障。
3. **Evidence notes 未在报告正文展示**：当前 Phase 1 实现将 Source Intake 证据沉淀到 knowledge base，报告装配尚未显式消费这些证据生成「官方事实核验摘要」章节。
4. **技术面数据因代理问题不完整**：技术评分依赖的 K 线/指数数据部分缺失，可能影响技术面结论的可靠性。

## Blocker

无。所有 focused tests、smoke、fast-test 报告、质量检查、全量回归均通过。Source Intake 在「圣邦股份」上跑通端到端，evidence notes 正常写入，报告正常生成。

## 下一步建议

- 若需要报告正文展示 Source Intake 官方事实，可在 report renderer 中消费 `external_evidence_keep_items` 生成「官方事实核验摘要」章节。
- 若希望 claim verification 产生更多结构化风险信号，可扩展 `claim_risk_signals.py` 的正则覆盖范围，或引入更高信用的财报类公告正文。
- 技术数据代理失败问题属于运行环境网络问题，非本次任务范围；如需稳定跑通技术面，可在网络环境良好时重跑。
