# External Producer v3 Peer Group Reliability Task

1. Add RED tests for non-consecutive downgrade, continuous identity, and oversized fail-closed behavior.
2. Add one private normalization helper in `curated_external_full_body_viewpoint_claims.py` and call it before
   `validate_external_unit_selection`.
3. Run focused external producer/display tests, affected Chapter 4 tests, CI grep gates, and diff check.
4. Do not call a live LLM or generate reports during implementation.
