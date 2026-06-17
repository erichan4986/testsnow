# Claude Task: Periodic Report LLM Analysis v2 Phase A

Date: 2026-06-16

## Goal

Implement helper-only Periodic Report LLM Analysis v2.

This replaces the keyword-heavy annual/semiannual report interpretation approach with:

```text
report text
  -> generic evidence pack
  -> bounded LLM prompt
  -> deterministic fidelity validator
  -> Markdown/JSON preview helpers
```

Do not connect this to Source Intake, report generation, evidence notes, scoring, risk, or synthesis.

## Read First

- `docs/agent_workflow/2026-06-16-periodic-report-llm-analysis-v2-design.md`
- Especially:
  - `Codex Follow-up After Round 1`
  - `Fidelity Validator`
  - `Implementation Phases`
  - `Test Plan`

## Allowed Files

You may create/modify only:

- `scripts/utils/periodic_report_evidence_pack.py`
- `scripts/utils/periodic_report_llm_analysis_v2.py`
- `tests/utils/test_periodic_report_evidence_pack.py`
- `tests/utils/test_periodic_report_llm_analysis_v2.py`
- `docs/agent_workflow/2026-06-16-periodic-report-llm-analysis-v2-claude-notes.md`

## Forbidden Files / Actions

Do not modify:

- `scripts/utils/periodic_report_extractor.py`
- `scripts/utils/periodic_report_llm_analysis.py`
- `KnowledgeSynthesizer`
- `synthesis_skills.py`
- Source Intake skills/renderers
- `evidence_note_writer.py`
- `scoring_engine.py`
- technical-analysis modules
- `config/stocks.json`
- `knowledge/`
- `reports/`
- `data/raw/`

Do not:

- access external network
- run real LLM calls
- add CLI
- run full stock reports
- start Chrome/CDP
- scrape Xueqiu details

## Required Implementation

### 1. Evidence Pack Builder

Create `scripts/utils/periodic_report_evidence_pack.py`.

Required API:

```python
def build_periodic_report_evidence_pack(text: str, *, report_type: str = "auto") -> dict:
    ...
```

Output shape:

```python
{
    "schema_version": "periodic_report_evidence_pack.v1",
    "report_type": "annual_report",
    "audit_status": "audited",
    "blocks": [
        {
            "id": "business_overview-0",
            "usage": "business_overview",
            "section": "第三节 管理层讨论与分析",
            "title": "报告期内公司从事的主要业务",
            "text": "...bounded excerpt...",
            "source_span": {"start": 420, "end": 540},
        }
    ],
}
```

Allowed usage values:

- `business_overview`
- `industry_outlook`
- `business_model`
- `segment_table`
- `segment_margin_table`
- `region_table`
- `customer_supplier_table`
- `rd_table`
- `management_strategy`
- `risk_disclosure`
- `income_statement`
- `balance_sheet`
- `cash_flow`
- `ar_aging_note`
- `inventory_note`
- `capex_cip_note`
- `goodwill_note`
- `government_grant_note`
- `restricted_assets_note`
- `related_party_transactions`
- `contingencies_litigation`
- `subsequent_events`
- `shareholder_structure`
- `pledge`
- `commitments`
- `audit_opinion`

Caps:

- max 30 blocks
- max 2,000 chars per block
- stable ids for stable spans
- no company/industry-specific product keywords such as `碳纤维`, `T1100`, `芯片`, etc.

### 2. LLM Analysis v2 Helper

Create `scripts/utils/periodic_report_llm_analysis_v2.py`.

Required APIs:

```python
SCHEMA_VERSION = "periodic_report_llm_analysis.v2"

def build_periodic_report_llm_v2_prompt(evidence_pack: dict, *, max_blocks: int = 30) -> dict:
    ...

def validate_periodic_report_llm_v2_output(raw_text: str, evidence_pack: dict) -> dict:
    ...

def summarize_periodic_report_with_llm_v2(evidence_pack: dict, client: object) -> dict:
    ...

def render_periodic_report_llm_v2_markdown(analysis: dict) -> str:
    ...
```

Returned analysis metadata:

```python
{
    "source_type": "periodic_report_analysis",
    "source_credit": 75,
    "verification_status": "professional_analysis",
    "claim_status": "professional_analysis",
    "knowledge_eligible": False,
    "report_eligible": True,
}
```

### 3. Fidelity Validator Contract

Implement:

- invalid refs reject whole analysis
- raw URLs reject whole analysis
- Markdown citation markers reject whole analysis
- `confirmed_fact`, `fact_candidate`, `核心事实`, `已证实` reject whole analysis
- confidence must be integer in `[0, 100]`
- v1 schema rejected

Numeric fidelity:

- verbatim concrete values must appear in referenced evidence after normalization
- contextual report year may appear even if not repeated in every block
- unit-normalized values should pass where straightforward, e.g. `1.2亿元` vs `12000万元`
- derived growth rate should pass only when both operands appear in referenced evidence and the result can be reproduced
- invented numbers/percentages drop offending section

Entity fidelity:

- Phase A uses strict normalized substring matching
- invented product/customer names drop offending section
- Chinese NER and fuzzy alias matching are out of scope

Failure policy:

- Invalid refs / illegal markers / URLs / schema mismatch: reject whole analysis
- Invented numbers/entities: drop offending section
- If no useful sections remain: reject whole analysis

## Required Tests

Write failing tests first.

Evidence pack tests:

- locates management discussion without company-specific terms
- extracts segment/margin table block
- extracts customer/supplier block
- extracts R&D table block
- extracts risk disclosure block
- extracts AR aging, inventory, CIP, government grants, restricted assets
- extracts related-party, litigation/contingencies, subsequent-events, shareholder/pledge, commitments blocks
- caps block length/count
- stable ids for same input
- no full report outside bounded blocks

LLM v2 tests:

- prompt contains evidence ids and usage labels
- prompt caps at 30 blocks / bounded total size
- validator accepts valid v2 JSON
- validator rejects v1 schema
- validator rejects invalid refs
- validator rejects raw URLs and citation markers
- validator rejects `confirmed_fact` / `fact_candidate` / `核心事实` / `已证实`
- validator drops invented number section
- validator drops invented percentage section
- validator allows contextual report year
- validator allows simple unit normalization (`1.2亿元` vs `12000万元`)
- validator allows derived growth rate when operands exist
- validator drops invented product/customer name
- validator rejects cross-evidence misattribution
- validator avoids completing truncated table numbers
- output metadata has `source_credit: 75`, `professional_analysis`, `knowledge_eligible: False`, `report_eligible: True`
- empty evidence pack returns empty analysis without calling fake client
- no import-time OpenAI/DeepSeek dependency

## Verification Commands

Run:

```bash
python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_llm_analysis_v2.py -q
python3 -m pytest tests/utils/test_periodic_report_extractor.py tests/utils/test_periodic_report_llm_analysis.py -q
```

Do not run real LLM or full reports.

## Notes Output

Write:

```text
docs/agent_workflow/2026-06-16-periodic-report-llm-analysis-v2-claude-notes.md
```

Include:

- files changed
- tests run and exact results
- validator behavior summary
- any deviations
- blockers

## Stop Conditions

Stop and report if:

- you need to modify forbidden files
- fidelity validation cannot be implemented without a much broader parser
- tests require network/LLM
- implementation needs Source Intake/report integration
- existing unrelated tests fail in a way that suggests broader regression
