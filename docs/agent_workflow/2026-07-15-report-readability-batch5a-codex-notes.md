# Report Readability Batch 5A - Codex Notes

## Scope

Implemented the two approved display-only corrections:

- Executive summary now distinguishes a structured fundamental score from an
  incomplete high-credit fact base, instead of presenting those as a logical
  contradiction.
- Curated external narrative citations now reuse a footnote only when source
  URLs are both non-empty and exactly equal. URL-less claims retain separate
  citations. Shared citations retain every claim ID for reasoning-card lookup.

The Chapter 4 MaterialSnapshot, formal-thin offset calculation, producer,
source intake, scores, target price, risk, technical analysis, profile logic,
and LLM prompts were not changed.

## TDD Evidence

The focused RED run failed as intended before implementation:

- summary expected the clarified evidence-boundary wording but saw the old
  “not sufficiently formal material” wording;
- same-URL claims produced two citation entries rather than one;
- the formal-thin regression fixture initially exposed an import-path coupling,
  so it was made a pure renderer fixture and no production import path was
  changed.

After the minimal implementation:

- focused new behaviors: `4 passed`;
- executive-summary, curated-external narrative, and deep-analysis renderer:
  `157 passed`;
- report-quality and source-boundary suites: `107 passed`;
- `bash tools/ci_grep_gates.sh`: passed;
- `git diff --check`: clean.

## Scope Audit

The worktree already contained substantial unrelated modifications. This batch
only edited the two runtime files and three test files listed in the task, plus
this task/notes pair. No report was generated.

## Runtime Delta

This batch adds one small citation identity helper and a shared-claim lookup
loop. It stays below the task's +80 runtime stop condition. Repository-wide
`git diff --numstat` is not a valid batch delta because it includes pre-existing
uncommitted work in the same files.

## Follow-up

The remaining readability issue is Batch 5B: paragraph density/theme overlap
in external maps. It remains separate from this citation hygiene change.
