# Claim Verification Phase 4 Design

> Date: 2026-06-13  
> Owner: Codex  
> Status: Draft for Claude review  

---

## 1. Goal

建立一个可测试、可回滚、默认 dry-run 的 claim verification 框架，用高信用 evidence notes 验证低信用社区观点。

Phase 4 解决的问题：

- 官网、公告、IR、交易所文件等高信用来源可以作为事实候选。
- 雪球/知乎等社区内容保留为低信用待验证观点。
- 低信用观点不能直接进入 `KnowledgeSynthesizer` 或报告事实基座。
- 系统需要先产出“哪些 claim 被哪些高信用来源支持/冲突/无法验证”的结构化计划。

---

## 2. Current Inputs

### 2.1 High-Credit Evidence Notes

路径：

```text
knowledge/10-Stocks/<stock>/evidence/*.md
```

来源：

- Agent-Reach official URLs
- Phase 2 `write_evidence_notes()`

典型字段：

- `source_type`
- `source_credit`
- `verification_status`
- `claims`
- `claim_status`
- `verified_by`
- `conflicts_with`
- `topics`
- `url`
- `title`

### 2.2 Legacy Social Notes

路径：

```text
knowledge/10-Stocks/<stock>/*.md
```

现状：

- 已保留。
- 已打标为雪球/知乎社区信息。
- 典型字段：
  - `source_type: social_discussion`
  - `source_platforms: ["雪球", "知乎"]`
  - `source_credit: 35`
  - `verification_status: market_opinion`
  - `confidence: 待验证观点`
  - `report_eligible: false`
  - `source_note: 来自雪球/知乎等社区内容，保留为待验证观点，不作为确认事实。`

重要限制：

- `MOC.md` 是索引文件，不应提取 claim。
- 已有正文里可能仍有 `confirmed_facts` 等旧字段名，但 Phase 4 必须按 frontmatter 的 `source_type=social_discussion` 和 `verification_status=market_opinion` 处理为低信用观点。

---

## 3. Non-Goals

本阶段不做：

- 不调用 LLM。
- 不修改 `KnowledgeSynthesizer`。
- 不修改 `SynthesisSkill._build_synthesis_items()`。
- 不把 verified claims 喂给报告。
- 不修改评分、技术分析、风险评分、报告 renderer。
- 不抓取网络、不启动浏览器、不调用 subprocess。
- 不运行 `xueqiu_monitor_v2.py`。
- 不刷新知乎，不运行 ZhihuCurator/DeepSeek curator。
- 不删除 legacy social notes。
- 不移动 legacy social notes 到新目录。
- 不在默认模式下写真实 `knowledge/`。
- 不从 legacy social note 正文里的 `confirmed_facts`、`announcements`、`inferences` 等旧字段推断事实可信度。

---

## 4. Proposed Architecture

### 4.1 New Pure Module

新增：

```text
scripts/utils/claim_verification.py
```

职责：

- 读取 evidence notes 和 legacy social notes。
- 抽取确定性 claim candidates。
- 按 source credit 分层。
- 用高信用 claims 验证低信用 claims。
- 返回 dry-run verification plan。
- 可选写回 notes，但 Phase 4 默认不写。

不负责：

- 不调用 LLM。
- 不抓取内容。
- 不渲染报告。
- 不接 pipeline。

### 4.2 Data Classes

建议 dataclass：

```python
@dataclass(frozen=True)
class ClaimCandidate:
    claim_id: str
    stock: str
    source_file: str
    source_type: str
    source_credit: int
    verification_status: str
    claim_status: str
    claim_text: str
    topics: List[str]
    url: str = ""
    title: str = ""
    source_platforms: List[str] = field(default_factory=list)
    extraction_method: str = ""
```

```python
@dataclass(frozen=True)
class ClaimVerification:
    claim_id: str
    action: str
    verified_by: List[str]
    conflicts_with: List[str]
    confidence: int
    reasons: List[str]
```

```python
@dataclass
class ClaimVerificationPlan:
    stock: str
    high_credit_claims: List[ClaimCandidate]
    low_credit_claims: List[ClaimCandidate]
    verifications: List[ClaimVerification]
    skipped_files: List[Dict[str, str]]
```

### 4.3 Public API

```python
def build_claim_verification_plan(
    stock_name: str,
    base_dir: Union[str, Path],
    dry_run: bool = True,
) -> ClaimVerificationPlan:
    pass
```

Phase 4 实现时只要求 dry-run plan。即使参数允许 `dry_run=False`，也可以先显式拒绝真实写入：

```python
if not dry_run:
    raise NotImplementedError("Phase 4 only supports dry_run=True")
```

实现必须显式保留该 guard。Phase 4 不提供真实写回能力。

### 4.4 Frontmatter Parsing

新增内部 helper：

```python
def parse_frontmatter(path: Path) -> Tuple[Dict[str, Any], str]:
    pass
```

要求：

- 先按 `---` fence 分割 frontmatter 和 body。
- 同时支持 YAML-style frontmatter 和 JSON frontmatter。
- Evidence notes 通常是 YAML。
- Legacy social notes 当前多为 JSON。
- 优先使用安全 loader；如果 PyYAML 不可用，至少要能解析 JSON frontmatter。
- malformed frontmatter 不抛出到调用方，而是进入 `skipped_files`。
- `skipped_files` entry 必须包含：

```python
{"path": "knowledge/10-Stocks/黑芝麻智能/bad-note.md", "reason": "malformed_frontmatter"}
```

其他跳过原因也必须写入 `reason`，例如 `moc_index`, `unknown_source_type`, `no_claims`。

---

## 5. Claim Extraction Rules

### 5.1 Evidence Notes

来源：

```text
knowledge/10-Stocks/<stock>/evidence/*.md
```

规则：

- 只读取 frontmatter。
- 使用 frontmatter `claims` 里的 `claim_text`。
- `claim_id` 必须稳定：
  - 推荐 `sha256(source_file + claim_text)[:12]`
- `source_credit >= 80` 进入 high-credit bucket。
- `55 <= source_credit < 80` 进入 medium/professional bucket，可作为辅助支持，但不能单独验证低信用 claim。
- `source_credit < 55` 不作为验证来源。

### 5.2 Legacy Social Notes

来源：

```text
knowledge/10-Stocks/<stock>/*.md
```

规则：

- 按文件名跳过 `MOC.md`。必须使用 basename 大小写不敏感判断：`path.name.lower() == "moc.md"`，不能依赖 frontmatter，因为 MOC 本身也可能带有 `source_type=social_discussion`。
- 只处理 `source_type=social_discussion` 或 `verification_status=market_opinion` 的文件。
- 如果 frontmatter 已有 `claims`，优先使用。
- 如果没有 `claims`，创建一条 coarse legacy stub：

```text
{title or stock/category}：该社区笔记包含待验证观点，需用高信用来源核查。
```

- `claim_status=unverified_claim`
- `extraction_method=legacy_social_stub`
- 这类 claim 只能被验证，不能反过来验证其他 claim。

说明：

Phase 4 不做 LLM claim extraction，因此 legacy social notes 的 claim 粒度会偏粗。这是刻意选择，避免把旧正文里的 `confirmed_facts` 误读成事实。

强制 guardrail：

- 对 legacy social notes，正文只可用于构造粗粒度 stub 的标题上下文。
- 不得从正文的 `confirmed_facts`、`announcements`、`inferences`、`原始数据` 等章节提取事实。
- 即使 legacy 文件名或 category 是 `公司公告`，只要 frontmatter 是 `source_type=social_discussion` 或 `verification_status=market_opinion`，就必须按低信用社区观点处理。

---

## 6. Verification Rules

### 6.1 Trust Direction

只允许高信用或中高信用来源向低信用来源提供支持：

```text
high-credit evidence -> verifies/supports social claim
medium professional evidence -> supports but does not fully verify social claim
social claim -> never verifies other claims
```

### 6.2 Deterministic Matching

Phase 4 使用确定性弱匹配，不用 LLM。

匹配信号：

1. same stock
2. overlapping topics
3. key term overlap from claim text/title
4. shared product/customer/company terms
5. date proximity if available

建议 key term extraction：

- 中文连续词暂不做复杂分词。
- 用关键词表 + 正则提取：
  - 产品：`A2000U`, `A2000X`, `A1000`, `芯片`, `SoC`, `自动驾驶`, `ADAS`, `NOA`
  - 客户/合作：`理想`, `东风`, `如祺`, `上实`, `合作`, `定点`, `订单`, `交付`
  - 认证/公告：`ASIL-D`, `ISO 26262`, `认证`, `获奖`, `公告`
  - 财务：`营收`, `收入`, `亏损`, `毛利率`, `同比`, `环比`

匹配强度：

| Match Type | Conditions | Result |
|---|---|---|
| strong high-credit match | high-credit source, same stock, same/compatible topic, at least one specific key term such as product/customer/certification | `verified` |
| weak high-credit match | high-credit source but only weak/generic terms or missing context | `needs_review` |
| medium-credit match | 55-79 source, same/compatible topic and specific key term | `supported` |
| no useful match | no source with topic/key-term overlap | `unverified` |

Generic single terms that are insufficient by themselves:

- `芯片`
- `公告`
- `合作`
- `收入`
- `增长`
- `投资者`

`needs_review` downgrade conditions:

- only one generic term matches and no specific product/customer/certification term
- matched sources span multiple incompatible topics
- claim appears time-sensitive but neither side has usable date context
- multiple high-credit matches suggest different interpretations

### 6.3 Actions

`ClaimVerification.action` 可取：

| action | Meaning |
|---|---|
| `verified` | 高信用来源明确支持低信用 claim。 |
| `supported` | 中信用/专业来源或弱匹配支持，但不足以完全验证。 |
| `conflicted` | 高信用来源与低信用 claim 存在明显冲突。 |
| `unverified` | 找不到可用验证来源。 |
| `needs_review` | 匹配信号混杂，需要人工/LLM 后续判断。 |

Phase 4 默认不写回文件，只返回 plan。

Confidence bands:

| action | confidence |
|---|---:|
| `verified` | 70-100 |
| `supported` | 40-69 |
| `unverified` | 0-39 |
| `needs_review` | 0 |
| `conflicted` | 0 |

Medium-credit sources must never produce `verified`; their confidence is capped at 69.

---

## 7. Output Plan Shape

`build_claim_verification_plan()` 返回 dataclass；也应提供 helper 转 plain dict：

```python
def claim_verification_plan_to_dict(plan: ClaimVerificationPlan) -> Dict[str, Any]:
    pass
```

plain dict 结构：

```python
{
    "stock": "黑芝麻智能",
    "high_credit_claims": [
        {"claim_id": "official_a2000u_asil", "source_credit": 85, "claim_text": "A2000U/A2000X 获得 ASIL-D 认证"}
    ],
    "low_credit_claims": [
        {"claim_id": "social_a2000u_safety", "source_credit": 35, "claim_text": "社区认为 A2000U 安全认证是量产催化"}
    ],
    "verifications": [
        {
            "claim_id": "social_a2000u_safety",
            "action": "verified",
            "verified_by": ["official_a2000u_asil"],
            "conflicts_with": [],
            "confidence": 78,
            "reasons": ["topic overlap: product_progress", "key terms: A2000U, ASIL-D"]
        }
    ],
    "skipped_files": [{"path": "knowledge/10-Stocks/黑芝麻智能/MOC.md", "reason": "moc_index"}]
}
```

---

## 8. Optional Future Writeback

Phase 4 只设计 dry-run plan。

后续 Phase 4B 或 Phase 5 才考虑写回：

- evidence note frontmatter:
  - `verified_by`
  - `conflicts_with`
  - `claim_status`
- legacy social note frontmatter:
  - `verified_by`
  - `conflicts_with`
  - `claim_verification_status`

写回必须单独设计，且默认 dry-run。

---

## 9. Files Expected To Change In Implementation

| File | Change Type | Reason |
|---|---|---|
| `scripts/utils/claim_verification.py` | Create | Pure claim reading and verification module. |
| `tests/utils/test_claim_verification.py` | Create | Unit tests for readers, claim extraction, trust direction, verification actions. |
| `docs/agent_workflow/2026-06-13-claim-verification-implementation-claude-notes.md` | Create | Implementation notes after coding. |

No pipeline wiring in Phase 4.

---

## 10. Files That Must Not Change

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/report_skills/evidence_note_skill.py`
- `scripts/utils/evidence_note_writer.py`
- `scripts/utils/source_credit.py`
- `scripts/utils/source_adapter.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/run_黑芝麻智能.py`
- `scripts/xueqiu_monitor_v2.py`
- `config/stocks.json`
- `reports/**`
- `knowledge/10-Stocks/**` in default tests

---

## 11. Tests Required

Create `tests/utils/test_claim_verification.py`.

Required cases:

1. parse evidence note frontmatter with YAML-style frontmatter from `write_evidence_notes`.
2. parse legacy social note JSON frontmatter.
3. parse JSON frontmatter without PyYAML available if the test can monkeypatch the module.
4. skip `MOC.md` / `moc.md` by filename, regardless of frontmatter.
5. social notes with no `claims` create `legacy_social_stub` claims.
6. legacy social note body fields like `confirmed_facts` and `announcements` are ignored for fact extraction.
7. legacy social note with `category: 公司公告` still enters low-credit bucket when frontmatter says `social_discussion`.
8. high-credit official claim enters high-credit bucket.
9. social claim enters low-credit bucket.
10. legacy social notes never enter high-credit bucket even if they have a `claims` list.
11. social claim never verifies another social claim.
12. high-credit claim with shared topic and specific key terms verifies social claim.
13. single generic term match downgrades to `needs_review`, not `verified`.
14. medium professional claim can produce `supported` but not `verified`; confidence <= 69.
15. unrelated claim remains `unverified`.
16. malformed frontmatter goes into `skipped_files` with `reason`, no exception escapes.
17. plan converts to plain dict.
18. `dry_run=False` raises `NotImplementedError`.
19. tests use `tmp_path`, never write real `knowledge/`.

Suggested focused command:

```bash
python3 -m pytest tests/utils/test_claim_verification.py -q
```

Broader safety command:

```bash
python3 -m pytest tests/utils/test_claim_verification.py \
  tests/utils/test_evidence_note_writer.py \
  tests/reporter/test_evidence_note_skill.py -q
```

Do not run `xueqiu_monitor_v2.py`.

---

## 12. Open Questions For Review

1. Should medium-credit broker/media claims be allowed to produce `supported`, or should Phase 4 restrict all validation to source_credit >= 80?
2. Should legacy social notes without explicit claims become coarse stubs, or should Phase 4 skip them until LLM claim extraction exists?
3. Should `MOC.md` be entirely ignored even though it now carries social metadata?
   - Recommendation: yes, always ignore MOC as index notes.
4. Should Phase 4 include any writeback function at all?
   - Recommendation: no writeback in Phase 4; dry-run plan only.
