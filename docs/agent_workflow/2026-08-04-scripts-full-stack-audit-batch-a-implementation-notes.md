# Scripts 全栈审计 Batch A Implementation Notes

## 结果

- Batch A accepted: yes
- Worktree：`/Users/erichan/testsnow/.worktrees/annual-producer-v2`
- 基线：`f6f3714`
- 未处理主仓库 `/Users/erichan/testsnow`；未提交、未推送。

## 修改与删除文件

修改：

- `README.md`：删除已不在正式 registry 的旧 renderer 条目。
- `scripts/utils/reporter/sections/__init__.py`：删除 `PriceTargetRenderer` import/export。
- `scripts/utils/reporter/data_fetcher.py`：删除零调用 `fetch_index_bars`。
- `scripts/utils/periodic_report_narrative_pack_store.py`：删除零调用 `v2_note_card_fingerprint`。
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`：删除三个零调用 cache wrapper，保留 rows helpers 与一次读盘的 active skill 路径。
- `scripts/utils/external_source_document.py`：删除零调用 plural builder；保留 `Iterable`，因为 active `_is_comparative` 注解仍使用它。
- `scripts/utils/periodic_report_required_metrics.py`：删除零调用 `RequiredMetricsError`。
- `tests/test_runtime_hygiene.py`：增加 obsolete-surface 缺失断言与 active-owner 保留断言。

删除：

- `scripts/utils/reporter/sections/price_target_renderer.py`。

未修改 active technical renderer、price target engine、cache owner、scoring、risk、LLM、引用或采集逻辑。

## RED / GREEN

- RED：新增 hygiene tests 后运行 `tests/test_runtime_hygiene.py`，结果 `1 failed, 4 passed`；失败点为旧 `price_target_renderer.py` 仍存在，符合预期。
- GREEN：完成最小删除后，hygiene suite `5 passed`。
- focused：`96 passed`。

## 验证

- 全量：`2853 passed, 10 skipped in 54.32s`。
- CI：`bash tools/ci_grep_gates.sh`，all gates passed。
- whitespace：`git diff --check`，clean。
- offline smoke：
  `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_stock_report.py --stock 黑芝麻智能 --offline-smoke`
  退出码 0；报告与 audit 产物只写入 `/tmp/testsnow_offline_smoke`，未联网。

## Runtime numstat

相对 `f6f3714`，`scripts/` 的 runtime 变化：

| 文件 | 增加 | 删除 | 净变化 |
|---|---:|---:|---:|
| `external_source_document.py` | 0 | 5 | -5 |
| `periodic_report_narrative_pack_store.py` | 0 | 12 | -12 |
| `periodic_report_required_metrics.py` | 0 | 4 | -4 |
| `periodic_report_fulltext_intake_skill.py` | 0 | 52 | -52 |
| `reporter/data_fetcher.py` | 0 | 23 | -23 |
| `reporter/sections/__init__.py` | 0 | 2 | -2 |
| `reporter/sections/price_target_renderer.py` | 0 | 110 | -110 |
| **合计** | **0** | **208** | **-208** |

测试新增 45 行；runtime 仍净减 208 行，未触发停止条件。

## Owner / scope audit

- 目标价显示 owner 仍是 `TechnicalRenderer`；目标价计算 engine 未删除。
- 指数数据 owner 仍是 `technical_analyzer` + v2 OHLCV cache；旧 wrapper 无仓库调用。
- pack 完整性仍由 `_integrity()` 与 `normalized_source_excerpt_hash()` 负责。
- fulltext skill 仍一次加载 `cache_rows`，直接调用三个 rows helper。
- external document 单数 builder、`Iterable`、所有入口与 preview/tool 保留。
- 主仓库、data、knowledge、reports 未作为任务对象处理。

## Blocker / warning / deviation

- Blocker：无。
- Warning：A1 的历史 workflow 文档仍提及旧 `PriceTargetRenderer`，按设计保留历史文档不改；README 当前 renderer 列表已同步。
- Deviation：无。

