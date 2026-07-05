import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
import numpy as np
from technical_analyzer import find_support_resistance


def _make_df(close_list):
    return pd.DataFrame({
        "close": close_list,
        "open": close_list,
        "high": [c * 1.01 for c in close_list],
        "low": [c * 0.99 for c in close_list],
        "volume": [1000] * len(close_list),
    })


def test_support_resistance_found():
    """构造有明显支撑阻力的价格序列。"""
    np.random.seed(42)
    close = []
    for _ in range(50):
        close.extend([100.0 + np.random.normal(0, 0.5) for _ in range(5)])
        close.extend([110.0 + np.random.normal(0, 0.5) for _ in range(5)])
    df = _make_df(close)
    result = find_support_resistance(df)
    assert result["support_zone"] is not None
    assert result["resistance_zone"] is not None
    assert result["support_zone"]["touches"] >= 3
    assert result["resistance_zone"]["touches"] >= 3


def test_support_resistance_none_for_new_stock():
    """新股数据不足时应返回 None。"""
    df = _make_df([100.0] * 10)
    result = find_support_resistance(df)
    assert result.get("support_zone") is None
    assert result.get("resistance_zone") is None


def test_success_path_includes_reason():
    """支撑/阻力识别成功时，diagnostics 必须包含 reason，不能为默认兜底文案。"""
    np.random.seed(42)
    close = []
    for _ in range(50):
        close.extend([100.0 + np.random.normal(0, 0.5) for _ in range(5)])
        close.extend([110.0 + np.random.normal(0, 0.5) for _ in range(5)])
    df = _make_df(close)
    result = find_support_resistance(df)
    diag = result.get("diagnostics", {})
    reason = diag.get("reason", "")
    assert reason, "success path 必须包含 reason"
    assert "历史数据不足" not in reason, "success path 不应回退到默认兜底文案"
    assert "支撑区" in reason or "压力区" in reason, "reason 应描述识别结果"


def test_insufficient_touches_includes_reason():
    """有效触及次数不足时，diagnostics 应返回详细 reason 而非默认文案。"""
    np.random.seed(1)
    close = [100.0 + np.random.normal(0, 0.3) for _ in range(40)]
    df = _make_df(close)
    result = find_support_resistance(df)
    diag = result.get("diagnostics", {})
    reason = diag.get("reason", "")
    assert reason, "必须包含 reason"
    assert "历史数据不足" not in reason, "不应回退到默认兜底文案"
    # 应包含具体的触及次数信息
    assert "次" in reason, "reason 应提及触及次数"
