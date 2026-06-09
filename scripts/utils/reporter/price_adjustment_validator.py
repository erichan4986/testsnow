"""价格复权验证器 — 检测相邻交易日 close 跳变，识别除权断点。"""

from typing import Dict

import pandas as pd

__all__ = ["detect_price_gaps", "validate_adjustment", "apply_qfq_adjustment"]


def detect_price_gaps(df: pd.DataFrame, gap_threshold: float = 0.25) -> Dict:
    """
    检查相邻交易日 close 是否出现超过 gap_threshold 的跳变。

    Args:
        df: 日K DataFrame，必须包含 close 和 date 列
        gap_threshold: 跳变阈值，默认 25%

    Returns:
        {
            "possible_exrights_gap": bool,
            "max_gap_pct": float,
            "gap_date": str | None,
            "gap_details": list[dict],
        }
    """
    if df is None or len(df) < 2 or "close" not in df.columns:
        return {
            "possible_exrights_gap": False,
            "max_gap_pct": 0.0,
            "gap_date": None,
            "gap_details": [],
        }

    close = df["close"].astype(float)
    dates = df["date"] if "date" in df.columns else pd.Series(range(len(df)))

    # 计算相邻交易日涨跌幅
    prev_close = close.shift(1)
    gap = (close - prev_close) / prev_close.abs()
    gap_pct = gap.abs() * 100

    gaps = []
    max_gap = 0.0
    max_gap_date = None
    max_gap_info = None

    for i in range(1, len(df)):
        gp = float(gap_pct.iloc[i])
        if gp > gap_threshold * 100:
            gap_info = {
                "date": str(dates.iloc[i]),
                "prev_close": round(float(prev_close.iloc[i]), 2),
                "close": round(float(close.iloc[i]), 2),
                "gap_pct": round(gp, 2),
            }
            gaps.append(gap_info)
            if gp > max_gap:
                max_gap = gp
                max_gap_date = str(dates.iloc[i])
                max_gap_info = gap_info

    latest_gap = None
    if gaps:
        latest_gap = max(gaps, key=lambda g: g["date"])

    return {
        "possible_exrights_gap": len(gaps) > 0,
        "max_gap_pct": round(max_gap, 2),
        "gap_date": max_gap_date,
        "gap_details": gaps,
        "latest_gap": latest_gap,
        "largest_gap": max_gap_info,
        "all_detected_gaps": gaps,
    }


def validate_adjustment(
    df: pd.DataFrame,
    adjustment: str = "raw",
    quote: Dict | None = None,
    gap_threshold: float = 0.25,
) -> Dict:
    """
    综合验证价格序列复权状态。

    Returns:
        {
            "adjustment": str,
            "price_gaps": dict,
            "requires_qfq": bool,
            "warning_message": str | None,
            "confidence_limit": str,  # "高" | "中" | "低"
        }
    """
    price_gaps = detect_price_gaps(df, gap_threshold)
    has_gap = price_gaps["possible_exrights_gap"]

    # A股默认要求 qfq
    is_qfq = adjustment == "qfq"
    requires_qfq = has_gap and not is_qfq

    latest_gap = price_gaps.get("latest_gap")
    largest_gap = price_gaps.get("largest_gap")

    if requires_qfq:
        if latest_gap:
            warning = (
                f"当前价格序列疑似存在除权断点，最近一次为 {latest_gap['date']}，"
                f"跳变约 {latest_gap['gap_pct']:.1f}%；若未使用前复权数据，均线、BIAS、BOLL等指标可能失真。"
            )
        else:
            warning = (
                f"当前价格序列疑似存在除权断点（{price_gaps['gap_date']} 跳变 {price_gaps['max_gap_pct']:.1f}%），"
                f"若未使用前复权数据，均线、BIAS、BOLL等指标可能失真。"
            )
        confidence_limit = "低"
    elif has_gap and is_qfq:
        if latest_gap:
            warning = (
                f"价格序列存在除权断点，最近一次为 {latest_gap['date']}，"
                f"跳变约 {latest_gap['gap_pct']:.1f}%；已使用前复权数据。"
            )
        else:
            warning = (
                f"价格序列存在除权断点（{price_gaps['gap_date']} 跳变 {price_gaps['max_gap_pct']:.1f}%），"
                f"已使用前复权数据。"
            )
        confidence_limit = "中"  # 有断点但已复权，最多中
    else:
        warning = None
        confidence_limit = "高" if is_qfq else "中"

    return {
        "adjustment": adjustment,
        "price_gaps": price_gaps,
        "latest_gap": latest_gap,
        "largest_gap": largest_gap,
        "requires_qfq": requires_qfq,
        "warning_message": warning,
        "confidence_limit": confidence_limit,
    }


def apply_qfq_adjustment(df: pd.DataFrame, xdxr_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    基于 mootdx xdxr 除权除息记录，对价格序列进行前复权处理。

    qfq 公式（单条记录）:
        adjusted = (price - fenhong/10) / (1 + songzhuangu/10 + peigu/10)

    处理逻辑：从最近一条除权记录开始，向前逐条应用累积系数。
    只有 category == 1（除权除息）的记录会被处理。

    Args:
        df: 原始日K DataFrame，必须包含 date, open, high, low, close 列
        xdxr_df: mootdx xdxr() 返回的除权记录 DataFrame

    Returns:
        前复权后的 DataFrame（深拷贝，不修改原始数据）
    """
    if df is None or df.empty:
        return df

    df = df.copy()
    if xdxr_df is None or xdxr_df.empty:
        return df

    # 只取除权除息记录 (category == 1)
    actions = xdxr_df[xdxr_df["category"] == 1].copy()
    if actions.empty:
        return df

    # 构建日期列
    actions["date"] = pd.to_datetime(
        actions["year"].astype(int).astype(str) + "-"
        + actions["month"].astype(int).astype(str).fillna("1") + "-"
        + actions["day"].astype(int).astype(str).fillna("1")
    )
    # 按日期降序（从最近到最早）
    actions = actions.sort_values("date", ascending=False)

    # 确保 df 有 datetime 日期列
    if "date" not in df.columns:
        df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"])

    price_cols = ["open", "high", "low", "close"]
    available_cols = [c for c in price_cols if c in df.columns]

    # 累积调整系数：从最近到最早逐条应用
    for _, row in actions.iterrows():
        action_date = row["date"]
        fenhong = float(row["fenhong"]) if pd.notna(row["fenhong"]) else 0.0
        songzhuangu = float(row["songzhuangu"]) if pd.notna(row["songzhuangu"]) else 0.0
        peigu = float(row["peigu"]) if pd.notna(row["peigu"]) else 0.0

        # 单条调整因子
        dividend = fenhong / 10.0
        split_factor = 1.0 + songzhuangu / 10.0 + peigu / 10.0

        # 对 action_date 之前的所有 bar 应用前复权
        mask = df["date"] < action_date
        for col in available_cols:
            df.loc[mask, col] = (df.loc[mask, col] - dividend) / split_factor

    return df
