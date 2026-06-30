# Evidence Note Writer Phase 2 Design

> **Date**: 2026-06-12  
> **Owner**: Codex  
> **Status**: Draft → Ready For Implementation (with minor clarifications noted)

---

## 1. Goal

把经过 Source Credit Framework Phase 1 标注的 Agent-Reach `SynthesisItem`，按来源信用分层写入知识库 evidence notes，实现从“直接展示在报告里”到“先进入知识库”的转向。

具体目标：
- 高信用来源（交易所公告、公司 IR/官网、电话会纪要）作为 **事实候选（fact candidate）** 入库。
- 中等信用来源（券商研报、主流财经媒体）作为 **专业分析/二级来源（professional analysis）** 入库。
- 低信用来源（知乎、雪球、微博、小红书、未知网页）作为 **待验证 claim / hypothesis** 入库。
- 为后续 LLM wiki、claim verification、KnowledgeSynthesizer 提供带信用标签、可追溯、可去重的证据原子。

---

## 2. Non-Goals

- **不调用 LLM**：Phase 2 只做确定性 claim stub，不抽取、不验证、不总结 claims。
- **不修改 pipeline**：`build_stock_report_pipeline` 顺序不变，不把 evidence note writer 接入默认 skill chain。
- **不修改质量门**：`agent_reach_quality_skill` 的阈值、逻辑、输出不变。
- **不修改渲染器**：`AgentReachEvidenceRenderer` 输出不变；renderer 可继续按原方式展示 keep/demote 证据。
- **不修改 KnowledgeSynthesizer**：prompt、输入组装、引用逻辑不变。
- **不修改 scoring_engine / technical analyzer / report templates / 入口脚本 / `config/stocks.json`**。
- **不改动 `knowledge/` 下已有 `posts/` 目录**：新增 `evidence/` 子目录，与现有 `posts/` 并存。
- **不抓取网络、不启动浏览器、不调用 subprocess**。

---

## 3. Current Context

| Area | Current Behavior | Relevant Files |
|------|------------------|----------------|
| Agent-Reach 采集 | `agent_reach_fetch_skill` 通过 RSS/Web connector 获取记录，去重后转成 `SynthesisItem`。 | `scripts/utils/report_skills/agent_reach_skill.py` |
| Agent-Reach 质量门 | `agent_reach_quality_skill` 对 item 打分并划分为 keep / demote / discard；输出到 `ctx`。 | `scripts/utils/report_skills/agent_reach_quality_skill.py` |
| Agent-Reach 渲染 | `AgentReachEvidenceRenderer` 读取 `ctx` 中的 keep/demote items 生成 Markdown 表格。 | `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` |
| Source-Credit 标注 | `AgentReachAdapter.to_synthesis_item()` 把 `source_type`, `source_credit`, `source_domain`, `verification_status`, `credit_reasons`, `knowledge_eligible`, `report_eligible` 写入 `item.extra`。 | `scripts/utils/source_adapter.py`, `scripts/utils/source_credit.py` |
| 知识库结构 | 每只股票一个目录 `knowledge/10-Stocks/<stock_name>/`，目前只有 `posts/` 子目录存放原始帖子。 | `knowledge/10-Stocks/` |
| 主题分类 | `classify_agent_reach_topic()` 基于 title+content+quality reasons 做确定性主题分类。 | `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` |

---

## 4. Proposed Design

### 4.1 Components

| Component | Responsibility | Inputs | Outputs |
|-----------|----------------|--------|---------|
| `scripts/utils/evidence_note_writer.py` | 纯模块：把 `SynthesisItem` 列表转成 evidence note Markdown 文件。 | `stock_name`, `stock_code`, `items: List[SynthesisItem]`, `base_dir`, optional `dry_run` | 写入磁盘或返回待写入清单 |
| `EvidenceWritePlan` | dataclass：返回 dry-run / 实写计划与结果。 | `written`, `skipped_existing`, `filtered` | 可测试的写入结果 |
| module-level helpers | 构建单条 note 的 frontmatter、正文、claims stub、文件名。 | `SynthesisItem` + quality action + collected_at | Markdown 字符串 + 元数据 dict |
| `_canonical_url()` | URL 归一化，用于去重。 | `url: str` | 规范化字符串 |
| `_safe_filename()` | 生成安全、稳定、可排序的文件名。 | `published_at`, `source_type`, `domain`, `short_hash` | 文件名 |
| `_dedupe_existing()` | 扫描 `evidence/` 目录已有文件，按 canonical URL 去重。 | `evidence_dir` | 已存在 URL 集合 |
| `_classify_topics()` | 确定性主题分类。 | `SynthesisItem` | `list[str]` |

Public API:

```python
def write_evidence_notes(
    stock_name: str,
    stock_code: str,
    items: List[SynthesisItem],
    base_dir: Union[str, Path],
    collected_at: Optional[str] = None,
    dry_run: bool = False,
) -> EvidenceWritePlan:
    ...
```

`items` must already be quality-gated keep/demote items. The writer must not accept raw `agent_reach_items` before the quality gate.

### 4.2 Data Flow

```text
Agent-Reach connector raw records
  -> AgentReachAdapter.to_synthesis_item()      [附加 source-credit metadata]
  -> agent_reach_quality_skill()                [keep / demote / discard]
  -> evidence_note_writer.write_evidence_notes()
       |
       |- 过滤: knowledge_eligible=True
       |- 过滤: 来自 keep/demote（discard 丢弃）
       |- 去重: canonical URL 是否在 evidence/ 已存在
       |- 构建 frontmatter + 正文
       |- 写入: knowledge/10-Stocks/<stock>/evidence/<filename>.md
```

在 Phase 2，证据写入器**不被 pipeline 自动调用**；通过单测和手动脚本验证。

### 4.3 Evidence Note Schema

#### 4.3.1 目录与文件名

- **目录**：`knowledge/10-Stocks/<股票名>/evidence/`
- **文件名**：`YYYYMMDD-<source_type>-<source_domain>-<short_hash>.md`
  - `YYYYMMDD`：优先取 `published_at` 的日期部分；缺失则使用 `collected_at` 日期。
  - `source_type`：如 `company_official`, `social_discussion`。
  - `source_domain`：已归一化的 domain；对中文或特殊字符做 safe 替换（小写、非 alphanum/- 替换为 `-`）。为空时使用 `no-domain`。
  - `short_hash`：canonical URL 的 SHA-256 前 8 位；无 URL 时用 `source_platform + title + publish_time` 兜底。
- **稳定性**：同一 URL 在任何时间生成的 short_hash 相同；日期部分按原始发布时间固定，便于排序和回滚。

#### 4.3.2 Frontmatter

```yaml
---
stock: 黑芝麻智能
code: "02533"
source_type: company_official
source_domain: blacksesame.com
source_credit: 85
verification_status: primary_source
knowledge_eligible: true
report_eligible: true
url: https://www.blacksesame.com/zh/list_10/972.html
title: "黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证"
published_at: "2026-06-08"
collected_at: "2026-06-12T10:30:00+08:00"
topics:
  - product_progress
claims:
  - claim_id: c1
    claim_text: "黑芝麻智能华山A2000U、A2000X芯片获得ISO 26262 ASIL-D功能安全认证。"
    claim_status: fact_candidate
    extracted_from: title_and_excerpt
claim_status: fact_candidate
verified_by: []
conflicts_with: []
source_platform: AgentReach(web)
agent_reach_quality_score: 72
agent_reach_quality_action: keep
---
```

字段说明：

| Field | Type | Description |
|-------|------|-------------|
| `stock` | string | 股票名称。 |
| `code` | string | 股票代码，从调用方传入的 stock config 取得。 |
| `source_type` | string | source-credit 分类。 |
| `source_domain` | string | 归一化域名。 |
| `source_credit` | int | 0-100 信用分。 |
| `verification_status` | string | `primary_source` / `professional_analysis` / `secondary_source` / `market_opinion` / `unverified`。 |
| `knowledge_eligible` | bool | 是否可进知识库。 |
| `report_eligible` | bool | 是否可进报告证据区。 |
| `url` | string | 原始 URL。 |
| `title` | string | 标题。 |
| `published_at` | string | 发布日期（ISO 8601 日期或原始字符串）。 |
| `collected_at` | string | 采集时间（ISO 8601 datetime）。 |
| `topics` | list[str] | 确定性主题标签；优先复用 `classify_agent_reach_topic()`，导入失败或返回空时使用 writer 内置 fallback。 |
| `claims` | list[dict] | Phase 2 仅 1 条 stub：从 `title + excerpt` 合成。 |
| `claim_status` | string | 整条 evidence 的 claim 状态：`fact_candidate` / `professional_analysis` / `unverified_claim` / `hypothesis`。 |
| `verified_by` | list | 高信用来源验证链；Phase 2 固定为空。 |
| `conflicts_with` | list | 冲突证据 ID；Phase 2 固定为空。 |
| `source_platform` | string | Agent-Reach 平台标签，如 `AgentReach(web)`。 |
| `agent_reach_quality_score` | int | 质量门分数。 |
| `agent_reach_quality_action` | string | `keep` / `demote`。 |

#### 4.3.3 Claim Status Mapping（确定性）

根据 `source_credit` 决定 `claim_status`：

| source_credit | claim_status | 含义 |
|---:|---|---|
| ≥ 80 | `fact_candidate` | 事实候选，可进入后续事实基座。 |
| 55 - 79 | `professional_analysis` | 专业分析/二级来源，需交叉验证后引用。 |
| 30 - 54 | `unverified_claim` | 低信用来源提出的 claim，仅为假设。 |
| < 30 或 `knowledge_eligible=False` | 不写入 | `missing_source` 等直接丢弃。 |

Important semantics:

- `fact_candidate` means “the source is high-credit enough to become a fact candidate.” It does **not** mean the claim has been independently verified.
- `professional_analysis` means “professional/secondary analysis candidate.” It may contain conflicts of interest and still requires cross-source verification.
- `unverified_claim` means “hypothesis or low-credit claim.” It should be retained for later verification but must not be treated as fact.

#### 4.3.4 Note 正文结构

```markdown
# {title}

## 摘要
{1-2 句话摘要：title + 一句话 excerpt}

## 原始证据摘录
{content 前 800 字符，保留换行但不做 LLM 改写}

## 初步 Claims
- **[{claim_status}]** {claim_text}
  - 来源: {source_domain} ({source_type})
  - 置信: {verification_status}

## 信用评分理由
- {credit_reasons[0]}
- {credit_reasons[1]}
...

## 后续核查问题
- 该 claim 是否能在更高信用来源（交易所公告、公司 IR）中得到交叉验证？
- 是否有时间更近、来源更权威的反向或补充信息？
- 原始 URL 是否仍然可访问？
```

### 4.4 Error Handling And Fallbacks

- **无 URL 但有标题+平台**：使用 `source_platform + title + publish_time` 生成兜底 canonical key；hash 用于文件名。
- **无 URL 兜底去重限制**：title/time/platform 轻微变化可能导致重复写入；这是 Phase 2 已知限制，后续 claim graph 可再合并。
- **日期缺失**：使用 `collected_at` 日期；若也缺失，使用 `19700101-` 前缀并在文件名中体现 `unknown-date`。
- **文件名冲突**：在 short_hash 后追加 `-n`（n=1,2,…）序号，不覆盖已有文件。
- **目录不存在**：由调用方或模块自动创建 `evidence/` 目录；单元测试使用 `tmp_path` 不碰真实知识库。
- **重复 URL**：静默跳过，返回 skipped 清单；不报错。
- **dry_run=True**：不写入磁盘，返回 `EvidenceWritePlan`（待写、已存在、被过滤三类清单）。

---

## 5. Files Expected To Change

| File | Change Type | Reason |
|------|-------------|--------|
| `scripts/utils/evidence_note_writer.py` | 新建 | 核心纯模块：构建并写入 evidence notes。 |
| `tests/utils/test_evidence_note_writer.py` | 新建 | 单元测试覆盖来源分层、去重、文件名安全、dry-run。 |
| `knowledge/10-Stocks/<stock>/evidence/` | 新建目录（仅运行时） | Phase 2 写入目标；本次设计阶段不创建。 |

---

## 6. Files That Must Not Change

| File/Area | Reason |
|-----------|--------|
| `scripts/utils/report_skills/agent_reach_quality_skill.py` | 质量门阈值与逻辑不变。 |
| `scripts/utils/report_skills/agent_reach_skill.py` | Connector 行为不变。 |
| `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` | 报告渲染输出不变；仅可能作为 topic classifier 的只读依赖。 |
| `scripts/utils/knowledge_synthesizer.py` | LLM synthesis 逻辑不变。 |
| `scripts/utils/reporter/scoring_engine.py` | 评分逻辑不变。 |
| `scripts/utils/report_skills/__init__.py` | Pipeline 顺序不变。 |
| `scripts/run_黑芝麻智能.py`, `scripts/xueqiu_monitor_v2.py` | 入口脚本不变。 |
| `config/stocks.json` | 股票配置不变。 |
| `knowledge/10-Stocks/<stock>/posts/` | 现有 posts 目录不动。 |
| `reports/` | 报告输出不受影响。 |

---

## 7. Data And Reporting Constraints

- 所有 evidence note 内容必须来自实际 `SynthesisItem` 字段或 `item.extra["raw"]`，不能编造。
- 不调用 LLM、不启动浏览器、不访问外部网站。
- `collected_at` 由调用方传入（通常为 `datetime.now().isoformat()`），确保可追溯。
- 高信用来源的 `fact_candidate` 不等于“已证实事实”，仅表示“值得进入事实基座候选”。
- `source_credit`, `verification_status`, `credit_reasons`, `knowledge_eligible`, `report_eligible` 必须直接透传 `item.extra`，不得在 writer 内重新计算。
- 固定“后续核查问题”应作为模块常量，方便 Phase 3 替换为 claim-specific questions。

---

## 8. Acceptance Gates

### Tests

```bash
python3 -m pytest tests/utils/test_evidence_note_writer.py -q
```

并回归现有测试：

```bash
python3 -m pytest tests/utils/test_source_credit.py tests/utils/test_source_adapter.py tests/reporter/test_agent_reach_quality_skill.py -q
```

### Report Generation

本次设计阶段**不要求**运行报告入口，因为 evidence note writer 不接入 pipeline，也不影响 report 输出。

### Manual Review

- [ ] 高信用 item 生成 `claim_status: fact_candidate`。
- [ ] 社交 item 生成 `claim_status: unverified_claim`。
- [ ] `knowledge_eligible=False` item 不写入。
- [ ] 重复 URL 不重复写。
- [ ] 文件名安全、无路径遍历、无中文特殊字符问题。
- [ ] 未修改 quality gate、renderer、KnowledgeSynthesizer、pipeline。

---

## 9. Open Questions

| Question | Owner | Decision |
|----------|-------|----------|
| `topics` 是否直接复用 `AgentReachEvidenceRenderer.classify_agent_reach_topic()`，还是 evidence note writer 内建轻量分类器？ | 设计 | 优先复用 renderer 的纯函数以保持标签一致；同时内建最小 fallback 关键字表，避免 renderer 导入失败或未来移动导致 writer 不可用。 |
| `claim_status` 的 `professional_analysis` 是否覆盖 `broker_research` 和 `mainstream_media` 两者？ | 设计 | 是：55-79 分段统一为 `professional_analysis`，在 claims 列表中再细分。 |
| 无 URL item 是否写入？ | 设计 | 只要 `knowledge_eligible=True` 且来自 keep/demote 就写入；canonical key 使用 platform+title+time 兜底。 |
| 是否需要在 Phase 2 接入 `build_stock_report_pipeline` 作为一个可选 skill？ | 设计 | 否。Phase 2 只交付独立模块 + 单测；pipeline 接入作为 Phase 2B/Phase 3 选项。 |

---

## 10. Claude Review Log

### Round 1 Feedback

- Claude reviewed the design and returned **Ready to implement with minor clarifications**.
- Main asks:
  - clarify topic classification coupling and fallback behavior;
  - clarify `fact_candidate` / claim status semantics;
  - document no-URL dedupe limitations;
  - use `no-domain` for empty domain filenames;
  - keep writer input limited to quality-gated keep/demote items.

### Codex Response To Round 1

- Adopted all requested clarifications:
  - added public API and `EvidenceWritePlan`;
  - added writer topic fallback;
  - added explicit claim-status semantics;
  - added `no-domain` filename behavior;
  - documented no-URL dedupe limitation;
  - required source-credit fields to be passed through from `item.extra`;
  - clarified writer consumes already-gated keep/demote items only.

### Round 2 Feedback

- Not required. Round 1 had no blocker and requested only minor clarifications.

### Final Implementation Readiness

- Ready to implement as an isolated pure module plus unit tests.
