# Source Intake Orchestration Deduplication: Codex Self-Review Round 2

## Verdict

`needs_revision` before the edits recorded below; `ok` after revision.

## Findings and fixes

### M1: the standard-entry environment change was understated

The first revision described environment support as preserved compatibility,
but the current query-level read happens after conditional pipeline assembly
and therefore cannot enable the standard reporter path. Moving the decision to
the compiler deliberately repairs that archived contract. The goal and
enablement sections now identify this as the task's only behaviour correction.

### M2: ambient environment could invalidate an offline smoke

Once the standard entry honours the variable, a developer shell containing
`ENABLE_AGENT_REACH=1` could trigger connectors during smoke verification. The
design now requires the smoke process to remove that variable explicitly. The
reporter environment test must mock pipeline construction and execution.

### M3: environment API remained underspecified

The design now locks the compiler parameter to
`Mapping[str, str] | None = None`, with `None` treated as an empty mapping. It
also preserves the exact legacy true values instead of broadening parsing.

### M4: standard-entry behaviour lacked a direct test owner

The TDD plan and matrix now assign a mocked, no-network reporter test for the
environment-only path.

## Final consistency check

- One enablement decision owner: yes.
- Existing disabled context shape preserved: yes.
- Connector and quality logic excluded: yes.
- Partial-timeout and merge ordering contracts covered: yes.
- Deterministic compiler tests and no-network acceptance covered: yes.
- Runtime target is non-binding and hard stop forbids growth: yes.

## Remaining blocker / must-fix

None. The design is ready for independent read-only review.
