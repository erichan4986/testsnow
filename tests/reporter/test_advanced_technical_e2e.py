import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter" / "sections"))

import pandas as pd
import numpy as np
from technical_analyzer import analyze
from technical_renderer import TechnicalRenderer


def _make_df(close_list):
    return pd.DataFrame({
        "close": close_list,
        "open": [c * 0.99 for c in close_list],
        "high": [c * 1.01 for c in close_list],
        "low": [c * 0.98 for c in close_list],
        "volume": [1000] * len(close_list),
    })


def test_e2e_uptrend_stock():
    """模拟一只上涨股票，验证完整流程。"""
    close = [100.0]
    for i in range(1, 150):
        close.append(close[-1] * (1 + 0.005 + np.random.normal(0, 0.005)))
    df = _make_df(close)
    result = analyze(df)

    assert "indicators" in result
    assert "resonance" in result
    res = result["resonance"]
    assert res["trend_state"]["stage"] in ["主升期", "加速期", "启动期"]
    assert 0 <= res["trend_health"]["score"] <= 100
    assert res["key_levels"]["medium_term_invalid"] is not None

    # renderer
    ctx = {
        "stock_name": "测试",
        "stock_raw": {"technical": {"indicators": {"_resonance": res}}},
        "chart_paths": {},
    }
    renderer = TechnicalRenderer()
    output = renderer.render(ctx)
    assert "中期趋势提醒" in output


def test_e2e_choppy_stock():
    """模拟震荡股票。"""
    close = [100.0 + (i % 10 - 5) * 2 for i in range(150)]
    df = _make_df(close)
    result = analyze(df)
    res = result["resonance"]
    assert res["weekly_background"]["trend"] in ["震荡", "未知", "趋势修复中"]
