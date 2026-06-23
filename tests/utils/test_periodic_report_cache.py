from __future__ import annotations

import json
import subprocess
import sys
import builtins
from types import SimpleNamespace
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_cache import (  # noqa: E402
    cache_periodic_report,
    cache_periodic_report_from_url,
    discover_cninfo_annual_report,
    get_cninfo_market,
    standard_cache_paths,
)


def test_standard_cache_paths_use_stock_name_year_and_report_type(tmp_path: Path) -> None:
    text_path, meta_path = standard_cache_paths(
        stock_name="黑芝麻智能",
        report_year=2025,
        report_type="annual",
        cache_dir=tmp_path,
    )

    assert text_path == tmp_path / "黑芝麻智能_2025_annual_jina.txt"
    assert meta_path == tmp_path / "黑芝麻智能_2025_annual_meta.json"


def test_cache_periodic_report_registers_text_input_and_meta(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("第一节 公司业务\nA2000 芯片量产推进。\n", encoding="utf-8")

    result = cache_periodic_report(
        stock_name="黑芝麻智能",
        stock_code="02533",
        report_year=2025,
        market="HK",
        input_path=source,
        cache_dir=tmp_path / "cache",
        official_url="https://www1.hkexnews.hk/example.pdf",
    )

    assert result.text_path.exists()
    assert result.meta_path.exists()
    assert result.text_path.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")

    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta["schema_version"] == "periodic_report_cache_meta.v1"
    assert meta["stock_name"] == "黑芝麻智能"
    assert meta["stock_code"] == "02533"
    assert meta["market"] == "HK"
    assert meta["report_year"] == 2025
    assert meta["report_type"] == "annual"
    assert meta["input_format"] == "txt"
    assert meta["cached_text_path"].endswith("黑芝麻智能_2025_annual_jina.txt")
    assert meta["official_url"] == "https://www1.hkexnews.hk/example.pdf"
    assert len(meta["text_hash_sha256"]) == 64
    assert meta["text_chars"] > 0


def test_cache_periodic_report_extracts_pdf_text_with_local_reader(monkeypatch, tmp_path: Path) -> None:
    source_pdf = tmp_path / "annual.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 fake")

    import periodic_report_cache

    monkeypatch.setattr(
        periodic_report_cache,
        "_extract_pdf_text",
        lambda path: "PDF 抽取文本\nRobotaxi 与 SesameX 平台推进。\n",
    )

    result = cache_periodic_report(
        stock_name="MiniMax",
        stock_code="06677",
        report_year=2025,
        market="HK",
        input_path=source_pdf,
        cache_dir=tmp_path / "cache",
    )

    assert "SesameX" in result.text_path.read_text(encoding="utf-8")
    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta["input_format"] == "pdf"
    assert meta["source_path"].endswith("annual.pdf")


def test_cache_periodic_report_rejects_empty_pdf_text(monkeypatch, tmp_path: Path) -> None:
    source_pdf = tmp_path / "annual.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 fake")

    import periodic_report_cache

    monkeypatch.setattr(periodic_report_cache, "_extract_pdf_text", lambda path: "   ")

    with pytest.raises(ValueError, match="No text extracted"):
        cache_periodic_report(
            stock_name="MiniMax",
            stock_code="06677",
            report_year=2025,
            market="HK",
            input_path=source_pdf,
            cache_dir=tmp_path / "cache",
        )


def test_extract_pdf_text_falls_back_to_pdfplumber(monkeypatch, tmp_path: Path) -> None:
    source_pdf = tmp_path / "annual.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 fake")

    import periodic_report_cache

    real_import = builtins.__import__

    class _FakePdf:
        pages = [
            SimpleNamespace(extract_text=lambda: "第一页文本"),
            SimpleNamespace(extract_text=lambda: "第二页文本"),
        ]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in {"pypdf", "PyPDF2"}:
            raise ImportError(name)
        if name == "pdfplumber":
            return SimpleNamespace(open=lambda path: _FakePdf())
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert periodic_report_cache._extract_pdf_text(source_pdf) == "第一页文本\n第二页文本"


def test_periodic_report_cache_cli_registers_text_input(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("圣邦股份 年报文本\n信号链与电源管理产品矩阵。\n", encoding="utf-8")
    cache_dir = tmp_path / "cache"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/periodic_report_cache.py",
            "--stock",
            "圣邦股份",
            "--code",
            "300661",
            "--year",
            "2025",
            "--market",
            "A",
            "--input",
            str(source),
            "--cache-dir",
            str(cache_dir),
        ],
        cwd=Path(__file__).parent.parent.parent,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["text_path"].endswith("圣邦股份_2025_annual_jina.txt")
    assert payload["meta_path"].endswith("圣邦股份_2025_annual_meta.json")
    assert (cache_dir / "圣邦股份_2025_annual_jina.txt").exists()


def test_get_cninfo_market_maps_a_share_prefixes() -> None:
    assert get_cninfo_market("688017") == "沪深京"
    assert get_cninfo_market("300661") == "沪深京"
    assert get_cninfo_market("000001") == "沪深京"
    assert get_cninfo_market("832000") == "沪深京"


def test_discover_cninfo_annual_report_prefers_exact_year_annual(monkeypatch) -> None:
    class _FakeDataFrame:
        def __init__(self, rows):
            self._rows = rows

        def to_dict(self, orient):
            assert orient == "records"
            return list(self._rows)

    rows = [
        {
            "公告标题": "圣邦股份：2025年第一季度报告",
            "公告类型": "季度报告",
            "公告日期": "2026-04-20",
            "公告链接": "https://example.com/q1.pdf",
        },
        {
            "公告标题": "圣邦股份：2025年年度报告摘要",
            "公告类型": "年度报告摘要",
            "公告日期": "2026-04-25",
            "公告链接": "https://example.com/summary.pdf",
        },
        {
            "公告标题": "圣邦股份：2025年年度报告",
            "公告类型": "年度报告",
            "公告日期": "2026-04-25",
            "公告链接": "https://example.com/annual.pdf",
        },
    ]

    def fake_loader(symbol, market):
        assert symbol == "300661"
        assert market == "沪深京"
        return _FakeDataFrame(rows)

    result = discover_cninfo_annual_report(
        stock_code="300661",
        report_year=2025,
        disclosure_loader=fake_loader,
    )

    assert result["title"] == "圣邦股份：2025年年度报告"
    assert result["url"] == "https://example.com/annual.pdf"
    assert result["market"] == "沪深京"
    assert result["report_year"] == 2025


def test_discover_cninfo_annual_report_rejects_missing_annual(monkeypatch) -> None:
    class _FakeDataFrame:
        def to_dict(self, orient):
            return [
                {
                    "公告标题": "圣邦股份：2025年半年度报告",
                    "公告类型": "半年度报告",
                    "公告日期": "2025-08-20",
                    "公告链接": "https://example.com/semi.pdf",
                }
            ]

    with pytest.raises(ValueError, match="No annual report announcement"):
        discover_cninfo_annual_report(
            stock_code="300661",
            report_year=2025,
            disclosure_loader=lambda symbol, market: _FakeDataFrame(),
        )


def test_periodic_report_cache_cli_discovers_cninfo_with_loader(monkeypatch, capsys) -> None:
    import scripts.periodic_report_cache as cli

    class _FakeDataFrame:
        def to_dict(self, orient):
            return [
                {
                    "公告标题": "测试股份：2025年年度报告",
                    "公告类型": "年度报告",
                    "公告日期": "2026-04-20",
                    "公告链接": "https://example.com/annual.pdf",
                }
            ]

    monkeypatch.setattr(
        cli,
        "_load_cninfo_disclosures",
        lambda symbol, market: _FakeDataFrame(),
    )

    rc = cli.main([
        "--discover-cninfo",
        "--code",
        "300661",
        "--year",
        "2025",
    ])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["url"] == "https://example.com/annual.pdf"
    assert payload["title"] == "测试股份：2025年年度报告"


def test_cache_periodic_report_from_url_downloads_pdf_and_reuses_cache(monkeypatch, tmp_path: Path) -> None:
    import periodic_report_cache

    monkeypatch.setattr(
        periodic_report_cache,
        "_extract_pdf_text",
        lambda path: "远程 PDF 文本\n收入与产品矩阵说明。\n",
    )

    result = cache_periodic_report_from_url(
        stock_name="圣邦股份",
        stock_code="300661",
        report_year=2025,
        market="A",
        url="https://static.cninfo.com.cn/finalpage/2026-04-25/annual.pdf",
        cache_dir=tmp_path / "cache",
        downloader=lambda url: b"%PDF-1.4 fake annual report",
    )

    assert result.text_path.read_text(encoding="utf-8").startswith("远程 PDF 文本")
    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta["official_url"] == "https://static.cninfo.com.cn/finalpage/2026-04-25/annual.pdf"
    assert meta["input_format"] == "pdf"
    source_path = Path(meta["source_path"])
    assert source_path.exists()
    assert source_path.name == "圣邦股份_2025_annual_source.pdf"
    assert source_path.read_bytes() == b"%PDF-1.4 fake annual report"


def test_periodic_report_cache_cli_downloads_url_with_injected_downloader(monkeypatch, capsys, tmp_path: Path) -> None:
    import periodic_report_cache
    import scripts.periodic_report_cache as cli

    monkeypatch.setattr(
        periodic_report_cache,
        "_extract_pdf_text",
        lambda path: "CLI 下载 PDF 文本\n管理层讨论与产品进展。\n",
    )
    monkeypatch.setattr(
        cli,
        "_download_url_bytes",
        lambda url: b"%PDF-1.4 cli fake report",
    )

    rc = cli.main([
        "--download-url",
        "https://static.cninfo.com.cn/finalpage/2026-04-25/annual.pdf",
        "--stock",
        "圣邦股份",
        "--code",
        "300661",
        "--year",
        "2025",
        "--market",
        "A",
        "--cache-dir",
        str(tmp_path / "cache"),
    ])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["text_path"].endswith("圣邦股份_2025_annual_jina.txt")
    assert Path(payload["text_path"]).read_text(encoding="utf-8").startswith("CLI 下载 PDF 文本")


def test_periodic_report_cache_cli_discovers_and_downloads_cninfo(monkeypatch, capsys, tmp_path: Path) -> None:
    import periodic_report_cache
    import scripts.periodic_report_cache as cli

    class _FakeDataFrame:
        def to_dict(self, orient):
            return [
                {
                    "公告标题": "圣邦股份：2025年年度报告",
                    "公告类型": "年度报告",
                    "公告日期": "2026-04-20",
                    "公告链接": "https://static.cninfo.com.cn/finalpage/2026-04-20/annual.pdf",
                }
            ]

    monkeypatch.setattr(periodic_report_cache, "_extract_pdf_text", lambda path: "发现后下载文本\n")
    monkeypatch.setattr(cli, "_load_cninfo_disclosures", lambda symbol, market: _FakeDataFrame())
    monkeypatch.setattr(cli, "_download_url_bytes", lambda url: b"%PDF-1.4 discovered")

    rc = cli.main([
        "--discover-cninfo",
        "--download-discovered",
        "--stock",
        "圣邦股份",
        "--code",
        "300661",
        "--year",
        "2025",
        "--cache-dir",
        str(tmp_path / "cache"),
    ])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["text_path"].endswith("圣邦股份_2025_annual_jina.txt")
    assert payload["text_chars"] == len("发现后下载文本\n")
