import json
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta

import pandas as pd

try:
    from mootdx.quotes import Quotes
except ImportError:
    Quotes = None

try:
    import stockstats
except ImportError:
    stockstats = None

logger = logging.getLogger(__name__)


class TechnicalCollector:
    """采集技术指标数据（mootdx + stockstats）"""

    def __init__(self):
        self.client = None
        if Quotes is not None:
            try:
                self.client = Quotes.factory(market="std")
            except Exception as e:
                logger.warning(f"mootdx 初始化失败: {e}")

    def fetch_kline(self, code: str, market: int = 0, days: int = 120) -> Optional[pd.DataFrame]:
        """
        获取日K线数据
        Args:
            code: 股票代码，如 "300661"
            market: 0=深圳, 1=上海
            days: 需要多少天的数据
        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        if self.client is None:
            logger.error("mootdx 客户端未初始化")
            return None

        try:
            end = datetime.now()
            begin = end - timedelta(days=days * 2)
            df = self.client.k(
                symbol=code,
                begin=begin.strftime("%Y%m%d"),
                end=end.strftime("%Y%m%d"),
            )
            if df is None or df.empty:
                logger.warning(f"{code} K线数据为空")
                return None

            # Rename columns to standard names
            df = df.rename(columns={
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
            })

            # Keep only last N days
            if len(df) > days:
                df = df.tail(days).reset_index(drop=True)

            return df
        except Exception as e:
            logger.error(f"获取 {code} K线失败: {e}")
            return None

    def compute_indicators(self, df: pd.DataFrame) -> Dict:
        """
        使用 stockstats 计算技术指标
        Returns:
            Dict with latest indicator values
        """
        if stockstats is None:
            logger.error("stockstats 未安装")
            return {}

        try:
            ss = stockstats.StockDataFrame.retype(df.copy())

            if "close" not in ss.columns:
                logger.error("DataFrame missing 'close' column")
                return {}

            # Pre-compute indicators to ensure columns exist
            _ = ss["macd"]
            _ = ss["rsi_14"]
            _ = ss["kdjk"]
            _ = ss["close_5_sma"]
            _ = ss["close_20_sma"]
            _ = ss["close_60_sma"]
            _ = ss["boll"]
            _ = ss["boll_ub"]
            _ = ss["boll_lb"]

            result = {
                "close": float(ss["close"].iloc[-1]),
                "volume": int(ss["volume"].iloc[-1]),
                "macd": float(ss["macd"].iloc[-1]) if "macd" in ss.columns else None,
                "macd_signal": float(ss["macds"].iloc[-1]) if "macds" in ss.columns else None,
                "macd_hist": float(ss["macdh"].iloc[-1]) if "macdh" in ss.columns else None,
                "rsi_14": float(ss["rsi_14"].iloc[-1]) if "rsi_14" in ss.columns else None,
                "kdj_k": float(ss["kdjk"].iloc[-1]) if "kdjk" in ss.columns else None,
                "kdj_d": float(ss["kdjd"].iloc[-1]) if "kdjd" in ss.columns else None,
                "kdj_j": float(ss["kdjj"].iloc[-1]) if "kdjj" in ss.columns else None,
                "ma_5": float(ss["close_5_sma"].iloc[-1]) if "close_5_sma" in ss.columns else None,
                "ma_20": float(ss["close_20_sma"].iloc[-1]) if "close_20_sma" in ss.columns else None,
                "ma_60": float(ss["close_60_sma"].iloc[-1]) if "close_60_sma" in ss.columns else None,
                "ma_120": float(ss["close_120_sma"].iloc[-1]) if "close_120_sma" in ss.columns else None,
                "ma_250": float(ss["close_250_sma"].iloc[-1]) if "close_250_sma" in ss.columns else None,
                "boll_upper": float(ss["boll_ub"].iloc[-1]) if "boll_ub" in ss.columns else None,
                "boll_mid": float(ss["boll"].iloc[-1]) if "boll" in ss.columns else None,
                "boll_lower": float(ss["boll_lb"].iloc[-1]) if "boll_lb" in ss.columns else None,
            }

            # Remove None values for cleaner JSON
            return {k: v for k, v in result.items() if v is not None}
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
            return {}

    def collect(self, code: str, market: int = 0, days: int = 120) -> Dict:
        """一键采集技术指标"""
        df = self.fetch_kline(code, market, days)
        if df is None or df.empty:
            return {}
        indicators = self.compute_indicators(df)
        return {
            "code": code,
            "market": market,
            "days": len(df),
            "indicators": indicators,
            "fetched_at": datetime.now().isoformat(),
        }
