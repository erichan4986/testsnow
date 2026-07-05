import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_extractor import extract_periodic_report, render_markdown


SAMPLE_REPORT = """
中简科技股份有限公司 2025 年年度报告

第一节 重要提示、目录和释义
公司面临客户集中、产品价格下降、技术迭代及供应链波动风险。

第二节 公司简介和主要财务指标
营业收入 100,000,000 元，上年同期 70,000,000 元，同比增长 42.86%。
应收账款 90,000,000 元，上年同期 30,000,000 元，同比增长 200.00%。
归属于上市公司股东的净利润 10,000,000 元。
扣除非经常性损益后的净利润 -2,000,000 元。
经营活动产生的现金流量净额 -5,000,000 元。
研发投入金额 30,000,000 元，其中资本化研发投入 18,000,000 元。
存货 80,000,000 元，上年同期 30,000,000 元，同比增长 166.67%。
存货跌价准备 500,000 元。
在建工程 120,000,000 元，上年同期 40,000,000 元。

第三节 管理层讨论与分析
报告期内，公司认为半导体行业仍处于景气度下行周期，部分成熟制程产品价格承压。
公司将继续围绕高端产品和核心客户需求进行研发布局，提升自主可控能力。
报告期内客户对公司部分产品的需求量阶段性减少，导致发货暂时减少。

第十节 财务报告
审计意见类型：标准无保留意见。
"""


def test_detects_annual_report_and_audit_status():
    result = extract_periodic_report(SAMPLE_REPORT, industry="semiconductor")

    assert result["report_type"] == "annual_report"
    assert result["audit_status"] == "audited"


def test_extracts_management_discussion_as_management_view_not_confirmed_fact():
    result = extract_periodic_report(SAMPLE_REPORT, industry="semiconductor")

    management = [item for item in result["items"] if item["usage"] == "management_view"]
    assert management
    assert any("景气度下行周期" in item["evidence"] for item in management)
    assert all(item["usage"] != "confirmed_fact" for item in management)


def test_financial_forensics_flags_core_semiconductor_risks():
    result = extract_periodic_report(SAMPLE_REPORT, industry="semiconductor")
    titles = {item["title"] for item in result["items"]}

    assert "应收账款增速显著高于营收增速" in titles
    assert "扣非净利润弱于净利润" in titles
    assert "经营现金流弱于利润" in titles
    assert "研发资本化率偏高" in titles
    assert "存货增长且跌价准备偏低" in titles
    assert "在建工程快速增长" in titles


def test_render_markdown_uses_risk_language_without_calling_fraud():
    result = extract_periodic_report(SAMPLE_REPORT, industry="semiconductor")
    markdown = render_markdown(result)

    assert "## 财报排雷观察" in markdown
    assert "应收账款增速显著高于营收增速" in markdown
    assert "管理层讨论与分析摘录" in markdown
    assert "造假" not in markdown


def test_detects_semiannual_report_as_interim_unaudited():
    text = SAMPLE_REPORT.replace("2025 年年度报告", "2025 年半年度报告")
    result = extract_periodic_report(text, industry="semiconductor")

    assert result["report_type"] == "semiannual_report"
    assert result["audit_status"] == "interim_unaudited"


def test_cli_outputs_json_and_markdown(tmp_path):
    input_path = tmp_path / "annual.txt"
    input_path.write_text(SAMPLE_REPORT, encoding="utf-8")
    script_path = Path(__file__).parent.parent.parent / "scripts" / "periodic_report_extractor.py"

    json_run = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--txt",
            str(input_path),
            "--industry",
            "semiconductor",
            "--format",
            "json",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(json_run.stdout)
    assert payload["report_type"] == "annual_report"
    assert any(item["usage"] == "financial_forensics" for item in payload["items"])

    markdown_run = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--txt",
            str(input_path),
            "--industry",
            "semiconductor",
            "--format",
            "markdown",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "## 管理层讨论与分析摘录" in markdown_run.stdout


def test_jina_style_toc_does_not_become_management_view():
    text = """
    目录
    第三节 管理层讨论与分析 ................................ 9
    第四节 公司治理 ................................ 60

    # 一、报告期内公司从事的主要业务
    公司作为国内航空航天领域高端碳纤维核心供应商，专注于高性能碳纤维及结构材料的自主创新与工程化应用。
    报告期内，公司按照技术向纵深发展、应用向纵横发展的思路，结合行业竞争格局和市场变化开展相关工作。

    第四节 公司治理
    """
    result = extract_periodic_report(text, industry="hardtech")
    management = [item for item in result["items"] if item["usage"] == "management_view"]

    assert management
    assert all("................................" not in item["evidence"] for item in management)
    assert any("核心供应商" in item["evidence"] for item in management)


def test_balance_sheet_percentage_columns_do_not_create_fake_growth_signals():
    text = """
    2025 年年度报告
    营业收入（元） 846,092,620.66 812,470,190.54 4.14%
    应收账款 400,706,972.46 7.93% 835,058,483.10 17.99% -10.06% 本报告期末回款增加
    存货 111,460,663.53 2.21% 530,764,964.44 11.43% -9.22%
    第三节 管理层讨论与分析
    公司认为行业竞争格局仍在变化。
    第十节 财务报告
    """
    result = extract_periodic_report(text, industry="hardtech")
    titles = {item["title"] for item in result["items"]}

    assert "应收账款增速显著高于营收增速" not in titles
    assert "存货增长且跌价准备偏低" not in titles


def test_detects_standard_unqualified_opinion_with_de():
    text = SAMPLE_REPORT.replace("标准无保留意见", "标准的无保留意见")
    result = extract_periodic_report(text, industry="hardtech")

    assert result["audit_status"] == "audited"


def test_non_standard_audit_opinion_not_misclassified_as_audited():
    text = SAMPLE_REPORT.replace("标准无保留意见", "非标准无保留意见")
    result = extract_periodic_report(text, industry="hardtech")

    assert result["audit_status"] == "audited_attention_required"


def test_internal_control_nonstandard_does_not_override_financial_standard_opinion():
    text = """
    2025 年年度报告
    内控审计报告意见类型 带强调事项段的无保留意见。
    会计师事务所是否出具非标准意见的内部控制审计报告：是。
    第八节 财务报告
    一、审计报告
    审计意见类型 标准的无保留意见。
    """
    result = extract_periodic_report(text, industry="hardtech")

    assert result["audit_status"] == "audited"


def test_metric_value_skips_legal_description_and_uses_later_amount():
    text = """
    2025 年年度报告
    公司最近三个会计年度扣除非经常性损益后的净利润三者孰低为负值。
    归属于上市公司股东的净利润 10,000,000 元。
    扣除非经常性损益后的净利润 -2,000,000 元。
    经营活动产生的现金流量净额 8,000,000 元。
    第三节 管理层讨论与分析
    公司认为行业仍有压力。
    第十节 财务报告
    审计意见类型：标准无保留意见。
    """
    result = extract_periodic_report(text, industry="semiconductor")
    titles = {item["title"] for item in result["items"]}

    assert "扣非净利润弱于净利润" in titles


def test_sections_found_filters_toc_lines_and_deduplicates():
    text = """
    目录
    第三节 管理层讨论与分析 ................................ 9
    第三节 管理层讨论与分析 ................................ 9
    第三节 管理层讨论与分析
    公司认为行业仍有压力。
    第四节 公司治理
    """
    result = extract_periodic_report(text, industry="hardtech")

    assert all("..." not in section for section in result["sections_found"])
    assert result["sections_found"].count("第三节管理层讨论与分析") == 1


def test_forensics_notes_list_unextracted_required_checks():
    result = extract_periodic_report(SAMPLE_REPORT, industry="semiconductor")

    notes = result["forensics_notes"]
    assert "应收票据/商业承兑结构" in notes["not_extracted"]
    assert "政府补助占利润比" not in notes["not_extracted"]
    assert "客户集中度与第一大客户依赖" not in notes["not_extracted"]
    assert "应收账款账龄结构" not in notes["not_extracted"]
    assert "受限资产/质押/冻结资产" not in notes["not_extracted"]
    assert "研发人员数量与人均研发投入" in notes["not_extracted"]
    assert notes["interpretation"] == "未列为风险不代表无风险；以下项目当前版本尚未结构化抽取。"


def test_management_view_keeps_long_sentence_without_premature_ellipsis():
    text = """
    2025 年年度报告
    第三节 管理层讨论与分析
    报告期内，公司在巩固现有航空航天主力型号批产交付任务的基础上，按照“技术向纵深发展，
    应用向纵横发展”的思路，深耕高壁垒、高价值应用场景，结合行业竞争格局和市场变化，
    重点围绕高性能碳纤维产能提升与技术创新、延伸结构与功能材料业务以及新应用、
    新场景的开拓开展了相关工作，形成了“纤维+预浸料+功能材料”这一特色鲜明、
    优势凸显的业务布局。
    第四节 公司治理
    """
    result = extract_periodic_report(text, industry="hardtech")
    management = [item for item in result["items"] if item["usage"] == "management_view"]

    assert any("纤维+预浸料+功能材料" in item["evidence"] for item in management)
    assert any("业务布局" in item["evidence"] for item in management)
    assert all(not item["evidence"].endswith("…") for item in management)


def test_render_markdown_does_not_repeat_same_interpretation_on_every_row():
    text = SAMPLE_REPORT + "\n第六节 重要事项\n公司持续加大项目投入，固定资产逐步提升，可能存在产能闲置情形。"
    result = extract_periodic_report(text, industry="semiconductor")
    markdown = render_markdown(result)

    assert markdown.count("管理层观点可用于理解公司叙事，但不等同于外部确认事实。") == 1
    assert markdown.count("资本开支、回购、激励或重大合同需要与现金流、产能利用率和订单消化交叉验证。") == 1
    assert "| 等级 | 主题 | 证据 | 解读 |" not in markdown
    assert "| 等级 | 主题 | 证据 |" in markdown


def test_capital_action_filters_not_applicable_checkbox_noise():
    text = """
    2025 年年度报告
    第三节 管理层讨论与分析
    公司认为行业仍在变化，持续提升研发和产能能力。
    第四节 公司治理
    公司与实际控制人之间的产权及控制关系的方框图 实际控制人通过信托或其他资产管理方式控制公司 □适用 ☑不适用
    4、公司控股股东或第一大股东及其一致行动人累计质押股份数量占其所持公司股份数量比例达到 80% □适用 ☑不适用
    5、其他持股在 10% 以上的法人股东 □适用 ☑不适用
    6、控股股东、实际控制人、重组方及其他承诺主体股份限制减持 □适用 ☑不适用
    第六节 重要事项
    为满足终端用户需求，公司近年来持续加大项目投入，固定资产逐步提升，若客户需求或市场开拓不及预期，公司可能存在产能闲置情形。
    """
    result = extract_periodic_report(text, industry="hardtech")
    capital = [item for item in result["items"] if item["usage"] == "capital_action"]

    assert capital
    assert any("产能闲置" in item["evidence"] for item in capital)
    assert all("☑不适用" not in item["evidence"] and "不适用" not in item["evidence"] for item in capital)
    assert all("方框图" not in item["evidence"] for item in capital)


def test_capital_action_does_not_treat_generic_capacity_strategy_as_capex():
    text = """
    2025 年年度报告
    第三节 管理层讨论与分析
    公司围绕高性能碳纤维产能提升与技术创新、新应用场景开拓开展相关工作，形成纤维+预浸料+功能材料的发展格局。
    公司持续加大项目投入，固定资产逐步提升，四期项目建设进展顺利，若客户需求不及预期可能存在产能闲置情形。
    第四节 公司治理
    """
    result = extract_periodic_report(text, industry="hardtech")
    capital = [item for item in result["items"] if item["usage"] == "capital_action"]

    assert capital
    assert any("固定资产逐步提升" in item["evidence"] for item in capital)
    assert all("产能提升与技术创新、新应用场景开拓" not in item["evidence"] for item in capital)


def test_capital_action_filters_repeated_not_applicable_table_rows():
    text = """
    2025 年年度报告
    第六节 重要事项
    股权激励承诺 不适用 不适用 不适用 不适用 其他对公司中小股东所作承诺 不适用 不适用。
    四期项目建设进展顺利，进一步优化公司产能布局，夯实高端碳纤维规模化供应能力。
    """
    result = extract_periodic_report(text, industry="hardtech")
    capital = [item for item in result["items"] if item["usage"] == "capital_action"]

    assert capital
    assert any("四期项目建设进展顺利" in item["evidence"] for item in capital)
    assert all("股权激励承诺 不适用" not in item["evidence"] for item in capital)


def test_risk_disclosure_filters_see_detail_pointer_sentence():
    text = """
    2025 年年度报告
    第一节 重要提示、目录和释义
    # 结合监管政策、行业发展及产品应用领域等因素，公司在生产经营中或可 # 能面临相关风险，具体风险及应对措施请见
    第三节 管理层讨论与分析
    公司认为行业仍在变化，持续提升研发能力。
    """
    result = extract_periodic_report(text, industry="hardtech")
    risk = [item for item in result["items"] if item["usage"] == "risk_disclosure"]

    assert risk == []


def test_risk_disclosure_uses_actual_risk_subsection_after_front_pointer():
    text = """
    2025 年年度报告
    第一节 重要提示、目录和释义
    结合监管政策、行业发展及产品应用领域等因素，公司在生产经营中可能面临相关风险，具体风险及应对措施请见第三节。

    第三节 管理层讨论与分析
    十一、公司未来发展的展望
    （四）公司可能面对的风险
    1、客户集中风险：公司主要客户集中于航空航天领域，若重点型号订单节奏发生波动，可能对公司经营业绩产生不利影响。
    2、原材料价格波动风险：若上游原材料价格持续上涨，公司产品毛利率可能承压。
    第四节 公司治理
    """
    result = extract_periodic_report(text, industry="hardtech")
    risk = [item for item in result["items"] if item["usage"] == "risk_disclosure"]

    assert len(risk) >= 2
    assert any("客户集中风险" in item["evidence"] for item in risk)
    assert any("原材料价格波动风险" in item["evidence"] for item in risk)
    assert all("具体风险及应对措施请见" not in item["evidence"] for item in risk)


def test_financial_forensics_extracts_subsidy_customer_concentration_ar_aging_and_restricted_assets():
    text = """
    2025 年年度报告
    第二节 公司简介和主要财务指标
    营业收入 800,000,000 元，上年同期 760,000,000 元，同比增长 5.26%。
    归属于上市公司股东的净利润 30,000,000 元。
    经营活动产生的现金流量净额 28,000,000 元。

    第三节 管理层讨论与分析
    公司认为行业仍在变化，持续提升研发能力。

    第十节 财务报告
    计入当期损益的政府补助 18,000,000 元。
    前五名客户合计销售金额 620,000,000 元，占年度销售总额比例 77.50%。
    应收账款账龄组合中，1年以上应收账款余额 96,000,000 元，占应收账款余额比例 24.00%。
    所有权或使用权受到限制的资产：货币资金 45,000,000 元，受限原因主要为银行承兑汇票保证金。
    审计意见类型：标准无保留意见。
    """
    result = extract_periodic_report(text, industry="hardtech")
    titles = {item["title"] for item in result["items"]}

    assert "政府补助占利润比例较高" in titles
    assert "客户集中度较高" in titles
    assert "应收账款账龄老化" in titles
    assert "受限资产需要关注" in titles


def test_extracts_business_segments_and_product_revenue_margin_table():
    text = """
    2025 年年度报告
    第三节 管理层讨论与分析
    一、报告期内公司从事的主要业务
    1、高性能碳纤维及织物业务 报告期内，公司持续巩固航空航天主力型号批产交付任务，并开拓商业航天等新用户。
    2、结构与功能材料业务 公司设立常宏功能材料公司，开发多款结构材料与功能材料，向产业链高附加值环节延伸。

    四、主营业务分析
    （2）占公司营业收入或营业利润 10% 以上的行业、产品、地区、销售模式的情况
    分产品
    其中：碳纤维 443,494,353.42 198,630,573.93 55.21% -19.59% 0.05% -8.79%
    碳纤维织物 402,520,846.01 98,780,474.86 75.46% 54.60% 0.04% 13.38%
    第四节 公司治理
    """
    result = extract_periodic_report(text, industry="hardtech")
    business = [item for item in result["items"] if item["usage"] == "business_segment"]
    product_rows = [item for item in result["items"] if item["usage"] == "product_revenue_margin"]

    assert any("高性能碳纤维及织物业务" in item["evidence"] for item in business)
    assert any("结构与功能材料业务" in item["evidence"] for item in business)
    assert any("碳纤维：" in item["evidence"] and "毛利率55.21%" in item["evidence"] for item in product_rows)
    assert any("碳纤维织物：" in item["evidence"] and "营收同比54.60%" in item["evidence"] for item in product_rows)
    assert all("新材料制造业" not in item["evidence"] for item in product_rows)
    assert all("第三节 管理层讨论与分析" not in item["evidence"] for item in business)


def test_extracts_rd_progress_and_customer_concentration_as_structured_business_items():
    text = """
    2025 年年度报告
    第三节 管理层讨论与分析
    公司持续加大技术创新力度，湿法工艺和干喷湿纺工艺两种工艺路线均实现 T1100 级碳纤维关键技术重大突破。
    公司客户主要为国内大型航空航天企业集团，客户明确且集中度高。
    第十节 财务报告
    前五名客户合计销售金额 620,000,000 元，占年度销售总额比例 77.50%。
    审计意见类型：标准无保留意见。
    """
    result = extract_periodic_report(text, industry="hardtech")
    rd = [item for item in result["items"] if item["usage"] == "rd_progress"]
    customers = [item for item in result["items"] if item["usage"] == "customer_concentration"]

    assert any("T1100" in item["evidence"] and "重大突破" in item["evidence"] for item in rd)
    assert all("报告期内公司从事的主要业务" not in item["evidence"] for item in rd)
    assert any("77.50%" in item["evidence"] for item in customers)
