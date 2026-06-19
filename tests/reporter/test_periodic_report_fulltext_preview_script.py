import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from periodic_report_fulltext_preview import build_preview_markdown, default_output_path


SAMPLE_REPORT = """
2025年年度报告

营业收入 100.00万元 同比增长 20.00%
归属于上市公司股东的净利润 10.00万元

分产品
产品A 营业收入 80.00万元 毛利率 30.00%

前五名客户销售额 90.00万元 占年度销售总额比例 90.00%

研发项目
高性能芯片项目 已完成验证并量产。
"""


def test_build_preview_markdown_from_cache_item_content(tmp_path):
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    (cache_dir / "测试股_2025_annual_jina.txt").write_text(SAMPLE_REPORT, encoding="utf-8")

    markdown = build_preview_markdown(
        stock_code="000001",
        stock_name="测试股",
        cache_dir=cache_dir,
        report_type="annual_report",
        source_intake_section=False,
    )

    assert "# 定期报告全文摘要 Preview" in markdown
    assert "测试股" in markdown
    assert "periodic_report_fulltext_analysis" in markdown
    assert "professional_analysis" in markdown
    assert "定期报告全文判断摘要" in markdown
    assert "confirmed_fact" not in markdown
    assert "fact_candidate" not in markdown


def test_build_preview_markdown_can_render_source_intake_section(tmp_path):
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    (cache_dir / "000001_2025_annual_jina.txt").write_text(SAMPLE_REPORT, encoding="utf-8")

    markdown = build_preview_markdown(
        stock_code="000001",
        stock_name="测试股",
        cache_dir=cache_dir,
        report_type="annual_report",
        source_intake_section=True,
    )

    assert "## Source Intake 分层证据观察" in markdown
    assert "### 定期报告全文摘要（实验路径）" in markdown
    assert "professional_analysis" in markdown
    assert "confirmed_fact" not in markdown
    assert "fact_candidate" not in markdown


def test_build_preview_markdown_reports_missing_cache(tmp_path):
    markdown = build_preview_markdown(
        stock_code="000001",
        stock_name="测试股",
        cache_dir=tmp_path / "missing",
        report_type="annual_report",
    )

    assert "未找到本地年报缓存" in markdown
    assert "000001" in markdown
    assert "测试股" in markdown


def test_default_output_path_uses_tmp_and_stock_name():
    path = default_output_path("测试股", "000001", "annual_report")

    assert str(path).startswith("/tmp/")
    assert path.name == "测试股_000001_annual_report_fulltext_preview.md"


def test_cli_runs_from_repo_root(tmp_path):
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    (cache_dir / "测试股_2025_annual_jina.txt").write_text(SAMPLE_REPORT, encoding="utf-8")
    output = tmp_path / "preview.md"
    script = Path(__file__).parent.parent.parent / "scripts" / "periodic_report_fulltext_preview.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--stock-code",
            "000001",
            "--stock-name",
            "测试股",
            "--cache-dir",
            str(cache_dir),
            "--source-intake-section",
            "--output",
            str(output),
        ],
        cwd=Path(__file__).parent.parent.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert str(output) in result.stdout
    content = output.read_text(encoding="utf-8")
    assert "## Source Intake 分层证据观察" in content
    assert "professional_analysis" in content
