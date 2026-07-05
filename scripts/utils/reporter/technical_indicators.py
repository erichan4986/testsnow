"""基础技术指标计算模块 — 纯 pandas 实现。"""

import numpy as np
import pandas as pd
from typing import Tuple

__all__ = [
    "sma", "ema", "atr", "adx", "cci",
    "williams_r", "stoch_rsi", "obv", "macd", "bollinger", "rsi",
]


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=1).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=1).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()


def adx(df: pd.DataFrame, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0)

    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr_series = tr.rolling(window=period, min_periods=1).mean()

    plus_di = 100 * (plus_dm.rolling(window=period, min_periods=1).mean() / atr_series)
    minus_di = 100 * (minus_dm.rolling(window=period, min_periods=1).mean() / atr_series)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).fillna(0)
    adx_series = dx.rolling(window=period, min_periods=1).mean()
    return adx_series, plus_di, minus_di


def cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma_tp = tp.rolling(window=period, min_periods=1).mean()
    mad = tp.rolling(window=period, min_periods=1).apply(lambda x: np.abs(x - x.mean()).mean(), raw=False)
    return (tp - sma_tp) / (0.015 * mad)


def williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
    highest_high = df["high"].rolling(window=period, min_periods=1).max()
    lowest_low = df["low"].rolling(window=period, min_periods=1).min()
    return -100 * (highest_high - df["close"]) / (highest_high - lowest_low)


def stoch_rsi(close: pd.Series, period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> Tuple[pd.Series, pd.Series]:
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))

    stoch = (rsi_series - rsi_series.rolling(window=period, min_periods=1).min()) / (
        rsi_series.rolling(window=period, min_periods=1).max() - rsi_series.rolling(window=period, min_periods=1).min()
    )
    stoch = stoch.fillna(0)
    k = sma(stoch, smooth_k)
    d = sma(k, smooth_d)
    return k, d


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    obv_list = [0]
    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i - 1]:
            obv_list.append(obv_list[-1] + volume.iloc[i])
        elif close.iloc[i] < close.iloc[i - 1]:
            obv_list.append(obv_list[-1] - volume.iloc[i])
        else:
            obv_list.append(obv_list[-1])
    return pd.Series(obv_list, index=close.index)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(close: pd.Series, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
    mid = sma(close, period)
    std = close.rolling(window=period, min_periods=1).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))
