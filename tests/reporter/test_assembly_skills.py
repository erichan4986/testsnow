import sys
import json
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.skill_pipeline import SkillContext
from utils.report_skills.assembly_skills import ReportAssemblySkill


def _summary_context(tmp_path=None):
    data = {
        "stock_name": "测试股",
        "date_str": "20260719",
        "recommendation_decision": SimpleNamespace(
            total_score=5.3,
            ev=SimpleNamespace(ev_display="+8.00%", targets={"base": 42.0}),
            display_recommendation="谨慎持有",
            recommendation_sentence="谨慎持有，等待趋势确认。",
            entry_constraint=SimpleNamespace(position_cap_note="建议仓位 5-10%。"),
            risk=SimpleNamespace(level="中等风险", position_advice="控制仓位。"),
        ),
        "pillar": {"fundamental": 7.0, "fwd_pe": 28.0, "eps_growth": 20.0},
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend_state": {"stage": "转弱期"},
                        "trend_health": {"grade": "转弱观察", "score": 47},
                    }
                }
            }
        },
    }
    if tmp_path is not None:
        data["output_dir"] = str(tmp_path)
    return SkillContext(input=data)


def test_prepare_executive_summary_stores_view_and_dated_image(tmp_path, monkeypatch):
    captured = {}

    def fake_generate(view, output_path):
        captured["view"] = view
        captured["path"] = output_path
        return str(output_path)

    monkeypatch.setattr(
        "utils.report_skills.assembly_skills.generate_decision_chain_chart",
        fake_generate,
    )
    ctx = _summary_context(tmp_path)

    ReportAssemblySkill()._prepare_executive_summary(ctx)

    assert ctx.get("executive_summary_view") is captured["view"]
    assert Path(captured["path"]).name == "测试股_20260719_decision.png"
    assert ctx.get("chart_paths")["executive_summary"].endswith(
        "测试股_20260719_decision.png"
    )


def test_prepare_executive_summary_without_output_dir_uses_text_fallback(monkeypatch):
    monkeypatch.setattr(
        "utils.report_skills.assembly_skills.generate_decision_chain_chart",
        lambda *_: (_ for _ in ()).throw(AssertionError("must not generate")),
    )
    ctx = _summary_context()

    ReportAssemblySkill()._prepare_executive_summary(ctx)

    assert ctx.get("executive_summary_view").image_ready is True
    assert ctx.get("chart_paths").get("executive_summary") is None


def test_formal_assembly_does_not_register_legacy_price_target_renderer():
    assert all(name != "price_target" for name, *_ in ReportAssemblySkill.RENDERERS)


def test_assembly_writes_agent_reach_audit_json(tmp_path):
    skill = ReportAssemblySkill()
    summary = {
        "stock_name": "测试股",
        "date_str": "20260604",
        "enabled": True,
        "fetch_status": "ok",
        "quality_status": "ok",
        "queries": [{"query": "web_read", "target_platforms": ["web"], "url_count": 1, "urls": ["http://example.com/a"]}],
        "counts": {"total": 1, "keep": 1, "demote": 0, "discard": 0},
        "warnings": [],
        "results": [{"title": "t", "source": "AgentReach(web)", "url": "http://example.com/a", "action": "keep", "score": 60, "reasons": ["有URL"], "official_seed_url": True}],
    }
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "output_dir": str(tmp_path),
        "pillar_scores": {"valuation": 7, "technical": 6, "sentiment": 5, "fundamental": 6, "fundflow": 5},
        "total_score": 5.8,
        "quote": {"pe_ttm": 20},
        "consensus": {},
        "ind_fwd_pe": 25,
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": ""},
        "keep_posts": [],
        "agent_reach_enabled": True,
        "agent_reach_run_summary": summary,
    })
    result = skill.run(ctx)
    audit_path = tmp_path / "测试股_20260604_agent_reach.json"
    assert audit_path.exists()
    assert result.get("agent_reach_audit_path") == str(audit_path)
    data = json.loads(audit_path.read_text(encoding="utf-8"))
    assert data["stock_name"] == "测试股"
    assert data["counts"]["keep"] == 1
    assert "content" not in str(data)


def test_assembly_writes_industry_relevance_manifest_sidecar(tmp_path):
    skill = ReportAssemblySkill()
    manifest = {
        "schema": "industry_relevance_manifest.v1",
        "events_catalysts_chains": [
            {
                "chain_id": "memory_capacity_to_cis_pricing",
                "confidence": 0.82,
                "allowed_terms": ["存储产品涨价", "晶圆厂产能紧张", "CIS排产变化", "待验证变量"],
            }
        ],
    }
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "output_dir": str(tmp_path),
        "pillar_scores": {"valuation": 7, "technical": 6, "sentiment": 5, "fundamental": 6, "fundflow": 5},
        "total_score": 5.8,
        "quote": {"pe_ttm": 20},
        "consensus": {},
        "ind_fwd_pe": 25,
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": ""},
        "keep_posts": [],
        "industry_relevance_manifest": manifest,
    })

    result = skill.run(ctx)

    sidecar_path = tmp_path / "测试股_20260604_industry_relevance_manifest.json"
    assert sidecar_path.exists()
    assert result.get("industry_relevance_manifest_path") == str(sidecar_path)
    data = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert data["events_catalysts_chains"][0]["chain_id"] == "memory_capacity_to_cis_pricing"


def test_assembly_writes_fundflow_material_sidecar(tmp_path):
    skill = ReportAssemblySkill()
    pack = {
        "schema": "fundflow_material_pack.v1",
        "rows": [{"date": "2026-07-02", "main_net": 1200.0}],
        "summary": {"days": 1, "main_net_total": 1200.0, "signal": "inflow_with_price_up"},
    }
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "output_dir": str(tmp_path),
        "pillar_scores": {"valuation": 7, "technical": 6, "sentiment": 5, "fundamental": 6, "fundflow": 5},
        "total_score": 5.8,
        "quote": {"pe_ttm": 20},
        "consensus": {},
        "ind_fwd_pe": 25,
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": ""},
        "keep_posts": [],
        "fundflow_material_pack": pack,
    })

    result = skill.run(ctx)

    sidecar_path = tmp_path / "测试股_20260604_fundflow_material.json"
    assert sidecar_path.exists()
    assert result.get("fundflow_material_path") == str(sidecar_path)
    data = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert data["schema"] == "fundflow_material_pack.v1"
    assert data["summary"]["main_net_total"] == 1200.0


def test_assembly_does_not_write_audit_when_disabled(tmp_path):
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "output_dir": str(tmp_path),
        "pillar_scores": {"valuation": 7, "technical": 6, "sentiment": 5, "fundamental": 6, "fundflow": 5},
        "total_score": 5.8,
        "quote": {"pe_ttm": 20},
        "consensus": {},
        "ind_fwd_pe": 25,
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": ""},
        "keep_posts": [],
        "agent_reach_enabled": False,
        "agent_reach_run_summary": {"enabled": False, "counts": {"total": 0}},
    })
    skill.run(ctx)
    audit_path = tmp_path / "测试股_20260604_agent_reach.json"
    assert not audit_path.exists()


def test_report_assembly_skill(tmp_path):
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "output_dir": str(tmp_path),
        "pillar_scores": {
            "valuation": 7.0,
            "technical": 6.0,
            "sentiment": 5.0,
            "fundamental": 6.0,
            "fundflow": 5.0,
        },
        "total_score": 5.8,
        "quote": {"pe_ttm": 20.0},
        "consensus": {},
        "ind_fwd_pe": 25.0,
        "synthesis": {
            "industry_logic": "行业逻辑",
            "fundamentals": "基本面",
            "valuation_debate": "估值多空",
            "funding_sentiment": "资金情绪",
            "events_catalysts": "事件催化",
        },
        "keep_posts": [],
        "cross_source_summary": "",
    })
    result = skill.run(ctx)
    md_path = result.get("md_path")
    html_path = result.get("html_path")
    assert md_path is not None
    assert html_path is not None
    assert Path(md_path).exists()
    assert Path(html_path).exists()
    md_content = Path(md_path).read_text(encoding="utf-8")
    assert "精品帖子深度解读与关键评论摘录已迁移至知识库" not in md_content
    assert "agent_reach_evidence: skipped" not in md_content


def test_header_uses_dynamic_data_sources():
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "all_posts": [{"title": "社区"}],
        "synthesis_sources": ["研报", "公告"],
        "stock_raw": {
            "technical": {"indicators": {}},
            "fundflow": [{"date": "2026-06-04"}],
            "news": [{"title": "新闻"}],
        },
        "quote": {"price": 10.0},
    })

    header = skill._header(ctx)

    assert "**数据来源**:" in header
    assert "雪球/社区讨论" in header
    assert "研报" in header
    assert "公告" in header
    assert "技术行情数据" in header
    assert "资金流向" in header
    assert "新闻资讯" in header
    assert "实时行情/估值" in header
    assert "雪球网热门讨论" not in header


def test_header_prefers_stock_config_industry_and_competitors():
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "圣邦股份",
        "date_str": "20260604",
        "stock_config": {
            "industry": "测试行业",
            "competitors": ["测试对手"],
        },
    })

    header = skill._header(ctx)

    assert "**所属赛道**: 测试行业" in header
    assert "**可比公司**: 测试对手" in header
    assert "模拟芯片/半导体" not in header
    assert "思瑞浦" not in header


def test_header_falls_back_to_constants_when_stock_config_missing():
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "圣邦股份",
        "date_str": "20260604",
    })

    header = skill._header(ctx)

    assert "**所属赛道**: 模拟芯片/半导体" in header
    assert "**可比公司**: 思瑞浦、杰华特、纳芯微、艾为电子" in header


def test_header_renders_dash_when_config_and_constants_missing():
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "未知股票",
        "date_str": "20260604",
    })

    header = skill._header(ctx)

    assert "**所属赛道**: —" in header
    assert "**可比公司**: —" in header


def test_source_intake_evidence_renderer_order():
    skill = ReportAssemblySkill()
    names = [name for name, _, _ in skill.RENDERERS]
    assert "source_intake_evidence" in names
    assert names.index("deep_analysis") < names.index("source_intake_evidence")
    assert names.index("source_intake_evidence") < names.index("agent_reach_evidence")
    assert names.index("source_intake_evidence") < names.index("risk")


def test_curated_external_analysis_renderer_order():
    skill = ReportAssemblySkill()
    names = [name for name, _, _ in skill.RENDERERS]
    assert "curated_external_analysis" in names
    assert names.index("source_intake_evidence") < names.index("curated_external_analysis")
    assert names.index("curated_external_analysis") < names.index("agent_reach_evidence")
    assert names.index("curated_external_analysis") < names.index("risk")


def test_report_renders_when_source_intake_keys_absent(tmp_path):
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "output_dir": str(tmp_path),
        "pillar_scores": {"valuation": 7.0, "technical": 6.0, "sentiment": 5.0, "fundamental": 6.0, "fundflow": 5.0},
        "total_score": 5.8,
        "quote": {"pe_ttm": 20.0},
        "consensus": {},
        "ind_fwd_pe": 25.0,
        "synthesis": {
            "industry_logic": "行业逻辑",
            "fundamentals": "基本面",
            "valuation_debate": "估值多空",
            "funding_sentiment": "资金情绪",
            "events_catalysts": "事件催化",
        },
        "keep_posts": [],
        "cross_source_summary": "",
    })
    result = skill.run(ctx)
    md_path = result.get("md_path")
    assert md_path is not None
    md_content = Path(md_path).read_text(encoding="utf-8")
    assert "Source Intake" not in md_content
    assert "source_intake_evidence: skipped" not in md_content


def test_report_assembly_renders_curated_external_analysis_section(tmp_path):
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "output_dir": str(tmp_path),
        "pillar_scores": {"valuation": 7.0, "technical": 6.0, "sentiment": 5.0, "fundamental": 6.0, "fundflow": 5.0},
        "total_score": 5.8,
        "quote": {"pe_ttm": 20.0},
        "consensus": {},
        "ind_fwd_pe": 25.0,
        "synthesis": {
            "industry_logic": "行业逻辑",
            "fundamentals": "基本面",
            "valuation_debate": "估值多空",
            "funding_sentiment": "资金情绪",
            "events_catalysts": "事件催化",
        },
        "keep_posts": [],
        "cross_source_summary": "",
        "curated_external_analysis_items": [
            {
                "source_kind": "wechat_product_signal",
                "source_type": "wechat_product_signal",
                "title": "圣邦微 SGM25890 新品",
                "content": "AI 服务器电源方向的 90A Smart Power Stage。",
                "quality_action": "preview_only",
                "knowledge_eligible": False,
                "synthesis_eligible": False,
                "scoring_eligible": False,
                "risk_score_eligible": False,
            }
        ],
    })

    result = skill.run(ctx)
    md_content = Path(result.get("md_path")).read_text(encoding="utf-8")

    assert "## 精选外部观察（Preview）" in md_content
    assert "### 微信精选观察" in md_content
    assert "#### 产品/事件信号" in md_content
    assert "圣邦微 SGM25890 新品" in md_content


def test_agent_reach_only_report_does_not_render_source_intake_section(tmp_path):
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "output_dir": str(tmp_path),
        "pillar_scores": {"valuation": 7.0, "technical": 6.0, "sentiment": 5.0, "fundamental": 6.0, "fundflow": 5.0},
        "total_score": 5.8,
        "quote": {"pe_ttm": 20.0},
        "consensus": {},
        "ind_fwd_pe": 25.0,
        "synthesis": {
            "industry_logic": "行业逻辑",
            "fundamentals": "基本面",
            "valuation_debate": "估值多空",
            "funding_sentiment": "资金情绪",
            "events_catalysts": "事件催化",
        },
        "keep_posts": [],
        "cross_source_summary": "",
        "agent_reach_enabled": True,
        "agent_reach_quality_status": "ok",
        "agent_reach_keep_items": [{"title": "t"}],
        "agent_reach_demote_items": [],
    })
    result = skill.run(ctx)
    md_path = result.get("md_path")
    assert md_path is not None
    md_content = Path(md_path).read_text(encoding="utf-8")
    assert "Agent-Reach 外部证据观察" in md_content
    assert "Source Intake" not in md_content


    skill = ReportAssemblySkill()
    names = [name for name, _, _ in skill.RENDERERS]
    assert "deep_analysis" in names
    assert "agent_reach_evidence" in names
    assert "risk" in names
    assert names.index("deep_analysis") < names.index("agent_reach_evidence")
    assert names.index("agent_reach_evidence") < names.index("risk")


def test_header_includes_agent_reach_when_enabled_ok_and_items():
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "agent_reach_enabled": True,
        "agent_reach_quality_status": "ok",
        "agent_reach_keep_items": [{"title": "t"}],
        "agent_reach_demote_items": [],
    })
    header = skill._header(ctx)
    assert "Agent-Reach外部检索" in header


def test_header_excludes_agent_reach_when_disabled():
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "agent_reach_enabled": False,
    })
    header = skill._header(ctx)
    assert "Agent-Reach外部检索" not in header


def test_header_excludes_agent_reach_when_skipped():
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "agent_reach_enabled": True,
        "agent_reach_quality_status": "skipped",
        "agent_reach_keep_items": [],
        "agent_reach_demote_items": [],
    })
    header = skill._header(ctx)
    assert "Agent-Reach外部检索" not in header


def test_header_excludes_agent_reach_when_empty():
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "agent_reach_enabled": True,
        "agent_reach_quality_status": "empty",
        "agent_reach_keep_items": [],
        "agent_reach_demote_items": [],
    })
    header = skill._header(ctx)
    assert "Agent-Reach外部检索" not in header


def test_assembly_writes_peer_comparison_material_sidecar(tmp_path):
    skill = ReportAssemblySkill()
    sidecar_material = {
        "schema": "peer_comparison_material.v1",
        "target": "测试股",
        "peers": ["同行A", "同行B"],
        "rows": [
            {
                "dimension": "盈利能力",
                "target": "测试股",
                "peer": "同行A",
                "metric": "gross_margin",
                "target_value": 60.0,
                "peer_value": 65.0,
                "period": "latest",
                "unit": "%",
                "comparison": "毛利率低于同行A",
                "source_refs": ["指标:competitor_metrics"],
                "confidence": 0.85,
                "usage": "claim_eligible",
            }
        ],
        "warnings": [],
    }
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "output_dir": str(tmp_path),
        "pillar_scores": {"valuation": 7, "technical": 6, "sentiment": 5, "fundamental": 6, "fundflow": 5},
        "total_score": 5.8,
        "quote": {"pe_ttm": 20},
        "consensus": {},
        "ind_fwd_pe": 25,
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": ""},
        "keep_posts": [],
        "peer_comparison_material": sidecar_material,
    })

    result = skill.run(ctx)

    sidecar_path = tmp_path / "测试股_20260604_peer_comparison_material.json"
    assert sidecar_path.exists()
    assert result.get("peer_comparison_material_path") == str(sidecar_path)
    data = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert data["schema"] == "peer_comparison_material.v1"
    assert len(data["rows"]) == 1


def test_assembly_does_not_write_peer_comparison_material_when_rows_empty(tmp_path):
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "output_dir": str(tmp_path),
        "pillar_scores": {"valuation": 7, "technical": 6, "sentiment": 5, "fundamental": 6, "fundflow": 5},
        "total_score": 5.8,
        "quote": {"pe_ttm": 20},
        "consensus": {},
        "ind_fwd_pe": 25,
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": ""},
        "keep_posts": [],
        "peer_comparison_material": {
            "schema": "peer_comparison_material.v1",
            "target": "测试股",
            "peers": [],
            "rows": [],
            "warnings": ["No data"],
        },
    })

    skill.run(ctx)

    sidecar_path = tmp_path / "测试股_20260604_peer_comparison_material.json"
    assert not sidecar_path.exists()
