# Run Stock Report Entry Cleanup Batch D Implementation Notes

## Result

Batch D is complete. The unused bootstrap CLI was removed, cache loading and
offline-smoke patching were consolidated in place, and no runtime module was
added.

## Modified Files

- `scripts/run_stock_report.py`
- `tests/reporter/test_run_stock_report_entry.py`
- `tests/test_runtime_hygiene.py`
- Batch D design, self-review notes, and this implementation record

No existing user-owned broker notes, reports, plan packets, data, knowledge, or
configuration were modified.

## TDD Evidence

### Bootstrap hard cut

- RED: 8 failures for the old unknown-stock message, six accepted bootstrap
  options, and five surviving helpers.
- GREEN: 8 passed after deleting the options/helpers and changing the error to
  show the actual config path.

### Cache owner

- RED: `_load_cached_value` was absent; the two characterization tests passed.
- GREEN: 5 focused cache/entry tests passed after introducing the shared
  exact-date-first reader.
- Self-review correction: reordered the malformed/wrong-type/valid fixture so
  all three candidates are actually traversed.

### Offline smoke owner

- RED: the shared disabling helper was absent and the old fixed-signature
  `fetch_ps` patch raised `TypeError`.
- GREEN: 5 focused tests passed after using one mixed-signature-safe disabling
  owner for both data-fetch modules and charts.
- The two-pass API-key clear is covered against simulated `.env` restoration.

## Verification

- Focused entry/pipeline/runtime-hygiene suite: `104 passed`
- Full repository suite: `2876 passed, 10 skipped`
- `tools/ci_grep_gates.sh`: all gates passed
- `git diff --check`: clean
- Python compile check: passed
- Real offline smoke: exit 0; generated Markdown, HTML, and Agent-Reach audit
  only under `/tmp/testsnow_offline_smoke`; PDF remained disabled

## Runtime Ledger

Against `e2fe945`:

- `scripts/run_stock_report.py`: 61 added, 216 removed, net `-155`
- line count: 680 -> 525
- no new runtime file

The design target of at most 525 lines and at least 140 net deleted lines was
met without moving code or removing active report behavior.

## Scope And Deviations

- Independent Claude review was skipped by explicit user instruction.
- No implementation scope deviation.
- The six bootstrap-only options are intentionally incompatible after this
  user-approved hard cut. Unknown stocks now direct operators to the selected
  config path.
