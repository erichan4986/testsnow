# Source Credit Framework Design

## Goal

Add a deterministic source-credit layer that scores evidence by source trustworthiness before any Agent-Reach item is promoted into the knowledge base, report, or future `KnowledgeSynthesizer` context.

This phase does **not** write evidence notes, does **not** change report conclusions, and does **not** feed Agent-Reach data into LLM synthesis.

## Background

The current Agent-Reach flow can fetch official Black Sesame web pages and render them in the report, but its quality gate mixes several concerns:

- source trust (`official`, URL present, author present)
- content relevance
- evidence density
- social engagement
- portal/noise penalties

For knowledge-base-first research, source trust must be independent from content quality. A company announcement can have high source credit even if Jina returns navigation chrome. A Zhihu or Xueqiu post can contain useful hypotheses but should not be treated as a hard fact unless verified by higher-credit sources.

## Scope

### In Scope

1. Add a deterministic `source_credit` module.
2. Score source credibility from URL, platform, metadata, and user-provided status.
3. Add source-credit fields to Agent-Reach adapted `SynthesisItem.extra`.
4. Unit-test official/company/announcement/social/unknown source classes.
5. Keep all functions pure and testable without network, browser, subprocess, or LLM.

### Out of Scope

- Writing knowledge-base evidence notes.
- Cross-verifying low-credit claims against high-credit claims.
- Modifying `KnowledgeSynthesizer` prompts or input assembly.
- Changing report score/risk/technical logic.
- Changing Agent-Reach connector behavior.
- Changing Agent-Reach renderer layout.
- Calling any LLM.

## Proposed Files

### Create: `scripts/utils/source_credit.py`

Responsibilities:

- Define source-credit categories.
- Detect source type from `SynthesisItem` or raw record.
- Assign numeric `source_credit` and stable reasons.
- Decide default `report_eligible` and `knowledge_eligible`.

Suggested public API:

```python
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SourceCreditResult:
    source_type: str
    source_domain: str
    source_credit: int
    verification_status: str
    credit_reasons: List[str]
    knowledge_eligible: bool
    report_eligible: bool


def score_source_credit(
    *,
    url: str = "",
    source_platform: str = "",
    author: str = "",
    raw: Optional[Dict[str, Any]] = None,
) -> SourceCreditResult:
    ...
```

### Modify: `scripts/utils/source_adapter.py`

Only `AgentReachAdapter.to_synthesis_item()` should call `score_source_credit()` and attach the result into `extra`:

```python
extra = {
    "raw": raw,
    "source_domain": result.source_domain,
    "source_credit": result.source_credit,
    "source_type": result.source_type,
    "verification_status": result.verification_status,
    "credit_reasons": result.credit_reasons,
    "knowledge_eligible": result.knowledge_eligible,
    "report_eligible": result.report_eligible,
}
```

Do not change `SynthesisItem` fields or constructor signature.

### Create/Modify Tests

- Create: `tests/utils/test_source_credit.py`
- Modify: `tests/utils/test_source_adapter.py`

## Source-Credit Policy

Use deterministic source classes. Initial values can be conservative:

| Source Type | Detection | Credit | Verification Status | Knowledge | Report |
|---|---|---:|---|---|---|
| `exchange_announcement` | `hkexnews.hk`, `sse.com.cn`, `szse.cn`, `cninfo.com.cn` | 98 | `primary_source` | true | true |
| `company_official` | known company domain, explicit `is_official`, `user_provided_url` on official/company domain | 85 | `primary_source` | true | true |
| `company_ir` | URL contains `/ir`, `/investor`, `/announcement`, or raw `source_type=ir` | 88 | `primary_source` | true | true |
| `broker_research` | platform/metadata indicates 研报, research, broker, institution | 72 | `professional_analysis` | true | true |
| `mainstream_media` | known finance/news domains, RSS news | 65 | `secondary_source` | true | true |
| `industry_media` | known industry/RSS/blog media, no official status | 55 | `secondary_source` | true | false |
| `social_discussion` | Zhihu, Xueqiu, Twitter/X, Reddit, Bilibili, Weibo, Xiaohongshu | 35 | `market_opinion` | true | false |
| `unknown_web` | URL present but no known class | 30 | `unverified` | true | false |
| `missing_source` | no URL/platform/metadata | 10 | `unverified` | false | false |

Notes:

- Portal/navigation noise should **not** lower source credit. That belongs to content-quality scoring.
- Explicit user-provided URL is a small positive signal only when the domain is official/known. It should not turn random blogs into high-credit sources.
- Social sources can be useful knowledge-base inputs, but they should default to `report_eligible=False` until verified.
- `knowledge_eligible=True` means “eligible to enter the knowledge base as a candidate evidence or hypothesis.” It does **not** mean verified fact.
- `report_eligible=True` means “eligible for future report evidence sections.” It does **not** mean eligible to influence final conclusions or LLM synthesis in this phase.
- Broker research is professional analysis with potential conflicts of interest. It can be retained and shown as analysis evidence, but future claim verification should not treat it as a primary fact source.

## Detection Priority

Implement source detection in this exact order and cover conflicts with tests:

1. `missing_source`
   - Only when URL, platform, and useful raw metadata are all missing.
2. `exchange_announcement`
   - Regulatory/exchange domains override every other signal.
3. `company_ir`
   - Raw `source_type="ir"` or official/company domain with IR/announcement path.
4. `company_official`
   - Known company official domain.
   - Raw official metadata only counts as official when paired with a known official/company domain.
5. `broker_research`
   - Platform or metadata indicates 研报/research/broker/institution.
6. `mainstream_media`
   - Known mainstream finance/news domains or platform labels.
7. `industry_media`
   - Known industry/RSS/blog media domains or labels.
8. `social_discussion`
   - Social platform labels or social domains.
9. `unknown_web`
   - Parseable URL with no known source class.

Conflict examples:

- `source_platform="知乎"` + `url="https://www.blacksesame.com/..."` -> `company_official`, because official URL outranks platform label.
- `raw={"source_type": "ir"}` + unknown URL -> `company_ir`, because IR metadata is explicit.
- `raw={"is_official": True}` + unknown URL -> `unknown_web`, because unknown official flags are not enough without a trusted domain.
- empty URL + `source_platform="知乎"` -> `social_discussion`, because platform label is sufficient for social candidate evidence.

## URL Normalization

`score_source_credit()` must normalize URL before domain checks:

- Accept URLs with or without scheme.
- Lowercase host.
- Remove leading `www.`.
- Ignore query strings and fragments.
- Keep both normalized domain and path for detection.
- Return normalized domain in `SourceCreditResult.source_domain`.

Examples:

- `https://www.blacksesame.com/zh/list_10/972.html?utm=abc` -> domain `blacksesame.com`
- `http://blacksesame.com.cn/news` -> domain `blacksesame.com.cn`
- malformed or non-URL text -> empty domain and falls through to metadata/platform rules.

## Domain Rules For Phase 1

Start narrow and transparent:

### Exchange / regulatory

- `hkexnews.hk`
- `sse.com.cn`
- `szse.cn`
- `cninfo.com.cn`

### Company official for current validated case

- `blacksesame.com`
- `blacksesame.com.cn` if encountered

### Broker research signals

- `source_platform` contains `研报`
- raw `source_type` is `research`, `broker_research`, or `report`
- raw contains `institution`

### Mainstream media initial domains

- `eastmoney.com`
- `finance.sina.com.cn`
- `stcn.com`
- `yicai.com`
- `caixin.com`

### Industry media initial domains

- `36kr.com`
- `jiemian.com`
- `leiphone.com`

### Social platform aliases/domains

- Zhihu: `知乎`, `zhihu`, `zhihu.com`
- Xueqiu: `雪球`, `xueqiu`, `xueqiu.com`
- Twitter/X: `twitter`, `x.com`
- Reddit: `reddit`, `reddit.com`
- Bilibili: `bilibili`, `bilibili.com`
- Weibo: `微博`, `weibo`, `weibo.com`
- Xiaohongshu: `小红书`, `xiaohongshu`, `xhslink.com`

The module should be easy to extend later through constants, not hard-coded branching scattered across functions.

## Data Flow

1. Agent-Reach connector returns raw records.
2. `AgentReachAdapter.to_synthesis_item()` adapts raw record to `SynthesisItem`.
3. The adapter computes source credit and stores it in `item.extra`.
4. Existing Agent-Reach quality gate and renderer continue to work unchanged.
5. Future evidence note writer will use `item.extra["source_credit"]` and related fields.

## Tests

Required cases:

1. `https://www.blacksesame.com/zh/list_10/972.html` -> `company_official`, credit >= 80, `primary_source`, report eligible.
2. `https://www.hkexnews.hk/...` -> `exchange_announcement`, credit >= 95.
3. URL with `/ir/` or raw `source_type="ir"` -> `company_ir`.
4. Zhihu URL or `source_platform="知乎"` -> `social_discussion`, credit around 35, knowledge eligible, report not eligible.
5. Xueqiu URL or `source_platform="雪球"` -> `social_discussion`.
6. Unknown URL -> `unknown_web`, report not eligible.
7. Missing URL/platform -> `missing_source`, not knowledge eligible.
8. Raw `user_provided_url=True` on Black Sesame official URL should include a reason such as `用户显式提供官网URL`.
9. `AgentReachAdapter.to_synthesis_item()` includes all source-credit fields in `extra`.
10. Existing `adapt_all(agent_reach_items=[...])` contract tests still pass.
11. Conflict: social platform label + official domain -> official domain wins.
12. Conflict: raw `is_official=True` + unknown URL -> stays `unknown_web`.
13. Empty URL + `source_platform="知乎"` -> `social_discussion`.
14. URL normalization covers `http`, `https`, `www`, `.cn`, query strings, and fragments.
15. `source_domain` is populated for parseable URLs and empty for missing/malformed URLs.

## Non-Goals And Guardrails

- Do not replace `agent_reach_quality_skill.py`.
- Do not change quality thresholds.
- Do not change renderer output.
- Do not change `KnowledgeSynthesizer`.
- Do not write files to `knowledge/`.
- Do not introduce network or LLM calls.

## Open Questions For Review

1. Should source credit live in `scripts/utils/source_credit.py` or inside `source_adapter.py`?
   - Recommendation: separate module to keep it reusable for Zhihu/Xueqiu/announcements later.
2. Should `report_eligible` mean “can appear in raw evidence section” or “can influence narrative synthesis”?
   - Recommendation: in Phase 1 it means “eligible for future evidence notes and report evidence sections,” not synthesis.
3. Should company domain allowlist be global or stock-config driven?
   - Recommendation: start with constants; later move to config when multiple official domains are needed.

## Acceptance Criteria

- Source credit is deterministic and covered by unit tests.
- Agent-Reach adapted items carry source-credit metadata.
- No report output, LLM synthesis, scoring, technical analysis, or connector behavior changes.
- Focused tests pass:

```bash
python3 -m pytest tests/utils/test_source_credit.py tests/utils/test_source_adapter.py tests/reporter/test_agent_reach_quality_skill.py -q
```

## Codex Review Response

Claude Round 1 returned `Ready with changes`. Changes adopted:

1. Added explicit detection priority and conflict examples.
2. Clarified that `knowledge_eligible=True` means candidate evidence/hypothesis, not verified fact.
3. Clarified that `report_eligible=True` does not mean synthesis eligibility.
4. Added URL normalization requirements and `source_domain` to `SourceCreditResult`.
5. Added constant-based domain/signal lists for exchange, company, broker, mainstream media, industry media, and social aliases.
6. Added conflict and normalization tests to required coverage.
7. Clarified broker research conflict-of-interest semantics.

Rejected changes: none.
