"""Tests for product/project/customer evidence extraction helper.

These tests use Huizhiwei-style fixtures (L-PAMiD, RedCap, AEC-Q104, Samsung,
etc.) only to verify that the *generic* context-driven mechanisms capture
proprietary product names, statuses, customer chains, and business meaning.
The implementation must not rely on a fixed whitelist of those terms.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

import periodic_report_product_project_evidence as product_project_evidence
from periodic_report_product_project_evidence import (
    build_company_profile_backfill,
    build_rd_progress_backfill,
    extract_product_project_evidence,
)


HUIZHIWEI_PROFILE_SNIPPET = """
射频前端芯片作为无线通信设备的核心器件，负责保障信号的发射和接收。公司产品系列覆
盖 2G 、3G 、4G 、3GHz 以下的 5G 重耕频段、 3GHz~6GHz 的 5G UHB 等蜂窝通信频段和 Wi-Fi
通信等，可为客户提供无线通信射频前端发射模组、接收模组等。

公司的射频前端产品应用于三星 、vivo 、小米 、OPPO 、荣耀等国内外智能手机品牌机型 ，并
进入华勤通讯和龙旗科技等一线移动终端设备 ODM 厂商和移远通信、广和通、日海智能等头部
无线通信模组厂商。
"""

HUIZHIWEI_SALES_MODEL_SNIPPET = """
3、销售模式

公司的终端客户包括智能手机品牌客户、移动终端设备 ODM 客户及物联网模组客户等。按
照集成电路行业惯例和企业自身特点，公司采用 “经销为主、直销为辅 ”的销售模式。公司与经
销商的关系属于买断式销售关系。公司与经销商签订销售框架协议，经销商根据其客户需求和自
身销售备货等因素向公司下达订单，公司根据订单安排出货，后续的定期对账、付款和开票均由
公司与经销商双方完成。此外，针对部分终端客户公司采取直销模式，直接对接客户需求并开展
业务。
"""

HUIZHIWEI_RD_SNIPPET = """
报告期内，公司研发投入为 22,421.94 万元，占营业收入比例为 27.77%。
2025 年公司率先量产了 Phase8L 方案的全集成 L-PAMiD，RedCap 方案也实现规模量产。
公司 5G UHB 频段 L-PAMiF 模组已在三星自研体系规模商用。
公司部分产品已经通过车规可靠性的测试，获得 AEC-Q104 车规认证，并在客户端推广。
5G 场景高性能 GSM PA 模组项目处于预量产阶段。
"""


def _make_item_map(*texts):
    return {
        f"fulltext-{index}-0": {
            "id": f"fulltext-{index}-0",
            "usage": "fulltext_section",
            "section": "管理层讨论与分析",
            "title": "主要业务",
            "text": text,
        }
        for index, text in enumerate(texts)
    }


def test_extract_snippets_caches_marker_patterns(monkeypatch):
    """Snippet extraction should reuse compiled marker patterns across calls."""
    calls = []
    original_spaced_pattern = product_project_evidence._spaced_pattern

    def counting_spaced_pattern(marker):
        calls.append(marker)
        return original_spaced_pattern(marker)

    product_project_evidence._compiled_marker_pattern.cache_clear()
    monkeypatch.setattr(product_project_evidence, "_spaced_pattern", counting_spaced_pattern)

    text = "公司产品应用于智能手机，覆盖 2G/3G/4G/5G 通信频段，并已进入头部客户。"
    first = product_project_evidence._extract_snippets(
        text,
        ("应用于", "覆盖", "进入"),
        require_tokens=("智能手机", "客户", "通信频段"),
    )
    second = product_project_evidence._extract_snippets(
        text,
        ("应用于", "覆盖", "进入"),
        require_tokens=("智能手机", "客户", "通信频段"),
    )

    assert first
    assert second == first
    assert calls == ["应用于", "覆盖", "进入"]


def test_extracts_customer_chain_near_customer_and_odm_markers():
    """Generic mechanism: terms near 应用于/进入/客户/ODM should be captured."""
    item_map = _make_item_map(HUIZHIWEI_PROFILE_SNIPPET)
    evidence = extract_product_project_evidence(item_map)

    customer = evidence["customer_chain"]
    assert customer["present"]
    joined = " ".join(customer["snippets"])
    # Fixture terms appear only because they sit in the right context.
    assert "三星" in joined
    assert "vivo" in joined
    assert "OPPO" in joined
    assert "荣耀" in joined
    assert "华勤通讯" in joined
    assert "龙旗科技" in joined
    assert "移远通信" in joined
    assert customer["refs"]
    for ref in customer["refs"]:
        assert ref.startswith("fulltext-")


def test_extracts_sales_model_near_sales_mode_markers():
    """Generic mechanism: sales-model wording near 销售模式/经销/直销 should be captured."""
    item_map = _make_item_map(HUIZHIWEI_SALES_MODEL_SNIPPET)
    evidence = extract_product_project_evidence(item_map)

    sales = evidence["sales_model"]
    assert sales["present"]
    joined = " ".join(sales["snippets"])
    assert "经销为主" in joined
    assert "直销为辅" in joined
    assert "买断式" in joined
    assert sales["refs"]


def test_extracts_frequency_coverage_near_coverage_markers():
    """Generic mechanism: band names near 覆盖/频段 should be captured."""
    item_map = _make_item_map(HUIZHIWEI_PROFILE_SNIPPET)
    evidence = extract_product_project_evidence(item_map)

    freq = evidence["frequency_coverage"]
    assert freq["present"]
    joined = " ".join(freq["snippets"])
    assert "2G" in joined
    assert "3G" in joined
    assert "4G" in joined
    assert "5G" in joined
    assert "UHB" in joined
    assert "Wi-Fi" in joined
    assert freq["refs"]


def test_extracts_product_lines_and_statuses_near_project_markers():
    """Generic mechanism: product names + statuses near 量产/规模商用/认证/预量产 should be captured."""
    item_map = _make_item_map(HUIZHIWEI_RD_SNIPPET)
    evidence = extract_product_project_evidence(item_map)

    products = evidence["product_lines"]
    assert products["present"]
    joined = " ".join(products["snippets"])
    assert "L-PAMiD" in joined
    assert "L-PAMiF" in joined
    assert "RedCap" in joined
    assert "AEC-Q104" in joined

    statuses = evidence["project_statuses"]
    assert statuses["present"]
    status_text = " ".join(statuses["snippets"])
    assert any(s in status_text for s in ("量产", "规模量产", "规模商用"))
    assert "预量产" in status_text or "认证" in status_text


def test_company_profile_backfill_combines_generic_evidence():
    """Backfill judgment should assemble captured snippets without upgrading to fact."""
    item_map = _make_item_map(HUIZHIWEI_PROFILE_SNIPPET, HUIZHIWEI_SALES_MODEL_SNIPPET)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_company_profile_backfill(evidence)

    assert judgment
    assert refs
    assert all(ref.startswith("fulltext-") for ref in refs)
    # The summary should mention representative customer brands and channels.
    assert "三星" in judgment
    assert any(b in judgment for b in ("vivo", "小米", "OPPO", "荣耀"))
    assert any(c in judgment for c in ("华勤", "龙旗", "移远"))
    assert "买断式" in judgment or "经销" in judgment
    assert "2G" in judgment
    assert "5G" in judgment
    assert "UHB" in judgment or "Wi-Fi" in judgment
    assert "confirmed_fact" not in judgment
    assert "核心事实" not in judgment
    assert "已证实" not in judgment


def test_rd_progress_backfill_combines_generic_evidence():
    """Backfill judgment should assemble product/status snippets without upgrading to fact."""
    item_map = _make_item_map(HUIZHIWEI_RD_SNIPPET)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_rd_progress_backfill(evidence)

    assert judgment
    assert refs
    assert all(ref.startswith("fulltext-") for ref in refs)
    # Summary should capture at least one product/technology name and one status.
    assert any(p in judgment for p in ("L-PAMiD", "L-PAMiF", "RedCap", "AEC-Q104", "GSM PA"))
    assert any(s in judgment for s in ("量产", "规模量产", "规模商用", "认证", "预量产"))
    assert "confirmed_fact" not in judgment
    assert "核心事实" not in judgment
    assert "已证实" not in judgment


def test_returns_empty_when_no_signals():
    item_map = _make_item_map("公司主要从事一般贸易业务，无特殊客户或项目。")
    evidence = extract_product_project_evidence(item_map)

    assert not evidence["customer_chain"]["present"]
    assert not evidence["sales_model"]["present"]
    assert not evidence["frequency_coverage"]["present"]
    assert not evidence["product_lines"]["present"]
    assert not evidence["project_statuses"]["present"]

    assert build_company_profile_backfill(evidence) == ("", [])
    assert build_rd_progress_backfill(evidence) == ("", [])


def test_profile_backfill_filters_issuer_self_name():
    """公司画像 should not treat the issuer's own name as a customer/channel."""
    text = """
    第一节 重要提示、目录和释义
    股票简称：圣邦股份
    公司名称：圣邦微电子（北京）股份有限公司

    第三节 管理层讨论与分析
    公司主要产品为高性能模拟芯片，应用于通信、消费、汽车等领域。
    公司采用买断式经销为主的销售模式，圣邦微电子与经销商签订买断式协议，产品覆盖下游电子设备制造商。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_company_profile_backfill(evidence)

    assert "圣邦微电子" not in judgment
    assert "圣邦股份" not in judgment
    assert "买断式经销" in judgment or "经销为主" in judgment
    assert refs


def test_generic_mechanism_catches_aerospace_new_material_terms():
    """Generic markers should capture carbon fiber / aerospace project contexts."""
    text = """
    公司主要产品为碳纤维及碳纤维织物、预浸料等功能材料。
    公司产品应用于航空航天、轨道交通、新能源等领域。
    公司采用直销为主、经销为辅的销售模式。
    国产 T1100 级碳纤维材料制备技术研发项目目标已达成，可批量供货；
    ZM40X 碳纤维百吨级工程化制备技术研究项目已完成生产线安装，达到批产可批量供货。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)

    customer = evidence["customer_chain"]
    assert customer["present"]
    assert "航空航天" in " ".join(customer["snippets"])

    sales = evidence["sales_model"]
    assert sales["present"]
    assert "直销为主" in " ".join(sales["snippets"])

    products = evidence["product_lines"]
    assert products["present"]
    product_text = " ".join(products["snippets"])
    assert "T1100" in product_text
    assert "ZM40X" in product_text
    assert "预浸料" in product_text or "碳纤维" in product_text

    statuses = evidence["project_statuses"]
    assert statuses["present"]
    assert "批量供货" in " ".join(statuses["snippets"])

    judgment, refs = build_company_profile_backfill(evidence)
    assert "航空航天" in judgment or "碳纤维" in judgment or "预浸料" in judgment
    assert "频段" not in judgment
    assert "芯片" not in judgment
    assert refs

    rd_judgment, _ = build_rd_progress_backfill(evidence)
    assert any(t in rd_judgment for t in ("T1100", "ZM40X", "百吨级", "工程化", "批量供货"))


def test_customer_chain_filters_percent_point_company_noise():
    """Cross-table fragments like '百分点深圳英集芯科技' should be dropped."""
    text = """
    公司采用经销为主的销售模式，产品应用于小米、OPPO、vivo、三星等品牌。
    百分点深圳英集芯科技、也不断应用于新款智能终端产品。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)

    customer = evidence["customer_chain"]
    joined = " ".join(customer["snippets"])
    assert "百分点" not in joined
    assert "深圳英集芯科技" not in joined
    assert "小米" in joined
    assert "OPPO" in joined
    assert "vivo" in joined
    assert "三星" in joined

    judgment, refs = build_company_profile_backfill(evidence)
    assert "百分点" not in judgment
    assert "深圳英集芯科技" not in judgment
    assert "小米" in judgment
    assert refs


def test_generic_mechanism_catches_other_company_terms():
    """Same generic patterns should work for a different industry fixture."""
    text = """
    公司主要产品为高性能碳纤维，产品应用于航空航天、轨道交通、新能源等领域。
    公司采用直销为主、经销为辅的销售模式，与主要客户签订长期供货协议。
    国产 T1100 级碳纤维材料制备技术研发项目目标已达成，可批量供货；
    ZM40X 碳纤维百吨级工程化制备技术研究项目已完成生产线安装，达到批产可批量供货。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)

    customer = evidence["customer_chain"]
    assert customer["present"]
    assert "航空航天" in " ".join(customer["snippets"])

    sales = evidence["sales_model"]
    assert sales["present"]
    assert "直销为主" in " ".join(sales["snippets"])

    products = evidence["product_lines"]
    assert products["present"]
    product_text = " ".join(products["snippets"])
    assert "T1100" in product_text
    assert "ZM40X" in product_text

    statuses = evidence["project_statuses"]
    assert statuses["present"]
    assert "批量供货" in " ".join(statuses["snippets"])

    judgment, refs = build_rd_progress_backfill(evidence)
    assert "T1100" in judgment
    assert "ZM40X" in judgment
    assert "批量供货" in judgment
    assert refs


def test_generic_mechanism_catches_eda_product_and_certification_terms():
    """A small EDA signal set should improve recall without hard-coding issuers."""
    text = """
    公司主要从事用于集成电路设计、制造和封装的 EDA 工具软件开发、销售及相关服务业务。
    公司围绕数字芯片设计 EDA、模拟设计 EDA、存储芯片设计 EDA、先进封装 EDA、3DIC 设计 EDA
    等领域取得重大突破，产品成功导入国内龙头芯片设计和制造企业核心设计流程。
    报告期内，公司在 AI+EDA、PDK 生态和 Chiplet 设计验证方向持续推进。
    验证工具 Qualib 和高精度时序仿真分析工具 ICE xplorer-XTime 等八款工具获得 ISO 26262
    TCL3 和 IEC 61508 T2 国际标准认证。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)

    products = evidence["product_lines"]
    assert products["present"]
    product_text = " ".join(products["snippets"])
    assert "EDA" in product_text
    assert "3DIC" in product_text
    assert "Chiplet" in product_text or "PDK" in product_text

    statuses = evidence["project_statuses"]
    assert statuses["present"]
    status_text = " ".join(statuses["snippets"])
    assert "ISO 26262" in status_text
    assert "IEC 61508" in status_text

    judgment, refs = build_rd_progress_backfill(evidence)
    assert any(term in judgment for term in ("EDA", "3DIC", "Chiplet", "PDK"))
    assert any(term in judgment for term in ("ISO 26262", "IEC 61508", "认证"))
    assert "。认证与导入：" in judgment
    assert refs


def test_generic_mechanism_catches_smart_vehicle_soc_project_terms():
    """Smart-vehicle SoC annual reports should be covered by generic product/status tokens."""
    text = """
    公司聚焦汽車級智能車計算 SoC 及基於 SoC 的解決方案。
    華山 A2000 是面向高階智能駕駛的高算力芯片，採用 7nm 工藝，已完成回片並獲得頭部車企定點。
    武當 C1200 系列芯片在 2025 年實現從定點到量產。
    SesameX 平台已在具身智能、Robotaxi 和智能影像場景推進商業化落地。
    端側 AI、NPU 和艙駕一體方案是公司後續產品演進方向。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)

    products = evidence["product_lines"]
    assert products["present"]
    product_text = " ".join(products["snippets"])
    assert "SoC" in product_text
    assert "智能駕駛" in product_text or "具身智能" in product_text
    assert any(term in product_text for term in ("A2000", "C1200", "SesameX"))

    statuses = evidence["project_statuses"]
    assert statuses["present"]
    status_text = " ".join(statuses["snippets"])
    assert any(term in status_text for term in ("回片", "定點", "量產", "商業化落地"))

    judgment, refs = build_rd_progress_backfill(evidence)
    assert any(term in judgment for term in ("SoC", "A2000", "C1200", "SesameX"))
    assert any(term in judgment for term in ("回片", "定點", "量產", "商業化落地"))
    assert refs


def test_company_profile_backfill_summarizes_smart_vehicle_solution_coverage_without_noise():
    """Profile backfill should not turn generic phrases like '能夠為智能' into customers."""
    text = """
    公司產品矩陣將實現高中低全系列覆蓋，能夠為智能汽車、機器人以及各類 AIoT 終端
    提供從雲側到端側、從車規到消費級的完整 AI 推理芯片解決方案。
    一方面，用 A2000 芯片推動 L2/L3 級輔助駕駛規模化落地，同時佈局 L4 級 Robotaxi 場景。
    目前公司已經與核心算法廠商及頭部車企達成合作，後續將推進更多量產項目落地。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_company_profile_backfill(evidence)

    assert refs
    assert "能夠為智能" not in judgment
    assert any(term in judgment for term in ("智能汽車", "機器人", "AIoT", "Robotaxi", "SoC", "芯片"))
    assert "解决方案" in judgment or "解決方案" in judgment or "产品/技术方向" in judgment


def test_rd_progress_backfill_strips_section_number_prefix():
    """RD summaries should not keep heading prefixes such as '二、'."""
    text = """
    二、 SesameX 平台引領具身智能新範式，具身智能解決方案業務商業化落地。
    2025 年公司通過發佈 SesameX 平台，完成端側 AI 全棧芯片供應商轉型。
    A2000 芯片已取得頭部車企定點，預計 2026 年內將有多個量產項目落地。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_rd_progress_backfill(evidence)

    assert refs
    assert "产品/项目进展：二、" not in judgment
    assert "SesameX" in judgment or "A2000" in judgment


def test_black_sesame_profile_backfill_keeps_chip_platforms_and_customer_scenarios():
    """Smart-vehicle AI chip profile backfill should retain platforms, scenarios, customers."""
    text = """
    公司聚焦汽車級智能車計算 SoC 及基於 SoC 的解決方案，產品覆蓋智能汽車、機器人、AIoT 及端側 AI 等場景。
    華山 A2000 是面向高階智能駕駛的高算力芯片，武當 C1200 系列芯片瞄準艙駕一體及輔助駕駛市場，
    SesameX 平台已在具身智能、Robotaxi 和智能影像場景推進商業化落地。
    公司與吉利、東風、比亞迪、一汽等頭部車企達成合作，並與蘿蔔快跑、雲深處、傅利葉、聯想、極智嘉等
    客戶及合作夥伴在機器人、具身智能等場景展開合作。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_company_profile_backfill(evidence)

    assert refs
    assert any(term in judgment for term in ("A2000", "C1200", "SesameX", "SoC"))
    assert any(term in judgment for term in ("智能汽車", "具身智能", "Robotaxi", "機器人", "AIoT"))
    assert any(term in judgment for term in ("吉利", "東風", "比亞迪", "一汽"))
    assert any(term in judgment for term in ("蘿蔔快跑", "雲深處", "傅利葉", "聯想", "極智嘉"))
    assert any(term in judgment for term in ("量产车型", "客户导入", "场景放量", "商业化落地", "商業化落地"))
    assert "confirmed_fact" not in judgment


def test_profile_backfill_deduplicates_repeated_partner_brand_tokens():
    text = """
    公司與蘿蔔快跑合作推動 L4 級 Robotaxi 場景量產落地，蘿蔔快跑作為合作方推進商業化落地。
    產品覆蓋智能駕駛、端側 AI 和具身智能等方向。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_company_profile_backfill(evidence)

    assert refs
    assert judgment.count("蘿蔔快跑") == 1


def test_black_sesame_profile_backfill_extracts_generic_partner_and_platform_names():
    text = """
    截止目前，A2000 正與元戎啟行、Nullmax 等核心算法廠商進行端到端、視覺—語言—動作
    (VLA) 算法的深度適配與驗證，目前已取得頭部車企定點。
    一方面，用 A2000 芯片推動 L2/L3 級輔助駕駛規模化落地，同時佈局 L4 級 Robotaxi 場景，
    目前公司已經與元戎啟行、蘿蔔快跑等行業領先企業達成戰略合作；另一方面，擴大
    A1000 系列和 C1200 系列芯片的量產規模。
    11 月，SesameX 多維具身智能平台正式發佈，產品覆蓋智能駕駛、端側 AI、具身智能和智能影像等方向。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_company_profile_backfill(evidence)

    assert refs
    assert "元戎啟行" in judgment
    assert "Nullmax" in judgment
    assert "蘿蔔快跑" in judgment
    assert "A2000" in judgment
    assert "SesameX" in judgment


def test_horizon_profile_backfill_does_not_treat_generic_business_phrase_as_partner():
    text = """
    憑藉世界級的算法能力、在中國車載級芯片領域卓越的生態影響力、靈活的商業模式及深受好評的
    HSD 量產表現，我們的算法及軟件棧已成為智能輔助駕駛領域備受推崇的基座模型，
    並推動更廣泛的 OEM 及生態系統合作夥伴採用我們的授權方案。
    Horizon SuperDrive（HSD）正式量產，為中國首個量產的基於一段式端到端技術的智能駕駛大模型。
    征程 6 系列處理硬件驅動的產品解決方案需求旺盛，支持高速公路和城區 NOA。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_company_profile_backfill(evidence)

    assert refs
    assert "深受好評" not in judgment
    assert "軟件棧已成為" not in judgment
    assert any(term in judgment for term in ("HSD", "Horizon", "征程", "NOA"))
    assert any(term in judgment for term in ("智能駕駛", "輔助駕駛", "車載級芯片"))


def test_black_sesame_rd_backfill_keeps_project_statuses():
    """Smart-vehicle AI chip RD backfill should retain product names and status words."""
    text = """
    華山 A2000 採用 7nm 工藝，已完成回片並獲得頭部車企定點，預計 2026 年內將有多個量產項目落地。
    下一代 NPU 及 IP 研發持續推進，相關芯片已完成流片並進入驗證階段，支持 AUTOSAR 軟件生態。
    武當 C1200 系列芯片在 2025 年實現從定點到量產，艙駕一體方案已開始交付頭部客戶。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_rd_progress_backfill(evidence)

    assert refs
    assert any(term in judgment for term in ("A2000", "C1200", "SesameX", "NPU"))
    assert any(term in judgment for term in ("回片", "定點", "量產", "流片", "驗證", "交付"))
    assert "收入转化" in judgment or "毛利改善" in judgment or "量产节奏" in judgment
    assert "confirmed_fact" not in judgment


def test_product_project_backfill_does_not_emit_table_fragments():
    """Mixed table/number fragments should not appear in backfill output."""
    text = """
    4,436.26 168.61 3,580.60 A2000 芯片 2025 年實現回片並取得定點。
    2,133.50 89.12 1,800.00 C1200 系列芯片實現量產並交付客戶。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_rd_progress_backfill(evidence)

    assert refs
    assert "4,436.26" not in judgment
    assert "168.61" not in judgment
    assert "3,580.60" not in judgment
    assert "2,133.50" not in judgment
    assert any(term in judgment for term in ("A2000", "C1200"))
    assert any(term in judgment for term in ("回片", "定點", "量產", "交付"))


def test_fulltext_backfill_does_not_pollute_financial_risks():
    """Backfill judgments must not be inferred as financial risks by fulltext validator."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))
    from periodic_report_fulltext_llm_analysis import _infer_risk_type_from_text

    profile = "公司画像补充判断：客户与场景：吉利、东风、比亚迪等车企，覆盖智能汽车、Robotaxi、具身智能场景。"
    rd = "研发与技术进展补充判断：产品/项目进展：华山 A2000 完成回片/定点，武当 C1200 实现量产，SesameX 推进商业化落地。"
    assert _infer_risk_type_from_text(profile) == ""
    assert _infer_risk_type_from_text(rd) == ""


def test_wifi_snippet_gets_technical_term_score():
    """Wi-Fi token should be recognized as a technical term so coverage snippets retain it."""
    from periodic_report_product_project_evidence import _snippet_quality_score

    wifi_snippet = "公司产品系列覆盖 2G、3G、4G、5G UHB 等蜂窝通信频段和 Wi-Fi 通信等。"
    score = _snippet_quality_score(wifi_snippet)
    assert score > 0, f"Wi-Fi snippet should score above zero, got {score}"


def test_rd_progress_backfill_includes_statuses_even_if_not_in_products():
    """Statuses bucket should contribute to RD backfill when product_lines omits a snippet."""
    evidence = {
        "product_lines": {
            "present": True,
            "snippets": ["产品A 已量产。"] * 5,
            "refs": ["fulltext-1-0"],
        },
        "project_statuses": {
            "present": True,
            "snippets": ["产品B 获得 AEC-Q104 认证。"],
            "refs": ["fulltext-2-0"],
        },
        "business_significance": {"present": False, "snippets": [], "refs": []},
    }
    judgment, refs = build_rd_progress_backfill(evidence)
    assert "AEC-Q104" in judgment
    assert "fulltext-2-0" in refs


def test_rd_progress_backfill_keeps_certification_among_mass_production():
    """Certification/testing snippets should not be completely displaced by mass-production snippets."""
    text = """
    2025 年公司率先量产了 Phase8L 方案的全集成 L-PAMiD，并成功导入头部客户的旗舰手机机型，项目目标已达成。
    报告期内，Phase8L 全集成 L-PAMiD 产品已在头部品牌客户高端旗舰机型实现量产出货，同时公司于 2024 年导入的三星自研供应链体系项目已逐步释放订单量，推动营业收入实现增长。
    2025 年公司推出 5G UHB 频段 L-PAMiF 模组，已在三星自研体系规模商用，客户导入进展顺利。
    公司 RedCap 射频前端完整解决方案已经在头部物联网客户规模量产，并持续获得客户认可。
    新一代小尺寸高功率 MMMB PA 模组已在三星自研体系规模商用，产品竞争力进一步提升。
    其中，Phase8L 全集成 L-PAMiD 模组实现在头部品牌客户高端旗舰机型量产出货，产品结构得到显著优化。
    公司部分产品已经通过车规可靠性的测试，获得 AEC-Q104 车规认证，并在客户端推广。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_rd_progress_backfill(evidence)
    assert "AEC-Q104" in judgment, f"Expected AEC-Q104 in judgment, got: {judgment}"


def test_company_profile_backfill_is_concise():
    """公司画像 backfill should be at most 3 short sentences, each <=120 chars."""
    item_map = _make_item_map(HUIZHIWEI_PROFILE_SNIPPET, HUIZHIWEI_SALES_MODEL_SNIPPET)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_company_profile_backfill(evidence)

    assert judgment.startswith("公司画像补充判断：")
    # Split by the sentence delimiter “。”
    sentences = [s for s in judgment.split("。") if s.strip()]
    assert len(sentences) <= 3, f"Expected <=3 sentences, got {len(sentences)}: {sentences}"
    for sent in sentences:
        assert len(sent) <= 120, f"Sentence too long ({len(sent)}): {sent}"
    assert "三星" in judgment
    assert "经销" in judgment or "买断式" in judgment
    assert "Wi-Fi" in judgment or "UHB" in judgment


def test_profile_backfill_summarizes_platform_product_categories():
    """Non-RF platform companies should keep product categories, not only application buzzwords."""
    text = """
    公司产品覆盖信号链、电源管理、传感器三大方向，拥有 38 大类、6,800 余款可供销售产品。
    公司产品广泛应用于工业与能源、汽车、网络与计算、消费电子、新能源汽车、数据中心、机器人、人工智能等领域。
    公司采用 “经销为主、直销为辅 ”的销售模式。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_company_profile_backfill(evidence)

    assert "信号链" in judgment
    assert "电源管理" in judgment
    assert "传感器" in judgment
    assert "人工智能，采用" not in judgment
    assert refs


def test_profile_backfill_does_not_treat_smart_device_phrase_as_customer():
    text = """
    公司产品可应用于智能手机、蓝牙耳机等智能可穿戴设备。
    公司采用 “经销为主、直销为辅 ”的销售模式。
    产品覆盖模拟信号采集和电池管理等产品方向。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_company_profile_backfill(evidence)

    assert refs
    assert "可应用于智能" not in judgment
    assert "耳机等智能" not in judgment
    assert "经销为主" in judgment
    assert "模拟" in judgment


def test_rd_progress_backfill_is_concise_and_filters_table_fragments():
    """RD backfill should be at most 3 short sentences and drop numeric table fragments."""
    text = """
    4,436.26 168.61 3,580.60 第二代产品处于预量产阶段设计推出 LNA 的接收模组，支持 Sub3G 射频前端方案。
    2025 年公司率先量产了 Phase8L 方案的全集成 L-PAMiD，RedCap 方案也实现规模量产。
    公司部分产品已经通过车规可靠性的测试，获得 AEC-Q104 车规认证，并在客户端推广。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_rd_progress_backfill(evidence)

    assert judgment.startswith("研发与技术进展补充判断：")
    sentences = [s for s in judgment.split("。") if s.strip()]
    assert len(sentences) <= 3, f"Expected <=3 sentences, got {len(sentences)}: {sentences}"
    for sent in sentences:
        assert len(sent) <= 120, f"Sentence too long ({len(sent)}): {sent}"
    # The table-fragment snippet should not appear literally.
    assert "4,436.26" not in judgment
    assert "168.61" not in judgment
    assert "3,580.60" not in judgment
    assert "Phase8L" in judgment or "L-PAMiD" in judgment
    assert "AEC-Q104" in judgment


def test_rd_progress_backfill_avoids_mid_word_carbon_fiber_concat():
    """Carbon-fiber RD summaries should not start mid-word or include raw repeated table text."""
    text = """
    湿法工艺和干喷湿纺工艺两种工艺路线均实现 T1100 级碳纤维关键技术重大突破，
    通过工艺创新，在国内首次采用非石墨化工艺实现百吨级高模 ZM40X 级产品工业化稳定生产。
    达到批产可批量供货为现有用户及新客户提供更多选择，完善产品谱系，提升竞争力
    国产 T1000 级碳纤维材料制备技术研发研发高强高模 T1000 碳纤维 (6K/12K) 已完成设备调试及工艺验证。
    """
    item_map = _make_item_map(text)
    evidence = extract_product_project_evidence(item_map)
    judgment, refs = build_rd_progress_backfill(evidence)

    assert "产品/项目进展：法工艺" not in judgment
    assert "认证与导入：法工艺" not in judgment
    assert "研发研发" not in judgment
    assert "提升竞争力国产" not in judgment
    assert any(term in judgment for term in ("湿法工艺", "T1100", "ZM40X", "T1000"))
    for sent in [s for s in judgment.split("。") if s.strip()]:
        assert len(sent) <= 120, f"Sentence too long ({len(sent)}): {sent}"
    assert refs


def test_backfill_judgments_are_excluded_from_risk_inference():
    """Risk inference should ignore company profile and RD supplemental backfill text."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))
    from periodic_report_fulltext_llm_analysis import _infer_risk_type_from_text

    profile_text = (
        "公司画像补充判断：客户与渠道：三星、vivo等品牌，华勤/龙旗等ODM，采用买断式经销为主。"
        "产品覆盖：2G、3G、4G、5G、UHB、Wi-Fi等频段/场景。"
        "收入对终端需求周期和渠道备货节奏较为敏感。"
    )
    rd_text = (
        "研发与技术进展补充判断：产品/项目进展：Phase8L 全集成 L-PAMiD 已量产。"
        "认证与导入：AEC-Q104 车规认证已通过。"
        "技术迭代和客户导入是后续收入转化的重要观察点。"
    )
    black_sesame_profile_text = (
        "公司画像补充判断：客户与场景：吉利、东风、比亚迪、萝卜快跑、云深处等客户/合作方，"
        "覆盖智能汽車、Robotaxi、具身智能、机器人、AIoT 等场景，采用車規 SoC 解决方案。"
        "产品覆盖：华山 A2000、武当 C1200、SesameX 平台等芯片/平台方向。"
        "收入取决于量产车型、客户导入和场景放量。"
    )
    black_sesame_rd_text = (
        "研发与技术进展补充判断：产品/项目进展：华山 A2000 已完成回片并获得头部車企定點，"
        "武当 C1200 系列芯片实现从定點到量產，SesameX 平台推进具身智能、Robotaxi 和智能影像場景商業化落地。"
        "认证与导入：下一代 NPU、流片、AUTOSAR 等持续投入。"
        "技术转化和量产节奏是收入与毛利改善观察点。"
    )
    assert _infer_risk_type_from_text(profile_text) == ""
    assert _infer_risk_type_from_text(rd_text) == ""
    assert _infer_risk_type_from_text(black_sesame_profile_text) == ""
    assert _infer_risk_type_from_text(black_sesame_rd_text) == ""


def test_snippets_remain_close_to_original_text():
    """Extracted snippets must be repair-normalized slices of the source block text."""
    import re

    item_map = _make_item_map(HUIZHIWEI_PROFILE_SNIPPET)
    evidence = extract_product_project_evidence(item_map)

    full_text = HUIZHIWEI_PROFILE_SNIPPET
    full_compact = re.sub(r"\s+", "", full_text)
    for category in ("customer_chain", "frequency_coverage"):
        for snippet in evidence[category]["snippets"]:
            snippet_compact = re.sub(r"\s+", "", snippet)
            assert snippet_compact in full_compact
