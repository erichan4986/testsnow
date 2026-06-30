# 中简科技单股深度报告入口实现任务

## Context

Codex 已完成中简科技第二只股票 pilot 的前置准备：

- `config/stocks.json` 已为 `中简科技` 配置 Agent-Reach 官方 cninfo 种子源，且 smoke 验证通过。
- 本地低信用 claim 池已存在：`knowledge/10-Stocks/中简科技/20260614-雪球缓存社区claims.md`。
- 本地高信用/官方事实 notes 已存在：`knowledge/10-Stocks/中简科技/evidence/20260614-local-confirmed-facts.md`。
- claim verification plan 已能从本地 notes 生成 `needs_review` / `unverified` 结果，并能派生非计分的 structured risk signals。

现在需要补齐单股报告入口，让中简科技可以像黑芝麻智能一样通过单股深度报告 pipeline 快速生成报告。

## Goal

新增 `scripts/run_中简科技.py`，复用现有单股报告 pipeline，在 `--fast-test` 模式下只使用本地缓存/本地 knowledge posts，不抓雪球详情页、不刷新知乎、不启动 CDP，并能生成中简科技 Markdown/HTML/PDF 报告。

## Allowed Files

可以修改/新增：

- `scripts/run_中简科技.py`
- `tests/reporter/test_run_zhongjian_entry.py`
- `docs/codex_handoff/runbook.md`（可选，只补充新入口说明）
- `docs/agent_workflow/2026-06-14-zhongjian-single-stock-report-entry-claude-notes.md`

如果实现中发现必须修改其他文件，先停止并说明原因，不要自行扩大范围。

## Forbidden

- 不要修改 `config/stocks.json`；中简科技 Agent-Reach 配置已完成。
- 不要修改 `xueqiu_monitor_v2.py`。
- 不要修改 `scoring_engine.py`、技术分析算法、EV/仓位规则、风险评分规则。
- 不要修改 `KnowledgeSynthesizer` prompt 或 LLM 合成逻辑。
- 不要抓雪球详情页，不要连接/控制 Chrome/CDP。
- 不要刷新知乎或运行 ZhihuCurator/LLM curator 作为测试前置。
- 不要做无关重构、批量格式化或删除报告/缓存文件。

## Implementation Requirements

### 1. 新增入口脚本

以 `scripts/run_黑芝麻智能.py` 或其他现有 `scripts/run_*.py` 为模板，新增：

- `scripts/run_中简科技.py`

股票基础信息：

```python
STOCK = {
    "name": "中简科技",
    "code": "300777",
    "xueqiu_code": "SZ300777",
    "gid": "300777",
}
```

关键词建议：

```python
KEYWORDS = ["中简科技", "碳纤维", "航空航天", "军工", "复合材料", "T1100", "ZM40X"]
```

入口必须支持：

- `main(argv=None)`
- `--fast-test`
- 返回生成的 `md_path`

### 2. fast-test 数据策略

`--fast-test` 模式必须避免外部采集，按顺序使用：

1. `data/raw/xueqiu_data_*_中简科技.json`，如果存在；
2. 本地 `knowledge/10-Stocks/中简科技/posts/*.md`，如果存在；
3. 如果两者都没有，使用空帖子列表并记录 warning，不要调用外部 fetch。

需要新增脚本内 helper，例如：

- `_load_xueqiu_data(stock_name, date_str)`
- `_load_knowledge_posts(stock_name)`
- `_load_cached_zhihu_data(stock_name, date_str)`
- `_empty_zhihu_data()`
- `_load_agent_reach_config(stock_name)`

`_load_knowledge_posts()` 要把 markdown notes 转成 reporter 可用的 post dict，至少包含：

```python
{
    "title": "...",
    "content": "...",
    "url": "...",
    "like": 10,
    "comment": 5,
}
```

解析要求：

- 支持 YAML frontmatter 中的 `title` / `url`。
- 如果没有 frontmatter title，使用第一个 markdown heading 或文件 stem。
- content 使用去掉 frontmatter 后的正文。
- 空正文时用 title 兜底。

非 `--fast-test` 模式可以保持现有入口习惯：先尝试雪球缓存，不存在时回退 `fetch_all_stocks([STOCK], use_xueqiu=False)`，但仍不要抓雪球详情页/CDP。

### 3. Zhihu 策略

`--fast-test` 必须：

- 跳过 `ZhihuCollector`
- 优先复用 `data/raw/report_input_*_中简科技.json` 里的 `raw_data["中简科技"]["zhihu"]`
- 没有缓存时返回 `_empty_zhihu_data()`

非 `--fast-test` 可以沿用现有单股入口的 `ZhihuCollector.collect(..., use_curator=True)`。

### 4. Agent-Reach 配置

必须从 `config/stocks.json` 读取 `中简科技` 的 `agent_reach` 配置，并传给：

```python
PerStockReporter(..., agent_reach_configs=agent_reach_configs)
```

测试中需要断言传入配置包含 cninfo URL 和 `official_domains=["cninfo.com.cn"]`。

### 5. 数据保存与报告生成

与黑芝麻入口保持一致：

- 保存 `data/raw/report_input_<date>_中简科技.json`
- 调用 `PerStockReporter.generate_stock_report("中简科技", report_dir)`
- 如有 `md_path`，尝试 `export_pdf(...)`
- PDF 导出失败只 warning，不让入口崩溃。

## Tests

新增 `tests/reporter/test_run_zhongjian_entry.py`，至少覆盖：

1. `test_zhongjian_entry_passes_agent_reach_config`
   - monkeypatch posts/zhihu/reporter/export_pdf
   - 调 `main(["--fast-test"])`
   - 断言 `PerStockReporter` 收到中简科技的 Agent-Reach cninfo 配置。

2. `test_fast_test_mode_skips_zhihu_collector`
   - `ZhihuCollector` mock 成一旦调用就失败。
   - 断言 `--fast-test` 不调用 ZhihuCollector。

3. `test_fast_test_mode_reuses_cached_zhihu_data`
   - 在临时 `data/raw/report_input_*_中简科技.json` 写入 zhihu 缓存。
   - monkeypatch `__file__` 到临时 scripts 目录。
   - 断言 raw_data 中使用缓存 zhihu。

4. `test_load_knowledge_posts_parses_frontmatter_and_body`
   - 在临时 `knowledge/10-Stocks/中简科技/posts/*.md` 写入 frontmatter/body。
   - monkeypatch `__file__`。
   - 断言 title/url/content 被正确解析。

5. `test_fast_test_uses_knowledge_posts_without_external_fetch`
   - 无 xueqiu cache，有 knowledge posts。
   - mock `fetch_all_stocks` 为一旦调用就失败。
   - 调 `main(["--fast-test"])`
   - 断言 reporter 收到 posts。

推荐命令：

```bash
python3 -m pytest tests/reporter/test_run_zhongjian_entry.py tests/reporter/test_agent_reach_source_config.py tests/reporter/test_agent_reach_smoke_script.py -q
```

如果 focused tests 通过，可以做一次 runtime 验证：

```bash
cd scripts && python3 run_中简科技.py --fast-test
python3 scripts/check_report_quality.py reports/中简科技_YYYYMMDD.md
```

runtime 验证不是实现成功的硬前置；如果 PDF/浏览器权限、磁盘空间或本地环境问题导致失败，记录即可，不要绕权限硬改。

## Stop Conditions

遇到以下情况必须停止并回报：

- 需要修改 allowed files 之外的源码才能完成。
- 需要改评分、技术算法、LLM prompt、pipeline order 或 report renderer。
- fast-test 会被迫访问外部网站、刷新知乎、抓雪球详情页、启动 CDP。
- focused tests 暴露出与本任务无关的大面积失败。
- 本地报告 runtime 需要外部登录或危险采集。

## Completion Notes

完成后写入：

- `docs/agent_workflow/2026-06-14-zhongjian-single-stock-report-entry-claude-notes.md`

notes 必须包含：

- 改了哪些文件
- focused tests 结果
- 是否跑了 runtime；如果跑了，报告路径和 quality check 结果
- fast-test 是否跳过知乎/外部 fetch
- Agent-Reach config 是否传入
- 偏离点
- blocker
