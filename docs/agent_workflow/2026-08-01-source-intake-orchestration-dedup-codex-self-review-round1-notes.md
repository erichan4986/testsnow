# Source Intake Orchestration Deduplication: Codex Self-Review Round 1

## Verdict

`needs_revision` before the edits recorded below; all findings are now closed.

## Findings and fixes

### M1: compiler tests could inherit the process environment

The first draft did not define the default for the new environment mapping.
Defaulting to `os.environ` inside the compiler would make existing direct unit
tests dependent on the shell. The design now requires an empty default;
`PerStockReporter` explicitly forwards `os.environ`.

### M2: pipeline/context equality wording implied an output-shape change

The current disabled plan omits `enable_agent_reach` from context. The design
now preserves that omission while requiring both pipeline inclusion and the
enabled context key to derive from the same compiled decision.

### M3: direct query-skill environment compatibility was ambiguous

The design now states that direct query-skill callers must supply context. The
supported reporter entry retains environment compatibility by compiling the
environment before pipeline construction. This removes the second owner rather
than disguising it.

### M4: deterministic-default coverage was missing

The TDD plan and requirement-test matrix now include a test proving that a
compiler call with no environment mapping does not read process state.

### N1: test deletion scope was too open

The design now plans no test-module deletion and permits individual deletion
only with exact surviving-contract mapping.

## Remaining blocker / must-fix

None after revision.
