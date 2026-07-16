"""Tests for scripts/prepare_annual_report_materials.py.

All network/download/PDF extraction calls are avoided by using file:// URLs
pointing to local sample text files.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "utils"))

from prepare_annual_report_materials import (  # noqa: E402
    _default_preview_path,
    _infer_market_from_stock_entry,
    _load_stock_entry_from_config,
    prepare_annual_report_materials,
)


SAMPLE_REPORT = """
2025年年度报告

一、公司从事的主要业务
公司是国内领先的高性能模拟集成电路设计企业，主要从事模拟芯片及传感器产品的研发、设计、销售。
产品广泛应用于工业控制、汽车电子、网络通信、消费电子、医疗设备等领域。
公司采取Fabless经营模式，专注于集成电路设计，晶圆制造及封装测试委托专业代工厂完成。

二、行业情况
受益于AI算力、新能源汽车及工业自动化需求增长，全球模拟芯片市场保持稳健增长。
国产替代加速推进，国内模拟芯片厂商市场份额持续提升。

三、研发与产品进展
截至报告期末，公司已拥有38大类、6,800余款可供销售产品。
信号链产品包括运算放大器、SAR ADC、Δ-Σ ADC、Pipeline ADC、DAC、Audio DAC、EEPROM、DIMM周边产品等。
电源管理产品包括LDO、DC/DC、LED驱动、AMOLED电源芯片、PMU、电池充放电管理芯片等。
传感器产品包括温度传感器和磁传感器。
面向汽车电子领域，公司在信号链、电源管理、传感器等关键领域不断推出通过车规级认证的新产品。

四、经营情况讨论与分析
报告期内，公司实现营业收入38.98亿元，同比增长16.46%；归属于上市公司股东的净利润5.47亿元，同比增长9.36%。
公司持续加大研发投入，2025年研发费用10.45亿元，占营业收入比例26.81%。

五、可能面对的风险
市场竞争加剧，进入模拟集成电路设计行业的门槛较高，加剧了对该行业的人才争夺，公司存在技术人员流失的风险。
公司将通过扩大招聘、加强培训和企业文化建设，稳定和扩大人才队伍。
"""


def _write_sample_report(tmp_path: Path) -> Path:
    sample = tmp_path / "sample_annual_report.txt"
    sample.write_text(SAMPLE_REPORT, encoding="utf-8")
    return sample


# --- helper unit tests ---


def test_load_stock_entry_by_name(tmp_path: Path) -> None:
    config = tmp_path / "stocks.json"
    config.write_text(
        json.dumps(
            [{"name": "黑芝麻智能", "code": "02533", "xueqiu_code": "HK02533"}]
        ),
        encoding="utf-8",
    )
    entry = _load_stock_entry_from_config(config, "黑芝麻智能")
    assert entry["code"] == "02533"


def test_load_stock_entry_by_code(tmp_path: Path) -> None:
    config = tmp_path / "stocks.json"
    config.write_text(
        json.dumps(
            [{"name": "黑芝麻智能", "code": "02533", "xueqiu_code": "HK02533"}]
        ),
        encoding="utf-8",
    )
    entry = _load_stock_entry_from_config(config, "02533")
    assert entry["name"] == "黑芝麻智能"


def test_load_stock_entry_by_xueqiu_code(tmp_path: Path) -> None:
    config = tmp_path / "stocks.json"
    config.write_text(
        json.dumps(
            [{"name": "黑芝麻智能", "code": "02533", "xueqiu_code": "HK02533"}]
        ),
        encoding="utf-8",
    )
    entry = _load_stock_entry_from_config(config, "HK02533")
    assert entry["name"] == "黑芝麻智能"


def test_load_stock_entry_not_found(tmp_path: Path) -> None:
    config = tmp_path / "stocks.json"
    config.write_text(json.dumps([{"name": "其他"}]), encoding="utf-8")
    with pytest.raises(SystemExit, match="stock not found in config"):
        _load_stock_entry_from_config(config, "不存在")


def test_infer_market_from_explicit() -> None:
    assert _infer_market_from_stock_entry({"market": "A"}) == "A"
    assert _infer_market_from_stock_entry({"market": "hk"}) == "HK"


def test_infer_market_from_xueqiu_code() -> None:
    assert _infer_market_from_stock_entry({"xueqiu_code": "HK02533"}) == "HK"
    assert _infer_market_from_stock_entry({"xueqiu_code": "SZ300661"}) == ""


def test_infer_market_from_code() -> None:
    assert _infer_market_from_stock_entry({"code": "300661"}) == "A"
    assert _infer_market_from_stock_entry({"code": "02533"}) == "HK"
    assert _infer_market_from_stock_entry({"code": "AAPL"}) == ""


def test_default_preview_path_uses_tmp() -> None:
    path = _default_preview_path("黑芝麻智能", "02533", 2025, "annual")
    assert str(path).startswith("/tmp/")
    assert "2025" in path.name
    assert "annual" in path.name
    assert path.name.endswith("_narrative_cards_preview.md")


# --- orchestration tests ---


def test_prepare_with_config_url(monkeypatch, tmp_path: Path) -> None:
    """Config with annual_report_url should use it and skip discovery."""
    sample = _write_sample_report(tmp_path)
    config = tmp_path / "stocks.json"
    config.write_text(
        json.dumps(
            [
                {
                    "name": "测试股份",
                    "code": "TEST01",
                    "market": "HK",
                    "annual_report_url": sample.as_uri(),
                }
            ]
        ),
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    preview_path = tmp_path / "preview.md"

    spy = {"called": False}
    import prepare_annual_report_materials as pam

    original_discover_hk = pam.discover_hkex_periodic_report
    monkeypatch.setattr(
        "prepare_annual_report_materials.discover_hkex_periodic_report",
        lambda **kwargs: (spy.update({"called": True}) or original_discover_hk(**kwargs)),
    )

    result = prepare_annual_report_materials(
        stock="测试股份",
        year=2025,
        config_path=config,
        cache_dir=cache_dir,
        report_type="annual",
        preview_output=str(preview_path),
    )

    assert result["stock_name"] == "测试股份"
    assert result["stock_code"] == "TEST01"
    assert result["market"] == "HK"
    assert result["report_year"] == 2025
    assert result["report_type"] == "annual"
    assert Path(result["text_path"]).exists()
    assert Path(result["meta_path"]).exists()
    assert result["preview_path"] == str(preview_path)
    assert preview_path.exists()
    assert result["evidence_blocks_count"] > 0
    assert result["cards_count"] > 0
    assert result["wrote_knowledge"] is False
    assert result["knowledge_written_count"] == 0
    assert spy["called"] is False


def test_prepare_a_share_no_url_discovers_cninfo(tmp_path: Path) -> None:
    """A-share without URL should discover via CNINFO and cache."""
    sample = _write_sample_report(tmp_path)
    config = tmp_path / "stocks.json"
    config.write_text(
        json.dumps([{"name": "圣邦股份", "code": "300661", "xueqiu_code": "SZ300661"}]),
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    preview_path = tmp_path / "preview.md"

    class _FakeDataFrame:
        def to_dict(self, orient):
            return [
                {
                    "公告标题": "圣邦股份：2025年年度报告",
                    "公告类型": "年度报告",
                    "公告时间": "2026-03-28",
                    "公告链接": sample.as_uri(),
                }
            ]

    result = prepare_annual_report_materials(
        stock="圣邦股份",
        year=2025,
        config_path=config,
        cache_dir=cache_dir,
        preview_output=str(preview_path),
        _cninfo_loader=lambda symbol, market, start_date="", end_date="": _FakeDataFrame(),
    )

    assert result["market"] == "A"
    assert Path(result["text_path"]).exists()
    assert Path(result["text_path"]).name.endswith("_jina.txt")
    assert preview_path.exists()
    assert result["evidence_blocks_count"] > 0
    assert result["cards_count"] > 0


def test_prepare_hk_no_url_discovers_hkex(tmp_path: Path) -> None:
    """HK without URL should discover via HKEX and cache."""
    sample = _write_sample_report(tmp_path)
    config = tmp_path / "stocks.json"
    config.write_text(
        json.dumps([{"name": "黑芝麻智能", "code": "02533", "xueqiu_code": "HK02533"}]),
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    preview_path = tmp_path / "preview.md"

    discovery = {
        "title": "2025年報",
        "date": "27/04/2026 16:48",
        "url": sample.as_uri(),
        "stock_code": "02533",
        "stock_id": "1000221013",
        "market": "HK",
        "report_year": 2025,
        "report_type": "annual",
        "lang": "ZH",
        "search_url": "https://example.com/search",
    }

    result = prepare_annual_report_materials(
        stock="黑芝麻智能",
        year=2025,
        config_path=config,
        cache_dir=cache_dir,
        preview_output=str(preview_path),
        _hkex_discoverer=lambda **kwargs: discovery,
    )

    assert result["market"] == "HK"
    assert Path(result["text_path"]).exists()
    assert preview_path.exists()
    assert result["evidence_blocks_count"] > 0
    assert result["cards_count"] > 0


def test_prepare_default_no_knowledge(tmp_path: Path) -> None:
    """By default no knowledge notes should be written."""
    sample = _write_sample_report(tmp_path)
    config = tmp_path / "stocks.json"
    config.write_text(
        json.dumps(
            [
                {
                    "name": "测试股份",
                    "code": "TEST01",
                    "market": "A",
                    "annual_report_url": sample.as_uri(),
                }
            ]
        ),
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    knowledge_dir = tmp_path / "knowledge"
    preview_path = tmp_path / "preview.md"

    result = prepare_annual_report_materials(
        stock="测试股份",
        year=2025,
        config_path=config,
        cache_dir=cache_dir,
        base_dir=knowledge_dir,
        preview_output=str(preview_path),
    )

    assert result["wrote_knowledge"] is False
    assert result["knowledge_written_count"] == 0
    assert not (knowledge_dir / "10-Stocks").exists()


def test_prepare_with_write_knowledge(tmp_path: Path) -> None:
    """--write-knowledge should persist one pack and one human view."""
    sample = _write_sample_report(tmp_path)
    config = tmp_path / "stocks.json"
    config.write_text(
        json.dumps(
            [
                {
                    "name": "测试股份",
                    "code": "TEST01",
                    "market": "A",
                    "annual_report_url": sample.as_uri(),
                }
            ]
        ),
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    knowledge_dir = tmp_path / "knowledge"
    preview_path = tmp_path / "preview.md"

    result = prepare_annual_report_materials(
        stock="测试股份",
        year=2025,
        config_path=config,
        cache_dir=cache_dir,
        write_knowledge=True,
        base_dir=knowledge_dir,
        preview_output=str(preview_path),
    )

    assert result["wrote_knowledge"] is True
    assert result["knowledge_written_count"] == 0
    stock_root = knowledge_dir / "10-Stocks" / "测试股份"
    assert not (stock_root / "periodic_narrative_cards").exists()
    pack_output = result["knowledge_outputs"]["periodic_narrative_pack"]
    assert pack_output["state"] == "bootstrap"
    assert Path(pack_output["pack_path"]).exists()
    assert Path(pack_output["manifest_path"]).exists()
    view_output = result["knowledge_outputs"]["periodic_narrative_view"]
    assert view_output["state"] == "created"
    assert Path(view_output["view_path"]).exists()
    assert view_output["total_cards"] == result["cards_count"]
    assert view_output["displayed_cards"] <= view_output["total_cards"]
    assert result["knowledge_outputs"]["legacy_note_count"] == 0


def test_prepare_with_write_knowledge_is_idempotent_for_view(tmp_path: Path) -> None:
    sample = _write_sample_report(tmp_path)
    config = tmp_path / "stocks.json"
    config.write_text(
        json.dumps(
            [
                {
                    "name": "测试股份",
                    "code": "TEST01",
                    "market": "A",
                    "annual_report_url": sample.as_uri(),
                }
            ]
        ),
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    knowledge_dir = tmp_path / "knowledge"
    preview_path = tmp_path / "preview.md"

    first = prepare_annual_report_materials(
        stock="测试股份",
        year=2025,
        config_path=config,
        cache_dir=cache_dir,
        write_knowledge=True,
        base_dir=knowledge_dir,
        preview_output=str(preview_path),
    )
    first_view = Path(first["knowledge_outputs"]["periodic_narrative_view"]["view_path"])
    first_bytes = first_view.read_bytes()

    second = prepare_annual_report_materials(
        stock="测试股份",
        year=2025,
        config_path=config,
        cache_dir=cache_dir,
        write_knowledge=True,
        base_dir=knowledge_dir,
        preview_output=str(preview_path),
    )

    assert first["knowledge_written_count"] == second["knowledge_written_count"] == 0
    assert second["knowledge_outputs"]["periodic_narrative_view"]["state"] == "unchanged"
    assert first_view.read_bytes() == first_bytes
    assert not (knowledge_dir / "10-Stocks" / "测试股份" / "periodic_narrative_cards").exists()


def test_prepare_custom_preview_output(tmp_path: Path) -> None:
    """--preview-output should override the default /tmp path."""
    sample = _write_sample_report(tmp_path)
    config = tmp_path / "stocks.json"
    config.write_text(
        json.dumps(
            [
                {
                    "name": "测试股份",
                    "code": "TEST01",
                    "market": "A",
                    "annual_report_url": sample.as_uri(),
                }
            ]
        ),
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    custom_preview = tmp_path / "custom_preview.md"

    result = prepare_annual_report_materials(
        stock="测试股份",
        year=2025,
        config_path=config,
        cache_dir=cache_dir,
        preview_output=str(custom_preview),
    )

    assert result["preview_path"] == str(custom_preview)
    assert custom_preview.exists()


def test_prepare_failure_no_market(tmp_path: Path) -> None:
    """Unsupported market without URL should exit non-zero."""
    config = tmp_path / "stocks.json"
    config.write_text(
        json.dumps([{"name": "美股测试", "code": "AAPL", "market": "US"}]),
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"

    with pytest.raises(SystemExit, match="Cannot determine cache strategy"):
        prepare_annual_report_materials(
            stock="美股测试",
            year=2025,
            config_path=config,
            cache_dir=cache_dir,
        )


# --- CLI subprocess tests ---


def test_cli_runs_with_stock_and_year(tmp_path: Path) -> None:
    sample = _write_sample_report(tmp_path)
    config = tmp_path / "stocks.json"
    config.write_text(
        json.dumps(
            [
                {
                    "name": "测试股份",
                    "code": "TEST01",
                    "market": "A",
                    "annual_report_url": sample.as_uri(),
                }
            ]
        ),
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    preview_path = tmp_path / "preview.md"

    script = REPO_ROOT / "scripts" / "prepare_annual_report_materials.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--stock", "测试股份",
            "--year", "2025",
            "--config", str(config),
            "--cache-dir", str(cache_dir),
            "--preview-output", str(preview_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["stock_name"] == "测试股份"
    assert payload["report_year"] == 2025
    assert payload["cards_count"] > 0


def test_cli_missing_stock(tmp_path: Path) -> None:
    config = tmp_path / "stocks.json"
    config.write_text(json.dumps([{"name": "其他"}]), encoding="utf-8")
    cache_dir = tmp_path / "cache"

    script = REPO_ROOT / "scripts" / "prepare_annual_report_materials.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--stock", "不存在",
            "--year", "2025",
            "--config", str(config),
            "--cache-dir", str(cache_dir),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "stock not found" in result.stderr


def test_cli_with_write_knowledge(tmp_path: Path) -> None:
    sample = _write_sample_report(tmp_path)
    config = tmp_path / "stocks.json"
    config.write_text(
        json.dumps(
            [
                {
                    "name": "测试股份",
                    "code": "TEST01",
                    "market": "A",
                    "annual_report_url": sample.as_uri(),
                }
            ]
        ),
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    knowledge_dir = tmp_path / "knowledge"
    preview_path = tmp_path / "preview.md"

    script = REPO_ROOT / "scripts" / "prepare_annual_report_materials.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--stock", "测试股份",
            "--year", "2025",
            "--config", str(config),
            "--cache-dir", str(cache_dir),
            "--write-knowledge",
            "--base-dir", str(knowledge_dir),
            "--preview-output", str(preview_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["wrote_knowledge"] is True
    assert payload["knowledge_written_count"] == 0
    assert not (knowledge_dir / "10-Stocks" / "测试股份" / "periodic_narrative_cards").exists()
    assert Path(payload["knowledge_outputs"]["periodic_narrative_pack"]["pack_path"]).exists()
    assert Path(payload["knowledge_outputs"]["periodic_narrative_view"]["view_path"]).exists()
