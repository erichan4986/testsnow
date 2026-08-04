"""技术分析阈值配置加载器。"""

import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = {
    "technical": {
        "horizon": "medium_term",
        "data": {
            "min_daily_bars": 120,
            "recommended_daily_bars": 250,
            "min_weekly_bars": 20,
            "recommended_weekly_bars": 60,
        },
        "ma": {
            "flat_threshold": 0.005,
            "ma20_warning_confirm_days": 3,
            "ma60_break_confirm_days": 2,
        },
        "boll": {
            "open_ratio": 1.2,
            "squeeze_ratio": 0.8,
            "width_ma_window": 5,
        },
        "bias": {
            "lookback": 120,
            "windows": [5, 10, 20],
            "extreme_windows": [5, 10],
        },
        "volume": {
            "confirm_ratio": 1.3,
            "ma_window": 20,
        },
        "support_resistance": {
            "lookback": 250,
            "local_extrema_window": 5,
            "min_touches": 3,
            "strong_touches": 5,
            "reverse_pct": 0.02,
            "reverse_atr_multiplier": 1.0,
            "bucket_pct": 0.005,
            "bucket_atr_multiplier": 0.5,
            "low_liquidity_downgrade": True,
        },
        "divergence": {
            "swing_left": 3,
            "swing_right": 3,
            "min_matched": 2,
            "total_conditions": 3,
            "lookback": 80,
            "max_signal_age": 10,
            "price_tolerance_pct": 0.01,
            "price_atr_multiplier": 0.5,
            "boll_upper_tolerance": 1.01,
        },
        "structure_path": {"shock": {"min_range_atr": 1.5, "min_body_range": 0.65, "close_extreme_pct": 0.20}},
        "scoring": {
            "weekly_structure_weight": 30,
            "daily_ma_weight": 25,
            "price_structure_weight": 15,
            "volume_weight": 10,
            "volatility_weight": 10,
            "risk_penalty_weight": 10,
        },
        "renderer": {
            "default_mode": "compact",
            "allow_full_mode": True,
        },
    }
}


def load_technical_config(path: str | None = None) -> Dict:
    """加载技术分析配置。文件缺失时使用内置默认值。"""
    if path is None:
        path = str(Path(__file__).parent.parent.parent.parent / "config" / "technical_config.yaml")

    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        merged = _deep_merge(dict(_DEFAULT_CONFIG), user_cfg)
        return merged
    except Exception as e:
        logger.warning(f"Config load failed ({e}), using defaults")
        return dict(_DEFAULT_CONFIG)


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """递归合并两个字典。override 覆盖 base。"""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
