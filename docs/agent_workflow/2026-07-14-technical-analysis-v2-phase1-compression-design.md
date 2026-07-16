# Technical Analysis v2 Phase 1 Compression Design

日期：2026-07-14

Worktree：`/Users/erichan/testsnow/.worktrees/annual-producer-v2`

## 1. 目标

在不改变 Technical Analysis v2 Phase 1 已锁定行为契约的前提下，把十个允许 runtime 文件相对 task-start baseline 的净增从 `+520` 压到约 `+170-180`，并保留唯一的 `+240` hard stop。

本任务是等价重构，不增加新功能，不调整技术指标、目标价、评分、EV、风险或仓位阈值。

## 2. 当前事实

当前十个 runtime 文件的净增分布：

| 文件 | 当前净增 |
|---|---:|
| `price_target.py` | +215 |
| `technical_state_machine.py` | +347 |
| 其余八个 consumer / orchestration 文件合计 | -42 |
| 合计 | +520 |

两个 owner 仍是主要压缩对象，但自审确认 `scoring_engine.py::_technical_position_guardrail()` 是零调用的私有旧 guardrail，删除可再净减约 57 行；`price_target.py::_macd_dead_expanding()` 在 direction-aware blocker 替换后也已零调用。已经通过测试的 consumer 迁移继续保留，不再回退到旧 `price_target.error/reason` 中文解析路径。

## 3. 不可改变的行为契约

以下行为属于 Phase 1 验收面，压缩时不得删减：

1. `price_target.py` 每个出口提供稳定 `status` 与 `reason_code`。
2. `structure_confidence` 与 `structure_evidence` 继续区分形态、周期方向和 Fibonacci 汇聚。
3. `fib_only` 恒为 `observe / structure_observation`，不进入盈亏比阻断。
4. MACD blocker 必须 direction-aware。
5. `technical_judgment.v1` 仍是 renderer、recommendation、scoring 和 dashboard 的唯一正式判断输入。
6. 趋势健康度 `<50` 的上升趋势映射为 `transition`。
7. 触发检查仍使用既定 price / trend / volume / momentum 公式；港股量比阈值为 `1.3`，A 股为 `1.5`。
8. legacy collector fallback 不得再次调用完整 analyzer。
9. 合法 `unavailable` judgment 不得泄漏旧三档目标、时间预期或旧中文 error 分支。
10. `PriceTargetRenderer` 不恢复到正式 renderer registry。
11. legacy `trigger_conditions.trend` 兼容文案也必须使用固定阈值 `ADX>=25`，不得继续把当前 ADX 值写成未来阈值。

## 4. 压缩策略

### 4.1 `technical_state_machine.py`

指导目标：从净增 `+347` 压到约 `+170`。这是规划值，不是独立 hard stop；只由十文件总量 `+240` 决定是否停止。

保留 public API：

- `build_technical_judgment()`
- `ensure_technical_judgment()`
- `resolve_target_display_mode()`

替换账本：

1. 用一个 `_trigger_checks(...)` owner 替换 `_check_price`、`_check_trend`、`_check_volume`、`_check_momentum` 和 `_normalise_checks` 五段重复装配逻辑。
   - 内部仍分别计算四项检查；只合并取数、状态字典构造和 supplied-check fallback。
   - 不允许新增第二套 trigger selector。
   - 固定执行顺序：若 supplied checks 同时含四项合法 dict，则原样采用；否则四项全部按结构数据重新计算；随后仅当 `structure_confidence == low` 时覆盖 `price=unknown`；最后只为真正缺失的 key 补 `unknown`。不得把 low-confidence 覆盖泛化到 trend/volume/momentum。
2. 新增一个小型 `_check(status, detail, **values)` 构造器，统一 `pass/pending/fail/unknown` payload，删除重复字典字面量。
3. `_trend_judgment()` 在完全缺失趋势输入时直接返回 `unknown`。这样 malformed-cache fallback 可直接复用 `build_technical_judgment({}, {})`。
4. 删除 `_unavailable_judgment()` 的整份 schema 复制。`ensure_technical_judgment()` 只做：合法 v1 原样返回；否则用结构输入重建；输入不足时 builder 自然返回 fail-closed judgment。
5. `_valid_judgment()` 改为 required enum checks 的紧凑 validator，不重复展开 schema。
6. confidence 中文 label 使用一个模块常量，禁止在 builder 中重复两份映射。
7. `_execution_state()` 与 `_action_state()` 保留独立职责，不合并为难以测试的大函数。

明确禁止：

- 把 trigger checks 移到 renderer 或 scoring；
- 从中文 detail 反向推断状态；
- 删除 adjustment/data-quality cap；
- 用表驱动技巧隐藏既有阈值，使测试难以定位。

### 4.2 `price_target.py`

指导目标：从净增 `+215` 压到约 `+100`。这是规划值，不是独立 hard stop。

替换账本：

1. 扩展 `_target_with_status(status, reason_code, common=None, **payload)`：
   - `common` 保存 `weekly_trend / daily_trend / direction / structure_evidence / structure_confidence`；
   - 各 return branch 只传差异字段；
   - 删除各分支重复的 4-6 个 context key。
2. 用 `_first_pattern(close)` 统一日线/周线双底、双顶检测，保持“第一个有效形态”的现有顺序。
3. 用 `_fib_projection(bands)` 统一 daily/weekly 的三档 Fibonacci candidate、压缩价位和 convergence 计算，替换两段近似循环。
4. 用 `_structure_summary(daily_info, weekly_info, weekly_direction, fib_convergence, has_bands)` 一次返回：
   - `direction`
   - `patterns_aligned`
   - `weekly_direction_aligned`
   - `method_family`
   - `structure_evidence`
   - `structure_confidence`
5. 保留 producer decision order，不把 conflict、observation、MACD、ATR、risk plan、盈亏比检查重新拆成第二条路径。
6. 保留旧 confidence/time/diagnostic 字段作为兼容输出，但不再为新 status 分支重复组装它们。
7. 删除零调用的 `_macd_dead_expanding()` compatibility wrapper；direction-aware `_opposing_macd_expanding()` 是唯一 blocker helper。
8. 把 legacy `trigger_conditions.trend` 改为固定 `ADX>=25 且方向 DI 确认`，不再插入当前 ADX 数值。

明确禁止：

- 删除形态冲突或 timeframe conflict；
- 从 `synthesize_targets()` 的压缩结果反推 convergence；
- 改动 Zigzag、Fibonacci、ATR、盈亏比或旧六因子公式；
- 为缩短代码把不同失败原因合并成同一 `reason_code`。

### 4.3 Consumer 文件与旧 guardrail 删除

除 `scoring_engine.py` 的两项明确变更外，当前 consumer 迁移保持现状：

- `data_collector.py`
- `technical_skills.py`
- `technical_analyzer.py`
- `recommendation_decision.py`
- `scoring_engine.py`
- `technical_renderer.py`
- `html_dashboard_renderer.py`
- `assembly_skills.py`

不得为了压预算恢复已删除的 `_entry_quality_guardrail()` 或旧 renderer target branch。

`scoring_engine.py` 允许且只允许：

1. 删除 `_technical_position_guardrail()`。全仓库 `rg/git grep` 均只有定义、没有调用或测试依赖；它是已迁移到 `EntryConstraint` 后遗留的私有第二 owner。
2. 修复 `risk_control` 仓位上限，使非“积极配置”起点也能降到已有 `position_cap_note` 的 `0-5%`，但不改变风险分数。

`PriceTargetRenderer` 类与 package export 本轮不删除；只保持它不进入正式 renderer registry。

## 5. 风险控制语义补齐

压缩前先锁定一个当前测试缺口：合法 judgment 的 `action.state == risk_control` 时，风险评估仓位必须固定降到 `0-5%`，不能只在原建议为“积极配置”时才降级。

该修复只能复用已有 `EntryConstraint.position_cap_note`，不得新增第二套仓位算法，也不修改风险分数。

## 6. TDD 执行顺序

### Batch C1：锁定行为基线

1. 运行当前非网络技术面 suite，确认 `179 passed` 和 collector subset `3 passed`。
2. 新增 risk-control 仓位测试，确认当前 RED。
3. 新增完全空输入 judgment 测试，断言 builder 返回完整 fail-closed schema。
4. 扩展 low-confidence trigger 测试：只允许 `price=unknown`，trend/volume/momentum 保持各自计算结果。
5. 新增 legacy trigger 文案测试，断言使用固定 `ADX>=25`，不包含当前 ADX 数值作为阈值。
6. 用 `rg/git grep` 记录 `_technical_position_guardrail` 与 `_macd_dead_expanding` 的零调用证据；这是 dead-code deletion，不新增实现细节测试。
7. 记录十文件 runtime numstat；任何其他文件变化视为越界。

### Batch C2：压缩 price target

1. 用现有 fixture 锁定所有 `status/reason_code`、direction-aware MACD、fib-only observation、profit-risk 完整性。
2. 引入 shared context、pattern helper、fib helper、structure summary，删除重复分支装配和 `_macd_dead_expanding()`。
3. 修正 legacy ADX trigger 文案为固定阈值。
4. 跑 `test_price_target.py` 与 `test_price_target_e2e.py`。
5. 记录总 runtime；如果基于实际剩余预算已无法在总计 `+240` 内完成 state machine，停止并返回设计。

### Batch C3：压缩 state machine

1. 用 C1 测试锁定 judgment schema、data-quality cap、trigger checks、HK 阈值、空输入、malformed cache 和 trend reconciliation。
2. 替换五段 trigger helper 与 duplicated unavailable schema。
3. 跑 `test_technical_state_machine.py`、`test_technical_skills_contract.py`、recommendation/renderer consumer tests。
4. 记录总 runtime；不得以压缩单文件为由删除行为契约。

### Batch C4：消费者与预算验收

1. 删除零调用的 `_technical_position_guardrail()`，再修复 risk-control 仓位 RED；保持评分/EV/风险分数不变。
2. 跑完整非网络 consumer suite、collector subset、CI grep gates、`git diff --check`。
3. 十文件总 runtime 工作目标约 `+170-180`，绝对 hard stop `+240`。
4. 未满足预算时不生成报告、不提交、不进入 Phase 2。

## 7. Requirement-Test Matrix

| 要求 | 测试 |
|---|---|
| status/reason_code 全出口稳定 | `test_price_target.py` status matrix |
| fib-only 不进入盈亏比阻断 | `test_fib_only_target_is_observation_before_reward_risk` |
| MACD direction-aware | `test_opposing_macd_expanding_is_direction_aware` |
| `<50` 上升趋势转 transition | `test_uptrend_with_health_below_fifty_is_transition` |
| 四项 trigger 从行情计算 | `test_judgment_calculates_trigger_checks_from_market_data` |
| HK 1.3 / A 股 1.5 | `test_judgment_uses_hk_volume_ratio_threshold` |
| malformed cache fail closed | `test_ensure_technical_judgment_malformed_cache_is_unavailable` |
| 完全空输入 fail closed 且 schema 完整 | 新增 `test_empty_inputs_build_complete_unavailable_judgment` |
| low confidence 只覆盖 price check | 扩展 low-confidence fixture，断言其余三项不被改写 |
| unavailable 不泄漏旧目标 | `test_technical_renderer.py` unavailable regression |
| judgment 覆盖 legacy target error | `test_recommendation_decision.py` judgment precedence |
| collector 不二次调用 analyzer | `test_legacy_indicator_fallback_does_not_call_full_analyzer` |
| dashboard 读取 nested judgment | `test_dashboard_reads_nested_technical_judgment` |
| risk_control 固定 0-5% | 新增 `test_risk_control_judgment_caps_position_at_zero_to_five` |
| legacy ADX 文案使用固定阈值 | 新增 `test_ready_target_uses_fixed_adx_trigger_text` |
| 第二套私有 guardrail 已删除 | `rg/git grep` 仅允许 design/notes 历史文本，不允许 runtime 定义或调用 |

## 8. Failure Modes

| 失败模式 | 表现 | 捕获方式 |
|---|---|---|
| shared context 覆盖 branch 字段 | reason/status 或方向错误 | status matrix + conflict fixtures |
| fib helper 丢失 daily-only convergence | confidence 从 medium/high 降为 low | daily convergence fixture |
| compact validator 接受残缺 judgment | renderer 读取缺字段异常 | malformed/partial cache fixtures |
| trigger 合并后港股阈值回归 | 1.4 量比被判 pending | HK/CN paired fixture |
| fail-closed builder 把空输入判 range | malformed cache 显示可用趋势 | unavailable cache fixture |
| risk_control 只降积极仓位 | 中风险仓位仍 10-15% | 新 risk-control position fixture |
| legacy trigger 继续使用当前 ADX | 报告/兼容消费者把观测值当阈值 | fixed-ADX compatibility fixture |
| dead guardrail 未删除 | 技术仓位仍存在两个 owner | runtime symbol audit |
| 为达预算删除兼容字段 | 旧消费者或 e2e 断言失败 | downstream suite |
| 预算通过但新增第二套 owner | 同状态在不同入口输出不一致 | AST/rg audit + consumer contract tests |

## 9. Scope 与停止条件

实现允许修改：

- `scripts/utils/reporter/technical_state_machine.py`
- `scripts/utils/reporter/price_target.py`
- `scripts/utils/reporter/scoring_engine.py`（仅删除零调用 `_technical_position_guardrail()` 与修复 risk-control 仓位）
- `tests/reporter/test_price_target.py`
- `tests/reporter/test_technical_state_machine.py`
- `tests/reporter/test_scoring_engine_risk.py`
- implementation notes

禁止修改指标算法、评分权重、目标价公式、LLM prompt、报告第四章、data、knowledge、reports、配置和采集源。

立即停止条件：

- 十文件 runtime 净增 `> +240`；
- 需要修改允许范围外 runtime 文件；
- 需要改变状态、阈值或技术公式才能过测试；
- 非网络 suite 出现无法解释的既有回归。

## 10. Design Delta

- accepted：保留 Phase 1 全部行为契约和唯一的 `+240` hard stop。
- accepted：消费者迁移不回退，压缩只针对两个 owner。
- accepted：补齐 `risk_control -> 0-5%` 的既有设计缺口。
- accepted：Round 1 B1。删除不可实现的 per-file hard stop；结合两个零调用 helper 的净删减，采用总量 `~+170-180` 的指导预算。
- accepted：Round 1 requirement-test gaps。新增空输入完整 schema 与 low-confidence 作用域断言。
- accepted：Codex self-review。删除零调用 `_technical_position_guardrail()` 与 `_macd_dead_expanding()`，避免为守预算过度压缩 state machine。
- accepted：Codex self-review。锁定 supplied-check / calculated-check / low-confidence override / missing-key default 的执行顺序。
- accepted：Codex self-review。legacy ADX trigger 文案同步固定为 `ADX>=25`。
- rejected：通过删除结构证据、触发检查或 reason codes 换取行数。
- rejected：提高预算或新增独立 technical judgment 模块。
- rejected：把 `+170` 重新设为 state-machine hard stop；review 给出的可行区间上沿为 `+175`，该硬门仍会产生假停止。
- deferred：抽取成交量/金额阈值常量；当前不存在两套数值计算 owner，压缩阶段不为文案复用增加接口。
- deferred：正式报告生成与 Phase 2；只有压缩实现通过后再执行。
- R2 required：yes。Round 1 有 B1 blocker，需确认修订后的总预算门和新增测试后再锁定实现。
