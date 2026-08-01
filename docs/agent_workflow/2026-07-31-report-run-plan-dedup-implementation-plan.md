# Report Run Plan Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compile report feature configuration once, slim `PerStockReporter` to a single-stock execution facade, and move legacy batch iteration into `xueqiu_monitor_v2.py` without changing report behavior or pipeline order.

**Architecture:** A pure `ReportRunPlan` compiler becomes the sole owner of Agent-Reach and Source Intake precedence. `PerStockReporter` combines invariant stock inputs with the compiled context and runs the existing pipeline. The legacy monitor owns its explicit stock loop and no longer asks the facade to generate a hard-coded summary.

**Tech Stack:** Python 3, frozen dataclasses, pathlib, pytest, unittest.mock, existing `SkillPipeline` and report skills.

---

## File Map

- Create `scripts/utils/report_run_plan.py`: pure configuration compiler; no I/O and no pipeline imports.
- Modify `scripts/utils/stock_reporter.py`: single-stock facade only.
- Modify `scripts/xueqiu_monitor_v2.py`: legacy batch iteration helper and existing PDF handoff.
- Create `tests/reporter/test_report_run_plan.py`: exact compiler contract matrix.
- Create `tests/reporter/test_stock_reporter_run_plan.py`: facade integration and failure behavior.
- Create `tests/reporter/test_xueqiu_monitor_report_batch.py`: no-network batch ownership test.
- Delete `tests/reporter/test_stock_reporter_agent_reach_config.py` only after its 18 contracts pass under the new owners.
- Delete `tests/reporter/test_stock_reporter_source_intake_config.py` only after its 27 contracts pass under the new owners.
- Keep `scripts/utils/report_skills/__init__.py` read-only; its current skill order remains authoritative.
- Keep `tests/reporter/test_pipeline_integration.py` and `tests/reporter/test_stock_reporter_charts.py` unchanged.
- Create `docs/agent_workflow/2026-07-31-report-run-plan-dedup-implementation-notes.md`: requirement/test mapping, line accounting, and deviations.

## Global Guardrails

- Do not change synthesis, rendering, scoring, target price, technical analysis, risk, citations, collection, LLM prompts, or report structure.
- Do not access the network, run Chrome/CDP, crawl Xueqiu details, or generate a formal report.
- Preserve all pre-existing dirty-worktree changes. Do not reformat unrelated files.
- Do not commit unless the user explicitly requests it.
- Stop if the refactor requires a runtime file outside the three listed above, changes pipeline skill order, changes any expected configuration payload, or misses either final line target.
- Post-clean targets from the locked design: runtime `<= 67,056` lines and tests `<= 62,645` lines.

### Task 1: Add the core pure run-plan compiler

**Files:**
- Create: `scripts/utils/report_run_plan.py`
- Create: `tests/reporter/test_report_run_plan.py`

- [ ] **Step 1: Write the failing core-gate test**

Create the test module with repository import setup and a parameterized core matrix:

```python
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from utils.report_run_plan import ReportRunPlan, compile_report_run_plan


@pytest.mark.parametrize(
    (
        "agent_cfg",
        "source_cfg",
        "global_agent",
        "expected_agent",
        "expected_source",
        "can_run",
    ),
    [
        ({}, {}, False, False, False, False),
        ({"enabled": True}, {}, False, True, False, True),
        ({"enabled": False}, {}, True, True, False, True),
        ({}, {"enabled": True}, False, False, True, True),
        ({"enabled": False}, {"enabled": False}, False, False, False, False),
    ],
)
def test_compile_report_run_plan_core_gates(
    tmp_path,
    agent_cfg,
    source_cfg,
    global_agent,
    expected_agent,
    expected_source,
    can_run,
):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config=agent_cfg,
        source_intake_config=source_cfg,
        global_agent_reach_enabled=global_agent,
    )

    assert isinstance(plan, ReportRunPlan)
    assert plan.pipeline_kwargs == {
        "enable_agent_reach": expected_agent,
        "enable_evidence_notes": False,
        "enable_claim_risk_signals": False,
        "enable_source_intake": expected_source,
    }
    assert plan.context_values == {"enable_claim_risk_signals": False}
    assert plan.can_run_without_posts is can_run
```

- [ ] **Step 2: Run the test and confirm RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_report_run_plan.py::test_compile_report_run_plan_core_gates \
  -q -p no:cacheprovider
```

Expected: collection fails because `utils.report_run_plan` does not exist.

- [ ] **Step 3: Add the frozen model and core compiler**

Create `scripts/utils/report_run_plan.py` with the public model, a defensive mapping helper, and the four always-present pipeline flags:

```python
"""Pure compilation of stock report runtime configuration."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ReportRunPlan:
    pipeline_kwargs: dict[str, Any]
    context_values: dict[str, Any]
    can_run_without_posts: bool


def _mapping(config: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = config.get(key, {})
    return value if isinstance(value, Mapping) else {}


def compile_report_run_plan(
    *,
    repo_root: Path,
    agent_reach_config: Mapping[str, Any],
    source_intake_config: Mapping[str, Any],
    global_agent_reach_enabled: bool = False,
    global_periodic_fulltext_enabled: bool = False,
) -> ReportRunPlan:
    del repo_root, global_periodic_fulltext_enabled
    agent_cfg = agent_reach_config if isinstance(agent_reach_config, Mapping) else {}
    source_cfg = source_intake_config if isinstance(source_intake_config, Mapping) else {}
    agent_enabled = bool(global_agent_reach_enabled or agent_cfg.get("enabled", False))
    source_enabled = bool(source_cfg.get("enabled", False))
    pipeline_kwargs = {
        "enable_agent_reach": agent_enabled,
        "enable_evidence_notes": False,
        "enable_claim_risk_signals": False,
        "enable_source_intake": source_enabled,
    }
    return ReportRunPlan(
        pipeline_kwargs=pipeline_kwargs,
        context_values={"enable_claim_risk_signals": False},
        can_run_without_posts=agent_enabled or source_enabled,
    )
```

- [ ] **Step 4: Run the core test and confirm GREEN**

Run the command from Step 2. Expected: `5 passed`.

### Task 2: Complete the configuration contract

**Files:**
- Modify: `scripts/utils/report_run_plan.py`
- Modify: `tests/reporter/test_report_run_plan.py`

- [ ] **Step 1: Add failing exact-contract cases**

Add focused tests with exact dictionary equality for these payloads:

```python
def test_agent_reach_context_preserves_urls_alias_and_optional_lists(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={
            "enabled": True,
            "urls": ["https://example.test/a"],
            "rss_feeds": ["https://example.test/feed.xml"],
            "rss_filter_terms": ["光模块"],
            "official_domains": ["example.test"],
        },
        source_intake_config={},
    )
    assert plan.context_values == {
        "enable_claim_risk_signals": False,
        "enable_agent_reach": True,
        "agent_reach_urls": ["https://example.test/a"],
        "agent_reach_rss_feeds": ["https://example.test/feed.xml"],
        "agent_reach_rss_filter_terms": ["光模块"],
        "agent_reach_official_domains": ["example.test"],
    }


@pytest.mark.parametrize(
    ("child", "global_default", "expected"),
    [({}, False, False), ({}, True, True), ({"enabled": True}, False, True), ({"enabled": False}, True, False)],
)
def test_periodic_fulltext_nested_value_overrides_global(tmp_path, child, global_default, expected):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={"enabled": True, "periodic_report_fulltext": child},
        global_periodic_fulltext_enabled=global_default,
    )
    assert plan.pipeline_kwargs.get("enable_periodic_report_fulltext_intake", False) is expected


def test_child_displays_require_active_source_intake_and_keep_limits(tmp_path):
    source = {
        "enabled": True,
        "periodic_narrative_cards_synthesis_display": {"enabled": True, "max_display_items": 7},
        "broker_research_digest_synthesis_display": {"enabled": True, "max_display_items": 6},
        "curated_external_argument_pack_synthesis_display": {
            "enabled": True,
            "pack_json": "data/curated_external/argument_packs/sample.json",
        },
    }
    plan = compile_report_run_plan(repo_root=tmp_path, agent_reach_config={}, source_intake_config=source)
    assert plan.context_values["periodic_narrative_cards_max_display_items"] == 7
    assert plan.context_values["broker_research_digest_max_display_items"] == 6
    assert plan.context_values["curated_external_argument_pack_json"] == str(
        tmp_path / "data/curated_external/argument_packs/sample.json"
    )
    assert plan.pipeline_kwargs["curated_external_argument_pack_json"] == plan.context_values[
        "curated_external_argument_pack_json"
    ]


def test_evidence_payload_keeps_agent_block_precedence_when_source_enables_notes(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={
            "enabled": False,
            "evidence_notes": {"enabled": True, "dry_run": False, "base_dir": "/agent/kb"},
        },
        source_intake_config={
            "enabled": True,
            "evidence_notes": {"enabled": True, "dry_run": True, "base_dir": "/source/kb"},
        },
    )
    assert plan.pipeline_kwargs["enable_evidence_notes"] is True
    assert plan.context_values["evidence_notes_dry_run"] is False
    assert plan.context_values["knowledge_base_dir"] == "/agent/kb"


def test_claim_precedence_and_risk_signal_independence(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={
            "claim_verification": {
                "enabled": False,
                "risk_signals": True,
                "base_dir": "/agent/claims",
                "max_verified": 3,
                "max_supported": 2,
                "max_unverified": 1,
            }
        },
        source_intake_config={"enabled": True, "claim_verification": {"enabled": True}},
    )
    assert plan.pipeline_kwargs["enable_claim_risk_signals"] is True
    assert "enable_claim_verification_context" not in plan.context_values
    assert plan.context_values["claim_verification_base_dir"] == "/agent/claims"
    assert plan.context_values["claim_verification_max_verified"] == 3
    assert plan.context_values["claim_verification_max_supported"] == 2
    assert plan.context_values["claim_verification_max_unverified"] == 1


def test_web_urls_take_precedence_over_legacy_urls_alias(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={
            "enabled": True,
            "web_urls": ["https://example.test/new"],
            "urls": ["https://example.test/legacy"],
        },
        source_intake_config={},
    )
    assert plan.context_values["agent_reach_urls"] == ["https://example.test/new"]


def test_disabled_source_parent_suppresses_all_child_displays(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={
            "enabled": False,
            "periodic_report_fulltext": {"enabled": True, "cache_dir": "/tmp/cache"},
            "periodic_narrative_cards_synthesis_display": {"enabled": True, "max_display_items": 7},
            "broker_research_digest_synthesis_display": {"enabled": True, "max_display_items": 6},
            "curated_external_argument_pack_synthesis_display": {
                "enabled": True,
                "pack_json": "/tmp/pack.json",
            },
        },
        global_periodic_fulltext_enabled=True,
    )
    assert "enable_periodic_report_fulltext_intake" not in plan.pipeline_kwargs
    assert "include_curated_external_argument_pack_in_deep_analysis_display" not in plan.pipeline_kwargs
    assert plan.context_values == {"enable_claim_risk_signals": False}


@pytest.mark.parametrize(
    ("policy", "expected"),
    [("formal_first", "formal_first"), ("legacy_mixed", None), ("", None)],
)
def test_only_formal_first_policy_is_emitted(tmp_path, policy, expected):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={
            "enabled": True,
            "canonical_synthesis_source_policy": policy,
        },
    )
    assert plan.pipeline_kwargs.get("canonical_synthesis_source_policy") == expected
    assert plan.context_values.get("canonical_synthesis_source_policy") == expected


def test_absolute_pack_path_is_not_rebased(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={
            "enabled": True,
            "curated_external_argument_pack_synthesis_display": {
                "enabled": True,
                "pack_json": "/absolute/pack.json",
            },
        },
    )
    assert plan.pipeline_kwargs["curated_external_argument_pack_json"] == "/absolute/pack.json"


def test_fulltext_cache_and_report_type_emit_only_when_enabled(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={
            "enabled": True,
            "periodic_report_fulltext": {
                "enabled": True,
                "cache_dir": "/tmp/annual-cache",
                "report_type": "annual_report",
            },
        },
    )
    assert plan.context_values["periodic_report_fulltext_cache_dir"] == "/tmp/annual-cache"
    assert plan.context_values["periodic_report_fulltext_report_type"] == "annual_report"


def test_malformed_nested_values_are_disabled(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={"evidence_notes": "invalid", "claim_verification": ["invalid"]},
        source_intake_config={
            "enabled": True,
            "periodic_report_fulltext": "invalid",
            "broker_research_digest_synthesis_display": 1,
        },
    )
    assert plan.pipeline_kwargs == {
        "enable_agent_reach": False,
        "enable_evidence_notes": False,
        "enable_claim_risk_signals": False,
        "enable_source_intake": True,
    }
    assert plan.context_values == {
        "enable_claim_risk_signals": False,
        "source_intake_enabled": True,
        "source_intake_config": {
            "enabled": True,
            "periodic_report_fulltext": "invalid",
            "broker_research_digest_synthesis_display": 1,
        },
    }


def test_source_intake_evidence_payload_is_used_without_agent_block(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={
            "enabled": True,
            "evidence_notes": {"enabled": True, "dry_run": False, "base_dir": "/source/kb"},
        },
    )
    assert plan.pipeline_kwargs["enable_evidence_notes"] is True
    assert plan.context_values["evidence_notes_dry_run"] is False
    assert plan.context_values["knowledge_base_dir"] == "/source/kb"


def test_source_claim_config_is_fallback_when_agent_claim_block_is_empty(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={"claim_verification": {}},
        source_intake_config={
            "claim_verification": {"enabled": True, "max_verified": 4},
        },
    )
    assert plan.context_values["enable_claim_verification_context"] is True
    assert plan.context_values["claim_verification_max_verified"] == 4
```

- [ ] **Step 2: Run the compiler module and confirm RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_report_run_plan.py -q -p no:cacheprovider
```

Expected: new optional-contract assertions fail against the core-only implementation.

- [ ] **Step 3: Replace the core compiler body with the full single-pass implementation**

Use this exact ownership sequence inside `compile_report_run_plan`:

```python
    agent_cfg = agent_reach_config if isinstance(agent_reach_config, Mapping) else {}
    source_cfg = source_intake_config if isinstance(source_intake_config, Mapping) else {}
    agent_enabled = bool(global_agent_reach_enabled or agent_cfg.get("enabled", False))
    source_enabled = bool(source_cfg.get("enabled", False))

    fulltext_cfg = _mapping(source_cfg, "periodic_report_fulltext")
    fulltext_requested = bool(
        fulltext_cfg.get("enabled", False)
        if "enabled" in fulltext_cfg
        else global_periodic_fulltext_enabled
    )
    fulltext_enabled = source_enabled and fulltext_requested
    narrative_cfg = _mapping(source_cfg, "periodic_narrative_cards_synthesis_display")
    broker_cfg = _mapping(source_cfg, "broker_research_digest_synthesis_display")
    external_cfg = _mapping(source_cfg, "curated_external_argument_pack_synthesis_display")
    narrative_enabled = source_enabled and bool(narrative_cfg.get("enabled", False))
    broker_enabled = source_enabled and bool(broker_cfg.get("enabled", False))
    external_enabled = source_enabled and bool(external_cfg.get("enabled", False))

    policy = str(source_cfg.get("canonical_synthesis_source_policy", "")).strip()
    policy = policy if policy == "formal_first" else ""
    pack_value = str(external_cfg.get("pack_json", "")).strip()
    pack_path = Path(pack_value) if pack_value else None
    if pack_path is not None and not pack_path.is_absolute():
        pack_path = repo_root / pack_path

    agent_evidence = _mapping(agent_cfg, "evidence_notes")
    source_evidence = _mapping(source_cfg, "evidence_notes")
    evidence_enabled = bool(
        (agent_enabled and agent_evidence.get("enabled", False))
        or (source_enabled and source_evidence.get("enabled", False))
    )
    evidence_payload = agent_evidence if agent_evidence.get("enabled") else source_evidence

    agent_claim = _mapping(agent_cfg, "claim_verification")
    source_claim = _mapping(source_cfg, "claim_verification")
    claim_cfg = agent_claim or source_claim
    claim_enabled = bool(claim_cfg.get("enabled", False))
    risk_enabled = bool(claim_cfg.get("risk_signals", False))

    pipeline_kwargs: dict[str, Any] = {
        "enable_agent_reach": agent_enabled,
        "enable_evidence_notes": evidence_enabled,
        "enable_claim_risk_signals": risk_enabled,
        "enable_source_intake": source_enabled,
    }
    context: dict[str, Any] = {"enable_claim_risk_signals": risk_enabled}

    if fulltext_enabled:
        pipeline_kwargs["enable_periodic_report_fulltext_intake"] = True
        if fulltext_cfg.get("cache_dir"):
            context["periodic_report_fulltext_cache_dir"] = fulltext_cfg["cache_dir"]
        if fulltext_cfg.get("report_type"):
            context["periodic_report_fulltext_report_type"] = fulltext_cfg["report_type"]
    if source_enabled:
        context.update(source_intake_enabled=True, source_intake_config=source_cfg)
        if policy:
            pipeline_kwargs["canonical_synthesis_source_policy"] = policy
            context["canonical_synthesis_source_policy"] = policy
    if narrative_enabled:
        context["include_periodic_narrative_cards_in_synthesis_display"] = True
        if narrative_cfg.get("max_display_items") is not None:
            context["periodic_narrative_cards_max_display_items"] = narrative_cfg["max_display_items"]
    if broker_enabled:
        context["include_broker_research_digest_in_synthesis_display"] = True
        if broker_cfg.get("max_display_items") is not None:
            context["broker_research_digest_max_display_items"] = broker_cfg["max_display_items"]
    if external_enabled:
        resolved_pack = str(pack_path) if pack_path is not None else ""
        pipeline_kwargs.update(
            include_curated_external_argument_pack_in_deep_analysis_display=True,
            curated_external_argument_pack_json=resolved_pack,
        )
        context.update(
            include_curated_external_argument_pack_in_deep_analysis_display=True,
            curated_external_argument_pack_json=resolved_pack,
        )
    if agent_enabled:
        context["enable_agent_reach"] = True
        web_urls = agent_cfg.get("web_urls", []) or agent_cfg.get("urls", [])
        for key, value in (
            ("agent_reach_urls", web_urls),
            ("agent_reach_rss_feeds", agent_cfg.get("rss_feeds", [])),
            ("agent_reach_rss_filter_terms", agent_cfg.get("rss_filter_terms", [])),
            ("agent_reach_official_domains", agent_cfg.get("official_domains", [])),
        ):
            if value:
                context[key] = value
    if evidence_enabled:
        context["enable_evidence_notes"] = True
        context["evidence_notes_dry_run"] = evidence_payload.get("dry_run", True)
        if evidence_payload.get("base_dir"):
            context["knowledge_base_dir"] = evidence_payload["base_dir"]
    if claim_enabled:
        context["enable_claim_verification_context"] = True
    if claim_enabled or risk_enabled:
        claim_keys = {
            "base_dir": "claim_verification_base_dir",
            "max_verified": "claim_verification_max_verified",
            "max_supported": "claim_verification_max_supported",
            "max_unverified": "claim_verification_max_unverified",
        }
        for source_key, context_key in claim_keys.items():
            value = claim_cfg.get(source_key)
            if value is not None and (source_key != "base_dir" or value):
                context[context_key] = value

    return ReportRunPlan(
        pipeline_kwargs=pipeline_kwargs,
        context_values=context,
        can_run_without_posts=agent_enabled or source_enabled,
    )
```

- [ ] **Step 4: Run all compiler tests and confirm GREEN**

Expected: all `test_report_run_plan.py` cases pass with exact dictionaries and no filesystem reads.

### Task 3: Cut `PerStockReporter` over to one compiled plan

**Files:**
- Modify: `scripts/utils/stock_reporter.py`
- Create: `tests/reporter/test_stock_reporter_run_plan.py`

- [ ] **Step 1: Add facade integration tests before changing runtime**

The new test module must cover exact plan forwarding, both no-post branches, and exception handling:

```python
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from utils.report_run_plan import ReportRunPlan
from utils.stock_reporter import PerStockReporter


def _pipeline_result(md="/tmp/report.md", html="/tmp/report.html"):
    pipeline = MagicMock()
    pipeline.run.return_value.output = {"md_path": md, "html_path": html}
    return pipeline


def test_reporter_forwards_one_compiled_plan_to_builder_and_context():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"content": "有效帖子"}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {"technical": {}}},
        stock_configs={"测试股": {"industry": "测试行业"}},
    )
    plan = ReportRunPlan(
        pipeline_kwargs={"enable_agent_reach": True},
        context_values={"enable_claim_risk_signals": False, "enable_agent_reach": True},
        can_run_without_posts=True,
    )
    pipeline = _pipeline_result()
    with patch("utils.stock_reporter.compile_report_run_plan", return_value=plan) as compile_plan, patch(
        "utils.report_skills.build_stock_report_pipeline", return_value=pipeline
    ) as build:
        result = reporter.generate_stock_report("测试股", "/tmp/out")

    assert result == ("/tmp/report.md", "/tmp/report.html")
    compile_plan.assert_called_once()
    build.assert_called_once_with(enable_agent_reach=True)
    assert pipeline.run.call_args.args[0] == {
        "stock_name": "测试股",
        "date_str": reporter.date_str,
        "output_dir": "/tmp/out",
        "stocks_data": reporter.stocks_data,
        "raw_data": reporter.raw_data,
        "stock_codes": reporter.stock_codes,
        "stock_config": {"industry": "测试行业"},
        "enable_claim_risk_signals": False,
        "enable_agent_reach": True,
    }


def test_reporter_skips_empty_posts_when_plan_has_no_source():
    reporter = PerStockReporter(stocks_data={"测试股": []})
    plan = ReportRunPlan({}, {"enable_claim_risk_signals": False}, False)
    with patch("utils.stock_reporter.compile_report_run_plan", return_value=plan), patch(
        "utils.report_skills.build_stock_report_pipeline"
    ) as build:
        assert reporter.generate_stock_report("测试股", "/tmp/out") == ("", "")
    build.assert_not_called()


def test_reporter_runs_empty_posts_when_plan_has_active_source():
    reporter = PerStockReporter(stocks_data={"测试股": []})
    plan = ReportRunPlan({}, {"enable_claim_risk_signals": False}, True)
    pipeline = _pipeline_result("", "")
    with patch("utils.stock_reporter.compile_report_run_plan", return_value=plan), patch(
        "utils.report_skills.build_stock_report_pipeline", return_value=pipeline
    ):
        assert reporter.generate_stock_report("测试股", "/tmp/out") == ("", "")
    pipeline.run.assert_called_once()


def test_reporter_returns_empty_paths_when_pipeline_raises():
    reporter = PerStockReporter(stocks_data={"测试股": [{"content": "有效帖子"}]})
    plan = ReportRunPlan({}, {"enable_claim_risk_signals": False}, False)
    pipeline = MagicMock()
    pipeline.run.side_effect = RuntimeError("boom")
    with patch("utils.stock_reporter.compile_report_run_plan", return_value=plan), patch(
        "utils.report_skills.build_stock_report_pipeline", return_value=pipeline
    ):
        assert reporter.generate_stock_report("测试股", "/tmp/out") == ("", "")
```

- [ ] **Step 2: Run the new facade tests and confirm RED**

Expected: patching `utils.stock_reporter.compile_report_run_plan` fails because the reporter does not import it yet.

- [ ] **Step 3: Replace reporter configuration plumbing**

At module level import:

```python
from .report_run_plan import compile_report_run_plan
```

Inside `generate_stock_report`, compile once before the early skip:

```python
        all_posts = self.stocks_data.get(stock_name, [])
        stock_cfg = self.stock_configs.get(stock_name, {})
        plan = compile_report_run_plan(
            repo_root=Path(__file__).resolve().parents[2],
            agent_reach_config=self.agent_reach_configs.get(stock_name, {}),
            source_intake_config=self.source_intake_configs.get(stock_name, {}),
            global_agent_reach_enabled=self.enable_agent_reach,
            global_periodic_fulltext_enabled=self.enable_periodic_report_fulltext_intake,
        )
        if not all_posts and not plan.can_run_without_posts:
            logger.warning(f"[{stock_name}] 无数据，跳过")
            return "", ""
```

Replace all branch-built `pipeline_kwargs` and optional input code with:

```python
            pipeline = build_stock_report_pipeline(**plan.pipeline_kwargs)
            pipeline_input = {
                "stock_name": stock_name,
                "date_str": self.date_str,
                "output_dir": output_dir,
                "stocks_data": self.stocks_data,
                "raw_data": self.raw_data,
                "stock_codes": self.stock_codes,
                "stock_config": stock_cfg,
            }
            pipeline_input.update(plan.context_values)
            ctx = pipeline.run(pipeline_input)
```

Do not remove the legacy batch methods or constructor `data_path` in this task; that deletion belongs to Task 5.

- [ ] **Step 4: Run facade, compiler, pipeline, and chart regressions**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_report_run_plan.py \
  tests/reporter/test_stock_reporter_run_plan.py \
  tests/reporter/test_pipeline_integration.py \
  tests/reporter/test_stock_reporter_charts.py \
  -q -p no:cacheprovider
```

Expected: all pass; pipeline order tests remain unchanged.

### Task 4: Migrate and delete duplicate configuration tests

**Files:**
- Modify: `tests/reporter/test_report_run_plan.py`
- Modify: `tests/reporter/test_stock_reporter_run_plan.py`
- Delete: `tests/reporter/test_stock_reporter_agent_reach_config.py`
- Delete: `tests/reporter/test_stock_reporter_source_intake_config.py`

- [ ] **Step 1: Inventory every legacy test contract**

Run:

```bash
rg -n '^def test_' \
  tests/reporter/test_stock_reporter_agent_reach_config.py \
  tests/reporter/test_stock_reporter_source_intake_config.py
```

Record all 45 names in the implementation notes under one of three owners:

- `test_report_run_plan.py`: all raw configuration precedence and optional payload assertions.
- `test_stock_reporter_run_plan.py`: facade forwarding, stock config, no-post, and error behavior.
- unchanged config/pack validation tests: production `stocks.json` and canonical-pack readability assertions.

- [ ] **Step 2: Move production-config assertions before deleting source files**

Keep tests that read `config/stocks.json` or validate canonical v4 packs in `test_report_run_plan.py` under a `production_config` section. Preserve their exact stock names, codes, policy checks, direct-relevance fields, and `read_external_argument_pack_v4` assertions. These are not compiler unit tests, but retaining them in one active configuration contract module avoids losing coverage.

- [ ] **Step 3: Run old and new modules together**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_report_run_plan.py \
  tests/reporter/test_stock_reporter_run_plan.py \
  tests/reporter/test_stock_reporter_agent_reach_config.py \
  tests/reporter/test_stock_reporter_source_intake_config.py \
  -q -p no:cacheprovider
```

Expected: every old and new assertion passes simultaneously.

- [ ] **Step 4: Delete only the two superseded test modules**

Delete:

```text
tests/reporter/test_stock_reporter_agent_reach_config.py
tests/reporter/test_stock_reporter_source_intake_config.py
```

Then rerun the new modules and the unchanged pipeline/chart modules. Expected: all pass with no lost production-config contract.

### Task 5: Move batch ownership and remove the hard-coded summary path

**Files:**
- Modify: `scripts/xueqiu_monitor_v2.py`
- Modify: `scripts/utils/stock_reporter.py`
- Create: `tests/reporter/test_xueqiu_monitor_report_batch.py`

- [ ] **Step 1: Add the failing no-network batch helper test**

```python
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import xueqiu_monitor_v2


def test_generate_deep_reports_uses_source_order_and_returns_only_stock_outputs(tmp_path):
    stocks = [
        {"name": "甲", "code": "000001", "agent_reach": {"enabled": True}},
        {"name": "乙", "code": "000002"},
    ]
    reporter = MagicMock()
    reporter.generate_stock_report.side_effect = [
        ("/tmp/甲.md", "/tmp/甲.html"),
        ("", "/tmp/乙.html"),
    ]
    with patch("utils.stock_reporter.PerStockReporter", return_value=reporter) as reporter_cls:
        paths = xueqiu_monitor_v2._generate_deep_reports(
            stocks,
            {"甲": [], "乙": []},
            {"甲": {"technical": {}}, "乙": {}},
            tmp_path,
        )

    reporter_cls.assert_called_once_with(
        stocks_data={"甲": [], "乙": []},
        stock_codes={"甲": "000001", "乙": "000002"},
        raw_data={"甲": {"technical": {}}, "乙": {}},
        agent_reach_configs={"甲": {"enabled": True}},
    )
    assert reporter.generate_stock_report.call_args_list[0].args == ("甲", str(tmp_path))
    assert reporter.generate_stock_report.call_args_list[1].args == ("乙", str(tmp_path))
    assert paths == ["/tmp/甲.md", "/tmp/甲.html", "/tmp/乙.html"]
    assert all("xueqiu_summary_" not in path for path in paths)
```

- [ ] **Step 2: Run the batch test and confirm RED**

Expected: `xueqiu_monitor_v2` has no `_generate_deep_reports` attribute.

- [ ] **Step 3: Add the helper and route the monitor through it**

Add before `run_monitor`:

```python
def _generate_deep_reports(stocks, stocks_data, collected_data, output_dir):
    from utils.stock_reporter import PerStockReporter

    stock_codes = {stock["name"]: stock["code"] for stock in stocks}
    agent_reach_configs = {
        stock["name"]: stock["agent_reach"]
        for stock in stocks
        if stock.get("agent_reach")
    }
    reporter = PerStockReporter(
        stocks_data=stocks_data,
        stock_codes=stock_codes,
        raw_data=collected_data,
        agent_reach_configs=agent_reach_configs,
    )
    paths = []
    for stock in stocks:
        md_path, html_path = reporter.generate_stock_report(stock["name"], str(output_dir))
        paths.extend(path for path in (md_path, html_path) if path)
    return paths
```

Replace the existing block that constructs `PerStockReporter` and calls
`reporter.generate_all_reports(output_dir=report_mgr.report_dir)` in
`run_monitor` with `_generate_deep_reports(stocks, stocks_data, collected_data,
report_mgr.report_dir)`. Retain the existing path logging, outer `try/except`,
and PDF loop.

- [ ] **Step 4: Remove batch, summary, and module-CLI code from the facade**

From `scripts/utils/stock_reporter.py` remove:

- `json` import;
- unused `List` import if no longer referenced;
- `data_path` constructor argument and JSON-loading branch;
- `self.date_display` if no longer referenced;
- `generate_all_reports`;
- `_resolve_repo_relative_path`;
- `_generate_summary_report`;
- the `if __name__ == "__main__"` block.

Constructor initialization becomes:

```python
        self.stocks_data = stocks_data or {}
```

- [ ] **Step 5: Run batch and facade regressions**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_xueqiu_monitor_report_batch.py \
  tests/reporter/test_stock_reporter_run_plan.py \
  tests/reporter/test_report_run_plan.py \
  tests/reporter/test_pipeline_integration.py \
  tests/reporter/test_stock_reporter_charts.py \
  -q -p no:cacheprovider
```

Expected: all pass, each configured stock is invoked once, and no summary path exists.

### Task 6: Verify behavior, hygiene, and reduction budgets

**Files:**
- Create: `docs/agent_workflow/2026-07-31-report-run-plan-dedup-implementation-notes.md`

- [ ] **Step 1: Run the focused suite**

Run the five modules from Task 5. Expected: zero failures.

- [ ] **Step 2: Run the full suite without cache artifacts**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

Expected: zero failures and no unexpected increase from the pre-task `10 skipped` baseline.

- [ ] **Step 3: Run repository gates**

```bash
bash tools/ci_grep_gates.sh
git diff --check
```

Expected: all grep gates pass and `git diff --check` emits no output.

- [ ] **Step 4: Run the no-network sample smoke**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_黑芝麻智能.py --offline-smoke
```

Expected: exit code `0`; artifacts are confined to `/tmp/testsnow_offline_smoke`; no report, data, knowledge, or source file is modified.

- [ ] **Step 5: Prove ownership and dead-path removal**

```bash
rg -n "generate_all_reports|_generate_summary_report|xueqiu_summary_|data_path=" scripts tests
rg -n "compile_report_run_plan" scripts tests
```

Expected: the first search finds no active runtime/test references; the second finds one compiler definition, one reporter call site, and tests.

- [ ] **Step 6: Measure line budgets against the locked baseline**

```bash
find scripts -name '*.py' -print0 | xargs -0 wc -l | tail -1
find tests -name '*.py' -print0 | xargs -0 wc -l | tail -1
```

Expected:

- runtime total `<= 67,056`;
- test total `<= 62,645`.

Stop and return to design if either target is missed; do not delete unrelated active tests or compress logic into opaque expressions to force the number.

- [ ] **Step 7: Write implementation notes**

Record:

- modified/deleted files;
- RED/GREEN commands and results per task;
- a 45-row legacy-test-to-new-owner mapping;
- exact pipeline order regression result;
- full-suite, CI, diff, and offline-smoke results;
- before/after runtime and test line totals;
- blocker, warning, deviation;
- confirmation that no formal report, network, Chrome/CDP, score, target, risk, technical, citation, or LLM behavior changed.
