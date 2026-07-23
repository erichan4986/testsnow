# Chapter 4.4 Retirement and External v4 D1 Report Acceptance

日期：2026-07-23
Verdict：PASS

## Scope

Combined acceptance for:

1. formal-medium generic Chapter 4.4 retirement;
2. External Producer v4 Batch D1 dead synthesis-bridge deletion.

## Fresh Reports

| Stock | Profile | Markdown | Size | mtime |
|---|---|---|---:|---|
| 中际旭创 | `formal_medium` | `reports/中际旭创_20260723.md` | 20,828 B | 2026-07-23 10:40:22 |
| 复旦微电 | `formal_thin_external_rich` | `reports/复旦微电_20260723.md` | 15,325 B | 2026-07-23 10:41:53 |

Both reports are newer than `deep_analysis_material_snapshot.py` (10:21:26) and `deep_analysis_renderer.py` (10:22:49).

Both report commands exited 0. The first sandboxed attempt demonstrated expected network degradation; the final acceptance uses fresh network-enabled reruns that restored market and peer data.

## Chapter 4 Contracts

- 中际旭创 contains 4.1, 4.2 and 4.3 only under `formal_medium`.
- 复旦微电 contains 4.1, 4.2 and 4.3 only under `formal_thin_external_rich`.
- Neither report contains the retired `4.4 上行 / 下行条件与股价推演` heading, its three labels, or its fixed conditional prose.
- Existing annual, broker and external sections remain populated.
- Source-boundary checks pass for both reports.

## Quality Gates

| Gate | 中际旭创 | 复旦微电 |
|---|---|---|
| `check_report_quality.py` | PASS | PASS |
| `check_report_source_boundary.py` | PASS | PASS |
| `check_report_prose_quality.py` | PASS with warnings | PASS with warnings |

The remaining prose warnings concern existing cross-section theme overlap and strong wording. They do not involve Chapter 4.4, missing citations, source leakage or the deleted v4 bridge.

## Code Gates

- Focused v4 + Chapter 4 contracts: `164 passed`.
- Full offline suite: `2576 passed, 16 skipped`.
- CI grep gates: PASS.
- `git diff --check`: clean.

## Blocker / Warning / Deviation

- Blocker: none.
- Warning: Zhihu and optional LLM keys were unavailable; deterministic/local material paths were used as designed.
- Deviation: none.
