# Claude Review Round 1: Xueqiu Detail Refill

Please review the design only. Do not modify code.

Design file:

- `docs/agent_workflow/2026-07-01-xueqiu-detail-refill-design.md`

Context:

- The project generates Chinese stock research reports.
- Xueqiu detail-page fetching is high risk and must remain user-authorized, logged-in CDP only, with slow request intervals.
- The Fudan Microelectronics trial found that long posts with `...展开` can be captured in the list cache and marked `_track=featured`, but still miss detail extraction because the first detail batch / topic sampler stops too early.
- Example missed post: `https://xueqiu.com/1606930351/392467740`, a valuation comparison post on 复旦微电 vs 紫光国微 and A/H discount.

Review focus:

1. Does the one-time refill policy solve the actual failure mode without encouraging unsafe crawling?
2. Are the trigger thresholds reasonable (`min_usable_details`, drop rate, topic coverage)?
3. Is the topic bucket design too Fudan/semiconductor-specific?
4. Is the design testable without launching Chrome or visiting Xueqiu?
5. Does it preserve 4.1-4.3 formal_first source boundary and 4.4 display-only isolation?
6. Should the helper be introduced as `xueqiu_detail_selection.py`, or should this stay inside existing fetcher/high_risk scripts?

Output format:

```markdown
# Review: Xueqiu Detail Refill

verdict: ok | needs_revision | blocked

## Blockers
- [ ] ...

## Must-Fix
- [ ] ...

## Nice-To-Have
- [ ] ...

## Specific Answers
- one_time_refill_policy:
- thresholds:
- topic_buckets:
- testability:
- source_boundary:
- helper_module_boundary:

## Recommendation
Proceed / revise before implementation / do not implement
```

Constraints:

- Do not edit files.
- Do not run Xueqiu fetches.
- Do not start Chrome/CDP/Playwright.
- Local grep/read-only inspection is fine.

