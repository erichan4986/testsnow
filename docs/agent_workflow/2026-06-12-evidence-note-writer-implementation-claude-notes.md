# Evidence Note Writer Phase 2 — Implementation Notes

**日期**: 2026-06-12
**任务**: 实现 Evidence Note Writer Phase 2，将 Agent-Reach source-credit 标注后的 keep/demote items 写入知识库 evidence notes。

---

## 改动文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `scripts/utils/evidence_note_writer.py` | 新增 | 核心实现模块，纯函数，不接 pipeline |
| `tests/utils/test_evidence_note_writer.py` | 新增 | 单元测试，全部使用 `tmp_path` |
| `docs/agent_workflow/2026-06-12-evidence-note-writer-implementation-claude-notes.md` | 新增 | 本实现笔记 |

---

## API 简述

```python
from scripts.utils.evidence_note_writer import write_evidence_notes, EvidenceWritePlan

plan = write_evidence_notes(
    stock_name="黑芝麻智能",
    stock_code="02533",
    items=gated_items,  # 必须是 keep/demote 的 SynthesisItem
    base_dir=Path("knowledge"),
    collected_at="2026-06-12T10:30:00+08:00",
    dry_run=False,
)

# plan.written          -> 已写入的清单
# plan.skipped_existing -> 因 canonical URL 已存在而跳过的清单
# plan.filtered         -> 因 eligibility/source-credit/discard 被过滤的清单
```

---

## Note Schema 简述

每篇 evidence note 为 Markdown，包含 YAML frontmatter 和正文：

**Frontmatter 字段**（至少）：
- `stock`, `code`
- `source_type`, `source_domain`, `source_credit`, `verification_status`, `credit_reasons`
- `knowledge_eligible`, `report_eligible`
- `url`, `canonical_url`
- `title`, `published_at`, `collected_at`
- `topics`
- `claims`（Phase 2 仅 1 条 deterministic stub）
- `claim_status`
- `verified_by`, `conflicts_with`
- `source_platform`
- `agent_reach_quality_score`, `agent_reach_quality_action`

**Claim status 映射**（由 `source_credit` 决定）：
- `>= 80` -> `fact_candidate`
- `55 - 79` -> `professional_analysis`
- `30 - 54` -> `unverified_claim`
- `< 30` -> 不写入

**正文结构**：
1. `# {title}`
2. `## 摘要`
3. `## 原始证据摘录`
4. `## 初步 Claims`
5. `## 信用评分理由`
6. `## 后续核查问题`

---

## 测试结果

```bash
python3 -m pytest tests/utils/test_evidence_note_writer.py -q
```

结果：**35 passed**

```bash
python3 -m pytest tests/utils/test_source_credit.py tests/utils/test_source_adapter.py tests/reporter/test_agent_reach_quality_skill.py -q
```

结果：**84 passed**

---

## 是否偏离设计

| 设计点 | 实现 | 是否偏离 |
|--------|------|----------|
| 独立纯模块，不接 pipeline | 是 | 否 |
| `EvidenceWritePlan` dataclass | 是 | 否 |
| 基于 canonical URL 去重 | 是 | 否 |
| 无 URL 时用 platform+title+time fallback | 是 | 否 |
| source-credit 字段直接透传 `item.extra` | 是 | 否 |
| claim status 确定性映射 | 是 | 否 |
| topics 优先复用 renderer classifier，fallback 关键字表 | 是 | 否 |
| dry_run 不写文件 | 是 | 否 |
| 文件名安全清洗，空 domain 用 `no-domain` | 是 | 否 |
| 默认不覆盖，冲突追加 `-1`, `-2` | 是 | 否 |
| 不调用 LLM / 网络 / 浏览器 / subprocess | 是 | 否 |

轻微增强：`_canonical_url()` 额外剥离了 `.html` / `.htm` / `.php` / `.aspx` / `.jsp` 等常见页面扩展名，使同一内容的带/不带扩展名 URL 能正确去重。这一增强不影响 schema 和 API。

---

## Git Status 摘要

新增/未跟踪文件：

```text
?? scripts/utils/evidence_note_writer.py
?? tests/utils/test_evidence_note_writer.py
```

未修改任何禁止文件：
- `scripts/utils/report_skills/agent_reach_quality_skill.py` ✗ 未改
- `scripts/utils/report_skills/agent_reach_skill.py` ✗ 未改
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` ✗ 未改
- `scripts/utils/knowledge_synthesizer.py` ✗ 未改
- `scripts/utils/reporter/scoring_engine.py` ✗ 未改
- `scripts/utils/report_skills/__init__.py` ✗ 未改
- `scripts/run_黑芝麻智能.py` ✗ 未改
- `scripts/xueqiu_monitor_v2.py` ✗ 未改
- `config/stocks.json` ✗ 未改
- `reports/` ✗ 未改
- `knowledge/10-Stocks/<stock>/posts/` ✗ 未改

---

## 是否触碰任何禁止文件

**否**。本次实现仅新增 `scripts/utils/evidence_note_writer.py`、`tests/utils/test_evidence_note_writer.py` 和本 notes 文件，未修改任何设计文档中列出的禁止文件或目录。

---

## 后续建议

- Phase 2B / Phase 3 可考虑在手动脚本或可选 skill 中调用 `write_evidence_notes`。
- 后续若引入 LLM claim 抽取，可替换 `_build_claim_stub()` 内部实现，但 frontmatter schema 可保持不变。
- 无 URL item 的去重稳定性仍是已知限制，后续 claim graph / 语义去重可再优化。
