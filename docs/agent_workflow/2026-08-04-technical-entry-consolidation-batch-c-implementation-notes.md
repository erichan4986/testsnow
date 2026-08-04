# Technical Entry Consolidation Batch C Implementation Notes

## Outcome

Implemented the user-approved direct path after two Codex design reviews. The
independent Claude design review was explicitly skipped by the user.

The three stock-specific entry paths remain in place. Their data acquisition
and stock-specific side effects remain wrapper-owned, while diagnostics,
`TechnicalRenderer` context projection, Markdown writing, and completion
logging now have one owner in `scripts/utils/technical_report_entry.py`.

## Modified Files

Runtime:

- `scripts/utils/technical_report_entry.py` (new)
- `scripts/run_中简科技技术分析_真实数据.py`
- `scripts/run_乐鑫科技技术分析_真实数据.py`
- `scripts/run_澜起科技技术分析_真实数据.py`

Tests:

- `tests/utils/test_technical_report_entry.py` (new)
- `tests/test_technical_analysis_entries.py` (new)

Workflow documents:

- `2026-08-04-technical-entry-consolidation-batch-c-design.md`
- `2026-08-04-technical-entry-consolidation-batch-c-claude-review-round1.md`
- this file

## TDD Evidence

1. Shared owner RED: 5 failures because `technical_report_entry` did not exist.
2. Shared owner GREEN: 5 passed.
3. Thin-wrapper RED: 8 failures against the duplicated entries, including the
   pre-existing broken direct `sections.*` import identity.
4. Thin-wrapper GREEN: 8 passed.
5. Self-review import-root RED: 3 failures requiring idempotent insertion of
   the sole `scripts/utils` root.
6. Final new contracts: 13 passed.

## Preserved Contracts

- Zhongjian still reads
  `data/raw/zhongjian_300777_daily_20260608.csv` and calls the analyzer directly.
- Espressif still calls `collect("688018", market=1, days=250,
  adjustment="qfq")`.
- Montage still calls `collect("688008", market=1, days=250,
  adjustment="qfq")`, fetches the same raw daily/weekly data, and writes both
  dated CSV files.
- All entries retain `main()`, their filenames, full renderer mode, report
  filename contract, and full-report logging.
- Optional target, fund-flow, and concept material is forwarded without
  changing technical calculations.
- Terminal market diagnostics now consistently consume the current
  `market_resonance` projection.

## Runtime Ledger

Line-count baseline for the three entries: 588.

Final runtime:

| File | Lines |
|---|---:|
| Zhongjian entry | 46 |
| Espressif entry | 48 |
| Montage entry | 68 |
| Shared owner | 143 |
| Total | 305 |

Net runtime deletion by line count: **283 lines**. The shared owner exceeded
its 135-line soft target by 8 lines, but the final total is 65 lines below the
370-line target and the deletion is 103 lines beyond the 180-line hard gate.
No diagnostics or readability were removed to satisfy the soft target.

## Verification

- Focused technical suite: `115 passed, 1 skipped`.
- Full repository suite: `2867 passed, 10 skipped`.
- `tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.
- `py_compile` for the shared owner and three entries: passed.

No live market-data entry was run, no network was accessed, and no report,
data, knowledge, configuration, prompt, scoring, risk, or technical-algorithm
file was modified. Existing broker-note, old-report, and plan-packet worktree
changes were left untouched.

## Blocker / Warning / Deviation

- Blocker: none.
- Warning: local acceptance generated the Zhongjian report successfully, while
  Espressif and Montage could not obtain akshare qfq data in the current proxy
  environment. The same explicit qfq acquisition contract existed before this
  refactor; mootdx raw was available but was not substituted because silently
  mixing adjusted and raw prices would change technical semantics. The Batch C
  acceptance verdict is `PASS_WITH_WARNINGS`; provider resilience remains a
  separate data-acquisition task.
- Deviation: independent Claude review was skipped at user direction; shared
  owner is 8 lines above its soft target, while the total hard budget passes by
  a wide margin.
