"""价格目标端到端集成测试。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
from price_target import analyze_price_target


def test_e2e_synthetic_data():
    """
    用合成数据验证 analyze_price_target 端到端输出格式。
    """
    # 构建一个 synthetic 双底走势（需要 >=70 日线以确保周线 >=14 根用于 ADX）
    base = 100
    daily = pd.DataFrame({
        "open": [base + i * 0.8 for i in range(70)],
        "high": [base + i * 0.8 + 2 for i in range(70)],
        "low": [base + i * 0.8 - 2 for i in range(70)],
        "close": [base + i * 0.8 + 0.5 for i in range(70)],
        "volume": [1000000] * 70,
    })
    # 制造双底：中间有回落
    daily.loc[20:25, "close"] = [115, 113, 111, 110, 112, 114]
    daily.loc[20:25, "low"] = [113, 111, 109, 108, 110, 112]
    daily.loc[40:45, "close"] = [131, 129, 127, 126, 128, 130]
    daily.loc[40:45, "low"] = [129, 127, 125, 124, 126, 128]

    weekly = daily.iloc[::5].reset_index(drop=True)
    result = analyze_price_target(daily, weekly, current_price=float(daily["close"].iloc[-1]))

    assert "direction" in result
    assert "confidence" in result
    print(f"E2E result: direction={result['direction']}, confidence={result['confidence']}")


if __name__ == "__main__":
    test_e2e_synthetic_data()
