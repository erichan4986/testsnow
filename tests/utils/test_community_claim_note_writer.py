import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from claim_verification import build_claim_verification_plan
from community_claim_note_writer import (
    extract_claims_from_cached_posts,
    write_cached_community_claim_note,
)


def _post(**kwargs):
    data = {
        "title": "黑芝麻智能讨论",
        "content": "",
        "url": "https://xueqiu.com/1/2",
        "like_count": 0,
        "comment_count": 0,
        "repost_count": 0,
        "_track": "featured",
    }
    data.update(kwargs)
    return data


def test_extract_claims_from_cached_posts_skips_ui_noise():
    posts = [
        _post(
            content=(
                "扫码下载雪球App。"
                "C1296将搭载在10万以内电动小车上，可能带来量产增量。"
                "应付：0 雪球币。"
            )
        )
    ]
    claims = extract_claims_from_cached_posts(posts, "黑芝麻智能", max_posts=5, max_claims=5)
    assert len(claims) == 1
    assert claims[0]["claim_status"] == "unverified_claim"
    assert "C1296" in claims[0]["claim_text"]
    assert "雪球币" not in claims[0]["claim_text"]
    assert "product_progress" in claims[0]["topics"]


def test_extract_claims_caps_posts_and_claims_by_interaction():
    posts = [
        _post(content="低互动帖子称A2000U获得认证。", like_count=1, comment_count=1, repost_count=0, url="https://xueqiu.com/1/low"),
        _post(content="高互动帖子称C1236进入比亚迪供应链。另有观点称毛利率承压。", like_count=20, comment_count=5, repost_count=1, url="https://xueqiu.com/1/high"),
    ]
    claims = extract_claims_from_cached_posts(posts, "黑芝麻智能", max_posts=1, max_claims=1)
    assert len(claims) == 1
    assert "高互动" in claims[0]["claim_text"] or "C1236" in claims[0]["claim_text"]


def test_extract_claims_skips_question_or_title_like_fragments():
    posts = [
        _post(
            content=(
                "A2000还有多少隐藏彩蛋？"
                "华山A2000深度解析和投资价值讨论。"
                "C1236已经获得比亚迪定点，今年处于产能爬坡阶段。"
            )
        )
    ]
    claims = extract_claims_from_cached_posts(posts, "黑芝麻智能", max_posts=5, max_claims=5)
    assert [c["claim_text"] for c in claims] == ["C1236已经获得比亚迪定点，今年处于产能爬坡阶段"]


def test_extract_claims_keeps_verifiable_financial_and_product_claims():
    posts = [
        _post(
            content=(
                "A2000U获得ASIL-D认证，后续量产节奏值得跟踪。"
                "2025年毛利率为41%，但短期盈利仍有压力。"
            )
        )
    ]
    claims = extract_claims_from_cached_posts(posts, "黑芝麻智能", max_posts=5, max_claims=5)
    texts = [c["claim_text"] for c in claims]
    assert "A2000U获得ASIL-D认证，后续量产节奏值得跟踪" in texts
    assert "2025年毛利率为41%，但短期盈利仍有压力" in texts


def test_write_cached_community_claim_note_dry_run_does_not_touch_disk(tmp_path):
    posts = [_post(content="社区称C1236进入比亚迪供应链。")]
    result = write_cached_community_claim_note(
        stock_name="黑芝麻智能",
        stock_code="02533",
        posts=posts,
        base_dir=tmp_path,
        date_str="20260614",
        dry_run=True,
    )
    assert result["status"] == "dry_run"
    assert result["claim_count"] == 1
    assert not (tmp_path / "10-Stocks").exists()


def test_write_cached_community_claim_note_creates_plan_readable_note(tmp_path):
    posts = [
        _post(content="社区称A2000U获得ASIL-D认证，是后续量产催化。", url="https://xueqiu.com/1/100"),
        _post(content="也有观点担心价格战加剧，毛利率承压。", url="https://xueqiu.com/1/101"),
    ]
    result = write_cached_community_claim_note(
        stock_name="黑芝麻智能",
        stock_code="02533",
        posts=posts,
        base_dir=tmp_path,
        date_str="20260614",
        dry_run=False,
    )
    assert result["status"] == "written"
    assert result["claim_count"] >= 2
    path = Path(result["path"])
    assert path.exists()

    plan = build_claim_verification_plan("黑芝麻智能", tmp_path)
    assert len(plan.low_credit_claims) == result["claim_count"]
    assert all(c.claim_status == "unverified_claim" for c in plan.low_credit_claims)
    assert all(c.source_credit == 35 for c in plan.low_credit_claims)


def test_write_cached_community_claim_note_skips_existing_without_overwrite(tmp_path):
    posts = [_post(content="社区称C1236进入比亚迪供应链。")]
    first = write_cached_community_claim_note("黑芝麻智能", "02533", posts, tmp_path, "20260614", dry_run=False)
    second = write_cached_community_claim_note("黑芝麻智能", "02533", posts, tmp_path, "20260614", dry_run=False)
    assert first["status"] == "written"
    assert second["status"] == "skipped_existing"
