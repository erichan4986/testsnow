import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from wechat_candidate_selector import (  # noqa: E402
    build_company_theme_terms,
    build_wechat_candidate_preview_markdown,
    select_wechat_candidates,
)


def test_selector_keeps_analysis_marks_theme_product_signal_and_drops_marketing():
    stock_config = {
        "name": "圣邦股份",
        "code": "300661",
        "source_intake": {
            "a_stock": {
                "iwencai_industry_research": {
                    "queries": [
                        "模拟芯片 行业研究报告",
                        "汽车芯片 行业研究报告",
                        "车规芯片 产业链 深度报告",
                    ]
                },
                "eastmoney_global_news": {
                    "keywords": ["半导体", "AI芯片", "汽车芯片"],
                },
            }
        },
    }
    candidates = [
        {
            "title": "半导体行业观察｜AI的火烧到了模拟芯片",
            "account": "半导体行业观察",
            "digest": "AI 数据中心让电源、功率和高速信号链成为模拟芯片新的结构性变量。",
            "url": "https://mp.weixin.qq.com/s/analysis",
        },
        {
            "title": "为AI应用而生！圣邦微电子推出90A高性能Smart Power Stage SGM25890",
            "account": "电子工程专辑",
            "digest": "新品面向 AI 电源和高性能服务器供电场景。",
            "url": "https://mp.weixin.qq.com/s/product",
        },
        {
            "title": "同行见未来，圣芯赋万物：上海展会邀请函",
            "account": "圣邦微电子",
            "digest": "7月1日-3日，圣邦微电子邀您共赴一场芯动夏日之约。",
            "url": "https://mp.weixin.qq.com/s/event",
        },
        {
            "title": "圣邦微电子推出LCD背光与偏置芯片SGM3810",
            "account": "圣邦微电子",
            "digest": "一颗芯片搞定背光与偏置。",
            "url": "https://mp.weixin.qq.com/s/plain-product",
        },
    ]

    summary = select_wechat_candidates(candidates, stock_config=stock_config, extra_theme_terms=["AI 电源", "信号链"])

    actions = {item["candidate"]["url"]: item["action"] for item in summary["items"]}
    assert actions["https://mp.weixin.qq.com/s/analysis"] == "keep"
    assert actions["https://mp.weixin.qq.com/s/product"] == "product_signal"
    assert actions["https://mp.weixin.qq.com/s/event"] == "drop"
    assert actions["https://mp.weixin.qq.com/s/plain-product"] == "drop"
    product = next(item for item in summary["items"] if item["candidate"]["url"].endswith("/product"))
    assert "AI 电源" in product["matched_terms"]
    assert product["category"] == "product_signal"
    assert summary["counts"] == {"keep": 1, "product_signal": 1, "drop": 2}


def test_selector_drops_honor_articles():
    summary = select_wechat_candidates(
        [
            {
                "title": "双喜临门！圣邦集团荣膺双项行业重磅荣誉，实力铸就标杆！",
                "account": "圣邦",
                "digest": "公司荣誉新闻。",
                "url": "https://mp.weixin.qq.com/s/honor",
            }
        ],
        stock_config={"name": "圣邦股份"},
    )

    item = summary["items"][0]
    assert item["action"] == "drop"
    assert item["category"] == "marketing_or_event"


def test_selector_uses_dynamic_theme_terms_for_other_company_without_shengbang_keywords():
    stock_config = {
        "name": "中际旭创",
        "code": "300308",
        "source_intake": {
            "a_stock": {
                "iwencai_industry_research": {
                    "queries": ["光模块 800G CPO 行业深度", "AI 算力 光通信 产业链"],
                }
            }
        },
    }

    theme_terms = build_company_theme_terms(stock_config)
    summary = select_wechat_candidates(
        [
            {
                "title": "中际旭创推出面向AI数据中心的1.6T光模块方案",
                "account": "光通信观察",
                "digest": "新品围绕 800G、1.6T、CPO 与 AI 算力网络升级。",
                "url": "https://mp.weixin.qq.com/s/optical-product",
            },
            {
                "title": "模拟芯片新周期之下谁能抢占红利",
                "account": "半导体产业纵横",
                "digest": "文章讨论模拟芯片、车规和电源管理。",
                "url": "https://mp.weixin.qq.com/s/analog",
            },
        ],
        stock_config=stock_config,
    )

    assert "光模块" in theme_terms
    actions = {item["candidate"]["url"]: item["action"] for item in summary["items"]}
    assert actions["https://mp.weixin.qq.com/s/optical-product"] == "product_signal"
    assert actions["https://mp.weixin.qq.com/s/analog"] == "drop"


def test_selector_marks_duplicate_by_url_and_title_fingerprint():
    candidates = [
        {
            "title": "周期反转，模拟芯片步入上行期",
            "digest": "模拟芯片行业复苏，汽车电子成为长期增量。",
            "url": "https://mp.weixin.qq.com/s/same",
        },
        {
            "title": "周期反转，模拟芯片步入上行期",
            "digest": "模拟芯片行业复苏，汽车电子成为长期增量。",
            "url": "https://mp.weixin.qq.com/s/same",
        },
        {
            "title": "周期反转，模拟芯片步入上行期",
            "digest": "模拟芯片行业复苏，汽车电子成为长期增量。",
            "url": "https://mp.weixin.qq.com/s/other",
        },
    ]

    summary = select_wechat_candidates(candidates, extra_theme_terms=["模拟芯片", "汽车电子"])

    assert [item["action"] for item in summary["items"]] == ["keep", "duplicate", "duplicate"]
    assert summary["counts"] == {"keep": 1, "duplicate": 2}
    assert summary["items"][1]["duplicate_of"] == "https://mp.weixin.qq.com/s/same"


def test_selector_keeps_deep_financial_series_and_drops_awards_or_price_hype():
    stock_config = {"name": "圣邦股份", "code": "300661"}
    candidates = [
        {
            "title": "芯财富 | 圣邦股份（下）：从数年“账本”看发展",
            "account": "芯财富",
            "digest": "分析圣邦股份收入结构、研发投入、盈利质量和国产替代进展。",
            "url": "https://mp.weixin.qq.com/s/financial-deep-dive",
        },
        {
            "title": "圣邦股份荣获第14届中国上市公司价值评选及第22届上市公司金牛奖",
            "account": "上市公司观察",
            "digest": "公司治理与资本市场奖项信息。",
            "url": "https://mp.weixin.qq.com/s/award",
        },
        {
            "title": "圣邦微上市首日涨44%，十个涨停后股价将是多少",
            "account": "打新观察",
            "digest": "围绕上市首日涨幅和涨停预期展开。",
            "url": "https://mp.weixin.qq.com/s/price-hype",
        },
    ]

    summary = select_wechat_candidates(candidates, stock_config=stock_config)

    actions = {item["candidate"]["url"]: item["action"] for item in summary["items"]}
    assert actions["https://mp.weixin.qq.com/s/financial-deep-dive"] == "keep"
    assert actions["https://mp.weixin.qq.com/s/award"] == "drop"
    assert actions["https://mp.weixin.qq.com/s/price-hype"] == "drop"


def test_selector_marks_high_signal_sgm_products_as_product_signal():
    stock_config = {"name": "圣邦股份", "code": "300661"}
    candidates = [
        {
            "title": "圣邦微电子推出集成电流检测、1/256微步进及高级衰减模式的45V、1.5A步进电机驱动器SGM42685",
            "account": "电子工程专辑",
            "digest": "面向电机控制和工业驱动应用。",
            "url": "https://mp.weixin.qq.com/s/stepper",
        },
        {
            "title": "18位、2MSPS、100dBFS SNR，圣邦微电子SGM51823D登场",
            "account": "电子工程专辑",
            "digest": "",
            "url": "https://mp.weixin.qq.com/s/adc-18bit",
        },
        {
            "title": "圣邦微电子推出SGM52461S4/SGM52461S8：4/8通道、24位、64kSPS同步采样精密ADC",
            "account": "电子工程专辑",
            "digest": "多通道同步采样精密 ADC，适合信号链场景。",
            "url": "https://mp.weixin.qq.com/s/adc-sync",
        },
    ]

    summary = select_wechat_candidates(
        candidates,
        stock_config=stock_config,
        extra_theme_terms=["信号链", "电源管理", "车规"],
    )

    assert [item["action"] for item in summary["items"]] == ["product_signal", "product_signal", "product_signal"]
    assert all(item["category"] == "product_signal" for item in summary["items"])


def test_selector_routes_solution_roundups_to_product_signal_not_keep():
    candidates = [
        {
            "title": "【方案精选】中微半导150V/1.5A高压非隔离DCDC芯片CMS6015，力芯微SOT563 17V/3A同步降压芯片，圣邦微SGMM2042/3电源模块等",
            "account": "半导纵横",
            "digest": "方案合集覆盖多家芯片公司的电源模块、降压芯片和驱动器。",
            "url": "https://mp.weixin.qq.com/s/solution-roundup",
        },
        {
            "title": "【方案精选】圣邦微SGMM2042/3电源模块，纳芯微集成式隔离电源NSIP9系列，杰华特NVDC架构降压充电IC芯片等",
            "account": "半导纵横",
            "digest": "多家公司产品方案合集。",
            "url": "https://mp.weixin.qq.com/s/solution-roundup-2",
        },
    ]

    summary = select_wechat_candidates(
        candidates,
        extra_theme_terms=["圣邦微", "电源管理", "电源模块"],
    )

    assert [item["action"] for item in summary["items"]] == ["product_signal", "product_signal"]
    assert all(item["category"] == "product_signal" for item in summary["items"])


def test_selector_drops_capital_market_flash_even_when_company_theme_matches():
    candidates = [
        {
            "title": "华为苹果也要涨价！国内又一MCU公司涨价！港交所圣邦微等6家同日招股，03661.HK拟本月上市",
            "account": "集微网",
            "digest": "短讯汇总涨价、招股和上市安排。",
            "url": "https://mp.weixin.qq.com/s/ipo-flash",
        },
        {
            "title": "圣邦股份港股上市首日股价大涨，市场关注模拟芯片龙头估值",
            "account": "资本市场观察",
            "digest": "围绕上市首日股价表现和估值情绪展开。",
            "url": "https://mp.weixin.qq.com/s/listing-price-flash",
        },
    ]

    summary = select_wechat_candidates(
        candidates,
        extra_theme_terms=["圣邦微", "模拟芯片", "港股"],
    )

    assert [item["action"] for item in summary["items"]] == ["drop", "drop"]
    assert all(item["category"] == "capital_market_flash" for item in summary["items"])


def test_selector_keeps_industry_price_cycle_analysis():
    summary = select_wechat_candidates(
        [
            {
                "title": "模拟芯片涨价周期复盘：库存出清后谁能受益",
                "account": "半导体行业观察",
                "digest": "文章分析模拟芯片库存、价格周期、汽车电子需求和国产替代格局。",
                "url": "https://mp.weixin.qq.com/s/price-cycle-analysis",
            }
        ],
        extra_theme_terms=["模拟芯片", "汽车电子", "国产替代"],
    )

    assert summary["items"][0]["action"] == "keep"
    assert summary["items"][0]["category"] == "analysis"


def test_preview_markdown_renders_actions_reasons_and_guardrails():
    summary = select_wechat_candidates(
        [
            {
                "title": "圣邦微电子推出车规级电子保险丝控制器SGM42148Q",
                "account": "电子工程专辑",
                "digest": "产品面向车规级电源保护。",
                "url": "https://mp.weixin.qq.com/s/product",
            }
        ],
        extra_theme_terms=["车规", "电源"],
    )

    markdown = build_wechat_candidate_preview_markdown(summary)

    assert "# WeChat Candidate Selector Preview" in markdown
    assert "不写 Knowledge" in markdown
    assert "product_signal" in markdown
    assert "车规" in markdown
    assert "电子保险丝" in markdown


def test_selector_results_are_review_only_not_synthesis_eligible():
    summary = select_wechat_candidates(
        [
            {
                "title": "模拟芯片周期复盘：库存出清后谁能受益",
                "digest": "模拟芯片行业复苏，汽车电子成为长期增量。",
                "url": "https://mp.weixin.qq.com/s/analysis",
            },
            {
                "title": "圣邦微电子推出车规级电子保险丝控制器SGM42148Q",
                "digest": "产品面向车规级电源保护。",
                "url": "https://mp.weixin.qq.com/s/product",
            },
        ],
        extra_theme_terms=["模拟芯片", "车规", "电源"],
    )

    assert [item["action"] for item in summary["items"]] == ["keep", "product_signal"]
    assert all(item["synthesis_eligible"] is False for item in summary["items"])
    assert all(item["review_eligible"] is True for item in summary["items"])
    assert all(item["display_eligible"] is True for item in summary["items"])
