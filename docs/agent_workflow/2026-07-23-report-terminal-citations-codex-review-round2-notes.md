# Report Terminal Citations Codex Review Round 2

## Verdict

`ok`

## Findings And Fixes

### M5: repeated use of one ref could become a false duplicate

The terminal-table resolver must count unique citation IDs used by 4.4, not marker occurrences. One source
reused across several claims remains one source entry and must not trigger the duplicate-source warning.

### M6: no-URL fallback identity differs between local and global row formats

Legacy local rows begin directly with the source name, while global rows include a separator and bold source
label. The parser must normalize both forms before comparing source/author/title identities.

### M7: sole appendix ownership needed an assembly invariant

Only `deep_analysis` may contribute the global citation appendix. A terminal local-source marker or a global
citation heading from any other renderer must raise instead of creating two appendices or interrupted prose.

### M8: deletion scope needed an explicit ledger

The implementation must delete the local-list helper, obsolete `used` accumulators, obsolete include flags,
and the second `display_refs` return used only by local rendering. This keeps the task net-small and avoids a
disabled compatibility branch.

## Closure

All findings are incorporated into the locked design. No blockers or must-fix items remain. The design is
ready for an implementation plan and TDD implementation.
