import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from fresh_social_claim_intake import (
    DEFAULT_MAX_CLAIMS,
    DEFAULT_MAX_CLAIMS_PER_PROVIDER,
    DEFAULT_MAX_RAW_ITEMS,
    _classify_provider_status,
    _is_community_like_url,
    _reject_negative_signals,
    _render_note,
    _strip_citations,
    build_provider_record,
    build_url_reader_url,
    extract_claims_from_provider_records,
    write_fresh_social_claim_note,
)


def test_module_import_is_pure_and_does_not_access_network():
    # Module import must succeed without network calls or optional CLI imports.
    assert DEFAULT_MAX_RAW_ITEMS == 20
    assert DEFAULT_MAX_CLAIMS_PER_PROVIDER == 5
    assert DEFAULT_MAX_CLAIMS == 10


def test_build_url_reader_uses_jina_reader_endpoint():
    url = build_url_reader_url("https://xueqiu.com/1/123")
    assert url == "https://r.jina.ai/https://xueqiu.com/1/123"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://xueqiu.com/1/123", True),
        ("https://guba.eastmoney.com/oa/300777.html", True),
        ("https://weibo.com/u/123", True),
        ("https://m.weibo.cn/detail/123", True),
        ("https://www.cninfo.com.cn/announcement/", False),
        ("https://data.eastmoney.com/report/", False),
        ("https://reportapi.eastmoney.com/list", False),
        ("https://pdf.dfcfw.com/pdf/H3_123.pdf", False),
        ("https://finance.sina.com.cn/stock/", False),
        ("https://www.stcn.com/article/", False),
        ("https://www.cls.cn/detail/123", False),
        ("https://www.gelonghui.com/p/123", False),
        ("https://xueqiu.com/1/123", True),
    ],
)
def test_url_domain_filter_rejects_official_news_research(url, expected):
    assert _is_community_like_url(url) is expected


def test_community_like_url_rejects_eastmoney_non_forum():
    assert _is_community_like_url("https://finance.eastmoney.com/a/202501011234.html") is False
    assert _is_community_like_url("https://data.eastmoney.com/report/stock.jshtml") is False
    assert _is_community_like_url("https://guba.eastmoney.com/oa/300777.html") is True


def test_gate_requires_stock_reference_and_predicate_and_community_marker():
    records = [
        {
            "status": "ok",
            "url": "https://guba.eastmoney.com/oa/300777.html",
            "text": "我认为中简科技的收入下降了，研发费用也增长不少。",
            "platform": "股吧",
        }
    ]
    claims = extract_claims_from_provider_records(records, "中简科技", "300777")
    assert len(claims) == 1
    assert claims[0]["claim_status"] == "unverified_claim"
    assert "中简科技" in claims[0]["claim_text"]


def test_gate_rejects_without_community_marker():
    records = [
        {
            "status": "ok",
            "url": "https://guba.eastmoney.com/oa/300777.html",
            "text": "中简科技收入下降约50%，研发费用同比增长。",
            "platform": "股吧",
        }
    ]
    claims = extract_claims_from_provider_records(records, "中简科技", "300777")
    assert len(claims) == 0


def test_gate_rejects_without_predicate():
    records = [
        {
            "status": "ok",
            "url": "https://guba.eastmoney.com/oa/300777.html",
            "text": "我觉得中简科技这家公司还不错。",
            "platform": "股吧",
        }
    ]
    claims = extract_claims_from_provider_records(records, "中简科技", "300777")
    assert len(claims) == 0


def test_gate_rejects_without_stock_reference():
    records = [
        {
            "status": "ok",
            "url": "https://guba.eastmoney.com/oa/300777.html",
            "text": "我认为这家公司的收入下降了。",
            "platform": "股吧",
        }
    ]
    claims = extract_claims_from_provider_records(records, "中简科技", "300777")
    assert len(claims) == 0


def test_gate_rejects_seo_news_text():
    records = [
        {
            "status": "ok",
            "url": "https://guba.eastmoney.com/oa/300777.html",
            "text": "我认为中简科技的收入下降了。点击阅读全文查看更多相关股票。",
            "platform": "股吧",
        }
    ]
    claims = extract_claims_from_provider_records(records, "中简科技", "300777")
    assert len(claims) == 0


def test_gate_rejects_pure_sentiment():
    records = [
        {
            "status": "ok",
            "url": "https://guba.eastmoney.com/oa/300777.html",
            "text": "中简科技要起飞了，垃圾庄家割韭菜。",
            "platform": "股吧",
        }
    ]
    claims = extract_claims_from_provider_records(records, "中简科技", "300777")
    assert len(claims) == 0


def test_gate_rejects_wild_up_down_forum_chatter():
    records = [
        {
            "status": "ok",
            "url": "https://guba.eastmoney.com/oa/300777.html",
            "text": "股吧帖子：中简科技难搞的碳纤维狂跌，普普通通的玻璃纤维狂涨，神奇的大啊。",
            "platform": "股吧",
        }
    ]
    claims = extract_claims_from_provider_records(records, "中简科技", "300777")
    assert len(claims) == 0


def test_gate_accepts_code_reference():
    records = [
        {
            "status": "ok",
            "url": "https://guba.eastmoney.com/oa/300777.html",
            "text": "我觉得300777的研发费用增长很快。",
            "platform": "股吧",
        }
    ]
    claims = extract_claims_from_provider_records(records, "中简科技", "300777")
    assert len(claims) == 1
    assert "300777" in claims[0]["claim_text"]


def test_gate_accepts_verifiable_business_and_shareholder_claims_from_forum():
    records = [
        {
            "status": "ok",
            "url": "https://guba.eastmoney.com/oa/300777.html",
            "text": "股吧帖子：中简科技前十大股东持股比例很高，宇航级碳纤维竞争压力不大。",
            "platform": "股吧",
        }
    ]
    claims = extract_claims_from_provider_records(records, "中简科技", "300777")
    assert len(claims) == 1
    assert "前十大股东" in claims[0]["claim_text"]


def test_deduplicate_claims_across_providers():
    records = [
        {
            "status": "ok",
            "url": "https://guba.eastmoney.com/oa/300777.html",
            "text": "我认为中简科技的研发费用增长了。",
            "platform": "股吧",
        },
        {
            "status": "ok",
            "url": "https://weibo.com/u/123",
            "text": "我认为中简科技的研发费用增长了。",
            "platform": "微博",
        },
    ]
    claims = extract_claims_from_provider_records(records, "中简科技", "300777")
    assert len(claims) == 1


def test_strip_citations_removes_numbered_markers():
    text = _strip_citations("中简科技收入下降[^1]，研发费用增长[2]。")
    assert "[^1]" not in text
    assert "[2]" not in text
    assert "收入下降" in text


def test_claim_text_length_is_capped():
    records = [
        {
            "status": "ok",
            "url": "https://guba.eastmoney.com/oa/300777.html",
            "text": "我认为" + "中简科技的收入下降了" * 20 + "，研发费用也增长。",
            "platform": "股吧",
        }
    ]
    claims = extract_claims_from_provider_records(records, "中简科技", "300777")
    assert len(claims) == 1
    assert len(claims[0]["claim_text"]) <= 180


def test_caps_limit_total_claims():
    records = [
        {
            "status": "ok",
            "url": f"https://guba.eastmoney.com/oa/300777_{i}.html",
            "text": f"我认为中简科技的{i}号订单发货了，收入下降。",
            "platform": "股吧",
        }
        for i in range(20)
    ]
    claims = extract_claims_from_provider_records(records, "中简科技", "300777")
    assert len(claims) <= DEFAULT_MAX_CLAIMS
    assert len(claims) <= DEFAULT_MAX_CLAIMS_PER_PROVIDER * 5


def test_reject_negative_signals_accepts_community_text():
    assert _reject_negative_signals("我觉得中简科技的毛利率承压。") is False


def test_reject_negative_signals_rejects_news():
    assert _reject_negative_signals("证券时报：中简科技毛利率承压。") is True


def test_provider_record_blocked_by_domain_filter():
    record = build_provider_record("https://www.cninfo.com.cn/announcement/")
    assert record["status"] == "blocked"
    assert record["claims"] == []


def test_provider_record_empty_text_returns_empty():
    record = build_provider_record("https://guba.eastmoney.com/oa/300777.html", raw_text="   ")
    assert record["status"] == "empty"
    assert record["claims"] == []


def test_write_fresh_social_claim_note_dry_run_does_not_touch_disk(tmp_path):
    claims = [
        {
            "claim_id": "c1",
            "claim_text": "我认为中简科技收入下降。",
            "claim_status": "unverified_claim",
            "source_url": "https://guba.eastmoney.com/oa/300777.html",
            "source_platform": "股吧",
        }
    ]
    result = write_fresh_social_claim_note(
        stock_name="中简科技",
        stock_code="300777",
        claims=claims,
        base_dir=tmp_path,
        date_str="20260615",
        dry_run=True,
    )
    assert result["status"] == "dry_run"
    assert result["claim_count"] == 1
    assert not (tmp_path / "10-Stocks" / "中简科技").exists()


def test_write_fresh_social_claim_note_writes_note_with_correct_credit(tmp_path):
    claims = [
        {
            "claim_id": "c1",
            "claim_text": "我认为中简科技收入下降。",
            "claim_status": "unverified_claim",
            "source_url": "https://guba.eastmoney.com/oa/300777.html",
            "source_platform": "股吧",
        }
    ]
    result = write_fresh_social_claim_note(
        stock_name="中简科技",
        stock_code="300777",
        claims=claims,
        base_dir=tmp_path,
        date_str="20260615",
        dry_run=False,
    )
    assert result["status"] == "written"
    path = Path(result["path"])
    assert path.exists()

    text = path.read_text(encoding="utf-8")
    assert "source_credit: 30" in text
    assert "fresh: true" in text
    assert "confirmed_fact" not in text
    assert "unverified_claim" in text
    assert "雪球缓存社区claims" not in path.name


def test_write_fresh_social_claim_note_never_writes_confirmed_fact(tmp_path):
    # Even if a caller tries to pass confirmed_fact, writer must refuse it.
    claims = [
        {
            "claim_id": "c1",
            "claim_text": "中简科技收入下降。",
            "claim_status": "confirmed_fact",
            "source_url": "https://guba.eastmoney.com/oa/300777.html",
            "source_platform": "股吧",
        }
    ]
    with pytest.raises(ValueError):
        write_fresh_social_claim_note(
            stock_name="中简科技",
            stock_code="300777",
            claims=claims,
            base_dir=tmp_path,
            date_str="20260615",
            dry_run=False,
        )


def test_fresh_note_filename_does_not_collide_with_cached_community_note(tmp_path):
    claims = [
        {
            "claim_id": "c1",
            "claim_text": "我认为中简科技收入下降。",
            "claim_status": "unverified_claim",
            "source_url": "https://guba.eastmoney.com/oa/300777.html",
            "source_platform": "股吧",
        }
    ]
    result = write_fresh_social_claim_note(
        stock_name="中简科技",
        stock_code="300777",
        claims=claims,
        base_dir=tmp_path,
        date_str="20260615",
        dry_run=False,
    )
    path = Path(result["path"])
    assert "新鲜外部社媒claims" in path.name
    assert "雪球缓存社区claims" not in path.name


def test_render_note_has_no_numbered_citations():
    claims = [
        {
            "claim_id": "c1",
            "claim_text": "我认为中简科技收入下降了[^1]。",
            "claim_status": "unverified_claim",
            "source_url": "https://guba.eastmoney.com/oa/300777.html",
            "source_platform": "股吧",
        }
    ]
    text = _render_note("中简科技", "300777", claims, "20260615")
    assert "[^1]" not in text
    assert "[1]" not in text


def test_classify_provider_status_from_http_codes():
    assert _classify_provider_status(429) == "rate_limited"
    assert _classify_provider_status(403) == "blocked"
    assert _classify_provider_status(500) == "error"
    assert _classify_provider_status(200) == "ok"
    assert _classify_provider_status(0) == "error"
