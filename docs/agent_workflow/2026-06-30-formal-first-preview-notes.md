# Formal-First Preview Notes

Date: 2026-06-30

Status: preview tooling implemented; cached-input audit complete.

## 1. What Was Added

Added a no-LLM preview CLI:

```text
scripts/previews/formal_first_source_policy_preview.py
```

Purpose:

- read a cached `data/raw/report_input_*.json`;
- apply the existing `formal_first` canonical source policy;
- compare formal-first item count against legacy-mixed item count;
- report which Xueqiu / Zhihu social items would be excluded;
- write JSON only under `/tmp` or `/private/tmp`;
- avoid LLM calls, report generation, network, scoring, risk, and technical
  analysis changes.

## 2. Cached Input Audit

Commands were run against the latest cached report inputs for:

- 中际旭创:
  `data/raw/report_input_20260630_中际旭创.json`
- 圣邦股份:
  `data/raw/report_input_20260629_圣邦股份.json`
- 黑芝麻智能:
  `data/raw/report_input_20260630_黑芝麻智能.json`

Outputs:

- `/private/tmp/zhongji_formal_first_source_policy_preview.json`
- `/private/tmp/shengbang_formal_first_source_policy_preview.json`
- `/private/tmp/heizhima_formal_first_source_policy_preview.json`

Result summary:

| Stock | Status | Formal items | Legacy items | Excluded Xueqiu | Excluded Zhihu |
| --- | --- | ---: | ---: | ---: | ---: |
| 中际旭创 | `formal_sources_insufficient` | 0 | 39 | 15 | 24 |
| 圣邦股份 | `formal_sources_insufficient` | 0 | 30 | 15 | 15 |
| 黑芝麻智能 | `formal_sources_insufficient` | 0 | 316 | 299 | 17 |

Interpretation:

- The cached `report_input` files mostly store legacy community / Zhihu /
  Eastmoney discussion materials.
- They do not contain the live `source_intake` formal materials that made the
  recent formal report runs produce meaningful `4.1-4.3`.
- Therefore cached-input audit alone cannot prove whether `formal_first` is
  viable for production reports.

## 3. Decision

Do not enable `formal_first` globally.

Do not judge `formal_first` viability from old `report_input` caches alone.

The next meaningful validation must run the ordinary report entry with
per-stock opt-in `canonical_synthesis_source_policy=formal_first`, allowing
the existing source-intake path to collect announcements / reports / formal
materials.

## 4. Next Step

Recommended next validation:

1. Temporarily opt in one A-share pilot, preferably 中际旭创, to
   `formal_first`.
2. Run:

   ```text
   python3 scripts/run_stock_report.py --stock 中际旭创 --no-pdf
   ```

3. Check:
   - `4.1-4.3` are not fallback templates;
   - no `雪球` / `知乎` citations appear in `4.1-4.3`;
   - `4.4` still renders as display-only narrative;
   - `check_report_quality.py` result is understood;
   - `tools/ci_grep_gates.sh` still passes.

Only after 中际旭创 passes should 圣邦股份 be used as the no-4.4 A-share
control.  黑芝麻智能 should remain later because HK formal-source coverage may
need a separate source-intake path or graceful degradation thresholds.
