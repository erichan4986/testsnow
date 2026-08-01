# Runtime 与测试环境去重设计

## 1. 目标

在不改变正式报告内容、数据源、评分、技术分析、风险规则、LLM prompt 和现有单股入口文件名的前提下，删除可证明无用的 runtime 代码，并把重复的单股入口与测试收敛到已有通用入口。

入口收敛允许两项明确的工程行为修正：通用 knowledge-post parser 必须保留旧入口支持的嵌套互动数字段；所有 `--fast-test` 入口在无本地帖子时必须保持离线，不再回退外部抓取。

本轮不是按行数粗暴删测试。所有删除必须满足以下至少一项：

- 模块被同名 package 遮蔽，静态和运行时导入均不可达；
- private helper 在 `scripts/` 与 `tests/` 中只有定义、没有调用；
- 多个入口复制已有通用入口的同一行为，可由薄包装转发；
- 测试函数体与断言完全相同，仅参数集合被人为拆开；
- 整个测试文件永久 `skip`，且验证的是尚未实现的未来能力。

## 2. 基线

- Runtime：171 个 Python 文件，68,592 行。
- Tests：172 个 Python 文件，63,754 行。
- 收集：2,834 tests。
- 全量基线：2,818 passed、16 skipped，48.55 秒。
- 当前工作区有 Chapter 2 毛利率功能的未提交改动；本任务不得撤销、覆盖、格式化或顺带重构这些文件中的现有改动。

## 3. 明确不做

- 不删除 `scripts/run_*.py` 用户入口，只将四个重复入口改成薄包装。
- 不删除 `scripts/utils/judgment_generator.py` 或 `scripts/utils/wechat_sogou_fetcher.py`；它们虽无 active runtime 调用，但 README 仍将其描述为手动能力，需另行做弃用决策。
- 不修改 `KnowledgeSynthesizer`、技术指标、评分、风险、目标价、引用、数据采集或报告结构。
- 不把小型测试 helper 统一搬入全局 `conftest.py`；节省不足以抵消测试耦合。
- 不删除不同输入、不同来源或不同股票的行为测试，即使测试骨架相似。
- 不生成正式报告，不联网，不启动 Chrome/CDP，不抓雪球详情页。

## 4. Batch A：确定性死代码删除

### 4.1 遮蔽模块

删除 `scripts/utils/reporter.py`。Python 实际解析 `utils.reporter` 时加载的是 `scripts/utils/reporter/__init__.py`；`ReportManager` 的唯一 active owner 是 `scripts/utils/reporter/report_manager.py`。

新增 AST/导入卫生测试，锁定：

- `utils.reporter` 的 spec 指向 package `__init__.py`；
- 仓库中不存在第二个 `scripts/utils/reporter.py` owner；
- `ReportManager` 仍由 package 导出。

### 4.2 零调用 private helper

删除以下只有定义、无调用的 helper：

- `broker_research_digest._looks_like_financial_snapshot_without_driver`
- `broker_research_digest._generic_driver_block_excerpt`（保留 plural owner）
- `a_stock_source_intake._report_row_matches_target`
- `periodic_report_evidence_pack._extract_section_excerpt`
- `periodic_report_required_financial_metrics._hk_current_thousand_metric`
- `periodic_report_required_financial_metrics._last_rate_cell`
- `periodic_report_required_metrics._block_for_usage`
- `reporter.sections._chart_paths`

暂不删除 `executive_summary_renderer._extract_conclusion`。它虽零调用，但注释明确标记为外部兼容入口；本轮不把隐式兼容删除混入确定性清理。

同时删除 `run_stock_report.py` 中重复的第二条 `PDF已生成` 日志。

### 4.3 Batch A 预期

- Runtime 净减不少于 180 行。
- 不改变任何输出或函数调用路径。

## 5. Batch B：单股入口收敛

### 5.1 唯一 owner

`scripts/run_stock_report.py` 已拥有以下完整能力：

- 股票配置解析与关键词；
- 雪球缓存、knowledge posts 与东方财富 fallback；
- fast-test 下知乎缓存复用；
- Agent-Reach 与 Source Intake 配置传递；
- Markdown、HTML 与默认 PDF 输出；
- `--fast-test`、`--no-pdf`、`--offline-smoke` 参数。

收敛前先补齐通用入口的一项解析差异：旧圣邦/中简入口可从 frontmatter 的 `interactions.likes/comments` 读取互动数，通用 `_parse_markdown_post()` 目前只识别顶层字段。将旧入口的窄正则能力移入通用 parser，并由唯一测试覆盖。

因此以下入口改为薄包装：

- `scripts/run_中际旭创.py`
- `scripts/run_圣邦股份.py`
- `scripts/run_黑芝麻智能.py`
- `scripts/run_中简科技.py`

每个包装只负责固定股票名，并把调用参数原样传给 `run_stock_report.main()`。入口文件名、直接执行方式和 `main(argv)` 测试接口保留。

### 5.2 参数契约

包装必须构造：

```python
["--stock", STOCK_NAME, *argv]
```

模块被测试导入时，`main()` 默认使用空参数；脚本直接执行时，`__main__` 显式传入 `sys.argv[1:]`。这样不会把 pytest 自身参数误传给通用入口。

### 5.3 测试收敛

删除三个重复实现测试文件：

- `tests/reporter/test_run_black_sesame_entry.py`
- `tests/reporter/test_run_shengbang_entry.py`
- `tests/reporter/test_run_zhongjian_entry.py`

新增一个参数化 wrapper 契约测试，覆盖四个入口：

- 固定股票名正确；
- `--fast-test` / `--no-pdf` / `--offline-smoke` 原样转发；
- 通用入口返回码原样返回；
- 每个入口可作为脚本导入。

原三个文件中与缓存、knowledge、配置、报告生成相关的行为，不再按股票重复测试，由 `tests/reporter/test_run_stock_report_entry.py` 的唯一 owner 覆盖。若缺少某个契约，先补到通用入口测试，再删除旧测试。

旧中际/黑芝麻入口在 `--fast-test` 且无雪球缓存时仍会回退东方财富；这是与 AGENTS.md 离线工程验证规则冲突的旧差异，不予保留。四个薄包装统一采用通用入口的本地 knowledge/空列表 fallback，并增加“不调用 `fetch_all_stocks`”测试。

### 5.4 Batch B 预期

- 四个 runtime 入口从 1,301 行降到约 40-60 行，runtime 净减不少于 1,150 行。
- 入口测试净减不少于 500 行。
- 保留 AGENTS.md 指定的 `run_黑芝麻智能.py --fast-test` 使用方式。

## 6. Batch C：测试重复与永久 skip 清理

### 6.1 参数化测试合并

在不减少 case 数的前提下合并：

- `test_periodic_report_narrative_evidence_cards.py` 中三个完全相同的 admission 测试体；
- `test_claim_risk_signals.py` 中两组竞争风险负例；
- `test_claim_risk_signals.py` 中两组资金流出负例。

合并后参数仍逐项收集，行为覆盖数不减少，只删除重复函数、fixture 建造和断言。

### 6.2 永久 skip

删除 `tests/reporter/test_skill_pipeline_observability.py`。该文件模块级永久 skip，原因是能力尚未实现；它不保护当前 runtime。未来实现 observability 时，应按 TDD 新建当时的真实契约测试。

### 6.3 保留项

- 保留 `tests/conftest.py` 自动 marker 体系；它实际为 391 个 report-core 和 1,159 个 external-material tests 注入 marker。
- 保留依赖环境的条件 skip（Kaleido、示例 PDF、live K-line），这些测试在具备依赖时仍会执行。
- 不合并跨文件的 2-3 行测试 helper。

## 7. Failure Modes 与检测

| Failure mode | 表现 | 检测 |
|---|---|---|
| `utils.reporter` 删除后 import 解析异常 | 批量入口无法导入 `ReportManager` | package import test + pipeline tests |
| wrapper 把 pytest 参数传入通用入口 | 单元测试出现未知 CLI 参数 | wrapper `main()` 空参数测试 |
| wrapper 丢失用户参数 | `--fast-test` / `--no-pdf` 无效 | 四股参数化 forwarding test |
| wrapper 改变默认 PDF 行为 | 原入口不再默认导出 PDF | 通用入口契约测试 + argv 精确断言 |
| 股票关键词或 Source Intake 配置丢失 | 报告材料变化 | 通用入口从 `stocks.json` 取配置的测试 |
| knowledge frontmatter 互动数丢失 | like/comment 回退到默认值 | 通用 parser 嵌套 interactions 测试 |
| fast-test 意外访问外部网络 | 工程验证触发东方财富 | fast-test 无缓存时 fetch 必须未调用 |
| 删除 private helper 实际存在动态调用 | runtime AttributeError | focused module tests + full suite |
| 测试合并丢失 case | 参数收集数下降 | 合并前后参数 case 清单对照 |
| 误改当前毛利率工作 | diff 出现非任务改动或功能回归 | 路径白名单审计 + full suite |

## 8. 实施顺序与测试门

每批均按 RED/GREEN 执行：

1. Batch A 先增加 runtime hygiene 失败测试，再删除死代码。
2. Batch B 先增加四股 wrapper forwarding 失败测试，再改薄包装；随后补齐通用入口契约并删除旧测试。
3. Batch C 先记录参数 case 数，再合并测试体和删除永久 skip 文件。

每批后运行对应 focused tests。最终必须运行：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
bash tools/ci_grep_gates.sh
git diff --check
python3 scripts/run_黑芝麻智能.py --offline-smoke
```

最后一条只写 `/tmp/testsnow_offline_smoke`，不访问网络、不生成正式报告。

## 9. 预算与停止条件

目标：

- Runtime 净减至少 1,300 行；
- Tests 净减至少 500 行；
- 全量测试保持零失败；
- active 行为测试 case 不因参数化合并而减少。

立即停止并返回设计的条件：

- 需要修改评分、技术分析、风险、目标价、引用、LLM prompt 或数据采集；
- 通用入口无法保持任一旧入口的外部行为；
- 删除项出现仓库内动态调用证据；
- 需要修改当前毛利率任务的 runtime/data 文件才能完成清理；
- full suite 出现与删除项无法直接解释的失败。

## 10. 允许修改范围

Runtime：

- `scripts/run_stock_report.py`
- 四个 `scripts/run_<股票>.py` 入口
- `scripts/utils/reporter.py`（删除）
- 第 4.2 节列出的 helper 所在模块
- `scripts/utils/reporter/sections/__init__.py`

Tests：

- 三个旧单股入口测试（删除）
- 新 wrapper 契约测试
- `tests/reporter/test_run_stock_report_entry.py`
- `tests/test_runtime_hygiene.py`
- 两个参数化重复测试文件
- `tests/reporter/test_skill_pipeline_observability.py`（删除）

Docs：

- 本设计、review notes、implementation plan/task/notes。
