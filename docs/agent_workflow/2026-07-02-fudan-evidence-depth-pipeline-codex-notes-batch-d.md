# Evidence Depth Pipeline Batch D Notes

## Scope

Batch D implements deterministic fund-flow material handling for 4.3.

It does not change scoring formulas, technical indicator algorithms, Xueqiu/Chrome/CDP collection, or social/display-only boundaries.

## Changes

- `scripts/utils/fundflow_material.py`
  - New deterministic `fundflow_material_pack.v1` builder.
  - Computes recent-day summary:
    - `main_net_total`
    - `super_large_net_total`
    - `small_net_total`
    - `price_change_total_pct`
    - objective `signal`.
  - Renders compact prompt appendix for 4.3.
- `scripts/utils/report_skills/technical_skills.py`
  - Bridges `technical["fund_flow"]` into `stock_raw["fundflow"]` when no dedicated fundflow exists.
  - Supports Baidu PAE and Eastmoney-style field names.
- `scripts/utils/source_adapter.py`
  - Makes `FundFlowAdapter` accept net-flow fields and split-order fields.
- `scripts/utils/report_skills/synthesis_skills.py`
  - Builds `fundflow_material_pack` before synthesis.
  - Removes raw fundflow items from synthesis input when the deterministic pack exists.
  - Passes the pack to `KnowledgeSynthesizer`.
- `scripts/utils/knowledge_synthesizer.py`
  - Adds the deterministic fund-flow appendix only to `funding_sentiment`.
  - Does not expose it to 4.1/4.2/4.4.
- `scripts/utils/report_skills/assembly_skills.py`
  - Persists `reports/<stock>_<date>_fundflow_material.json` when rows exist.
- `scripts/utils/report_quality.py`
  - Loads the fundflow sidecar.
  - Adds `fundflow_claim_without_fundflow_pack` for 4.3 directional/amount fund-flow claims without deterministic support.
  - The gate intentionally does not fail generic “需跟踪主力资金净流向” wording.

## Tests

Commands run:

```bash
python3 -m pytest tests/utils/test_fundflow_material.py tests/reporter/test_technical_skills_contract.py tests/utils/test_source_adapter.py tests/reporter/test_synthesis_skills.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_report_quality.py -q
# 169 passed

PYTHONPATH=/Users/erichan/testsnow/scripts:/Users/erichan/testsnow/scripts/utils python3 -m pytest tests/reporter/test_assembly_skills.py::test_assembly_writes_fundflow_material_sidecar tests/reporter/test_assembly_skills.py::test_assembly_writes_industry_relevance_manifest_sidecar tests/reporter/test_assembly_skills.py::test_assembly_writes_peer_comparison_material_sidecar -q
# 3 passed

bash tools/ci_grep_gates.sh
# all gates passed

git diff --check
# clean

python3 scripts/check_report_quality.py reports/复旦微电_20260702.md
# PASS
```

## Notes

- The current `reports/复旦微电_20260702.md` was generated before Batch D. It passes quality after the gate was narrowed to directional/amount fund-flow claims only, but it does not yet contain a new fundflow sidecar.
- A fresh report run is needed to verify whether live Baidu/PAE or fallback fundflow data is available for 复旦微电 and whether 4.3 becomes more useful.
- If live fundflow acquisition returns empty, 4.3 should still degrade cleanly rather than inventing funds-flow data.
