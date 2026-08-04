# Scripts 全栈审计 Batch A — Claude Code 只读 Review Round 1 Notes

审查日期: 2026-08-04
Worktree: `/Users/erichan/testsnow/.worktrees/annual-producer-v2`
审查基准: HEAD `f6f3714` (`feat: add resilient technical market cache`)，branch `codex/pipeline-stabilization`，ahead origin 7，worktree clean（仅本 review 两份文档 untracked）。
审查范围: 只读。未修改源码/测试/配置/data/knowledge/reports；未联网、未运行报告、未启动 Chrome/CDP。

## verdict: needs_revision

单个 must-fix（A5 的 `Iterable` import 删除理由与真实代码不符）。修正设计文本后即可实现；其余 A1–A4 均判定 **safe**。

## blockers

无。

## must_fix

1. **A5 删除 `Iterable` import 的前提不成立。**
   设计 §4-A5 写「删除仅为 plural helper 使用的 `Iterable` import」。事实：`Iterable` 在
   `scripts/utils/external_source_document.py` 中被两处使用——第 57 行 plural helper
   `build_external_source_documents(packets: Iterable[Mapping[str, Any]])` **和** 第 117 行 active 的
   `_is_comparative(title, stock, blocks: Iterable[Mapping[str, Any]])`（被 `validate_external_source_document`
   与 `is_comparative_external_document` 调用）。
   由于文件有 `from __future__ import annotations`，删 import 不会在运行时抛 NameError，但会留下悬挂的
   类型注解名，且与设计自述矛盾。
   **修正**：保留 `Iterable` import（推荐，符合「不改 active helper 实现」原则）；若坚持删，必须同时改写
   `_is_comparative` 的签名注解——后者属于改 active helper，超出最小删除边界。
   该修正只影响 A5 的文本与 1 行 line saving，不阻塞 plural helper 本身的删除。

## nice_to_have

1. Task 1 hygiene 断言建议补一条「active owner 存在」对称项：`build_external_source_document`（单数）仍在。
   当前它被 12 个测试文件与 `curated_external_full_body_viewpoint_claims.py:62` import，full suite 能兜底；
   但显式断言可让「多删一个 active helper」类回归在 hygiene 层直接 RED。
2. README:470 引用 `tests/test_price_target.py`，该文件不存在（仅存在 `test_price_target_e2e.py`），为既有 stale
   文档条目。与本批无关，可顺带修正，但不构成本批范围。
3. `docs/superpowers/*`、`docs/agent_workflow/2026-07-14-*`、`docs/codex_handoff/*` 中的历史引用（A1/A2/A3
   均涉及）无需改动，避免重写历史；本批只按设计动 README 的 renderer 行。

## A1–A5 逐项判断与证据

### A1 `PriceTargetRenderer` 删除 —— safe

- 文件 `scripts/utils/reporter/sections/price_target_renderer.py`（110 行）为自包含旧 renderer；全仓运行时引用
  仅三处：自身定义、`sections/__init__.py:22` import + `:35` `__all__`、`README.md:430` 表格行。其余为历史文档
  （`docs/superpowers/*`、`docs/agent_workflow/2026-07-14-*`）。
- **无任何运行时实例化点**：正式 `ReportAssemblySkill.RENDERERS`（`assembly_skills.py:41-52`）不含
  `price_target`；动态 `__import__(module_path, fromlist=[class_name])`（216 行）只消费 RENDERERS 路径。
  `xueqiu_monitor_v2.py:158-159` 仅向 `stock_raw` 携带 `price_target` 数据，不实例化任何 section renderer。
- `tests/reporter/test_assembly_skills.py:79-80` 是**负向锁定**（`assert all(name != "price_target" ...)`），
  已通过、非调用方。
- **替代 owner 完整**：`TechnicalRenderer` 在正式 assembly 与 3 个 `run_*技术分析_真实数据.py` 及
  `scripts/smoke/smoke_test.sh` 中被实例化；`technical_renderer.py:224/289` 经 `_render_target_judgment`
  渲染目标价表/trigger checks/止损。当前正式报告 `reports/中际旭创_20260804.md:198` 已显示
  `**价格目标分析**`（TechnicalRenderer 输出），旧「## 价格目标与触发条件」section 在正式链路早已不产出。
  目标价**引擎** `price_target.py`（`analyze_price_target`）仍由 `technical_analyzer.py:106/972` 与
  `test_price_target_e2e.py:7` 使用，不在删除范围。
- runtime 删除量：110（文件）+ 2（`__init__`）= 112 行。README 仅删 430 行一条。

### A2 `fetch_index_bars` 删除 —— safe

- `data_fetcher.py:862-882`（21 行）仅定义；scripts/tests/previews/tools 无 import 或调用；不在
  `reporter/__init__.py` 的 `from .data_fetcher import (...)` 公开导出列表内（导出项仅 quote/consensus/financial/
  competitor/valuation 相关）。
- 指数 owner 已由 `technical_analyzer._fetch_index_kline`（`client.index_bars`）+ `technical_ohlcv_cache.v2`
  承担，且在本批次之前的多轮冷/热验收中已验证热跑零指数 provider 请求。
- 历史引用仅在 `docs/superpowers/specs|plans/2026-06-08-technical-phase3*`。

### A3 `v2_note_card_fingerprint` 删除 —— safe

- `periodic_report_narrative_pack_store.py:91-101`（11 行）仅定义；scripts/tests 无其他引用。
- 设计声明的保留面全部属实：
  - `_integrity()`（80-87 行）用 `_hash(cards)`/`_hash(diagnostics)`/`_hash(_payload(envelope))` 计算
    cards_sha256/payload_sha256，是 active 完整性校验；
  - `normalized_source_excerpt_hash`（35 行）被 active `periodic_report_narrative_view_writer.py`（13/20/94 行）
    与 `tests/utils/test_periodic_report_narrative_pack_store.py:70-71` 使用，**必须保留**；
  - `deepcopy` 仍被 `_envelope()`（139 行）使用，import 保留正确。

### A4 三个 `*_from_cache` wrapper 删除 —— safe

- `periodic_report_fulltext_intake_skill.py`：三个 public wrapper（287-303 / 340-353 / 366-383，共 49 行）只做
  「`_load_periodic_report_cache_rows(... latest_only=True)` + 转发 rows helper」，全仓无任何调用方（tests 亦无）。
- active skill `periodic_report_fulltext_intake_skill()`（581 行起）**只加载一次** `cache_rows`（590-594 行），
  直接调用三个 rows helper（597-599 / 622 / 624-625 行）——与设计描述完全一致，删 wrapper 消除三次重复读盘。
- 三个 rows helper 定义保留；`_load_periodic_report_cache_rows` 仍在 active 路径使用。

### A5 删除 plural helper + `RequiredMetricsError` —— safe（附 must_fix 见上）

- `build_external_source_documents`（`external_source_document.py:57-60`，4 行）：仅定义。单数
  `build_external_source_document` 高度 active（12 个测试文件 + `curated_external_full_body_viewpoint_claims.py:62`）。
- `RequiredMetricsError`（`periodic_report_required_metrics.py:28-30`，3 行）：仅定义。模块仍被
  `periodic_report_fulltext_llm_analysis.py`/`periodic_report_required_financial_metrics.py`/skill 导入用于
  `build_required_business_metrics`/`_normalize_numeric`/`_value_cell`，该类本身无 import/捕获/实例化。
- `Iterable` import 判断见 must_fix。

## requirement-test gaps

- Task 1 hygiene RED 断言覆盖面：文件不存在（A1）、A2–A5 top-level defs 不存在、active owners 存在
  （TechnicalRenderer / normalized_source_excerpt_hash / 三个 rows helper）、RENDERERS 无 `price_target`——设计合理。
- 已实跑设计 §6 Task 2 的 focused 清单（`-q -p no:cacheprovider`，`PYTHONDONTWRITEBYTECODE=1`）：
  **94 passed in 62.94s**，基线绿，RED→GREEN 有干净基准。
- 缺口 1（minor）：hygiene 未断言单数 `build_external_source_document` 仍存在（见 nice_to_have）。
- 缺口 2（minor）：`RequiredMetricsError` 删除无测试锚点，属不可见 no-op 删除，可接受。
- 缺口 3（must_fix 延伸）：若实现按错误设计删 `Iterable` import，无测试会捕获悬挂注解——必须按 must_fix 修正设计后再实现。
- failure modes 表（§7）与 focused/full suite 对齐：A1→hygiene+assembly+full suite；A2→OHLCV cache+resonance；
  A3→pack store focused；A4→fulltext focused+full suite；A5→external doc tests；报告内容回归由 offline smoke 兜底。

## scope / compatibility audit

- 无 previews（`scripts/previews/` 9 个文件）引用任何候选；tools/ 无引用；无 star import 命中候选模块。
- 动态 registry（RENDERERS + `__import__`）不触达候选；`reporter/__init__.py` 公开导出不含 `fetch_index_bars`。
- AGENTS.md 声明的保留入口不受影响：3 个 `run_*技术分析_真实数据.py` 与 `smoke_test.sh` 用 `TechnicalRenderer`
  （保留）；`xueqiu_monitor_v2.py` 不用 section renderer；`run_stock_report.py --offline-smoke` 存在（66/93/660 行）。
- README 契约：A1 仅删 430 行一条；424 行 `TechnicalRenderer 渲染...价格目标` 与 411 行引擎条目均保留，描述一致。
- 主仓库同步边界（Q8）：设计 §9 将同步推迟到独立阶段并「先审主仓库真实 diff」，与 AGENTS.md Level 3 协作规则一致；
  本批在 clean canonical worktree 实施，baseline（f6f3714/172 文件/67,246 行/ahead 7）经核对全部属实，不混入主仓库脏改动。

## runtime deletion budget audit

- 精确清点（运行时行，不含 tests/README）：
  - A1 = 110（文件）+ 2（`__init__` import + `__all__`）= **112**
  - A2 = **21**
  - A3 = **11**
  - A4 = 17 + 14 + 18 = **49**
  - A5 = 4 + 3 = **7**（若按 must_fix 保留 `Iterable` import，则少计 1 行）
  - **合计 ≈ 200 行**（设计估计 ~197）。
- 目标「净减不少于 185」可信且达成有余量；A5 修正后仍 ≥ 197。无运行时新增（Task 1 只加测试断言）。
- 未发现「以删兼容能力凑行数」：每项均有 active 替代 owner（A1 TechnicalRenderer / A2 v2 cache+analyzer /
  A4 rows helpers / A5 单数 helper），A3/A5b 为纯 no-op 死代码。

## implementation_ready: no

需先按 must_fix 修正设计 §4-A5 的 `Iterable` import 说明（保留 import 或同步改 `_is_comparative` 注解）。
修正后本批可进入实现，无需 Round 2（无 blocker，must_fix 为局部文本修正且不改变高风险边界）。
