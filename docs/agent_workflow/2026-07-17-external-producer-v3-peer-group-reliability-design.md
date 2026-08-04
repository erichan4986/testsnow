# External Producer v3 Peer Group Reliability

## Goal

Remove avoidable `selector_incomplete` retries when the LLM groups filtered peer units whose original
`source_ordinal` values are not consecutive. Target admission, keep/skip decisions, prompts, schemas, and
reader validation stay unchanged.

## Contract

- Before validation, split a peer `group_id` into standalone units only when all members are known, kept,
  from one source, number 1-3, and their ordinals are non-consecutive.
- Preserve every keep/skip decision and reason. Do not invent or discard evidence.
- Continuous groups remain grouped.
- Cross-source, oversized, unknown-ID, duplicate/missing-ID, and skip-with-group responses still fail closed.
- No new selector, retry loop, prompt change, stock rule, or card cap.

## Tests

- A filtered `[1, 3]` peer group becomes two standalone cards in one request.
- A continuous group remains one card.
- An oversized group remains invalid and exhausts the existing two attempts.
