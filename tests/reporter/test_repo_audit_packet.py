import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from build_repo_audit_packet import report_sample_status_line


def test_report_sample_status_marks_stale_report_with_mtime(tmp_path):
    report = tmp_path / "reports" / "样例_20260630.md"
    report.parent.mkdir()
    report.write_text("# 样例报告\n", encoding="utf-8")
    os.utime(report, (100, 100))

    line = report_sample_status_line(report, repo_root=tmp_path, head_timestamp=200)

    assert "`reports/样例_20260630.md`" in line
    assert "stale_sample=true" in line
    assert "mtime=" in line


def test_report_sample_status_marks_missing_report():
    line = report_sample_status_line(Path("/tmp/missing_report.md"), repo_root=Path("/tmp"), head_timestamp=200)

    assert "MISSING" in line
