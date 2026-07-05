import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.report_skills.knowledge_skills import KnowledgePersistenceSkill
from utils.skill_pipeline import SkillContext


def test_knowledge_persistence_writes_notes(tmp_path):
    skill = KnowledgePersistenceSkill(vault_root=str(tmp_path))
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260606",
        "output_dir": str(tmp_path / "reports"),
    })
    ctx.set("stock_name", "测试股")
    ctx.set("date_str", "20260606")
    ctx.set("total_score", 6.2)
    ctx.set("pillar_scores", {"valuation": 7.0, "technical": 6.0})
    ctx.set("bullish_args", ["营收增长", "毛利提升"])
    ctx.set("bearish_args", ["估值偏高"])
    ctx.set("cross_source_summary", "跨源摘要内容")
    ctx.set("synthesis", {"industry_logic": "行业向好"})
    ctx.set("keep_posts", [
        {"title": "测试帖", "author": "测试者", "content": "这是测试内容", "likes": 10, "comments": 5, "reposts": 2}
    ])
    ctx.set("quote", {"pe_ttm": 20.0})
    ctx.set("chart_paths", {"radar": "/tmp/radar.png"})
    ctx.set("md_path", "/tmp/report.md")

    result = skill.run(ctx)

    # skill 不修改 ctx.output 新 key，返回原 ctx
    assert result is ctx

    stock_dir = tmp_path / "10-Stocks" / "测试股"
    assert stock_dir.exists()

    # 深度解读
    deep_path = stock_dir / "20260606-深度解读.md"
    assert deep_path.exists()
    content = deep_path.read_text(encoding="utf-8")
    assert "综合评分" in content
    assert "营收增长" in content
    assert "估值偏高" in content
    assert "跨源摘要内容" in content
    assert "行业向好" in content

    # 核心数据
    data_path = stock_dir / "20260606-核心数据.md"
    assert data_path.exists()
    content = data_path.read_text(encoding="utf-8")
    assert "20.0" in content
    assert "radar" in content
    assert "report.md" in content

    # 精选帖子
    posts_path = stock_dir / "20260606-精选帖子.md"
    assert posts_path.exists()
    content = posts_path.read_text(encoding="utf-8")
    assert "测试帖" in content
    assert "测试者" in content
    assert "这是测试内容" in content

    # MOC
    moc_path = stock_dir / "MOC.md"
    assert moc_path.exists()
    content = moc_path.read_text(encoding="utf-8")
    assert "20260606-深度解读" in content
    assert "20260606-核心数据" in content
    assert "20260606-精选帖子" in content


def test_knowledge_persistence_skips_without_stock_name(tmp_path):
    skill = KnowledgePersistenceSkill(vault_root=str(tmp_path))
    ctx = SkillContext(input={})
    result = skill.run(ctx)
    assert result is ctx
    assert not (tmp_path / "10-Stocks").exists()
