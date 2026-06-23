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
