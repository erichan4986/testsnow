# Knowledge Persistence Slimming 6A-2 Codex Review

verdict: ok

## Locked Contract

- Add an explicit pack-shadow builder; do not change the default legacy loader.
- Reuse the existing material-pack record/coverage path for pack cards plus v1 notes.
- Classify persisted v2 notes as active, stale duplicate, stale reindexed, stale orphan,
  or stale invalid using the shared pack fingerprint.
- Use the current writer path only as the deterministic active-note tie-breaker.
- Acceptance compares producer/pack cards, active-v2 cards, selected material cards, and
  all existing v1 diagnostics. It remains read-only.
- No archive/move/delete, report generation, profile/renderer/citation changes, or 6B switch.

## Failure Gates

- Invalid pack or manifest is reported as a typed shadow error, never treated as empty.
- Missing active notes, stale notes, selected-card drift, or v1 diagnostic drift blocks 6B.
- Memo/snapshot/report/citation parity remains a downstream gate; 6A-2 cannot declare 6B
  ready until those checks are run on fresh formal-medium and formal-thin reports.

## Baseline

| Runtime file | SHA256 | Lines |
| --- | --- | ---: |
| `annual_report_material_pack.py` | `98cf4f869bf914191fb5f0f2c8997b7197d688d694e9ee2fadb363f66573e97a` | 800 |
| `periodic_report_narrative_pack_store.py` | `dd7dfd8f5be92b40906463c50e4267de2f15dcd6d64758ca4669c780e90ae00e` | 223 |
| `periodic_report_narrative_card_note_writer.py` | `3bcc4ca064edc4e8cadea2970f77a1ce08ddb9f47968a6fcd1b6c332bcc663f3` | 491 |
| `periodic_report_narrative_cards_acceptance.py` | `295ac62c8c664c7535ffbeaa0e227bd495b454dc75f3362c6b30bec5a11b47fc` | 285 |

implementation_ready: yes
