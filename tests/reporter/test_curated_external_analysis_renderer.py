import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from skill_pipeline import SkillContext
from reporter.sections.curated_external_analysis_renderer import CuratedExternalAnalysisRenderer


def _ctx(items=None, **kwargs):
    payload = {"curated_external_analysis_items": items or []}
    payload.update(kwargs)
    return SkillContext(input=payload)


def _item(**kwargs):
    defaults = {
        "source_kind": "local_file",
        "title": "模拟芯片行业长文",
        "content": "模拟芯片国产替代进入深水区，信号链与电源管理产品需要结合客户导入节奏观察。",
        "url": "https://example.com/analog",
        "path": "",
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "synthesis_eligible": False,
        "scoring_eligible": False,
        "risk_score_eligible": False,
    }
    defaults.update(kwargs)
    return defaults


def test_curated_external_analysis_renderer_returns_empty_without_items():
    assert CuratedExternalAnalysisRenderer().render(_ctx()) == ""


def test_curated_external_analysis_renderer_renders_preview_only_section():
    result = CuratedExternalAnalysisRenderer().render(_ctx([_item()]))

    assert "## 精选外部观察（Preview）" in result
    assert "Preview-only" in result
    assert "不写 Knowledge" in result
    assert "不进入评分或风险评分" in result
    assert "### 精选长内容" in result
    assert "模拟芯片行业长文" in result
    assert "source_kind: `local_file`" in result
    assert "knowledge_eligible: `false`" in result
    assert "synthesis_eligible: `false`" in result
    assert "scoring_eligible: `false`" in result
    assert "risk_score_eligible: `false`" in result


def test_curated_external_analysis_renderer_groups_wechat_product_signals():
    result = CuratedExternalAnalysisRenderer().render(
        _ctx([
            _item(source_kind="jina_url", title="光模块深度文章"),
            _item(
                source_kind="wechat_product_signal",
                source_type="wechat_product_signal",
                title="圣邦微 SGM25890 新品",
                content="90A Smart Power Stage 面向 AI 服务器电源场景，但收入贡献仍需后续验证。",
                account="圣邦微电子",
                publish_time="2026-06-20",
                url="https://mp.weixin.qq.com/s/example",
            ),
        ])
    )

    assert "### 精选长内容" in result
    assert "光模块深度文章" in result
    assert "### 微信精选观察" in result
    assert "#### 产品/事件信号" in result
    assert "按材料类型分组展示" in result
    assert "圣邦微 SGM25890 新品" in result
    assert "account: 圣邦微电子" in result
    assert "publish_time: 2026-06-20" in result


def test_curated_external_analysis_renderer_keeps_all_analysis_and_commercial_events_when_limited():
    items = [
        _item(
            source_kind="wechat_high_quality_analysis",
            source_type="wechat_high_quality_analysis",
            wechat_signal_category="high_quality_analysis",
            title=f"深度分析{i}",
            content="AI 光互联龙头深度分析。",
        )
        for i in range(3)
    ]
    items.extend(
        [
            _item(
                source_kind="wechat_customer_order_or_design_win",
                source_type="wechat_customer_order_or_design_win",
                wechat_signal_category="customer_order_or_design_win",
                title=f"商业化事件{i}",
                content="客户定点、订单、量产或供应链进入信号。",
            )
            for i in range(2)
        ]
    )
    items.extend(
        [
            _item(
                source_kind="wechat_product_signal",
                source_type="wechat_product_signal",
                wechat_signal_category="product_or_event_signal",
                title=f"普通产品信号{i}",
                content="产品发布。",
            )
            for i in range(4)
        ]
    )

    result = CuratedExternalAnalysisRenderer().render(
        _ctx(items, curated_external_analysis_max_display_items=2)
    )

    assert "### 微信精选观察" in result
    assert "#### 深度分析" in result
    assert "深度分析0" in result
    assert "深度分析1" in result
    assert "深度分析2" in result
    assert "#### 商业化事件" in result
    assert "商业化事件0" in result
    assert "商业化事件1" in result
    assert "#### 产品/事件信号" in result
    assert "普通产品信号0" in result
    assert "普通产品信号1" in result
    assert "普通产品信号2" not in result


def test_curated_external_analysis_renderer_filters_unsafe_items():
    result = CuratedExternalAnalysisRenderer().render(
        _ctx([
            _item(title="安全材料"),
            _item(title="错误材料", knowledge_eligible=True),
            _item(title="合成材料", synthesis_eligible=True),
            _item(title="评分材料", scoring_eligible=True),
            _item(title="风险材料", risk_score_eligible=True),
            _item(title="正式材料", quality_action="keep"),
        ])
    )

    assert "安全材料" in result
    assert "错误材料" not in result
    assert "合成材料" not in result
    assert "评分材料" not in result
    assert "风险材料" not in result
    assert "正式材料" not in result


def test_curated_external_analysis_renderer_accepts_summary_items_and_limits_count():
    items = [_item(title=f"材料{i}") for i in range(4)]
    result = CuratedExternalAnalysisRenderer().render(
        _ctx(
            [],
            curated_external_analysis_summary={"items": items},
            curated_external_analysis_max_display_items=2,
        )
    )

    assert "材料0" in result
    assert "材料1" in result
    assert "材料2" not in result


def test_curated_external_analysis_renderer_balances_long_content_and_wechat_when_limited():
    wechat_items = [
        _item(
            source_kind="wechat_product_signal",
            source_type="wechat_product_signal",
            title=f"微信产品{i}",
            content=f"产品信号{i}",
        )
        for i in range(5)
    ]
    long_item = _item(source_kind="curated_preview", title="36氪产业长文", content="光芯片与模拟芯片产业链长文。")

    result = CuratedExternalAnalysisRenderer().render(
        _ctx(
            [*wechat_items, long_item],
            curated_external_analysis_max_display_items=4,
        )
    )

    assert "### 精选长内容" in result
    assert "36氪产业长文" in result
    assert "### 微信精选观察" in result
    assert "#### 产品/事件信号" in result
    assert "微信产品0" in result
    assert "微信产品1" in result
    assert "微信产品2" in result
    assert "微信产品3" not in result


def test_curated_external_analysis_renderer_quotes_external_excerpt_headings():
    result = CuratedExternalAnalysisRenderer().render(
        _ctx([
            _item(
                title="# 带`标题`材料",
                content="## 外部_原文_标题\n\n这里有 `代码`、*重点* 和 | 表格符。",
                account="作者`名`",
                path="/tmp/a|b.md",
            )
        ])
    )

    assert "#### 1. \\# 带\\`标题\\`材料" in result
    assert "account: 作者\\`名\\`" in result
    assert "path: `/tmp/a\\|b.md`" in result
    assert "> \\## 外部\\_原文\\_标题" in result
    assert "> 这里有 \\`代码\\`、\\*重点\\* 和 \\| 表格符。" in result
    assert "\n## 外部原文标题" not in result
