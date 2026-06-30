# Evidence Note Pipeline Integration Phase 3 Design

> Date: 2026-06-12  
> Owner: Codex  
> Status: Draft for Claude review  

---

## 1. Goal

把 Phase 2 的 `write_evidence_notes()` 接入单股深度报告流程，让 Agent-Reach 通过质量门后的 keep/demote 证据能够生成知识库 evidence notes。

本阶段的目标不是让报告结论变聪明，而是建立一条可控、可测试、可回滚的证据入库通道：

- 默认不写真实 `knowledge/`。
- 只有显式开关开启时才运行 evidence note writer。
- 写入结果只进入 `SkillContext` 的状态与 plan，不进入 `KnowledgeSynthesizer`。
- 黑芝麻单股入口可用 `--fast-test` 验证，不走 `xueqiu_monitor_v2.py`。

---

## 2. Current State

已有能力：

1. `scripts/utils/source_credit.py`
   - 对来源做确定性信用评分。
   - 输出 `source_type`, `source_credit`, `verification_status`, `knowledge_eligible`, `report_eligible` 等字段。

2. `scripts/utils/source_adapter.py`
   - `AgentReachAdapter.to_synthesis_item()` 已把 source-credit metadata 写入 `SynthesisItem.extra`。

3. `scripts/utils/evidence_note_writer.py`
   - `write_evidence_notes(stock_name, stock_code, items, base_dir, collected_at=None, dry_run=False)`。
   - 纯模块，不调用网络、LLM、浏览器、subprocess。
   - 写入路径为 `<base_dir>/10-Stocks/<stock_name>/evidence/`。
   - 支持 `dry_run=True`。

4. Agent-Reach pipeline:
   - `agent_reach_query_skill`
   - `agent_reach_fetch_skill`
   - `agent_reach_quality_skill`
   - quality skill 输出：
     - `agent_reach_quality_status`
     - `agent_reach_keep_items`
     - `agent_reach_demote_items`
     - `agent_reach_quality_results`
     - `agent_reach_quality_summary`

当前缺口：

- Evidence note writer 还没有被任何入口或 pipeline 调用。
- 没有统一的 ctx 状态说明本次会写/已写/跳过/过滤多少 evidence notes。
- 没有端到端测试证明“开启 Agent-Reach + evidence notes”不会污染 synthesis 或默认 pipeline。

---

## 3. Non-Goals

本阶段明确不做：

- 不修改 `KnowledgeSynthesizer`。
- 不把 evidence notes 传入 `SynthesisSkill._build_synthesis_items()`。
- 不修改 LLM prompt。
- 不让 evidence notes 影响评分、技术分析、风险评分或报告结论。
- 不修改 Agent-Reach connector。
- 不修改 Agent-Reach quality gate 阈值。
- 不改报告 renderer 展示形态。
- 不运行 `xueqiu_monitor_v2.py` 作为验证入口。
- 不自动刷新知乎、不运行 ZhihuCurator/DeepSeek curator。

---

## 4. Proposed Architecture

### 4.1 Add A Dedicated Pipeline Skill

新增文件：

`scripts/utils/report_skills/evidence_note_skill.py`

职责：

- 从 ctx 读取 Agent-Reach quality gate 输出。
- 合并 `agent_reach_keep_items + agent_reach_demote_items`。
- 调用 `write_evidence_notes()`。
- 把结果写回 ctx。
- disabled/skipped/error 都以 ctx 状态表达，尽量不让非关键写入失败中断报告生成。
- 在 skill 内部捕获所有 writer 异常。`@skill` 装饰器会重新抛出未捕获异常，所以 evidence skill 必须自己 `try/except`，写入 `evidence_note_status="error"` 后返回 ctx，不得让异常逃逸。
- 只读复制 `agent_reach_keep_items` 与 `agent_reach_demote_items`，不得原地过滤、pop 或修改这些列表/对象。

建议公共函数：

```python
@skill(name="evidence_note_writer")
def evidence_note_writer_skill(ctx: SkillContext) -> SkillContext:
    pass
```

建议 ctx 输入：

| Key | Type | Default | Meaning |
|---|---|---|---|
| `enable_evidence_notes` | bool | `False` | 是否启用 evidence note writer。 |
| `evidence_notes_dry_run` | bool | `True` | 是否只生成 write plan、不写磁盘。Phase 3 推荐默认 True。 |
| `knowledge_base_dir` | str | repo root `knowledge` | 知识库根目录；测试必须传入绝对 `tmp_path`。 |
| `stock_name` | str | required | 股票名。 |
| `stock_codes` | dict | `{}` | 从股票名取代码。 |

建议 ctx 输出：

| Key | Type | Meaning |
|---|---|---|
| `evidence_note_status` | str | `disabled` / `skipped` / `dry_run` / `written` / `completed` / `empty` / `error` |
| `evidence_note_write_plan` | dict | `written`, `skipped_existing`, `filtered` 三类清单 |
| `evidence_note_summary` | dict | `written_count`, `skipped_existing_count`, `filtered_count`, `dry_run`, `base_dir`, `reason`, `collected_at` |
| `evidence_note_error` | str | 出错时记录错误文本，正常为空 |

`evidence_note_write_plan` 必须是 plain dict，不能把 `EvidenceWritePlan` dataclass 直接塞进 ctx。推荐使用 `dataclasses.asdict(plan)` 或等价转换，保证后续 JSON dump/debug 不出问题。

### 4.2 Status Rules

严格状态规则：

1. `enable_evidence_notes=False`
   - status: `disabled`
   - summary reason: `disabled`
   - 不调用 `write_evidence_notes()`

2. `agent_reach_enabled=False`
   - status: `skipped`
   - summary reason: `agent_reach_disabled`
   - 该分支在 pipeline builder 正常路径下通常不可达，因为 writer 只在 Agent-Reach 启用时插入；保留为直接调用 skill 时的防御逻辑。

3. `agent_reach_quality_status` 不是 `ok`
   - status: `skipped`
   - summary reason: `agent_reach_quality_status=<status>`

4. keep/demote 均为空
   - status: `empty`
   - summary reason: `no_keep_or_demote_items`
   - 返回空 plan

5. `evidence_notes_dry_run=True`
   - 调用 writer 的 `dry_run=True`
   - status: `dry_run`
   - 不创建真实 evidence 文件

6. `evidence_notes_dry_run=False`
   - 调用 writer 的 `dry_run=False`
   - 若 `written_count > 0`，status: `written`
   - 若 `written_count == 0` 但 writer 成功返回，status: `completed`
   - `completed` 表示本次运行成功结束，但所有候选都因已存在或过滤规则未产生新文件

7. writer 抛异常
   - status: `error`
   - `evidence_note_error` 记录异常
   - 报告生成不中断

### 4.2.1 Collected Time

`evidence_note_writer_skill` 调用 writer 时必须传入 `collected_at`：

```python
collected_at = datetime.now().isoformat()
```

测试可 monkeypatch skill 模块里的 datetime provider 或直接断言 `collected_at` 在 summary 中为非空 ISO-like 字符串。不要把 `date_str` 拼成伪 ISO datetime；`date_str` 只用于报告文件名，不足以表达采集时间。

### 4.2.2 Knowledge Base Directory Resolution

默认知识库目录必须解析到 repo root 下的 `knowledge`，不能受 `scripts/` cwd 误导到 `scripts/knowledge`。

推荐实现：

```python
base_dir = ctx.get("knowledge_base_dir")
if not base_dir:
    base_dir = Path(__file__).resolve().parents[3] / "knowledge"
```

说明：`evidence_note_skill.py` 位于 `scripts/utils/report_skills/`，`parents[3]` 对应 repo root。测试必须传入绝对 `tmp_path` 覆盖默认目录，避免写真实知识库。

### 4.3 Pipeline Assembly

修改 `scripts/utils/report_skills/__init__.py`：

```python
def build_stock_report_pipeline(
    llm_client=None,
    enable_agent_reach: bool = False,
    enable_evidence_notes: bool = False,
) -> SkillPipeline:
    pass
```

插入位置：

```text
data_loading_skill
quality_gate_skill
agent_reach_query_skill
agent_reach_fetch_skill
agent_reach_quality_skill
evidence_note_writer_skill      # only when enable_agent_reach and enable_evidence_notes
cross_source_consolidation_skill
SynthesisSkill
ReportAssemblySkill
```

约束：

- 默认 `build_stock_report_pipeline()` 仍返回 11 skills。
- `enable_agent_reach=True, enable_evidence_notes=False` 仍返回当前 14 skills。
- `enable_agent_reach=True, enable_evidence_notes=True` 返回 15 skills。
- 如果 `enable_agent_reach=False, enable_evidence_notes=True`，不插入 writer skill；writer 依赖 Agent-Reach quality 输出。

### 4.4 PerStockReporter Wiring

修改 `scripts/utils/stock_reporter.py`，让每只股票配置可以显式启用 evidence notes：

```python
ar_cfg = self.agent_reach_configs.get(stock_name, {})
agent_reach_enabled = self.enable_agent_reach or ar_cfg.get("enabled", False)
evidence_cfg = ar_cfg.get("evidence_notes", {}) or {}
evidence_notes_enabled = bool(evidence_cfg.get("enabled", False))
```

传给 pipeline builder：

```python
pipeline = build_stock_report_pipeline(
    enable_agent_reach=agent_reach_enabled,
    enable_evidence_notes=agent_reach_enabled and evidence_notes_enabled,
)
```

传给 pipeline input：

```python
if evidence_notes_enabled:
    pipeline_input["enable_evidence_notes"] = True
    pipeline_input["evidence_notes_dry_run"] = evidence_cfg.get("dry_run", True)
    if evidence_cfg.get("base_dir"):
        pipeline_input["knowledge_base_dir"] = evidence_cfg["base_dir"]
```

默认行为：

- 现有 config 不含 `evidence_notes` 时，不运行 writer。
- Phase 3 可以只在测试里构造 `agent_reach_configs`，不强制改 `config/stocks.json`。
- 是否把黑芝麻 `config/stocks.json` 增加 `evidence_notes: {"enabled": true, "dry_run": true}` 作为最后一步，由实现前 review 决定。推荐先不改 config，避免默认运行时产生额外状态变化。

### 4.5 Knowledge Base Write Mode

Phase 3 推荐两种验证模式：

1. Unit/integration tests:
   - 使用 `tmp_path` 作为 `knowledge_base_dir`。
   - 覆盖 dry-run 和 real-write。

2. Black Sesame fast-test manual validation:
   - 推荐先用 dry-run，不写真实 `knowledge/`。
   - 只有用户明确确认后，再用 `dry_run=False` 写真实 knowledge evidence。

本阶段不要求将真实 evidence notes 写入仓库。

---

## 5. Files Expected To Change

| File | Change Type | Reason |
|---|---|---|
| `scripts/utils/report_skills/evidence_note_skill.py` | Create | 新增 pipeline skill，封装 writer 调用与 ctx 状态。 |
| `scripts/utils/report_skills/__init__.py` | Modify | 导入/export skill，新增可选 `enable_evidence_notes` 参数并插入 skill。 |
| `scripts/utils/stock_reporter.py` | Modify | 从 per-stock Agent-Reach config 读取 evidence_notes 配置并传入 pipeline。 |
| `tests/reporter/test_evidence_note_skill.py` | Create | 覆盖 skill 状态规则、dry-run、real-write、error 不阻断。 |
| `tests/reporter/test_pipeline_integration.py` | Modify | 覆盖 11/14/15 skill 数量与 ordering。 |
| `tests/reporter/test_stock_reporter_agent_reach_config.py` | Modify | 覆盖 PerStockReporter 传递 evidence note config。 |

Optional:

| File | Change Type | Reason |
|---|---|---|
| `docs/agent_workflow/2026-06-12-evidence-note-pipeline-integration-claude-notes.md` | Create | Claude implementation notes。 |

---

## 6. Files That Must Not Change

| File/Area | Reason |
|---|---|
| `scripts/utils/knowledge_synthesizer.py` | Evidence notes 还不进入 LLM synthesis。 |
| `scripts/utils/report_skills/synthesis_skills.py` | 禁止把 evidence notes 传入 `KnowledgeSynthesizer`。 |
| `scripts/utils/reporter/scoring_engine.py` | 不影响评分。 |
| `scripts/utils/report_skills/agent_reach_quality_skill.py` | 不调整质量门。 |
| `scripts/utils/report_skills/agent_reach_skill.py` | 不调整 connector/采集。 |
| `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` | 不调整报告展示。 |
| `scripts/run_黑芝麻智能.py` | 本阶段优先不改入口；如确需手工验证开关，必须先写设计补充。 |
| `scripts/xueqiu_monitor_v2.py` | 不作为验证入口，不修改。 |
| `knowledge/10-Stocks/**` | 单测不写真实知识库；真实写入需用户明确确认。 |

---

## 7. Tests

### 7.1 Evidence Skill Unit Tests

Create `tests/reporter/test_evidence_note_skill.py`.

Required cases:

1. disabled:
   - input `enable_evidence_notes=False`
   - status `disabled`
   - monkeypatch `write_evidence_notes` to fail if called

2. Agent-Reach disabled:
   - input `enable_evidence_notes=True`, `agent_reach_enabled=False`
   - status `skipped`
   - summary reason `agent_reach_disabled`

3. quality not ok:
   - input `agent_reach_quality_status="empty"` or `"skipped"`
   - status `skipped`
   - summary reason starts with `agent_reach_quality_status=`
   - writer not called

4. no keep/demote:
   - input quality ok but empty lists
   - status `empty`
   - summary reason `no_keep_or_demote_items`
   - writer not called

5. dry-run:
   - input one company official keep item
   - `evidence_notes_dry_run=True`
   - status `dry_run`
   - `evidence_note_write_plan["written"]` has one planned path
   - `evidence_note_write_plan` is a plain dict, not an `EvidenceWritePlan` dataclass
   - `evidence_note_summary["collected_at"]` is non-empty
   - no files created under tmp_path

6. real write:
   - same item
   - `evidence_notes_dry_run=False`
   - status `written`
   - one file created under `tmp_path/10-Stocks/黑芝麻智能/evidence/`

7. real write with only existing/skipped/filter outcomes:
   - pre-create existing evidence note or provide filter-only items
   - `evidence_notes_dry_run=False`
   - status `completed`
   - `written_count == 0`

8. demote included:
   - keep + demote item
   - writer receives both

9. keep/demote lists are read-only:
   - pass original `keep_items` and `demote_items`
   - run skill
   - assert the original lists are unchanged and still present in ctx

10. discard not passed:
   - skill should only read keep/demote lists; discard never appears

11. writer exception:
   - monkeypatch writer to raise
   - status `error`
   - `evidence_note_error` populated
   - no exception escapes

### 7.2 Pipeline Integration Tests

Modify existing pipeline tests:

1. default:
   - `build_stock_report_pipeline()` -> 11 skills

2. Agent-Reach only:
   - `build_stock_report_pipeline(enable_agent_reach=True)` -> 14 skills
   - order: query -> fetch -> quality -> consolidation

3. Agent-Reach + evidence:
   - `build_stock_report_pipeline(enable_agent_reach=True, enable_evidence_notes=True)` -> 15 skills
   - order: query -> fetch -> quality -> evidence_note_writer -> consolidation

4. evidence without Agent-Reach:
   - `build_stock_report_pipeline(enable_agent_reach=False, enable_evidence_notes=True)` -> 11 skills
   - writer not present

### 7.3 PerStockReporter Config Tests

Modify or add tests:

1. no `evidence_notes` config:
   - current behavior unchanged
   - builder called with `enable_evidence_notes=False`

2. `agent_reach.enabled=True`, `evidence_notes.enabled=True`:
   - builder called with `enable_agent_reach=True, enable_evidence_notes=True`
   - pipeline input includes `enable_evidence_notes=True`, `evidence_notes_dry_run=True` by default

3. `evidence_notes.dry_run=False`, `evidence_notes.base_dir=<tmp_path>`:
   - pipeline input carries both values

4. `evidence_notes.enabled=True` but Agent-Reach disabled:
   - builder does not enable evidence notes

### 7.4 Validation Commands

Focused:

```bash
python3 -m pytest tests/reporter/test_evidence_note_skill.py \
  tests/reporter/test_pipeline_integration.py \
  tests/reporter/test_stock_reporter_agent_reach_config.py \
  tests/utils/test_evidence_note_writer.py -q
```

Broader:

```bash
python3 -m pytest tests/utils tests/reporter/test_agent_reach_quality_skill.py \
  tests/reporter/test_agent_reach_evidence_renderer.py -q
```

Manual report validation only after tests:

```bash
cd scripts
python3 run_黑芝麻智能.py --fast-test
```

Do not run `xueqiu_monitor_v2.py`.

---

## 8. Rollback Plan

This phase is easy to revert:

1. Remove `evidence_note_skill.py`.
2. Remove `enable_evidence_notes` parameter and import from `report_skills/__init__.py`.
3. Remove `stock_reporter.py` config wiring.
4. Remove tests.

Because the default pipeline remains 11 skills and Agent-Reach-only remains 14 skills, existing behavior is preserved when the new flag is off.

---

## 9. Open Questions For Review

1. Should Phase 3 allow `dry_run=False` through config, or force dry-run only until a later explicit write phase?
2. Should writer exceptions be non-blocking (`status=error`) or should they fail the pipeline when `dry_run=False`?
3. Should `evidence_note_write_plan` be a plain dict in ctx, or can it store the `EvidenceWritePlan` dataclass directly?
   - Recommendation: plain dict, easier to serialize/debug in report input dumps.
4. Should `config/stocks.json` be modified now?
   - Recommendation: no. Use tests and manually constructed reporter config first.
