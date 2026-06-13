import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from claim_verification import (
    ClaimCandidate,
    ClaimVerification,
    ClaimVerificationPlan,
    build_claim_verification_plan,
    claim_verification_plan_to_dict,
    extract_legacy_social_claims_from_body,
    parse_frontmatter,
)


def write_note(path: Path, frontmatter: str, body: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")
    return path


def test_parse_frontmatter_yaml(tmp_path):
    note = write_note(
        tmp_path / "evidence.md",
        "stock: 黑芝麻智能\nsource_type: company_official\nsource_credit: 85",
        "# Body\ncontent",
    )
    meta, body = parse_frontmatter(note)
    assert meta["stock"] == "黑芝麻智能"
    assert meta["source_credit"] == 85
    assert "# Body" in body


def test_parse_frontmatter_json(tmp_path):
    note = write_note(
        tmp_path / "social.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35}',
        "# Body\ncontent",
    )
    meta, body = parse_frontmatter(note)
    assert meta["stock"] == "黑芝麻智能"
    assert meta["source_type"] == "social_discussion"
    assert meta["source_credit"] == 35


def test_parse_frontmatter_no_frontmatter(tmp_path):
    note = tmp_path / "plain.md"
    note.write_text("# No frontmatter\ncontent", encoding="utf-8")
    meta, body = parse_frontmatter(note)
    assert meta == {}
    assert "# No frontmatter" in body


def test_parse_frontmatter_malformed(tmp_path):
    note = write_note(
        tmp_path / "bad.md",
        "stock: [unclosed",
        "body",
    )
    with pytest.raises(Exception):
        parse_frontmatter(note)


def test_parse_frontmatter_without_pyyaml(monkeypatch, tmp_path):
    note = write_note(
        tmp_path / "social.json.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion"}',
        "body",
    )
    monkeypatch.setattr("claim_verification._YAML_AVAILABLE", False)
    meta, body = parse_frontmatter(note)
    assert meta["stock"] == "黑芝麻智能"


def test_moc_md_skipped(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    write_note(
        stock_dir / "MOC.md",
        '{"source_type": "social_discussion", "source_credit": 35}',
        "# Index",
    )
    write_note(
        stock_dir / "other.md",
        '{"source_type": "social_discussion", "source_credit": 35}',
        "# Social",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    skipped_mocs = [s for s in plan.skipped_files if s["reason"] == "moc_index"]
    assert len(skipped_mocs) == 1
    assert "MOC.md" in skipped_mocs[0]["path"]
    assert len(plan.low_credit_claims) == 1


def test_moc_md_lowercase_skipped(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    write_note(
        stock_dir / "moc.md",
        '{"source_type": "social_discussion", "source_credit": 35}',
        "# Index",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    skipped_mocs = [s for s in plan.skipped_files if s["reason"] == "moc_index"]
    assert len(skipped_mocs) == 1
    assert "moc.md" in skipped_mocs[0]["path"]


def test_social_no_claims_creates_stub(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    write_note(
        stock_dir / "20260612-深度分析.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "深度分析"}',
        "# 深度分析\n正文",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.low_credit_claims) == 1
    claim = plan.low_credit_claims[0]
    assert claim.extraction_method == "legacy_social_stub"
    assert claim.claim_status == "unverified_claim"
    assert "深度分析" in claim.claim_text


def test_social_body_confirmed_facts_extracted_as_unverified(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    body = """## 原始数据
- **confirmed_facts**: 1 条
  - 公司主业稳健，新业务提供长期增长动力
- **announcements**: 2 条
"""
    write_note(
        stock_dir / "20260612-深度分析.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "深度分析"}',
        body,
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    claims = [c for c in plan.low_credit_claims if c.extraction_method == "legacy_social_body_rule"]
    assert len(claims) == 1
    claim = claims[0]
    assert claim.claim_status == "unverified_claim"
    assert claim.verification_status == "market_opinion"
    assert claim.source_credit == 35
    assert claim.source_type == "social_discussion"
    assert "疑似事实线索" in claim.claim_text
    assert "确认事实" not in claim.claim_text


def test_reports_bullets_extract_multiple_low_credit_claims(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    body = """## 原始数据
- **reports**: 5 条
  - 2026年一季报点评：业绩符合市场预期，仿生机器人等新兴产业蓄势待发
  - 2025年净利润较快增长，拓展机器人、服务器液冷等新领域
  - 三花智控：2025Q4毛利率显著提升，积极布局机器人、储能等新兴业务
"""
    write_note(
        stock_dir / "20260612-最新研报.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "最新研报"}',
        body,
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    claims = [c for c in plan.low_credit_claims if c.extraction_method == "legacy_social_body_rule"]
    assert len(claims) == 3
    texts = [c.claim_text for c in claims]
    assert any("研报线索" in t for t in texts)
    assert any("仿生机器人" in t for t in texts)
    assert any("服务器液冷" in t for t in texts)


def test_announcements_bullets_extract_low_credit_claims(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    body = """## 原始数据
- **announcements**: 2 条
  - 黑芝麻智能：第八届董事会第十七次临时会议决议公告
  - 黑芝麻智能：关于召开2025年度股东会的通知
"""
    write_note(
        stock_dir / "20260612-公司公告.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "公司公告"}',
        body,
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    claims = [c for c in plan.low_credit_claims if c.extraction_method == "legacy_social_body_rule"]
    assert len(claims) == 2
    assert all("公告线索" in c.claim_text for c in claims)


def test_body_extracted_claims_preserve_social_metadata(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    body = """## 原始数据
- **reports**: 1 条
  - 业绩符合预期
"""
    write_note(
        stock_dir / "20260612-最新研报.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "source_platforms": ["雪球", "知乎"], "category": "最新研报"}',
        body,
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    claims = [c for c in plan.low_credit_claims if c.extraction_method == "legacy_social_body_rule"]
    assert len(claims) == 1
    c = claims[0]
    assert c.source_type == "social_discussion"
    assert c.source_credit == 35
    assert c.verification_status == "market_opinion"
    assert c.claim_status == "unverified_claim"
    assert c.extraction_method == "legacy_social_body_rule"
    assert c.source_platforms == ["雪球", "知乎"]


def test_body_extracted_claims_never_high_credit(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    evidence_dir = stock_dir / "evidence"
    write_note(
        evidence_dir / "official.md",
        """stock: 黑芝麻智能
source_type: company_official
source_credit: 85
verification_status: primary_source
title: 官方
claims:
  - claim_text: 官方信息
    claim_status: fact_candidate
""",
        "body",
    )
    body = """## 原始数据
- **confirmed_facts**: 1 条
  - 公司发布官方信息
"""
    write_note(
        stock_dir / "20260612-深度分析.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "深度分析"}',
        body,
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.high_credit_claims) == 1
    assert all(c.source_credit <= 35 for c in plan.low_credit_claims)
    assert all(c.extraction_method == "legacy_social_body_rule" for c in plan.low_credit_claims)


def test_empty_counts_without_child_bullets_do_not_create_claims(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    body = """## 原始数据
- **confirmed_facts**: 1 条
- **inferences**: 0 条
"""
    write_note(
        stock_dir / "20260612-深度分析.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "深度分析"}',
        body,
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    body_claims = [c for c in plan.low_credit_claims if c.extraction_method == "legacy_social_body_rule"]
    assert len(body_claims) == 0
    assert len(plan.low_credit_claims) == 1
    assert plan.low_credit_claims[0].extraction_method == "legacy_social_stub"


def test_noisy_bullets_filtered(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    body = """## 原始数据
- **reports**: 5 条
  - *AI分析暂缺*
  - [[20260612-深度分析]]
  - 5 条
  -
  - -
  - 短期线索1
  - 有效内容线索
"""
    write_note(
        stock_dir / "20260612-最新研报.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "最新研报"}',
        body,
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    claims = [c for c in plan.low_credit_claims if c.extraction_method == "legacy_social_body_rule"]
    assert len(claims) == 1
    assert claims[0].claim_text == "黑芝麻智能研报线索：有效内容线索"


def test_global_max_eight_cap_after_priority(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    reports = "\n".join([f"  - 研报内容示例{i}" for i in range(1, 7)])
    announcements = "\n".join([f"  - 公告内容示例{i}" for i in range(1, 7)])
    body = f"""## 原始数据
- **reports**: 6 条
{reports}
- **announcements**: 6 条
{announcements}
"""
    write_note(
        stock_dir / "20260612-最新研报.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "最新研报"}',
        body,
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    claims = [c for c in plan.low_credit_claims if c.extraction_method == "legacy_social_body_rule"]
    assert len(claims) == 8
    assert all("研报" in c.claim_text for c in claims[:5])
    assert all("公告" in c.claim_text for c in claims[5:])


def test_frontmatter_claims_take_precedence_over_body(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    body = """## 原始数据
- **reports**: 1 条
  - 研报内容线索
"""
    write_note(
        stock_dir / "20260612-最新研报.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "最新研报", "claims": [{"claim_text": "frontmatter claim"}]}',
        body,
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.low_credit_claims) == 1
    assert plan.low_credit_claims[0].claim_text == "frontmatter claim"
    assert plan.low_credit_claims[0].extraction_method == "legacy_social_frontmatter_claim"


def test_fallback_stub_when_no_body_claims(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    write_note(
        stock_dir / "20260612-最新研报.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "最新研报"}',
        "# 最新研报\n无结构数据。",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.low_credit_claims) == 1
    assert plan.low_credit_claims[0].extraction_method == "legacy_social_stub"


def test_topic_inference_for_body_claims(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    body = """## 原始数据
- **reports**: 3 条
  - 仿生机器人项目进展
  - 服务器液冷业务布局
  - 净利润同比增长
"""
    write_note(
        stock_dir / "20260612-最新研报.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "最新研报"}',
        body,
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    claims = [c for c in plan.low_credit_claims if c.extraction_method == "legacy_social_body_rule"]
    assert len(claims) == 3
    topics = [c.topics for c in claims]
    assert any("product_progress" in t for t in topics)
    assert any("earnings_business" in t for t in topics)


def test_sanhua_real_shaped_latest_report_yields_substantive_claims(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "三花智控"
    body = """## 原始数据
- **reports**: 5 条
  - 2026年一季报点评：业绩符合市场预期，仿生机器人等新兴产业蓄势待发
  - 2025年净利润较快增长，拓展机器人、服务器液冷等新领域
  - 三花智控：2025Q4毛利率显著提升，积极布局机器人、储能等新兴业务
  - 业绩符合预期，盈利能力持续提升
  - 2025年年报点评：汽零&家电提质增效稳步增长，仿生机器人等新兴产业蓄势待发
"""
    write_note(
        stock_dir / "20260612-最新研报.md",
        '{"stock": "三花智控", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "最新研报"}',
        body,
    )
    plan = build_claim_verification_plan("三花智控", root)
    claims = [c for c in plan.low_credit_claims if c.extraction_method == "legacy_social_body_rule"]
    assert len(claims) == 5
    texts = " ".join(c.claim_text for c in claims)
    assert "仿生机器人" in texts
    assert "服务器液冷" in texts
    assert "净利润" in texts


def test_body_extracted_claims_can_be_verified_by_evidence(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    evidence_dir = stock_dir / "evidence"
    write_note(
        evidence_dir / "official.md",
        """stock: 黑芝麻智能
source_type: company_official
source_credit: 85
verification_status: primary_source
title: 官方
claims:
  - claim_text: 黑芝麻智能拓展服务器液冷业务
    claim_status: fact_candidate
    topics:
      - product_progress
""",
        "body",
    )
    body = """## 原始数据
- **reports**: 1 条
  - 黑芝麻智能拓展服务器液冷业务
"""
    write_note(
        stock_dir / "20260612-最新研报.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "最新研报"}',
        body,
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.verifications) == 1
    v = plan.verifications[0]
    assert v.action in ("verified", "supported", "needs_review")
    assert len(v.verified_by) >= 1


def test_technical_notes_skipped_without_stub(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "三花智控"
    body = """## 原始数据
- **close**: 46.3
- **rsi_14**: 27.39
"""
    write_note(
        stock_dir / "20260612-技术指标.md",
        '{"stock": "三花智控", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "技术指标"}',
        body,
    )
    plan = build_claim_verification_plan("三花智控", root)
    assert len(plan.low_credit_claims) == 0
    assert any(s["reason"] == "technical_note_skipped" for s in plan.skipped_files)


def test_technical_notes_skipped_by_data_source(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "三花智控"
    body = """## 原始数据
- **close**: 46.3
"""
    write_note(
        stock_dir / "20260612-技术指标.md",
        '{"stock": "三花智控", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "其他", "data_source": "mootdx+stockstats"}',
        body,
    )
    plan = build_claim_verification_plan("三花智控", root)
    assert len(plan.low_credit_claims) == 0
    assert any(s["reason"] == "technical_note_skipped" for s in plan.skipped_files)


def test_older_notes_without_social_frontmatter_skipped(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "三花智控"
    body = """## 原始数据
- **reports**: 1 条
  -  older report content
"""
    write_note(
        stock_dir / "20260526-最新研报.md",
        '{"stock": "三花智控", "category": "最新研报", "data_source": "akshare/东财"}',
        body,
    )
    plan = build_claim_verification_plan("三花智控", root)
    assert len(plan.low_credit_claims) == 0
    assert any(s["reason"] == "unknown_source_type" for s in plan.skipped_files)


def test_position_suggestion_not_extracted(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    body = """## 原始数据
- **position_suggestion**: 持有
- **reports**: 1 条
  - 研报内容线索
"""
    write_note(
        stock_dir / "20260612-深度分析.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "深度分析"}',
        body,
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    claims = [c for c in plan.low_credit_claims if c.extraction_method == "legacy_social_body_rule"]
    assert len(claims) == 1
    assert "持有" not in claims[0].claim_text
    assert claims[0].claim_text == "黑芝麻智能研报线索：研报内容线索"


def test_body_extracted_social_claims_never_verify_other_social_claims(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    body_a = """## 原始数据
- **reports**: 1 条
  - 公司拓展机器人业务
"""
    body_b = """## 原始数据
- **reports**: 1 条
  - 公司拓展机器人业务
"""
    write_note(
        stock_dir / "20260612-a.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "最新研报"}',
        body_a,
    )
    write_note(
        stock_dir / "20260612-b.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "最新研报"}',
        body_b,
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.low_credit_claims) == 2
    assert len(plan.high_credit_claims) == 0
    for v in plan.verifications:
        assert v.action == "unverified"


def test_direct_extract_legacy_social_claims_from_body():
    meta = {
        "stock": "三花智控",
        "source_type": "social_discussion",
        "source_credit": 35,
        "verification_status": "market_opinion",
        "source_platforms": ["雪球", "知乎"],
        "category": "最新研报",
    }
    body = """## 原始数据
- **reports**: 2 条
  - 2026年一季报点评：业绩符合市场预期，仿生机器人等新兴产业蓄势待发
  - 2025年净利润较快增长
"""
    claims = extract_legacy_social_claims_from_body("三花智控", meta, body, "test.md")
    assert len(claims) == 2
    assert all(c.source_credit == 35 for c in claims)
    assert all(c.claim_status == "unverified_claim" for c in claims)


def test_direct_extract_legacy_social_claims_from_body_empty(tmp_path):
    meta = {
        "stock": "三花智控",
        "source_type": "social_discussion",
        "source_credit": 35,
        "verification_status": "market_opinion",
    }
    body = """## 原始数据
- **confirmed_facts**: 0 条
"""
    claims = extract_legacy_social_claims_from_body("三花智控", meta, body, "test.md")
    assert len(claims) == 0


def test_social_company_announcement_category_stays_low_credit(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    write_note(
        stock_dir / "20260612-公司公告.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "公司公告"}',
        "# 公司公告",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.high_credit_claims) == 0
    assert len(plan.low_credit_claims) == 1
    assert plan.low_credit_claims[0].source_type == "social_discussion"


def test_high_credit_evidence_enters_high_bucket(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    evidence_dir = stock_dir / "evidence"
    write_note(
        evidence_dir / "20260612-company-official-asil.md",
        """stock: 黑芝麻智能
source_type: company_official
source_credit: 85
verification_status: primary_source
title: 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证
url: https://www.blacksesame.com/zh/list_10/972.html
claims:
  - claim_text: 黑芝麻智能华山A2000U、A2000X芯片获得ISO 26262 ASIL-D功能安全认证
    claim_status: fact_candidate
    topics:
      - product_progress
""",
        "# Evidence",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.high_credit_claims) == 1
    assert len(plan.low_credit_claims) == 0
    assert plan.high_credit_claims[0].source_credit == 85


def test_social_claim_enters_low_bucket(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    write_note(
        stock_dir / "20260612-深度分析.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "claims": [{"claim_text": "社区认为A2000U安全认证是量产催化"}]}',
        "# 深度分析",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.high_credit_claims) == 0
    assert len(plan.low_credit_claims) == 1
    assert plan.low_credit_claims[0].source_credit == 35


def test_social_frontmatter_claim_defaults_to_unverified_market_opinion(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    write_note(
        stock_dir / "20260612-深度分析.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "claims": [{"claim_text": "社区认为A2000U安全认证是量产催化"}]}',
        "# 深度分析",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.low_credit_claims) == 1
    claim = plan.low_credit_claims[0]
    assert claim.claim_status == "unverified_claim"
    assert claim.verification_status == "market_opinion"
    assert claim.extraction_method == "legacy_social_frontmatter_claim"


def test_legacy_social_with_claims_never_high_credit(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    write_note(
        stock_dir / "20260612-深度分析.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "claims": [{"claim_text": "社区观点"}]}',
        "# 深度分析",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.high_credit_claims) == 0
    assert len(plan.low_credit_claims) == 1


def test_social_claim_never_verifies_another_social_claim(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    write_note(
        stock_dir / "20260612-a.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "claims": [{"claim_text": "A2000U获得ASIL-D认证"}]}',
        "# A",
    )
    write_note(
        stock_dir / "20260612-b.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "claims": [{"claim_text": "A2000U获得ASIL-D认证"}]}',
        "# B",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.low_credit_claims) == 2
    assert len(plan.high_credit_claims) == 0
    for v in plan.verifications:
        assert v.action == "unverified"


def test_high_credit_verifies_matching_social_claim(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    evidence_dir = stock_dir / "evidence"
    write_note(
        evidence_dir / "20260612-company-official-asil.md",
        """stock: 黑芝麻智能
source_type: company_official
source_credit: 85
verification_status: primary_source
title: 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证
url: https://www.blacksesame.com/zh/list_10/972.html
claims:
  - claim_text: 黑芝麻智能华山A2000U、A2000X芯片获得ISO 26262 ASIL-D功能安全认证
    claim_status: fact_candidate
    topics:
      - product_progress
""",
        "# Evidence",
    )
    write_note(
        stock_dir / "20260612-深度分析.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "claims": [{"claim_text": "A2000U获得ASIL-D认证，是量产催化"}]}',
        "# 深度分析",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.verifications) == 1
    v = plan.verifications[0]
    assert v.action == "verified"
    assert v.confidence >= 70
    assert len(v.verified_by) == 1
    reason_text = " ".join(v.reasons)
    assert "ASIL-D" in reason_text or "A2000U" in reason_text or "a2000u" in reason_text or "asil-d" in reason_text


def test_generic_term_only_downgrades_to_needs_review(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    evidence_dir = stock_dir / "evidence"
    write_note(
        evidence_dir / "20260612-company-official-generic.md",
        """stock: 黑芝麻智能
source_type: company_official
source_credit: 85
verification_status: primary_source
title: 黑芝麻智能发布芯片
claims:
  - claim_text: 黑芝麻智能发布芯片
    claim_status: fact_candidate
    topics:
      - product_progress
""",
        "# Evidence",
    )
    write_note(
        stock_dir / "20260612-深度分析.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "claims": [{"claim_text": "芯片行业有增长"}]}',
        "# 深度分析",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.verifications) == 1
    v = plan.verifications[0]
    assert v.action == "needs_review"
    assert v.confidence == 0


def test_medium_credit_produces_supported_not_verified(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    evidence_dir = stock_dir / "evidence"
    write_note(
        evidence_dir / "20260612-broker-research.md",
        """stock: 黑芝麻智能
source_type: broker_research
source_credit: 65
verification_status: professional_analysis
title: 黑芝麻智能研报
claims:
  - claim_text: 黑芝麻智能A2000U获得ASIL-D认证
    claim_status: professional_analysis
    topics:
      - product_progress
""",
        "# Research",
    )
    write_note(
        stock_dir / "20260612-深度分析.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "claims": [{"claim_text": "A2000U获得ASIL-D认证"}]}',
        "# 深度分析",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.verifications) == 1
    v = plan.verifications[0]
    assert v.action == "supported"
    assert v.confidence <= 69
    assert v.confidence >= 40


def test_unrelated_claim_remains_unverified(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    evidence_dir = stock_dir / "evidence"
    write_note(
        evidence_dir / "20260612-company-official-asil.md",
        """stock: 黑芝麻智能
source_type: company_official
source_credit: 85
verification_status: primary_source
title: 黑芝麻智能华山A2000U获ASIL-D认证
claims:
  - claim_text: 黑芝麻智能华山A2000U获得ASIL-D认证
    claim_status: fact_candidate
    topics:
      - product_progress
""",
        "# Evidence",
    )
    write_note(
        stock_dir / "20260612-深度分析.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "claims": [{"claim_text": "竞争对手发布新产品"}]}',
        "# 深度分析",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.verifications) == 1
    v = plan.verifications[0]
    assert v.action == "unverified"
    assert v.confidence < 40


def test_malformed_frontmatter_recorded_in_skipped_files(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    bad = write_note(
        stock_dir / "bad.md",
        "stock: [unclosed",
        "body",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.skipped_files) == 1
    assert plan.skipped_files[0]["reason"] == "malformed_frontmatter"
    assert str(bad) in plan.skipped_files[0]["path"]


def test_plan_converts_to_plain_dict(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    evidence_dir = stock_dir / "evidence"
    write_note(
        evidence_dir / "20260612-company-official-asil.md",
        """stock: 黑芝麻智能
source_type: company_official
source_credit: 85
verification_status: primary_source
title: 黑芝麻智能华山A2000U获ASIL-D认证
claims:
  - claim_text: 黑芝麻智能华山A2000U获得ASIL-D认证
    claim_status: fact_candidate
""",
        "# Evidence",
    )
    write_note(
        stock_dir / "20260612-深度分析.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "claims": [{"claim_text": "A2000U获得ASIL-D认证"}]}',
        "# 深度分析",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    d = claim_verification_plan_to_dict(plan)
    assert isinstance(d, dict)
    assert d["stock"] == "黑芝麻智能"
    assert isinstance(d["high_credit_claims"], list)
    assert isinstance(d["low_credit_claims"], list)
    assert isinstance(d["verifications"], list)
    assert isinstance(d["skipped_files"], list)
    assert isinstance(d["high_credit_claims"][0], dict)


def _build_plan_with_actions(tmp_path):
    """Helper returning a plan with verified, supported, unverified, and needs_review claims."""
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "三花智控"
    evidence_dir = stock_dir / "evidence"
    write_note(
        evidence_dir / "official.md",
        """stock: 三花智控
source_type: company_official
source_credit: 85
verification_status: primary_source
title: 三花智控官方业务介绍
claims:
  - claim_text: 三花智控积极拓展机器人与服务器液冷等新兴领域
    claim_status: fact_candidate
    topics:
      - product_progress
""",
        "# Evidence",
    )
    write_note(
        evidence_dir / "broker.md",
        """stock: 三花智控
source_type: broker_research
source_credit: 65
verification_status: professional_analysis
title: 三花智控研报覆盖
claims:
  - claim_text: 三花智控储能业务布局初见成效
    claim_status: professional_analysis
    topics:
      - product_progress
""",
        "# Research",
    )
    body = """## 原始数据
- **reports**: 4 条
  - 三花智控2026年一季报点评：业绩符合市场预期，仿生机器人等新兴产业蓄势待发
  - 三花智控2025年净利润较快增长，拓展机器人、服务器液冷等新领域
  - 三花智控：2025Q4毛利率显著提升，积极布局机器人、储能等新兴业务
  - 三花智控业绩符合预期，盈利能力持续提升
- **announcements**: 1 条
  - 三花智控：关于召开2025年度股东会的通知
"""
    write_note(
        stock_dir / "20260612-最新研报.md",
        '{"stock": "三花智控", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "最新研报"}',
        body,
    )
    return build_claim_verification_plan("三花智控", root)


def test_summarize_claim_verification_plan_returns_counts(tmp_path):
    plan = _build_plan_with_actions(tmp_path)
    from claim_verification import summarize_claim_verification_plan

    summary = summarize_claim_verification_plan(plan)
    assert isinstance(summary, dict)
    assert summary["stock"] == "三花智控"
    assert summary["counts"]["high_credit_claims"] == 1
    assert summary["counts"]["low_credit_claims"] == 5
    assert summary["counts"]["verified"] >= 1
    assert summary["counts"]["supported"] >= 0
    assert summary["counts"]["unverified"] >= 1
    assert "skipped_files" in summary["counts"]


def test_summarize_strips_uncitable_metadata(tmp_path):
    plan = _build_plan_with_actions(tmp_path)
    from claim_verification import summarize_claim_verification_plan

    summary = summarize_claim_verification_plan(plan)
    text = str(summary)
    assert "url" not in text
    assert "source_file" not in text
    assert "claim_id" not in text
    assert "'verified_by'" not in text
    for bucket in ("verified_claims", "supported_claims", "unverified_claims"):
        for row in summary.get(bucket, []):
            assert "url" not in row
            assert "source_file" not in row
            assert "claim_id" not in row
            assert "verified_by" not in row


def test_summarize_resolves_verified_by_titles(tmp_path):
    plan = _build_plan_with_actions(tmp_path)
    from claim_verification import summarize_claim_verification_plan

    summary = summarize_claim_verification_plan(plan)
    verified = summary.get("verified_claims", [])
    assert len(verified) > 0
    for row in verified:
        assert "verified_by_titles" in row
        titles = row["verified_by_titles"]
        assert isinstance(titles, list)
        assert all(isinstance(t, str) for t in titles)
        # Source title must be resolvable for matching verified claims
        assert any("三花智控" in t for t in titles)


def test_summarize_caps_claims(tmp_path):
    plan = _build_plan_with_actions(tmp_path)
    from claim_verification import summarize_claim_verification_plan

    summary = summarize_claim_verification_plan(plan, max_verified=2, max_supported=1, max_unverified=1)
    assert len(summary["verified_claims"]) <= 2
    assert len(summary["supported_claims"]) <= 1
    assert len(summary["unverified_claims"]) <= 1


def test_summarize_truncates_long_claim_text(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "三花智控"
    evidence_dir = stock_dir / "evidence"
    write_note(
        evidence_dir / "official.md",
        """stock: 三花智控
source_type: company_official
source_credit: 85
verification_status: primary_source
title: 三花智控官方
claims:
  - claim_text: """ + "拓展机器人业务。" * 100 + """
    claim_status: fact_candidate
    topics:
      - product_progress
""",
        "# Evidence",
    )
    body = """## 原始数据
- **reports**: 1 条
  - """ + "拓展机器人业务。" * 100 + """
"""
    write_note(
        stock_dir / "20260612-最新研报.md",
        '{"stock": "三花智控", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion", "category": "最新研报"}',
        body,
    )
    plan = build_claim_verification_plan("三花智控", root)
    from claim_verification import summarize_claim_verification_plan

    summary = summarize_claim_verification_plan(plan, max_chars=1200)
    text = str(summary)
    assert len(text) <= 1500  # allow some header overhead
    verified = summary.get("verified_claims", [])
    assert len(verified) <= 1
    if verified:
        assert len(verified[0]["claim_text"]) < 400


def test_summarize_respects_max_chars(tmp_path):
    plan = _build_plan_with_actions(tmp_path)
    from claim_verification import summarize_claim_verification_plan

    small = summarize_claim_verification_plan(plan, max_chars=500)
    large = summarize_claim_verification_plan(plan, max_chars=2500)
    assert len(str(small)) < len(str(large))


def test_dry_run_false_raises():
    from claim_verification import build_claim_verification_plan

    with pytest.raises(NotImplementedError, match="Phase 4 only supports dry_run=True"):
        build_claim_verification_plan("黑芝麻智能", "/tmp/any", dry_run=False)


def test_all_test_data_under_tmp_path(tmp_path):
    root = tmp_path / "knowledge"
    stock_dir = root / "10-Stocks" / "黑芝麻智能"
    write_note(
        stock_dir / "20260612-深度分析.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "verification_status": "market_opinion"}',
        "# 深度分析",
    )
    plan = build_claim_verification_plan("黑芝麻智能", root)
    assert len(plan.low_credit_claims) == 1
    assert Path(plan.low_credit_claims[0].source_file).parts[0] == "knowledge"
    assert str(tmp_path) not in plan.low_credit_claims[0].source_file
