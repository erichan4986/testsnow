# Scripts 全栈审计与确定性清理 Batch A 设计

## 1. 目标

沿正式单股报告运行链路审计 `scripts/`，第一批只删除具有静态引用证明、替代 owner
和运行基线保护的无效代码。不得改变报告内容、数据来源、Pipeline 顺序、评分、风险、
技术算法、目标价算法、引用或 LLM prompt。

本轮先在干净 canonical worktree
`/Users/erichan/testsnow/.worktrees/annual-producer-v2` 完成。主仓库
`/Users/erichan/testsnow` 的旧分支与脏改动必须留到独立同步阶段处理。

## 2. 已验证基线

- Branch / HEAD：`codex/pipeline-stabilization` / `f6f3714`。
- 初始工作区：clean，分支相对 origin ahead 7。
- Runtime：`scripts/` 下 172 个 Python 文件、67,246 行。
- 全量测试：2,851 passed、10 skipped，57.52 秒。
- 离线主入口：
  `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_stock_report.py --stock 黑芝麻智能 --offline-smoke`
  退出码 0，只写 `/tmp/testsnow_offline_smoke`。
- 当前正式链路：`run_stock_report.py` -> `PerStockReporter` ->
  `compile_report_run_plan` -> `build_stock_report_pipeline` -> data/quality/source intake ->
  annual fulltext -> consolidation -> quote/competitor/technical -> synthesis/scoring/charts ->
  `ReportAssemblySkill`。

## 3. 删除证明标准

每个删除项必须同时满足：

1. `rg` 与 AST 审计显示 `scripts/`、`tests/` 没有运行调用；
2. 如果旧代码曾有运行职责，当前 active owner 已明确；
3. focused test、full suite 与离线主入口能捕获导入或行为回归；
4. 不属于 README 保留的手动入口、preview、tool、配置路径或公共数据源能力。

仅有“看起来没用”或“测试没覆盖”不足以删除。动态 renderer registry、package export、
CLI 入口和 preview 均按公共面处理。

## 4. Batch A 删除账本

### A1. 删除旧 `PriceTargetRenderer`

删除：

- `scripts/utils/reporter/sections/price_target_renderer.py`；
- `scripts/utils/reporter/sections/__init__.py` 中 import 与 `__all__` 项；
- README 中该 renderer 的独立条目。

证明：

- 正式 `ReportAssemblySkill.RENDERERS` 不注册 `price_target`；
- `tests/reporter/test_assembly_skills.py` 已锁定正式 assembly 不注册旧 renderer；
- `TechnicalRenderer` 是目标价判断与触发条件的唯一显示 owner；
- 仓库内无独立实例化或 import，只有 package re-export 与 README。

预计 runtime 净减约 107 行。

### A2. 删除旧指数抓取 wrapper

删除 `scripts/utils/reporter/data_fetcher.py::fetch_index_bars`。

证明：

- 仓库内只有定义，没有 import 或调用；
- 当前指数抓取、规范化和缓存 owner 是
  `technical_analyzer` + `technical_ohlcv_cache.v2`；
- v2 cache focused tests 与市场共振 tests 保护 active 路径。

预计 runtime 净减 21 行。

### A3. 删除旧 note/card fingerprint

删除 `periodic_report_narrative_pack_store.py::v2_note_card_fingerprint`。

证明：

- 仓库内只有定义与历史设计文档引用；
- active pack integrity 使用 `_integrity()` 的 cards/payload SHA256；
- active display view 使用 `normalized_source_excerpt_hash()`，后者必须保留；
- `deepcopy` 仍被 `_envelope()` 使用，不删除 import。

预计 runtime 净减 10 行。

### A4. 删除三个未调用的 fulltext cache 转发包装

删除：

- `build_periodic_report_filing_core_facts_from_cache`；
- `build_periodic_report_explanation_pack_from_cache`；
- `build_periodic_report_narrative_cards_from_cache`。

保留并继续由 skill 直接调用：

- `_filing_core_facts_from_cache_rows`；
- `_explanation_pack_from_cache_rows`；
- `_narrative_cards_from_cache_rows`。

证明：三个 public-named wrapper 在 `scripts/`、`tests/`、preview 与 README 中均无引用；
它们只重复执行一次 `_load_periodic_report_cache_rows(... latest_only=True)` 后转发。
正式 skill 已一次加载 `cache_rows`，再调用三个 rows helper，避免三次重复读盘。

预计 runtime 净减约 52 行。

### A5. 删除两个无调用的小型定义

- `external_source_document.py::build_external_source_documents`，保留 active 的单文档
  `build_external_source_document`；`Iterable` import 继续由 active `_is_comparative`
  的签名注解使用，必须保留；
- `periodic_report_required_metrics.py::RequiredMetricsError`。

两者在仓库内都只有定义，无 import、捕获、实例化或文档契约。

预计 runtime 净减约 7 行。

### A6. 预计结果

- Runtime 目标净减：不少于 185 行；
- Runtime 硬门：不得净增；
- 不删除测试 case；只扩展 runtime hygiene 契约测试。

## 5. 明确保留

- 所有 `run_*.py`、preview、tools 与现行配置路径；
- `KimiAnalyzer`：仍由 `xueqiu_monitor_v2.py` 使用；
- `SourceAdapter`、`SectionRenderer`：公共协议与测试 import 面；
- `technical_indicators`：通过 alias 被 `technical_analyzer` 使用；
- `stock_quote_eastmoney`、`fund_flow_daily`、`valuation_industry_judgment`：虽无当前主链调用，
  仍是 reporter 对外数据能力或 package export，第一批不做兼容 hard cut；
- `executive_summary_renderer._extract_conclusion`：明确标注兼容 helper，延期；
- 所有评分、风险、技术算法、目标价引擎与外部采集实现。

## 6. 测试设计与 TDD 顺序

### Task 1：runtime hygiene RED

扩展 `tests/test_runtime_hygiene.py`，先断言：

- `price_target_renderer.py` 不存在，sections package 不导出 `PriceTargetRenderer`；
- A2-A5 列出的 top-level definitions 均不存在；
- active owners 仍存在：`TechnicalRenderer`、`normalized_source_excerpt_hash` 和三个 rows helper；
- `ReportAssemblySkill.RENDERERS` 不含 `price_target`。

修改 runtime 前运行该测试，必须 RED。

### Task 2：最小删除 GREEN

只按第 4 节账本删除，不改 active helper 实现，不合并新抽象。运行：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_runtime_hygiene.py tests/reporter/test_assembly_skills.py tests/utils/test_periodic_report_fulltext_intake.py tests/reporter/test_periodic_report_fulltext_intake_skill.py tests/utils/test_periodic_report_narrative_pack_store.py tests/utils/test_external_source_document.py tests/utils/test_technical_ohlcv_cache.py tests/reporter/test_technical_resonance.py -q -p no:cacheprovider
```

### Task 3：全链路验证

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
bash tools/ci_grep_gates.sh
git diff --check
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_stock_report.py --stock 黑芝麻智能 --offline-smoke
```

离线主入口产物只允许出现在 `/tmp/testsnow_offline_smoke`。

## 7. Failure Modes

| Failure mode | 表现 | 检测 |
|---|---|---|
| 旧 renderer 仍有动态 import | package import 或 report assembly 失败 | hygiene + assembly + full suite |
| TechnicalRenderer 未完整承接目标价 | 技术章节缺目标/触发/失效条件 | technical renderer/downstream tests + offline smoke |
| 旧指数 helper 实际仍被调用 | 市场共振或 cache test AttributeError | OHLCV cache + resonance tests |
| 删除 fingerprint 破坏 pack integrity | pack store 读写/hash tests 失败 | pack store focused tests |
| 删除 wrappers 误伤 preview/skill | fulltext import 或 ctx 字段缺失 | fulltext focused + pipeline/full suite |
| plural source helper 是隐式公共 API | 仓库外调用者受影响 | 本轮接受 internal hard cut；README/preview 均无契约，review 必须复核 |
| RequiredMetricsError 被外部捕获 | 仓库外 import 失败 | 本轮接受 internal hard cut；review 必须复核 |
| 清理混入主仓库脏改动 | 两套分支 diff 混杂 | 只在 canonical worktree 实施；主仓库独立同步 |

## 8. 停止条件

立即停止并返回设计，如果：

- 发现任一候选存在当前 runtime、test、preview、tool、README 公共契约调用；
- 需要改 active owner 的行为才能删除旧代码；
- focused 或 full suite 暴露报告内容变化；
- 需要修改评分、风险、技术算法、目标价公式、引用、LLM prompt 或采集逻辑；
- runtime 最终不是净减少；
- 需要在本批次处理主仓库脏改动。

## 9. 后续阶段

Batch A 通过后再做：

1. 动态/公共兼容面的单独弃用审计；
2. 大文件内部重复 owner 审计，不以行数为唯一目标；
3. 将 canonical commit 以独立 cherry-pick/rebase 计划同步到主仓库，先审主仓库真实 diff，
   不覆盖用户改动。

## 10. Design Delta（Round 1）

- accepted：修正 A5，保留 `Iterable` import；同时把单数
  `build_external_source_document` 加入 hygiene active-owner 断言。
- rejected：无。
- deferred：README 中既有 stale `tests/test_price_target.py` 引用不属于本批删除契约，留给
  后续文档卫生审计。
- R2 required：no。Round 1 无 blocker，唯一 must-fix 是不改变 runtime 边界的局部文本修正。
