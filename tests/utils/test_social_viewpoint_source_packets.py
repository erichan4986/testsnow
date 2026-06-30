from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from social_viewpoint_source_packets import build_social_source_packets


def _write_report_input(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "report_input.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_build_social_source_packets_from_cached_xueqiu_and_zhihu(tmp_path: Path):
    report_input = _write_report_input(
        tmp_path,
        {
            "stocks_data": {
                "测试股": [
                    {
                        "title": "雪球长文",
                        "content": "这是一篇雪球长文。" + "技术路线、商业化窗口和竞争格局需要跟踪。" * 20,
                        "url": "https://xueqiu.com/1/2",
                        "author": "雪球作者",
                        "source": "xueqiu",
                        "time": "06-29",
                    },
                    {
                        "title": "短情绪帖",
                        "content": "今天抄底吗？",
                        "url": "https://xueqiu.com/1/short",
                        "source": "xueqiu",
                    },
                ]
            },
            "raw_data": {
                "测试股": {
                    "zhihu": {
                        "report_items": [
                            {
                                "title": "知乎深度回答",
                                "content": "这是一篇知乎长回答。" + "费用收缩、收入质量和商业化节奏存在分歧。" * 20,
                                "url": "https://zhihu.com/question/1/answer/2",
                                "author_name": "知乎作者",
                                "edit_time": 1780000000,
                            }
                        ]
                    }
                }
            },
        },
    )

    packets = build_social_source_packets(report_input, stock_name="测试股", min_content_chars=120)

    assert [packet["source_kind"] for packet in packets] == ["social_xueqiu", "social_zhihu"]
    assert packets[0]["schema_version"] == "curated_external_source_packet.v1"
    assert packets[0]["source_ref"] == "https://xueqiu.com/1/2"
    assert packets[0]["account"] == "雪球作者"
    assert packets[1]["source_ref"] == "https://zhihu.com/question/1/answer/2"
    for packet in packets:
        assert packet["quality_action"] == "preview_only"
        assert packet["knowledge_eligible"] is False
        assert packet["synthesis_display_only"] is True
        assert packet["scoring_eligible"] is False
        assert packet["risk_score_eligible"] is False
        assert packet["verification_status"] == "professional_observation"
        assert packet["source_content_hash"]


def test_build_social_source_packets_dedupes_and_respects_max_sources(tmp_path: Path):
    long_content = "这是一篇较长的社媒观点。" + "订单节奏和需求指引需要跟踪。" * 20
    report_input = _write_report_input(
        tmp_path,
        {
            "stocks_data": {
                "测试股": [
                    {
                        "title": "雪球长文 A",
                        "content": long_content,
                        "url": "https://xueqiu.com/1/dup",
                        "source": "xueqiu",
                    },
                    {
                        "title": "雪球长文 A 转载",
                        "content": long_content,
                        "url": "https://xueqiu.com/1/dup",
                        "source": "xueqiu",
                    },
                    {
                        "title": "东方财富长帖",
                        "content": long_content,
                        "url": "https://caifuhao.eastmoney.com/news/1",
                        "source": "eastmoney",
                    },
                ]
            },
            "raw_data": {"测试股": {"zhihu": {"report_items": []}}},
        },
    )

    packets = build_social_source_packets(
        report_input,
        stock_name="测试股",
        min_content_chars=120,
        max_sources=1,
    )

    assert len(packets) == 1
    assert packets[0]["source_ref"] == "https://xueqiu.com/1/dup"


def test_build_social_source_packets_layers_xueqiu_column_and_reply_credit(tmp_path: Path):
    long_content = "这是一篇较长的社媒观点。" + "订单节奏和需求指引需要跟踪。" * 20
    report_input = _write_report_input(
        tmp_path,
        {
            "stocks_data": {
                "测试股": [
                    {
                        "title": "郭小松驾道05-19 来自雪球 专栏 黑芝麻智能深度分析",
                        "content": long_content,
                        "url": "https://xueqiu.com/1/column",
                        "source": "xueqiu",
                    },
                    {
                        "title": "梧桐树201805-31 来自Android 回复@益知: 机构调研信息",
                        "content": long_content,
                        "url": "https://xueqiu.com/1/reply",
                        "source": "xueqiu",
                    },
                ]
            },
            "raw_data": {"测试股": {"zhihu": {"report_items": []}}},
        },
    )

    packets = build_social_source_packets(report_input, stock_name="测试股", min_content_chars=120)

    assert [packet["source_detail_type"] for packet in packets] == ["xueqiu_column", "xueqiu_reply"]
    assert [packet["source_label"] for packet in packets] == ["雪球专栏观察", "雪球评论观察"]
    assert packets[0]["source_credit"] > packets[1]["source_credit"]
