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
    environment: Mapping[str, str] | None = None,
) -> ReportRunPlan:
    agent_cfg = agent_reach_config if isinstance(agent_reach_config, Mapping) else {}
    source_cfg = source_intake_config if isinstance(source_intake_config, Mapping) else {}
    env_enabled = (environment or {}).get("ENABLE_AGENT_REACH", "") in ("1", "true", "True")
    agent_enabled = bool(env_enabled or global_agent_reach_enabled or agent_cfg.get("enabled", False))
    source_enabled = bool(source_cfg.get("enabled", False))

    fulltext_cfg = _mapping(source_cfg, "periodic_report_fulltext")
    fulltext_requested = bool(
        fulltext_cfg.get("enabled", global_periodic_fulltext_enabled)
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
    raw_pack_value = external_cfg.get("pack_json", "")
    pack_value = str(raw_pack_value).strip() if isinstance(raw_pack_value, (str, Path)) else ""
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

    claim_cfg = _mapping(agent_cfg, "claim_verification") or _mapping(
        source_cfg, "claim_verification"
    )
    claim_enabled = bool(claim_cfg.get("enabled", False))
    risk_enabled = bool(claim_cfg.get("risk_signals", False))

    pipeline_kwargs: dict[str, Any] = dict(
        enable_agent_reach=agent_enabled,
        enable_evidence_notes=evidence_enabled,
        enable_claim_risk_signals=risk_enabled,
        enable_source_intake=source_enabled,
    )
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
        external_values = {
            "include_curated_external_argument_pack_in_deep_analysis_display": True,
            "curated_external_argument_pack_json": resolved_pack,
        }
        pipeline_kwargs.update(external_values)
        context.update(external_values)
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

    return ReportRunPlan(pipeline_kwargs, context, agent_enabled or source_enabled)
