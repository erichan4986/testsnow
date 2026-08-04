"""市场/板块共振集成测试 — 验证个股 vs 指数趋势共振链路。"""

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import numpy as np
import pandas as pd

UTILS = Path(__file__).resolve().parents[2] / "scripts" / "utils"
sys.path[:0] = [str(UTILS), str(UTILS / "reporter")]

SHANGHAI = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 8, 3, 16, 0, tzinfo=SHANGHAI)


def _make_uptrend_df(close_start=100.0, days=60, up=True):
    """生成一个简单趋势日K数据。"""
    dates = pd.date_range(end=pd.Timestamp("2026-06-08"), periods=days, freq="B")
    drift = 0.002 if up else -0.002
    closes = close_start * np.exp(np.cumsum(np.full(days, drift)))
    opens = closes * 0.998
    highs = closes * 1.01
    lows = closes * 0.99
    df = pd.DataFrame({
        "date": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.full(days, 10000),
    })
    return df


def test_analyzer_wires_market_resonance_with_index_data(monkeypatch):
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_analyzer import advanced_medium_term_resonance

    # 个股：上升趋势（价格 > MA20 > MA60）
    stock_df = _make_uptrend_df(close_start=100.0, days=120, up=True)
    # 把 MA 拉开形成多头排列
    stock_df["close"] = stock_df["close"] * 1.0

    # Mock 指数获取：市场指数也是上升趋势
    def _fake_fetch_index(symbol, days=120, **kwargs):
        return _make_uptrend_df(close_start=200.0, days=days, up=True)

    monkeypatch.setattr("technical_analyzer._fetch_index_kline", _fake_fetch_index)

    result = advanced_medium_term_resonance(
        df_daily=stock_df,
        quote={"code": "688008", "adjustment": "raw", "data_source": "test"},
    )
    resonance = result.get("resonance", {})
    mr = resonance.get("market_resonance")
    assert mr is not None
    assert mr.get("state") not in [None, "未知"], f"共振状态不应为未知：{mr}"
    assert "market_trend" in mr
    assert mr["market_trend"] is not None
    assert "theme_trend" in mr


def _fresh_frame(days=120, close_start=100.0):
    frame = _make_uptrend_df(close_start=close_start, days=days, up=True)
    frame["date"] = pd.date_range(end="2026-08-03", periods=days, freq="B")
    return frame


def _raw(frame):
    return frame.to_dict(orient="list")


def _write_index_cache(tmp_path, symbol="000001", fetched_at=None, now=NOW):
    from technical_ohlcv_cache import write_ohlcv_cache
    return write_ohlcv_cache(
        _raw(_fresh_frame()), asset_type="index", symbol=symbol, market="cn",
        source="akshare_index", adjustment="raw", fetched_at=fetched_at,
        cache_dir=tmp_path, now=now,
    )


def test_index_same_day_cache_skips_both_providers(monkeypatch, tmp_path):
    import akshare
    from mootdx.quotes import Quotes
    from technical_analyzer import _fetch_index_kline

    _write_index_cache(tmp_path)
    monkeypatch.setattr(akshare, "index_zh_a_hist", lambda *a, **k: pytest.fail("akshare called"))
    monkeypatch.setattr(Quotes, "factory", lambda *a, **k: pytest.fail("mootdx called"))

    result = _fetch_index_kline("000001", cache_dir=tmp_path, now=NOW)
    assert len(result) == 120


def test_malformed_akshare_index_falls_through_and_writes_mootdx(monkeypatch, tmp_path):
    import data_collector
    from mootdx.quotes import Quotes
    from technical_analyzer import _fetch_index_kline
    from technical_ohlcv_cache import load_ohlcv_cache

    monkeypatch.setattr(data_collector.AkshareHelper, "call", lambda *a, **k: pd.DataFrame({"bad": [1]}))
    client = type("Client", (), {"index_bars": lambda self, **kwargs: _fresh_frame()})()
    monkeypatch.setattr(Quotes, "factory", lambda *a, **k: client)

    result = _fetch_index_kline("000001", cache_dir=tmp_path, now=NOW)
    loaded = load_ohlcv_cache("index", "000001", "cn", cache_dir=tmp_path, now=NOW)
    assert len(result) == 120
    assert loaded["status"] == "same_day"
    assert loaded["source"] == "mootdx_index"


def test_shenzhen_index_fallback_uses_mootdx_index_bars(monkeypatch, tmp_path):
    import data_collector
    from mootdx.quotes import Quotes
    from technical_analyzer import _fetch_index_kline
    from technical_ohlcv_cache import load_ohlcv_cache

    monkeypatch.setattr(data_collector.AkshareHelper, "call", lambda *a, **k: None)
    calls = []
    frame = _fresh_frame()
    frame.index = pd.DatetimeIndex(frame["date"], name="date")
    frame["vol"] = frame["volume"] / 10

    class Client:
        def index_bars(self, **kwargs):
            calls.append(kwargs)
            return frame

    monkeypatch.setattr(Quotes, "factory", lambda *a, **k: Client())

    result = _fetch_index_kline("399006", cache_dir=tmp_path, now=NOW)
    loaded = load_ohlcv_cache("index", "399006", "cn", cache_dir=tmp_path, now=NOW)

    assert calls == [{"symbol": "399006", "frequency": 9, "start": 0, "offset": 120}]
    assert len(result) == 120
    assert loaded["status"] == "same_day"
    assert loaded["source"] == "mootdx_index"


def test_index_uses_recent_cache_only_after_provider_failure(monkeypatch, tmp_path):
    import data_collector
    from mootdx.quotes import Quotes
    from technical_analyzer import _fetch_index_kline

    friday = datetime(2026, 7, 31, 16, 0, tzinfo=SHANGHAI)
    _write_index_cache(tmp_path, fetched_at=friday.isoformat())
    path = tmp_path / "v2" / "index-cn-000001.json"
    before = path.stat().st_mtime_ns
    calls = []
    monkeypatch.setattr(data_collector.AkshareHelper, "call", lambda *a, **k: calls.append("ak") or None)
    monkeypatch.setattr(Quotes, "factory", lambda *a, **k: calls.append("mootdx") or type("Client", (), {"index_bars": lambda self, **kwargs: None})())

    result = _fetch_index_kline("000001", cache_dir=tmp_path, now=NOW)
    assert calls == ["ak", "mootdx"]
    assert len(result) == 120
    assert path.stat().st_mtime_ns == before


def test_index_cache_write_failure_keeps_live_frame(monkeypatch, tmp_path):
    import data_collector
    from technical_analyzer import _fetch_index_kline

    monkeypatch.setattr(
        data_collector.AkshareHelper, "call", lambda *a, **k: _fresh_frame(),
    )
    monkeypatch.setattr(
        "technical_analyzer.write_ohlcv_cache",
        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
    )
    assert len(_fetch_index_kline("000001", cache_dir=tmp_path, now=NOW)) == 120


def test_disabled_index_cache_uses_live_provider_without_touching_file(monkeypatch, tmp_path):
    import data_collector
    from technical_analyzer import _fetch_index_kline

    path = _write_index_cache(tmp_path)
    before = path.stat().st_mtime_ns
    calls = []
    monkeypatch.setattr(
        data_collector.AkshareHelper, "call",
        lambda *a, **k: calls.append("live") or _fresh_frame(close_start=300),
    )
    result = _fetch_index_kline(
        "000001", cache_dir=tmp_path, now=NOW, index_cache_enabled=False,
    )
    assert calls == ["live"]
    assert result["close"].iloc[-1] > 300
    assert path.stat().st_mtime_ns == before


def test_duplicate_index_mapping_fetches_once_then_reuses_cache(monkeypatch, tmp_path):
    import data_collector
    from technical_analyzer import advanced_medium_term_resonance

    calls = []
    monkeypatch.setattr(
        "technical_analyzer.load_market_index_map",
        lambda code: {"market": {"code": "399006"}, "thematic": {"code": "399006"}},
    )
    monkeypatch.setattr(
        data_collector.AkshareHelper, "call",
        lambda *a, **k: calls.append("ak") or _fresh_frame(close_start=200),
    )
    quote = {
        "code": "300308", "adjustment": "raw", "data_source": "test",
        "technical_ohlcv_cache_dir": tmp_path, "index_cache_enabled": True,
    }
    cold = advanced_medium_term_resonance(_fresh_frame(), quote=quote)
    warm = advanced_medium_term_resonance(_fresh_frame(), quote=quote)
    assert calls == ["ak"]
    assert cold["resonance"]["market_resonance"] == warm["resonance"]["market_resonance"]


def test_full_warm_skill_path_makes_zero_stock_or_index_provider_calls(monkeypatch, tmp_path):
    import akshare
    from mootdx.quotes import Quotes
    from report_skills.technical_skills import technical_fetching_skill
    from skill_pipeline import SkillContext
    from technical_ohlcv_cache import write_ohlcv_cache

    live_now = datetime.now(SHANGHAI)
    daily = _fresh_frame()
    daily["date"] = pd.date_range(end=live_now.date(), periods=len(daily), freq="B")
    write_ohlcv_cache(
        _raw(daily), weekly_data=_raw(daily.iloc[::5].reset_index(drop=True)),
        asset_type="stock", symbol="300308", market=0, source="mootdx",
        adjustment="raw", cache_dir=tmp_path, now=live_now,
    )
    _write_index_cache(tmp_path, symbol="399006", now=live_now)
    counters = {"stock": 0, "index": 0, "mootdx": 0}
    monkeypatch.setattr("report_skills.technical_skills.load_wind_package", lambda *a, **k: {})
    monkeypatch.setattr(akshare, "stock_zh_a_hist", lambda *a, **k: counters.__setitem__("stock", 1))
    monkeypatch.setattr(akshare, "index_zh_a_hist", lambda *a, **k: counters.__setitem__("index", 1))
    monkeypatch.setattr(Quotes, "factory", lambda *a, **k: counters.__setitem__("mootdx", 1))

    ctx = SkillContext(input={
        "stock_name": "中际旭创", "stock_codes": {"中际旭创": "300308"},
        "stock_raw": {}, "technical_ohlcv_cache_dir": tmp_path,
    })
    result = technical_fetching_skill(ctx)
    assert counters == {"stock": 0, "index": 0, "mootdx": 0}
    assert result.get("technical") is not None


def test_renderer_shows_market_resonance_with_impact_and_relative():
    from scripts.utils.reporter.sections.technical_renderer import TechnicalRenderer

    ctx = {
        "stock_name": "测试",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "close": 100,
                    "_resonance": {
                        "trend_state": {"primary_state": "上升趋势", "stage": "主升期"},
                        "trend_health": {"score": 75, "grade": "健康"},
                        "invalidation": {
                            "hard_invalid_price": 90,
                            "hard_invalid_source": "MA60",
                            "current_distance_to_invalid": "11.1%",
                            "status": "safe",
                            "message": "位于MA60上方",
                        },
                        "key_levels": {"support_zone": None, "resistance_zone": None},
                        "advisors": {
                            "macd": {"state": "多头延续", "meaning": "仅作趋势确认"},
                            "rsi": {"state": "正常", "meaning": "强趋势中不单独构成卖出信号"},
                            "bias": {"state": "正常", "meaning": "价格与均线偏离适中"},
                            "boll": {"state": "正常", "meaning": "中轨附近，波动正常"},
                        },
                        "bottom_signal": {"state": "none"},
                        "divergence_scan": None,
                        "market_resonance": {
                            "state": "顺风共振",
                            "confidence": "高",
                            "impact": "趋势信号可信度上调",
                            "relative_strength": "强于行业",
                            "evidence": ["个股趋势：主升期", "大盘趋势：主升期", "行业趋势：主升期"],
                            "missing": [],
                            "action_hint": "趋势跟随",
                        },
                    },
                },
            },
        },
        "technical_render_mode": "compact",
    }
    renderer = TechnicalRenderer()
    output = renderer.render(ctx)
    assert "顺风共振" in output, f"应显示共振状态：\n{output}"
    assert "趋势信号可信度上调" in output, f"应显示影响：\n{output}"
    assert "强于行业" in output, f"应显示相对强弱：\n{output}"
    assert "趋势跟随" in output, f"应显示提示：\n{output}"


def test_renderer_hides_unavailable_market_resonance_placeholder():
    from scripts.utils.reporter.sections.technical_renderer import TechnicalRenderer

    ctx = {
        "stock_name": "测试",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "close": 100,
                    "_resonance": {
                        "trend_state": {"primary_state": "上升趋势", "stage": "主升期"},
                        "trend_health": {"score": 75, "grade": "健康"},
                        "invalidation": {
                            "hard_invalid_price": 90,
                            "hard_invalid_source": "MA60",
                            "current_distance_to_invalid": "11.1%",
                            "status": "safe",
                            "message": "位于MA60上方",
                        },
                        "key_levels": {"support_zone": None, "resistance_zone": None},
                        "advisors": {
                            "macd": {"state": "多头延续", "meaning": "仅作趋势确认"},
                            "rsi": {"state": "正常", "meaning": "强趋势中不单独构成卖出信号"},
                            "bias": {"state": "正常", "meaning": "价格与均线偏离适中"},
                            "boll": {"state": "正常", "meaning": "中轨附近，波动正常"},
                        },
                        "bottom_signal": {"state": "none"},
                        "divergence_scan": None,
                        "market_resonance": {
                            "state": "未知",
                            "confidence": "低",
                            "impact": "暂未接入完整市场/行业数据，本次共振分析仅作占位。",
                            "relative_strength": "未知",
                            "evidence": [],
                            "missing": ["market index data missing", "sector index data missing"],
                            "action_hint": "继续观察",
                        },
                    },
                },
            },
        },
        "technical_render_mode": "compact",
    }
    renderer = TechnicalRenderer()
    output = renderer.render(ctx)
    assert "市场/板块共振" not in output, f"缺失共振数据不应占用正文：\n{output}"
    assert "占位" not in output, f"不应显示占位分析：\n{output}"
