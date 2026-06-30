# Periodic Report Intake Unification Design

Date: 2026-06-22

Status: Draft for Claude review

## 1. 背景

过去几轮年报能力是按风险边界逐步拆出来的，因此现在看起来像五条路径：

- `periodic_report_fulltext_analysis`：全文 LLM 摘要，给最终报告参考。
- `Ground Truth`：确定性财务数字块，用来约束全文 LLM 不编数字。
- `periodic_report_narrative_evidence_cards`：年报文字证据卡，可沉淀到 Knowledge。
- `periodic_report_structured_facts` / `filing_facts`：结构化财务事实，writer-only，暂未作为主线。
- `hk_periodic_report_fetcher` / HK evidence-pack：港股年报获取与版式适配，仍是另案。

这些拆分是为了安全：先防止全文 LLM 直接进入 Knowledge、评分、风险评分，再逐步把可追溯内容沉淀下来。但产品和维护层面不应该让后续 agent 以为这是五套互不相关的系统。

本设计的目标是统一概念和入口模型，先不做大代码重构。

## 2. 设计目标

1. 把年报能力统一成一个清晰心智模型：`Annual Report Intake`。
2. 明确哪些输出是 report material，哪些输出可以进 Knowledge。
3. 保留现有安全不变量：全文 LLM 摘要不直接进入 Knowledge、评分、风险评分。
4. 降低后续 Claude/Codex 修改成本：不用每次重读多份历史设计才能理解边界。
5. 为未来轻量 facade 或 hash anchoring 留接口，但本轮不要求实现。

## 3. 非目标

本设计不要求立刻：

- 重命名现有文件；
- 移动 helper 文件；
- 改 pipeline 顺序；
- 改 KnowledgeSynthesizer prompt；
- 改 scoring/risk/technical 逻辑；
- 接入 HK evidence-pack；
- 把 filing facts 接入 scoring；
- 新增运行产物、manifest、trace 或 run card。

## 4. 统一心智模型

建议把当前能力收敛为三层。

```text
年报缓存 / Jina 文本 / HKEX-CNINFO PDF 文本
        ↓
Annual Report Intake
  - evidence blocks
  - required metrics / financial metrics
  - Ground Truth numbers
  - narrative cards
  - filing facts
        ↓
        ├─ Annual Report Material
        │    - fulltext LLM summary
        │    - Ground Truth-constrained prompt
        │    - narrative cards as report context
        │    - Source Intake display material
        │
        └─ Annual Report Knowledge
             - narrative evidence cards
             - validated filing facts later
             - derived/risk facts only after invalidation/scoring design
```

### 4.1 Annual Report Intake

`Annual Report Intake` 是年报材料的入口层。它只负责读取、切块、抽取、归一化和打标签，不负责评分、不负责最终投资结论。

现有模块映射：

| 现有模块 | 在统一模型中的角色 |
| --- | --- |
| `hk_periodic_report_fetcher.py` | 港股年报获取/缓存 helper，属于 intake source adapter |
| `periodic_report_evidence_pack.py` | 年报原文切块，输出 evidence blocks |
| `periodic_report_required_metrics.py` | 经营指标确定性抽取 |
| `periodic_report_required_financial_metrics.py` | 财务/风险指标确定性抽取 |
| Ground Truth numbers | 不是独立 helper；由 `periodic_report_required_metrics.py` 和 `periodic_report_required_financial_metrics.py` 的确定性输出拼装，用于约束全文 LLM 数字 |
| `periodic_report_product_project_evidence.py` | 产品、项目、客户、研发进展的确定性证据抽取与 backfill 支撑 |
| `periodic_report_narrative_evidence_cards.py` | 年报文字证据卡抽取 |
| `periodic_report_structured_facts.py` | 结构化 filing facts/risk signals 原型 |
| `periodic_report_extractor.py` | 早期/独立 A 股年报结构化抽取 helper；可作对照和迁移参考，不是当前主 pipeline 入口 |

Cross-cutting helper:

| 现有模块 | 角色 |
| --- | --- |
| `periodic_report_validation.py` | LLM 输出、引用、数字 fidelity 的共享校验工具，不单独属于 intake/material/knowledge 任一层 |
| `periodic_reporter.py` | 旧式周期复盘 writer，会直接写 `knowledge/30-Periodics/`；保留为兼容/相邻入口，不作为新的 Annual Report Intake 主入口 |

### 4.2 Annual Report Material

`Annual Report Material` 是报告写作材料层。它可以影响最终报告表达，但不能直接变成核心事实、Knowledge 或评分输入。

现有模块映射：

| 现有模块 | Material 角色 |
| --- | --- |
| `periodic_report_fulltext_llm_analysis.py` | 生成全文 LLM 摘要；Ground Truth 约束数字；仍是 material-layer |
| `periodic_report_fulltext_intake_skill.py` | 把 fulltext preview item 放进 `ctx["periodic_report_fulltext_items"]` |
| `source_intake_evidence_renderer.py` | 独立展示全文摘要实验路径 |
| `synthesis_skills.py` | 可生成 `synthesis_display`，但 canonical `synthesis` / `synthesis_text` 保持 baseline |

Material 层允许：

- 被最终报告 LLM 参考；
- 在 Source Intake 或 display renderer 中展示；
- 用 Ground Truth 约束数字表述；
- 帮助用户阅读年报核心内容。

Material 层禁止：

- 直接进入 `confirmed_fact` / `fact_candidate`；
- 直接写入 Knowledge；
- 直接进入 scoring/risk scoring；
- 通过 `synthesis_text` 间接影响风险评分；
- 让 evidence refs 指向非 `fulltext-*` 的块。

### 4.3 Annual Report Knowledge

`Annual Report Knowledge` 是可沉淀层，只保存短小、可追溯、可复用的年报证据。

当前允许：

- `periodic_report_narrative_evidence` cards 写入 `knowledge/10-Stocks/<stock>/periodic_narrative_cards/`。
- `periodic_report_filing_fact` note writer 已存在于 writer-only 阶段；只允许显式调用、只读 `filing_facts[]`、不接 pipeline、不进入 scoring/risk。

现有 Knowledge 写入 helper：

| 现有模块 | Knowledge 角色 |
| --- | --- |
| `periodic_report_narrative_card_note_writer.py` | 将 `periodic_report_narrative_evidence` 短证据卡写入 `periodic_narrative_cards/` |
| `periodic_report_filing_fact_note_writer.py` | Phase B writer-only；将已锚定的 `periodic_report_filing_fact` 写入 `filing_facts/`，保持 `knowledge_eligible=False` 与 `knowledge_fact_status=filing_fact` |

未来可允许：

- 带 `schema_version`、`input_refs`、可失效机制的 derived facts；
- 设计完成后的 filing risk signals。

仍然禁止：

- `periodic_report_fulltext_analysis` 全文 LLM 摘要写入 Knowledge；
- 大段全文写入 Knowledge；
- 未结构化的完整财务表写入 Knowledge；
- LLM judgment 以事实身份持久化。

## 5. Source Type Policy

后续不要用“年报内容”这个模糊概念判断能否进入 Knowledge/评分，而要按 source_type。

| Source type | 当前信用 | Knowledge | Report material | Scoring/risk | 说明 |
| --- | --- | --- | --- | --- | --- |
| `periodic_report_fulltext_analysis` | 75 | no | yes | no | LLM/rule 混合摘要，只作材料 |
| `periodic_report_narrative_evidence` | 75 | yes | yes | no | 原文短摘录卡，可沉淀 |
| `periodic_report_filing_fact` | 75/独立 confidence | writer-only / future yes | yes | future gated | 结构化事实，需证据锚定 |
| `periodic_report_derived_fact` | future policy | no until invalidation | yes | future gated | 派生计算，先不持久化 |
| `periodic_report_filing_risk_signal` | future policy | no until design | yes | future gated | 需单独 scoring 设计 |

关键规则：

- 不要为了让 filing fact 进 Knowledge 而把 `source_credit` 粗暴提高到 80+。
- filing fact 应用独立字段表达可信度，如 `knowledge_fact_status=filing_fact`、`confidence`、`evidence_refs`。
- material-layer 的 fulltext source type 永远不因 Ground Truth 增强而升级。

## 6. 建议的轻量整理方式

短期不重构文件，只做文档和入口索引。

### Phase 0: 文档统一

本设计文件即 Phase 0。

补充到 `docs/agent_workflow/context_index.md`：

- 当前年报系统主线叫 `Annual Report Intake`；
- 各 helper 属于 intake/material/knowledge 哪一层；
- 常用验证命令；
- 禁止触碰的边界。

### Phase 1: 可选 facade，不改变行为

如果后续仍觉得入口分散，可新增一个薄门面：

`scripts/utils/periodic_report_intake.py`

只做 orchestration，不承载业务规则：

```python
def build_periodic_report_intake_pack(...):
    evidence_pack = build_periodic_report_evidence_pack(raw_text)
    required_metrics = build_required_periodic_report_metrics(...)
    financial_metrics = build_required_financial_risk_metrics(...)
    narrative_cards = build_periodic_report_narrative_evidence_cards(...)
    structured_facts = build_periodic_report_structured_fact_pack(...)
    return {
        "schema_version": "periodic_report_intake_pack.v1",
        "evidence_pack": evidence_pack,
        "required_metrics": required_metrics,
        "required_financial_metrics": financial_metrics,
        "narrative_cards": narrative_cards,
        "structured_facts": structured_facts,
    }
```

限制：

- 不接 pipeline；
- 不写 Knowledge；
- 不调用 LLM；
- 不访问网络；
- 不改变现有 helper 输出。

### Phase 2: Evidence hash anchoring

给 narrative cards 和 filing facts 增加不可逆证据锚：

- `source_excerpt_hash = sha256(normalized_source_excerpt)`
- `source_block_hash = sha256(normalized_block_text)` where available
- 可选 `filing_hash = sha1(raw_text)` 用于整份年报版本标识

用途：

- 验证 Knowledge card 是否仍对应原始年报段落；
- 去重；
- 后续更新/失效；
- 作为“可追溯但不泄露全文”的审计锚。

Implementation status: implemented for narrative evidence cards, narrative card notes, structured filing facts, and filing fact notes on 2026-06-22. Existing writer inputs without hash fields are still accepted; writers compute `source_excerpt_hash` as a compatibility fallback and preserve `source_block_hash` when present.

### Phase 3: HK evidence-pack adapter

HK 不应作为单独主线，而应作为 `Annual Report Intake` 的 source adapter / block extractor 扩展。

目标：

- 港股年报同样输出 evidence blocks；
- HK-specific labels 映射到统一 metrics/facts；
- 不改变 A 股 helper 行为。

## 7. Failure Modes

### 7.1 概念混淆导致 fulltext 进 Knowledge

表现：

- `periodic_report_fulltext_analysis` 被写入 Knowledge；
- `confirmed_fact` / `fact_candidate` 中出现 fulltext source；
- scoring/risk 读取 fulltext item。

已有防线：

- `ci_grep_gates.sh`;
- `test_fulltext_material_isolation.py`;
- `evidence_note_writer` source-type guard;
- Source Intake renderer 强制 professional_analysis。

### 7.2 narrative cards 变脏

表现：

- 会计政策模板进入 Knowledge；
- 目录/勾选框/表格碎片进入 cards；
- LLM 判断语气进入 cards。

防线：

- `test_periodic_report_narrative_evidence_cards.py`;
- 多公司 preview acceptance；
- future evidence hash 能辅助追踪来源。

### 7.3 filing facts 被当成高信用事实但证据不稳

表现：

- 没有 source block/excerpt 也写入 Knowledge；
- derived facts 缺 input_refs；
- 旧错误 facts 长期污染 claim verification。

防线/要求：

- unanchored facts must skip；
- Phase B writer-only；
- derived facts 不持久化，直到有 invalidation 设计；
- future schema_version + input_refs + hash anchoring。

### 7.4 HK adapter 破坏 A 股抽取

表现：

- 为支持繁体/HK 报表，A 股 required metrics 抽取回归；
- bare “收入” 在 A 股/HK 混乱匹配。

防线：

- HK usage 使用 `hk_*` block usages；
- A 股/HK fixture 分开；
- A 股 non-regression tests。

### 7.5 Knowledge 证据锚悬空

表现：

- 已写入 Knowledge 的 narrative card 或 filing fact 仍存在，但原始年报缓存重切块后找不到对应 source block；
- source excerpt 被截断或归一化规则变化，导致后续 agent 无法确认该 note 是否仍能回溯到原文；
- 旧 filing fact 的 input refs 指向已失效的块，claim verification 可能读到过期材料。

防线/要求：

- Phase 2 `source_excerpt_hash` / `source_block_hash` 是这个 failure mode 的小切片修复；
- filing facts 后续进入 derived/input_refs 前，需要 schema_version 与可失效策略；
- note writer 不应写入无法锚定的事实或大段全文。

## 8. Test Strategy

短期文档统一不需要新测试。

如果实现 Phase 1 facade，需要：

- facade 输出 schema 稳定；
- facade 调用现有 helpers，不改变子 helper 输出；
- 缺缓存/空 raw text 返回 diagnostics，不抛异常；
- no LLM / no network / no write side effects。

如果实现 Phase 2 hash anchoring，需要：

- 相同 excerpt hash 稳定；
- 空白/换行差异归一化后 hash 稳定；
- 不同原文 hash 不同；
- Knowledge writer 保留 hash 字段；
- preview 中显示 hash 可选，不污染报告正文。

## 9. 推荐下一步

推荐顺序：

1. 把这份设计交给 Claude 做只读 review。
2. 若无 blocker，把 `context_index.md` 补一小节 `Annual Report Intake Current Map`。
3. 暂不做 `periodic_report_intake.py` facade，除非后续仍出现“我不知道读哪个 helper”的维护问题。
4. `source_excerpt_hash/source_block_hash` 已作为小切片落地；下一步若继续代码化，应优先验证真实 Knowledge note 刷新和旧 note 迁移策略。

说明：hash anchoring 不是替换 roadmap 里的 Bucket 3/filing facts 方向，而是为 Bucket 3 的 `input_refs`、`schema_version`、失效策略先补一个最小前置切片。

## 10. Claude Review Prompt

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做只读设计审查。

请阅读：
- docs/agent_workflow/2026-06-22-periodic-report-intake-unification-design.md
- docs/agent_workflow/2026-06-20-vibe-trading-inspired-safety-and-periodic-report-roadmap.md
- docs/agent_workflow/context_index.md

目标：
审查“Annual Report Intake 三层统一模型”是否能减少当前年报系统概念分裂，同时不破坏已落地的 fulltext material-layer 隔离、narrative cards Knowledge 写入、filing facts writer-only 边界。

禁止事项：
- 不要修改源码、测试、配置、prompt。
- 不要运行真实 LLM。
- 不要访问外部网络。
- 不要写 data/raw、reports、knowledge。
- 不要启动 Chrome/CDP。

唯一允许的写操作：
- 作为上述禁止事项的唯一例外，只允许向本设计文档末尾 `## 11. Claude Review Log` 追加 review 结论；其余文件一律只读。

重点检查：
1. 逐行对照 §4.1/§4.2 的 helper 映射表，检查三层模型是否覆盖现有 helper：fulltext LLM、Ground Truth、narrative cards、filing facts、HK evidence-pack。
2. 是否有 source_type policy 冲突，尤其是 fulltext 永不进 Knowledge 与 narrative cards 可进 Knowledge 的边界。
3. 是否建议现在新增 `periodic_report_intake.py` facade，还是先只补 context/status 文档。
4. hash anchoring 是否适合作为下一桶代码任务。
5. 是否遗漏 failure mode 或测试门。

完成后把反馈追加到本文末尾 `## 11. Claude Review Log`，格式：
- Status: Ready / Needs fixes
- Blockers
- Must-fix
- Nice-to-have
- 是否建议进入下一步
- 是否需要二轮审查（R2）
```

## 11. Claude Review Log

### Round 1 — 2026-06-22 (Claude Code, read-only design review)

**Status: Needs fixes** （仅文档层面修正；不涉及代码 blocker，已落地的安全边界全部完好）

**审查方法**：逐行对照 §4.1/§4.2 映射表与仓库实际 helper；核实 source_type policy 与代码常量；核实 fulltext 隔离防线。所有引用文件与三份文档均已只读通读。

**已核实通过的安全不变量（未被本设计破坏）**

- fulltext material-layer 隔离完好：`tools/ci_grep_gates.sh` 的 denylist（`scoring_engine.py` / `risk_renderer.py` / `knowledge_skills.py`）与 grep 模式（`periodic_report_fulltext|synthesis_display`）与 §7.1 描述一致。
- source_type 常量与 §5 表一致：`periodic_report_fulltext_analysis`、`periodic_report_narrative_evidence`（`SOURCE_TYPE` 常量）、`periodic_report_filing_fact` 均存在；narrative cards 与 filing facts 的 `source_credit` 均为 `75`，与"不靠抬 credit 进 Knowledge"的规则自洽。
- filing facts writer-only 边界完好：`periodic_report_structured_facts.py` 中 `knowledge_eligible=False`、Phase A helper-only；`scoring_engine.py` / `risk_renderer.py` 未引用 filing facts，符合 §5 "future gated"。
- narrative cards Knowledge 写入路径真实存在：`periodic_report_narrative_card_note_writer.py` 写入 `knowledge/10-Stocks/<stock>/periodic_narrative_cards/`，`knowledge_persisted=True`，与 §4.3 一致。

**Blockers**

- 无。三层模型方向正确，且未触碰任何已落地的隔离/边界。推荐的下一步（补 context_index、暂缓 facade）可以进行。

**Must-fix（文档完整性，关系到本文档"单一权威地图"的目标）**

1. §4.1/§4.2 映射表不完整——至少 5 个现存 `periodic_report_*` helper 未被收录，未来 agent 看到这些文件时仍无法从本文档判断其归属，正是本设计想消除的"概念分裂"：
   - `periodic_report_product_project_evidence.py`（产品/项目/客户证据抽取）——属 Intake 层，且已被 `context_index.md` 列为关键实现文件，遗漏最明显。
   - `periodic_report_narrative_card_note_writer.py` 与 `periodic_report_filing_fact_note_writer.py`——这两个 **Knowledge 层 note-writer 正是 §4.3 所治理的"持久化机制"本身**，却没有出现在任何映射表里。§4.3 只描述"什么能进 Knowledge"，没有把执行写入的 helper 落到模型里。
   - `periodic_report_extractor.py`（standalone A 股 extractor）、`periodic_report_validation.py`（LLM 输出校验工具）——需各给一个角色或显式标注"cross-cutting / 不属三层"。
   建议：在 §4.1 增 product_project_evidence、extractor 行；在 §4.3 增两个 note-writer 行（标注 writer-only）；validation 作为 cross-cutting 工具单列一句。

**Nice-to-have**

1. §4.3 把 filing facts notes 写成"未来可允许"，但 `periodic_report_filing_fact_note_writer.py`（Phase B, writer-only）**今日已存在**，与 §5 表"writer-only / future yes"口径不一致。建议 §4.3 改为"writer 已存在（Phase B, helper-only, 未接 pipeline）"，避免低估现状。
2. hash anchoring（Phase 2）与 roadmap 的 Recommended Order 不完全一致：roadmap 把 Bucket 3/3A/4 排在前面，本设计把 hash anchoring 提为"下一桶代码"。二者不冲突，但建议在 §9 注明 hash anchoring 实际是 Bucket 3 `derived_facts` 所需 `input_refs`/`schema_version` 工作的前置小切片，而非替换 roadmap 顺序。
3. §7 可补一条 failure mode：note-writer 持久化的 card/fact 其 source block 在年报改版后已不存在（悬空证据锚）——这正是 Phase 2 hash anchoring 要解决的问题，可与 §7.2 交叉引用，使"为什么先做 hash"在 failure-mode 层面也成立。

**逐项回答重点检查**

1. 覆盖性：fulltext LLM(§4.2)/Ground Truth(§4.1 已补映射)/narrative cards(§4.1+§4.3)/filing facts(§4.1+§4.3)/HK evidence-pack(§4.1 source adapter) 五条主线均覆盖；但表外仍有 5 个 helper 未落位（见 Must-fix 1）。
2. source_type policy 无冲突：fulltext 永不进 Knowledge 与 narrative cards 可进 Knowledge 的边界由 source_type 而非 credit 决定，代码与文档一致。
3. facade：**同意暂不新增** `periodic_report_intake.py`，先补 context/status 文档。Phase 1 facade 为纯 orchestration，5 个被调 helper 均已存在，但当前无真实维护痛点，过早引入仅增加一层。
4. hash anchoring：**适合**作为下一桶代码——小、可测（§8 已列稳定性/归一化用例）、直接增强 Knowledge 可追溯性，并为 Bucket 3 的 input_refs 铺路。见 Nice-to-have 2 的排序说明。
5. 失败模式/测试门：§7/§8 覆盖扎实；建议补"悬空证据锚"failure mode（Nice-to-have 3）与表外 helper 的角色说明。

**是否建议进入下一步**：是。安全审查干净，可立即推进 §9 第 2 步（补 `context_index.md` 的 Annual Report Intake 小节）；建议在补 context_index 的同一改动里顺手修 Must-fix 1（两处同为"helper→层"映射，天然一起做）。

**是否需要二轮审查（R2）**：建议轻量 R2，仅复核 Must-fix 1 的映射表补全是否完整覆盖 11 个 `periodic_report_*` helper，无需重跑全量审查。若映射补全为纯加行且 self-consistent，可由作者自检替代 R2。

### Round 2 — 2026-06-22 (Claude Code, lightweight read-only re-review)

**Status: Needs fixes**（Round 1 的 Must-fix 1 尚未落实，文档映射缺口仍然存在）

**审查范围**：仅复核 §4.1/§4.2/§4.3 映射表是否补齐 Round 1 缺口；交叉核对仓库实际 `periodic_report_*` helper 清单与 `context_index.md`。未重跑全量审查。

**核心结论：映射缺口未修复**

- §4.1/§4.2/§4.3 三张表与 Round 1 状态逐字一致，未新增任何行。Round 1 列出的 5 个 helper 仍全部缺失：
  - `periodic_report_product_project_evidence.py`（Intake 层）
  - `periodic_report_narrative_card_note_writer.py` / `periodic_report_filing_fact_note_writer.py`（Knowledge 写入器，§4.3 治理对象本身）
  - `periodic_report_extractor.py`（standalone A 股 extractor）
  - `periodic_report_validation.py`（LLM 输出校验，cross-cutting）
- 仓库实际 helper 已逐一确认存在（`ls scripts/utils/periodic_report*.py` + `periodic_reporter.py`）。

**R2 新增发现（R1 未捕获）**

- `periodic_reporter.py`（class `PeriodicReporter`）是第 6 个未映射 helper，且性质更重：它经 `ObsidianWriter` **直接生成并写出**季报/半年报/年报笔记。一个会写 Obsidian/Knowledge 的入口完全不在三层模型里，比纯抽取 helper 的遗漏风险更高——后续 agent 无法判断它与 narrative-card note-writer 的边界关系。建议补表时单列一行，明确它是「独立 legacy/并行 reporter，不属本设计三层主线」或显式纳入治理。

**context_index 是否足够让后续 agent 找到正确文件**

- 部分足够、整体不足。`context_index.md` 的「Periodic Report Fulltext Status」小节已列出 product_project_evidence、structured_facts、fulltext_intake_skill、source_intake renderer、required(_financial)_metrics、hk_fetcher，对 fulltext 主线够用。
- 但仍**找不到**：narrative_evidence_cards.py、narrative_card_note_writer.py、filing_fact_note_writer.py、extractor.py、validation.py、periodic_reporter.py。且 §9 第 2 步推荐的 `Annual Report Intake Current Map` 小节**尚未创建**。因此一个要改 narrative-card 写入或 filing-fact note 的 agent，目前从 context_index 无法定位到正确文件。

**是否还有遗漏 helper**：有。除 R1 的 5 个外，新增 `periodic_reporter.py`（共 6 个未映射）。补全后三层模型应覆盖全部现存 helper（含明确标注「不属三层」者）。

**是否建议进入下一步 hash anchoring 设计/实现**：可以并行推进，但**不应替代文档修复**。理由：(1) hash anchoring 的安全前提（fulltext 隔离、narrative cards/filing facts 边界）在 R1 已逐项核实完好，未被破坏，技术上无 blocker；(2) 但 hash anchoring 的直接受益方正是 narrative_card_note_writer / filing_fact_note_writer 两个**当前未被文档收录**的写入器——若不先把它们落进 §4.3 与 context_index，实现 hash 时仍会遇到「我不知道该改哪个 writer」的同一痛点。建议：先以一次纯加行改动补齐 §4.1/§4.2/§4.3 + context_index 的 `Annual Report Intake` 小节（Must-fix，零代码风险），随即即可开 hash anchoring 设计。两者无依赖冲突，但顺序上文档应先行半步。

### Author Follow-up — 2026-06-22 (Codex)

R2 结论与当前文件内容不一致：当前 §4.1/§4.3 已包含 Round 1 要求补齐的 `periodic_report_product_project_evidence.py`、`periodic_report_narrative_card_note_writer.py`、`periodic_report_filing_fact_note_writer.py`、`periodic_report_extractor.py`、`periodic_report_validation.py`，并补充了 R2 新指出的 `periodic_reporter.py`。`context_index.md` 也已新增 `Annual Report Intake Current Map`，覆盖 intake/material/knowledge/cross-cutting 四层文件。

采纳 R2 中有效的新信息：`periodic_reporter.py` 不是普通 helper，而是旧式周期复盘 writer，会直接写 `knowledge/30-Periodics/`；本文件已显式标注为 legacy writer / adjacent entry，不纳入新的 Annual Report Intake 主线。
