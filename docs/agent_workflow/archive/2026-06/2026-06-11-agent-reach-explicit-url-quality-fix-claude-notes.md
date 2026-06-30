# Agent-Reach Explicit URL Quality Fix — Implementation Notes

## Status

Accepted

## Files Changed

1. `scripts/utils/report_skills/agent_reach_skill.py`
   - `WebConnector.run()` now marks every fetched record with:
     - `user_provided_url: True`
     - `query_type: "web_read"`

2. `scripts/utils/report_skills/agent_reach_quality_skill.py`
   - Web portal penalty logic now checks `raw_meta.get("user_provided_url")`.
   - For **explicit** user-provided URLs: apply portal penalty (-15) and add reason, but do **not** cap to `demote_threshold - 1`.
   - For **generic** Web pages (no provenance flag): keep existing behavior — cap below demote to force discard.

3. `tests/reporter/test_agent_reach_connector.py`
   - Added `test_web_connector_marks_user_provided_url` — verifies provenance fields.

4. `tests/reporter/test_agent_reach_quality_skill.py`
   - Added `test_explicit_url_data_rich_portal_not_discarded` — data-rich explicit URL with nav/footer survives as keep/demote.
   - Added `test_low_substance_explicit_url_portal_still_discarded` — low-substance explicit URL portal still gets discarded by its own low score.

## Tests Run

| Command | Result |
| --- | --- |
| `pytest tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_connector.py -q` | **83 passed** |

All existing tests still pass, including:
- `test_web_portal_page_discarded`
- `test_data_rich_web_portal_page_still_discarded`

## Smoke Test

URL: `https://www.blacksesame.com/zh/list_10/972.html`

| Step | Before Fix | After Fix |
| --- | --- | --- |
| Fetch | `ok` | `ok` |
| Quality action | `discard` | `keep` |
| Quality score | 29 | **51** |
| Renderer | empty (0 chars) | **non-empty, readable** |

The item now correctly classifies to the **产品/量产进展** theme and renders in the evidence table.

## Deviations From Task

None.

## Assessment

- Generic portal pages (no `user_provided_url`) are still capped to discard.
- Explicit user-provided URLs get the portal penalty but are allowed to survive if their raw content score is high enough.
- Low-substance explicit portal pages still discard naturally via low score after penalty.
- No domain whitelists were added.
