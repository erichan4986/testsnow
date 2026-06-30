# Claude Review Round 1: Agent-Reach Single-Stock Source Expansion

## Review Target

Read:

```text
docs/agent_workflow/2026-06-13-agent-reach-source-expansion-design.md
```

## Objective

Review whether this is the right next step for expanding Agent-Reach information sources inside a **single-stock deep research report** without letting noisy external data affect scoring, LLM synthesis, or Xueqiu collection.

## Review Focus

Please evaluate:

1. Whether the phase split is safe enough:
   - target-stock source inventory
   - target-stock config expansion
   - target-stock smoke validation
2. Whether adding `scripts/smoke_agent_reach.py --stock <name>` is worth the implementation cost.
3. Whether the design should allow curated third-party RSS feeds for the target stock in this phase, or restrict to official company/exchange pages only.
4. Whether source inventory should include live local network discovery, and if so what stop conditions should apply.
5. Whether any hidden path could feed Agent-Reach into LLM synthesis, scoring, or final recommendations.
6. What tests are missing from the acceptance gates.
7. Whether the design still accidentally implies batch/multi-stock expansion anywhere.

## Constraints

- Do not write implementation code.
- Do not modify `config/stocks.json`.
- Do not run full reports.
- Do not access Xueqiu detail pages, Chrome/CDP, logged-in browser state, or social scraping.
- If you use local network/browser research for source inventory feasibility, only inspect official/public pages for the target stock and record what you accessed.
- Do not edit source files.

## Expected Output

Update the design file directly by appending:

```markdown
## Round 1 Feedback

### Status

Ready / Must-fix before task / Blocked

### Findings

- [Severity: ...] ...

### Recommendations

- ...

### Source Inventory Guidance

- ...

### Open Questions

- ...

## Design Delta

- ...

## Final Implementation Readiness

Ready to write task / Needs Codex revision / Blocked
```

If there are no blockers or medium+ must-fix items, say that R2 is not needed.
