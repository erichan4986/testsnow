# Annual Producer v2 Eight-Stock Gate Notes

Date: 2026-07-13
Worktree: `/Users/erichan/testsnow/.worktrees/annual-producer-v2`
HEAD: `936ba351b5f53e8d2ebd38542967d46582159da6`

## Verdict

`PASS`。八股本地缓存 gate 全部达到：

- `v1_actionable_needs_recovery_count == 0`
- `v1_adapter_use_count == 0`

没有归档或删除 v1 notes，也没有删除 adapter。Fresh report phase was
therefore allowed and completed for 中际旭创 and 复旦微电.

## Fix Summary

- Producer admits complete source units for several previously missed generic
  relations: product composition/classification, customer procurement,
  platform-to-customer conversion, HK platform release, stable margin movement,
  and cash-flow reliance on collections.
- Interleaved R&D table detection now uses seam density, so long narrative blocks
  are not rejected merely because PDF extraction inserted spaces.
- Legacy classification rejects truncated endings, numbered section labels,
  interleaved table columns, and report-header/OCR splices before exact coverage
  proof.
- Legacy fragments use the same `annual_source_tail()` boundary as producer
  SourceUnits. The parser now covers the locked `mode -> page/header -> fact`
  prefix order found in A-share annual reports.
- Package imports work both as top-level `scripts/utils` test modules and as
  `scripts.utils` / `utils` formal-report modules.

## Tests

- Annual focused suites: `313 passed`
- Downstream reporter suites: `187 passed`
- `tools/ci_grep_gates.sh`: PASS
- `git diff --check`: PASS

## Eight-Stock Gate

Temporary mirror:
`/tmp/annual-producer-v2-eight-stock-gate-20260712-run5`

| 股票 | actionable recovery | adapter use | invalid legacy | v2 selected |
|---|---:|---:|---:|---:|
| 黑芝麻智能 | 0 | 0 | 18 | 56 |
| 长春高新 | 0 | 0 | 0 | 70 |
| 三花智控 | 0 | 0 | 0 | 66 |
| 中简科技 | 0 | 0 | 18 | 66 |
| 圣邦股份 | 0 | 0 | 15 | 80 |
| 乐鑫科技 | 0 | 0 | 8 | 83 |
| 中际旭创 | 0 | 0 | 6 | 65 |
| 复旦微电 | 0 | 0 | 0 | 57 |

The invalid counts are retained diagnostics, not silently recovered material.
They cover truncated v1 excerpts, interleaved table columns, headings, and OCR
splices that should not be promoted into v2 cards.

## Fresh Reports

Reports were generated with a temporary config pointing `knowledge_base_dir` at
the verified run5 mirror, avoiding stale worktree notes.

| 股票 | Markdown | mtime | profile | quality | source | prose |
|---|---|---|---|---|---|---|
| 中际旭创 | `reports/中际旭创_20260713.md` | 2026-07-13 00:20:57 +0800 | formal_medium | PASS | PASS | PASS with repeated-theme warning |
| 复旦微电 | `reports/复旦微电_20260713.md` | 2026-07-13 00:22:18 +0800 | formal_thin_external_rich | PASS | PASS | PASS |

Coverage comments match the verified mirror:

- 中际旭创 annual `seen=74`, `selected=65`; broker memo ready with four usable
  institutions.
- 复旦微电 annual `seen=57`, `selected=57`; broker memo absent as expected.

Network/API fallbacks still emitted warnings for some Eastmoney/akshare/Baidu
endpoints, and no LLM API key was configured. Mootdx and local formal materials
were sufficient for both reports to pass the blocking quality gates.

## Output Review

The producer/recovery contract is fixed, but Chapter 4.1 remains too close to a
material inventory. Zhongji still exposes production-mode and product-catalog
noise; Fudan still exposes audit/industry passages. This is a memo/renderer
selection problem and should be handled as a separate readability task rather
than by discarding source material in the producer.

## Scope

- No scoring, target price, risk score, technical algorithm, recommendation,
  LLM prompt, or collection logic was changed.
- No Xueqiu detail page or logged-in Chrome/CDP was used.
- Runtime delta versus the previous safe-closeout state is approximately +20
  lines; no second selector or stock-specific rule was introduced.
- Batch B allowed by coverage gate: `yes` (not executed in this task).
