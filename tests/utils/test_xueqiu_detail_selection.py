from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from xueqiu_detail_selection import (
    build_detail_plan,
    build_refill_plan,
    evaluate_detail_attempts,
    to_stocks_data_posts,
)


def _post(
    url: str,
    content: str,
    *,
    title: str = "",
    author: str = "作者",
    track: str = "featured",
    likes: int = 5,
    comments: int = 3,
) -> dict:
    return {
        "title": title or content[:60],
        "content": content,
        "url": url,
        "author": author,
        "source": "xueqiu",
        "_track": track,
        "like_count": likes,
        "comment_count": comments,
    }


VALUATION_POST = (
    "$上海复旦(01385)$ 复旦微电(688385)当前市值约530-555亿，"
    "2025年归母净利只有2.32亿，同比腰斩59%，2026年券商预测净利4-7.5亿，"
    "对应2026年PE高达70-130倍。而紫光国微市值约600亿，2025年净利14.37亿。"
    "两家业务高度可比，因此需要用前瞻PE、PS和港股折价交叉验证...展开"
)


def test_first_plan_keeps_fudan_valuation_long_post_despite_hot_aerospace_posts():
    posts = [
        _post(
            f"https://xueqiu.com/aerospace/{i}",
            "复旦微电参与G60千帆星座，抗辐照FPGA和宇航存储用于卫星载荷，"
            "单星价值300-500万元，航天订单和中标节奏需要验证...展开",
            likes=20 + i,
            comments=10,
        )
        for i in range(8)
    ]
    posts.append(_post("https://xueqiu.com/1606930351/392467740", VALUATION_POST))

    plan = build_detail_plan(
        posts,
        {
            "first_batch_size": 5,
            "enabled_extension_buckets": ["semiconductor_product", "aerospace"],
        },
    )

    selected_urls = [post["url"] for post in plan["first_batch"]]
    assert "https://xueqiu.com/1606930351/392467740" in selected_urls
    assert "valuation" in plan["audit"]["populated_topic_buckets"]


def test_effective_topic_coverage_does_not_require_missing_extension_buckets():
    posts = [
        _post("https://xueqiu.com/1/valuation", "这家公司估值和PE需要重估，市值和净利匹配度需要跟踪...展开"),
        _post("https://xueqiu.com/1/earnings", "公司半年报净利和营收修复，毛利率变化是关键变量...展开"),
    ]

    plan = build_detail_plan(posts, {"min_topic_coverage": 3, "first_batch_size": 4})

    assert plan["audit"]["populated_topic_buckets"] == ["earnings", "valuation"]
    assert plan["audit"]["effective_min_topic_coverage"] == 2


def test_duplicate_content_counts_once_when_deciding_refill():
    same = (
        "复旦微电三问预期差：Q2净利、FPGA收入和存储价格构成业绩弹性，需要半年报验证。"
        "如果半年报兑现，市场可能重新评估其业绩修复节奏和产品结构变化。"
    )
    attempts = [
        {"url": "https://xueqiu.com/1/a", "content": same, "topics": ["earnings"], "attempt_batch": "first", "status": "usable"},
        {"url": "https://xueqiu.com/1/b", "content": same, "topics": ["earnings"], "attempt_batch": "first", "status": "usable"},
        {
            "url": "https://xueqiu.com/1/c",
            "content": (
                "复旦微电估值分歧集中在PE、PS和港股折价，紫光国微是重要可比公司。"
                "当前市值与前瞻净利匹配度需要跟踪，不能直接使用静态PE判断。"
            ),
            "topics": ["valuation"],
            "attempt_batch": "first",
            "status": "usable",
        },
    ]

    result = evaluate_detail_attempts(
        attempts,
        {"min_usable_details": 3, "max_drop_rate": 0.4, "min_topic_coverage": 2},
    )

    assert result["usable_count"] == 2
    assert result["duplicate_count"] == 1
    assert result["should_refill"] is True
    assert "usable_below_minimum" in result["refill_reasons"]


def test_refill_is_one_time_capped_and_prioritizes_missing_topics():
    posts = [
        _post(f"https://xueqiu.com/1/earnings-{i}", "公司净利和营收修复需要验证，半年报是关键节点...展开")
        for i in range(10)
    ]
    posts.extend(
        [
            _post("https://xueqiu.com/1/valuation", VALUATION_POST),
            _post("https://xueqiu.com/1/risk", "订单不及预期、价格战和存货跌价可能导致盈利下修...展开"),
        ]
    )
    plan = build_detail_plan(posts, {"first_batch_size": 1, "refill_batch_size": 4, "max_detail_pages_total": 3})
    attempted = [{"url": post["url"], "content": "", "drop_reason": "ui_noise", "topics": post["detail_topic_buckets"]} for post in plan["first_batch"]]
    evaluation = evaluate_detail_attempts(attempted, {"min_usable_details": 2, "max_drop_rate": 0.4, "min_topic_coverage": 2})

    refill = build_refill_plan(plan["candidates"], attempted, evaluation, {"refill_batch_size": 4, "max_detail_pages_total": 3})

    assert refill["should_refill"] is True
    assert refill["audit"]["remaining_capacity"] == 2
    assert len(refill["refill_batch"]) <= 2
    assert any("valuation" in post["detail_topic_buckets"] or "risk" in post["detail_topic_buckets"] for post in refill["refill_batch"])

    second_refill = build_refill_plan(plan["candidates"], attempted, evaluation, {"refill_batch_size": 4, "max_detail_pages_total": 3, "refill_already_used": True})
    assert second_refill["should_refill"] is False


def test_refill_output_can_be_converted_to_stocks_data_shape():
    attempts = [
        {
            "url": "https://xueqiu.com/1606930351/392467740",
            "title": "复旦微电估值长文",
            "content": VALUATION_POST,
            "author": "锲而不舍",
            "publish_time": "06-03",
            "topics": ["valuation"],
            "attempt_batch": "refill",
            "status": "usable",
        }
    ]

    payload = to_stocks_data_posts(attempts, stock_name="复旦微电")

    post = payload["stocks_data"]["复旦微电"][0]
    assert post["source"] == "xueqiu"
    assert post["_track"] == "featured"
    assert post["selection_audit"]["batch"] == "refill"
    assert post["selection_audit"]["topics"] == ["valuation"]
