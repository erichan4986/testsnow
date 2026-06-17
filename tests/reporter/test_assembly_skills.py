import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.skill_pipeline import SkillContext
from utils.report_skills.assembly_skills import ReportAssemblySkill


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


def test_source_intake_evidence_renderer_order():
    skill = ReportAssemblySkill()
    names = [name for name, _, _ in skill.RENDERERS]
    assert "source_intake_evidence" in names
    assert names.index("deep_analysis") < names.index("source_intake_evidence")
    assert names.index("source_intake_evidence") < names.index("agent_reach_evidence")
    assert names.index("source_intake_evidence") < names.index("risk")


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
