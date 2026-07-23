# Report Terminal Citations Codex Review Round 1

## Verdict

`needs_revision`

## Findings

### M1: Duplicate-heading fail-closed was not enforceable

The design said duplicate global headings could remain for existing quality checks to catch, but
`_check_global_citation_alignment()` splits only on the first heading and has no duplicate-heading error.
Assembly must raise on more than one exact global citation heading instead of silently leaving malformed
ordering in place.

### M2: Identity deduplication was incorrectly implied

The current global citation list filters by visible IDs but does not generally merge identical source
identities. This task must preserve IDs and metadata rather than add a new deduplication pass. The output is a
single global list, not a newly identity-deduplicated list.

### M3: The 4.4 duplicate-source warning would lose its input

`duplicate_4_4_citation_source` currently inspects source lines inside the 4.4 body. Once local lists are
removed, the warning disappears. Preserve the rule by resolving 4.4 inline refs against the terminal global
citation table in `report_prose_quality.py`.

### M4: Reserved executive-summary refs need an explicit relocation test

`_visible_citations_only()` retains reserved summary refs even when they are not present inside Chapter 4.
Add an assembly-level regression proving those entries remain in the moved appendix.

## Resolution

All four findings are accepted and incorporated into the design. Runtime scope expands narrowly to the prose
quality checker; the citation producer and offset owner remain unchanged.
