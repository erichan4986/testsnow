"""数据获取层 — 外部 API 调用，无副作用，纯数据拉取。"""

import logging
import re
import ssl
import urllib.request
from typing import Any, Dict, List, Optional

from .constants import COMPETITOR_CODES, COMPETITOR_MAP
from .peer_config import get_peer_codes, get_peer_names
from .manual_financial_loader import load_manual_financials

# Mac 环境下 Python 的 SSL 证书可能未正确配置
ssl._create_default_https_context = ssl._create_unverified_context

logger = logging.getLogger(__name__)

# ============ global-stock-data 集成: 港股专用常量与 Helper ============

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"


def _is_hk_code(code: str) -> bool:
    """判断是否为港股代码: 5位数字且以0开头（如 02533）"""
    return len(code) == 5 and code.startswith("0")


def _is_standard_a_share_code(code: str) -> bool:
    """判断是否为可直接传给 A 股 akshare 财务接口的 6 位数字代码。"""
    return re.fullmatch(r"\d{6}", str(code or "").strip()) is not None


def eastmoney_datacenter(report_name: str, columns: str = "ALL",
                         filter_str: str = "", page_size: int = 50,
                         sort_columns: str = "", sort_types: str = "-1") -> list:
    """东财数据中心统一查询"""
    import requests
    params = {
        "reportName": report_name, "columns": columns,
        "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }
    r = requests.get(DATACENTER_URL, params=params, headers={"User-Agent": UA}, timeout=15)
    d = r.json()
    if d.get("result") and d["result"].get("data"):
        return d["result"]["data"]
    return []


def hk_stock_quote_tencent(code: str) -> Optional[Dict[str, Any]]:
    """
    腾讯港股行情 — 78字段（最全）
    code: 五位数字，如 "02533"
    返回含 name/price/pe/pb/market_cap/high_52w/low_52w 等
    """
    import requests
    url = f"https://qt.gtimg.cn/q=r_hk{code}"
    r = requests.get(url, timeout=10)
    r.encoding = "gbk"
    text = r.text

    m = re.search(r'"(.+)"', text)
    if not m:
        return None

    fields = m.group(1).split("~")
    if len(fields) < 50:
        return None

    return {
        "name": fields[1],           # 中文名
        "name_en": fields[2],        # 英文名
        "price": float(fields[3]) if fields[3] else 0,
        "prev_close": float(fields[4]) if fields[4] else 0,
        "open": float(fields[5]) if fields[5] else 0,
        "high": float(fields[33]) if fields[33] else 0,
        "low": float(fields[34]) if fields[34] else 0,
        "volume": int(float(fields[6])) if fields[6] else 0,
        "amount": float(fields[37]) if fields[37] else 0,
        "change_pct": float(fields[32]) if fields[32] else 0,
        "pe_ttm": float(fields[39]) if fields[39] else 0,
        "pb": float(fields[56]) if fields[56] else 0,
        "high_52w": float(fields[35]) if fields[35] else 0,
        "low_52w": float(fields[36]) if fields[36] else 0,
        "mcap_yi": float(fields[44]) if fields[44] else 0,  # 亿港元
        "timestamp": fields[30],
    }


def stock_quote_eastmoney(ticker_or_code: str, secid_prefix: int = 105) -> Dict:
    """
    东财 push2 实时行情 — 美股+港股统一接口
    港股: stock_quote_eastmoney("02533", 116)
    返回: price/high/low/open/volume/amount/turnover_rate/change_pct/name
    """
    import requests
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": f"{secid_prefix}.{ticker_or_code}",
        "fields": "f43,f44,f45,f46,f47,f48,f55,f57,f58,f59,f60,f170",
    }
    r = requests.get(url, timeout=10)
    d = r.json().get("data")
    if not d:
        return {}

    dec = d.get("f59", 3)
    divisor = 10 ** dec

    def _p(key):
        v = d.get(key)
        if v is None or v == "-":
            return None
        return round(v / divisor, dec)

    return {
        "code": d.get("f57"),
        "name": d.get("f58"),
        "price": _p("f43"),
        "high": _p("f44"),
        "low": _p("f45"),
        "open": _p("f46"),
        "volume": d.get("f47"),
        "amount": d.get("f48"),
        "turnover_rate": d.get("f55"),
        "prev_close": _p("f60"),
        "change_pct": round(d["f170"] / 100, 2) if d.get("f170") is not None else None,
    }


def hk_key_indicators(secucode: str, page_size: int = 4) -> List[Dict]:
    """
    东财 GMAININDICATOR 关键财务指标（港股，中文）
    secucode: "02533.HK"
    返回字段: OPERATE_INCOME(营收), GROSS_PROFIT_RATIO(毛利率%), BASIC_EPS, ROE_AVG, ROA, ...
    """
    report_name = "RPT_HKF10_FN_GMAININDICATOR"
    return eastmoney_datacenter(
        report_name=report_name,
        filter_str=f'(SECUCODE="{secucode}")',
        page_size=page_size,
        sort_columns="REPORT_DATE",
        sort_types="-1",
    )


def fund_flow_daily(ticker_or_code: str, secid_prefix: int = 105, limit: int = 100) -> List[Dict]:
    """
    东财 push2his 日级资金流 — 主力/大单/中单/小单净流入
    港股: fund_flow_daily("02533", 116)
    """
    import requests
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": f"{secid_prefix}.{ticker_or_code}",
        "klt": 101,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "lmt": limit,
    }
    r = requests.get(url, timeout=15)
    d = r.json()
    data = d.get("data")
    if not data or not data.get("klines"):
        return []

    result = []
    for line in data["klines"]:
        parts = line.split(",")
        result.append({
            "date": parts[0],
            "main_net": float(parts[1]),
            "small_net": float(parts[2]),
            "mid_net": float(parts[3]),
            "big_net": float(parts[4]),
            "super_big_net": float(parts[5]),
            "main_pct": float(parts[6]) if len(parts) > 6 and parts[6] else 0,
        })
    return result


def _manual_financials_for_code(code: str) -> Optional[Dict[str, Any]]:
    manual_fin = load_manual_financials(code)
    if manual_fin:
        return manual_fin
    pure_code = code.upper().replace(".HK", "")
    for name, mapped_code in COMPETITOR_CODES.items():
        if mapped_code.upper().replace(".HK", "") == pure_code:
            manual_fin = load_manual_financials(name)
            if manual_fin:
                return manual_fin
    return None


def fetch_ps(code: str, quote: Optional[Dict]) -> Optional[float]:
    """
    计算市销率 PS = 总市值(亿) / 年化营收(亿)。
    港股用东财 GMAININDICATOR 获取营收；A股用 akshare 财务摘要。
    """
    mcap = quote.get("mcap_yi") if quote else None
    if not mcap or mcap <= 0:
        return None

    # 港股
    if _is_hk_code(code):
        indicators = hk_key_indicators(f"{code}.HK", page_size=1)
        if indicators:
            revenue = indicators[0].get("OPERATE_INCOME")
            if revenue and revenue > 0:
                revenue_yi = revenue / 100000000
                return round(mcap / revenue_yi, 2)
        return None

    # A股
    fin = fetch_financial_abstract(code)
    if fin and fin.get("revenue") and fin["revenue"] > 0:
        revenue_yi = fin["revenue"] / 100000000
        # 简单年化：若营收小于典型季度值的2倍，乘以4
        if revenue_yi < 30:
            revenue_yi *= 4
        return round(mcap / revenue_yi, 2) if revenue_yi > 0 else None

    return None


# ============ 对外接口 ============

def us_stock_quote_tencent(code: str) -> Optional[Dict[str, Any]]:
    """
    腾讯美股行情 — 通过 us{code} 接口获取
    code: 如 "MBLY"
    返回: name/price/pe_ttm/mcap_yi(亿美元)/change_pct
    """
    import requests
    url = f"https://qt.gtimg.cn/q=us{code.upper()}"
    r = requests.get(url, timeout=10)
    r.encoding = "gbk"
    text = r.text

    m = re.search(r'"(.+)"', text)
    if not m:
        return None

    fields = m.group(1).split("~")
    if len(fields) < 50:
        return None

    return {
        "name": fields[1],
        "ticker": fields[2],
        "price": float(fields[3]) if fields[3] else 0,
        "prev_close": float(fields[4]) if fields[4] else 0,
        "change_pct": float(fields[32]) if fields[32] else 0,
        "pe_ttm": float(fields[39]) if fields[39] else 0,
        "mcap_usd_yi": float(fields[44]) if fields[44] else 0,  # 亿美元
    }


def _fetch_usd_to_hkd() -> float:
    """获取 USD→HKD 汇率，失败时回退到 7.8"""
    try:
        import requests
        r = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=10)
        d = r.json()
        return d["rates"].get("HKD", 7.8)
    except Exception:
        return 7.8


def _normalize_market_cap_fields(quote: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Normalize total/float market-cap fields before downstream rendering."""
    if quote is None:
        return None

    normalized = dict(quote)
    total = normalized.get("mcap_yi")
    float_mcap = normalized.get("float_mcap_yi")

    try:
        total_value = float(total) if total is not None else None
    except (TypeError, ValueError):
        total_value = None
    try:
        float_value = float(float_mcap) if float_mcap is not None else None
    except (TypeError, ValueError):
        float_value = None

    if float_value is None or float_value <= 0:
        normalized["float_mcap_yi"] = None
        normalized.setdefault("market_cap_quality", "float_market_cap_unavailable")
        return normalized

    if total_value and total_value > 0 and float_value > total_value * 1.05:
        normalized["float_mcap_yi"] = None
        normalized["market_cap_quality"] = "market_cap_inconsistent"
        normalized["market_cap_warning"] = "float_mcap_yi larger than mcap_yi"
        return normalized

    normalized["market_cap_quality"] = "ok"
    return normalized


def fetch_tencent_quote(code: str) -> Optional[Dict[str, Any]]:
    """
    调用腾讯财经 API 获取实时估值数据。
    港股(5位0开头 或 *.HK)使用 global-stock-data 专用接口，获取完整 PE/PB/52周高低等字段。
    美股(纯字母，如 MBLY)使用 us{code} 接口。
    A股保持原有逻辑不变。
    """
    try:
        # 统一处理 .HK 后缀，提取数字部分
        pure_code = code.upper().replace(".HK", "")
        if _is_hk_code(pure_code):
            # === 港股: 使用 global-stock-data 专用接口 ===
            result = hk_stock_quote_tencent(pure_code)
            if result:
                # 统一字段名以兼容下游 scoring_engine
                return _normalize_market_cap_fields({
                    "price": result.get("price", 0),
                    "last_close": result.get("prev_close", 0),
                    "change_pct": result.get("change_pct", 0),
                    "mcap_yi": result.get("mcap_yi", 0),
                    "float_mcap_yi": result.get("mcap_yi", 0),  # 港股统一用总市值
                    "pe_ttm": result.get("pe_ttm", 0),
                    "pb": result.get("pb", 0),
                    "pe_static": result.get("pe_ttm", 0),  # 港股无静态PE，用TTM替代
                    "high_52w": result.get("high_52w", 0),
                    "low_52w": result.get("low_52w", 0),
                    "turnover_rate": None,  # 腾讯接口无换手率，由东财补充
                    "source": "tencent_hk",
                })
            return None

        # === 美股: 纯字母代码，如 MBLY ===
        if code.isalpha():
            result = us_stock_quote_tencent(code)
            if result:
                rate = _fetch_usd_to_hkd()
                mcap_usd = result.get("mcap_usd_yi", 0)
                return _normalize_market_cap_fields({
                    "price": result.get("price", 0),
                    "last_close": result.get("prev_close", 0),
                    "change_pct": result.get("change_pct", 0),
                    "mcap_yi": round(mcap_usd * rate, 1) if mcap_usd else 0,
                    "pe_ttm": result.get("pe_ttm", 0),
                    "pb": None,
                    "source": "tencent_us",
                })
            return None

        # === A股: 原有逻辑 ===
        if code.startswith(("6", "9")):
            prefix = f"sh{code}"
        elif code.startswith("8"):
            prefix = f"bj{code}"
        else:
            prefix = f"sz{code}"

        url = f"https://qt.gtimg.cn/q={prefix}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read().decode("gbk")

        vals = data.split('"')[1].split("~")
        if len(vals) < 45:
            return None

        result = {
            "price": float(vals[3]) if vals[3] else 0,
            "last_close": float(vals[4]) if vals[4] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "mcap_yi": float(vals[44]) if vals[44] else 0,
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "float_mcap_yi": float(vals[45]) if vals[45] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
            "pe_static": float(vals[52]) if vals[52] else 0,
            "source": "tencent_a",
        }
        return _normalize_market_cap_fields(result)
    except Exception as e:
        logger.warning(f"[{code}] 腾讯财经 API 调用失败: {e}")
        return None


def fetch_consensus_eps(code: str) -> Optional[Dict[str, Any]]:
    """调用东财 reportapi 获取券商一致预期 EPS（不依赖 akshare）"""
    try:
        import requests

        REPORT_API = "https://reportapi.eastmoney.com/report/list"
        params = {
            "industryCode": "*", "pageSize": "20", "industry": "*",
            "rating": "*", "ratingChange": "*",
            "beginTime": "2000-01-01", "endTime": "2030-01-01",
            "pageNo": "1", "fields": "", "qType": "0",
            "orgCode": "", "code": code, "rcode": "",
            "p": "1", "pageNum": "1", "pageNumber": "1",
        }
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"}
        resp = requests.get(REPORT_API, params=params, headers=headers, timeout=30)
        data = resp.json()
        rows = data.get("data", [])
        if not rows:
            return None

        this_year_vals = []
        next_year_vals = []
        analyst_orgs = set()

        for r in rows:
            eps_this = r.get("predictThisYearEps")
            eps_next = r.get("predictNextYearEps")
            org = r.get("orgSName", "")
            if eps_this and float(eps_this) > 0:
                this_year_vals.append(float(eps_this))
                analyst_orgs.add(org)
            if eps_next and float(eps_next) > 0:
                next_year_vals.append(float(eps_next))

        if not this_year_vals:
            return None

        eps_cur = sum(this_year_vals) / len(this_year_vals)
        eps_next = sum(next_year_vals) / len(next_year_vals) if next_year_vals else None

        latest_date = rows[0].get("publishDate", "")
        year_current = latest_date[:4] if latest_date else ""
        year_next = str(int(year_current) + 1) if year_current else ""

        return {
            "eps_current": eps_cur,
            "eps_next": eps_next,
            "analyst_count": len(analyst_orgs),
            "year_current": year_current,
            "year_next": year_next,
        }
    except Exception as e:
        logger.warning(f"[{code}] 东财一致预期 EPS 获取失败: {e}")
        return None


def fetch_financial_abstract(code: str) -> Optional[Dict]:
    """调用 akshare 获取财务分析指标（存货周转、应收周转、毛利率等）"""
    code = str(code or "").strip()
    if not _is_standard_a_share_code(code):
        logger.info(f"[{code}] 非标准A股代码，已跳过财务摘要接口")
        return None

    try:
        import akshare as ak
        import pandas as pd
        df = ak.stock_financial_abstract(symbol=code)
        if df is None or df.empty:
            return None
        row = df.set_index('指标')
        def _get(indicator):
            if indicator not in row.index:
                return None
            val = row.loc[indicator]
            if isinstance(val, pd.DataFrame):
                val = val.iloc[0]
            for col in ['20260331', '20251231', '20240930', '20240630', '20240331', '20241231']:
                if col in val.index and pd.notna(val[col]):
                    return float(val[col])
            return None
        return {
            "inventory_days": _get('存货周转天数'),
            "receivable_days": _get('应收账款周转天数'),
            "gross_margin": _get('毛利率'),
            "net_margin": _get('销售净利率'),
            "roe": _get('净资产收益率(ROE)'),
            "revenue": _get('营业总收入'),
        }
    except Exception as e:
        logger.warning(f"[{code}] 财务指标获取失败: {e}")
        return None


def us_key_indicators(secucode: str, page_size: int = 4) -> List[Dict]:
    """
    东财 US GMAININDICATOR 关键财务指标（美股）
    secucode: "MBLY.O" (NASDAQ) / "BABA.N" (NYSE)
    返回字段: OPERATE_INCOME(营收), GROSS_PROFIT_RATIO(毛利率%), BASIC_EPS, ROE_AVG, ...
    """
    report_name = "RPT_USF10_FN_GMAININDICATOR"
    return eastmoney_datacenter(
        report_name=report_name,
        filter_str=f'(SECUCODE="{secucode}")',
        page_size=page_size,
        sort_columns="REPORT_DATE",
        sort_types="-1",
    )


def _extract_turnover_days(row: Dict) -> tuple:
    """
    从 GMAININDICATOR 行数据提取存货周转天数和应收账款周转天数。
    优先用 TDAYS 字段，没有则用 TR 计算：
      - 年报(FY): 360 / TR
      - 半年报(H1): 360 / (TR * 2)
      - 季报(Q): 360 / (TR * 4)
    """
    def _days(tr_val, report_type, date_type):
        if not tr_val or tr_val <= 0:
            return None
        if "FY" in report_type or "年报" in date_type:
            return 360 / tr_val
        elif "H1" in report_type or "半年报" in date_type:
            return 360 / (tr_val * 2)
        else:
            return 360 / (tr_val * 4)

    rt = row.get("REPORT_TYPE", "")
    dt = row.get("DATE_TYPE", "")

    inventory_days = row.get("INVENTORY_TDAYS")
    if inventory_days is None:
        inventory_days = _days(row.get("INVENTORY_TR"), rt, dt)

    receivable_days = row.get("ACCOUNTS_RECE_TDAYS")
    if receivable_days is None:
        receivable_days = _days(row.get("ACCOUNTS_RECE_TR"), rt, dt)

    return inventory_days, receivable_days


def fetch_competitor_metrics(
    stock_name: str,
    stock_codes: Dict[str, str],
    stock_config: Dict[str, Any] | None = None,
) -> Dict[str, Dict]:
    """获取目标股票及其竞争对手的财务+估值指标（支持A股、港股、美股）"""
    peer_codes = get_peer_codes(stock_name, stock_codes, stock_config)
    all_names = [stock_name] + get_peer_names(stock_name, stock_config)
    result = {}
    for name in all_names:
        code = peer_codes.get(name) or stock_codes.get(name) or COMPETITOR_CODES.get(name)
        if not code:
            continue
        metrics = {}

        # 财务数据：港股 vs A股 vs 美股
        is_hk = _is_hk_code(code) or ".HK" in code.upper()
        is_us = code.isalpha()
        manual_fin = load_manual_financials(name) or load_manual_financials(code)
        if manual_fin:
            metrics.update(manual_fin)
        elif is_hk:
            # 港股用东财 GMAININDICATOR（返回年报数据，无需年化）
            secucode = code if ".HK" in code.upper() else f"{code}.HK"
            hk_indicators = hk_key_indicators(secucode, page_size=1)
            if hk_indicators:
                row = hk_indicators[0]
                metrics["gross_margin"] = row.get("GROSS_PROFIT_RATIO")
                metrics["roe"] = row.get("ROE_AVG")
                metrics["revenue"] = row.get("OPERATE_INCOME")
                metrics["basic_eps"] = row.get("BASIC_EPS")
                inv_days, rec_days = _extract_turnover_days(row)
                metrics["inventory_days"] = inv_days
                metrics["receivable_days"] = rec_days
        elif is_us:
            # 美股用东财 US GMAININDICATOR（季度数据）
            secucode = f"{code.upper()}.O"  # NASDAQ 默认
            us_indicators = us_key_indicators(secucode, page_size=1)
            if us_indicators:
                row = us_indicators[0]
                metrics["gross_margin"] = row.get("GROSS_PROFIT_RATIO")
                metrics["roe"] = row.get("ROE_AVG")
                # 美股营收是美元，先保留原始值，后面统一换算
                metrics["revenue_usd"] = row.get("OPERATE_INCOME")
                metrics["basic_eps"] = row.get("BASIC_EPS")
                inv_days, rec_days = _extract_turnover_days(row)
                metrics["inventory_days"] = inv_days
                metrics["receivable_days"] = rec_days
        elif code.upper().startswith("H"):
            pass
        else:
            fin = fetch_financial_abstract(code)
            if fin:
                metrics.update(fin)

        quote = fetch_tencent_quote(code)
        if quote:
            metrics["mcap"] = quote.get("mcap_yi")
            metrics["pe_ttm"] = quote.get("pe_ttm")

        consensus = fetch_consensus_eps(code)
        if consensus and consensus.get("eps_current") and metrics.get("pe_ttm"):
            price = quote.get("price") if quote else None
            if price:
                fwd_pe = price / consensus["eps_current"] if consensus["eps_current"] else None
                growth = ((consensus["eps_next"] / consensus["eps_current"]) - 1) * 100 if consensus.get("eps_next") and consensus["eps_current"] else None
                metrics["forward_pe"] = fwd_pe
                metrics["eps_growth"] = growth
                metrics["peg"] = fwd_pe / growth if fwd_pe and growth else None

        if metrics.get("mcap") and metrics.get("revenue"):
            revenue_yi = metrics["revenue"] / 100000000
            if revenue_yi > 0:
                if is_hk:
                    metrics["ps"] = metrics["mcap"] / revenue_yi
                else:
                    metrics["ps"] = metrics["mcap"] / (revenue_yi * 4) if revenue_yi < 30 else metrics["mcap"] / revenue_yi
        elif metrics.get("mcap") and metrics.get("revenue_usd"):
            # 美股：营收是美元，市值已从腾讯接口转为港币
            # PS = 市值(亿港币) / (营收(美元) * 汇率 / 100000000 * 4)
            usd_to_hkd = _fetch_usd_to_hkd()
            revenue_yi = (metrics["revenue_usd"] / 100000000) * usd_to_hkd
            if revenue_yi > 0:
                metrics["ps"] = metrics["mcap"] / (revenue_yi * 4)
                # 将 revenue_usd 转换为等效港币用于后续展示
                metrics["revenue"] = metrics["revenue_usd"] * usd_to_hkd
        result[name] = metrics
    return result


def competitor_metrics_table(
    stock_name: str,
    metrics: Dict[str, Dict],
    stock_config: Dict[str, Any] | None = None,
) -> str:
    """生成竞争对手财务指标对比 Markdown 表格"""
    if not metrics:
        return ""
    lines = ["", "### 竞争对手财务指标对比", "", "> 数据来源: 东方财富财务摘要 + 腾讯财经实时行情 + 同花顺一致预期", ""]
    headers = ["公司", "存货周转(天)", "应收周转(天)", "毛利率(%)", "总市值(亿)", "PE(TTM)", "Forward PE", "PEG", "PS(市销率)"]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for name in [stock_name] + get_peer_names(stock_name, stock_config):
        m = metrics.get(name, {})
        def fmt(val, fmt_str="{:.1f}", suffix=""):
            if val is None:
                return "-"
            try:
                return fmt_str.format(float(val)) + suffix
            except (ValueError, TypeError):
                return str(val)
        row = [
            f"**{name}**" if name == stock_name else name,
            fmt(m.get("inventory_days")),
            fmt(m.get("receivable_days")),
            fmt(m.get("gross_margin")),
            fmt(m.get("mcap"), "{:.0f}"),
            fmt(m.get("pe_ttm")),
            fmt(m.get("forward_pe")),
            fmt(m.get("peg")),
            fmt(m.get("ps")),
        ]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    target = metrics.get(stock_name, {})
    if target.get("gross_margin"):
        lines.append(f"**{stock_name} 相对位置**: ")
        parts = []
        if target.get("inventory_days"):
            parts.append(f"存货周转天数 {target['inventory_days']:.0f} 天")
        if target.get("gross_margin"):
            parts.append(f"毛利率 {target['gross_margin']:.1f}%")
        if target.get("pe_ttm"):
            parts.append(f"PE(TTM) {target['pe_ttm']:.1f}")
        if target.get("ps"):
            parts.append(f"PS {target['ps']:.1f}")
        if parts:
            lines.append("、".join(parts) + "。")
        lines.append("")
    return "\n".join(lines)


def fetch_latest_quarterly_financials(code: str) -> Optional[Dict[str, Any]]:
    """
    获取最新季度财务数据（含同比）。

    港股：使用东财 GMAININDICATOR（含 YOY 字段）
    A股：使用 akshare 财务报告（取最新季度，手动计算同比）

    Returns:
        {
            "report_date": "2025-12-31",
            "date_type": "年报",
            "revenue": 822328000,
            "revenue_yoy": 73.4,
            "net_profit": -1773000000,
            "net_profit_yoy": -15.2,
            "gross_margin": 41.0,
            "gross_margin_yoy": -0.1,
            "net_margin": -215.6,
            "net_margin_yoy": 30.5,
            "roe": -126.5,
            "roe_yoy": -120.3,
            "basic_eps": -2.4,
            "eps_yoy": -300.0,
            "source": "eastmoney_gmainindicator",
        }
    """
    try:
        manual_fin = _manual_financials_for_code(code)
        if manual_fin:
            return manual_fin

        if _is_hk_code(code):
            secucode = f"{code}.HK"
            indicators = hk_key_indicators(secucode, page_size=1)
            if not indicators:
                return None
            row = indicators[0]
            return {
                "report_date": row.get("REPORT_DATE", ""),
                "date_type": row.get("DATE_TYPE", ""),
                "report_type": row.get("REPORT_TYPE", ""),
                "revenue": row.get("OPERATE_INCOME"),
                "revenue_yoy": row.get("OPERATE_INCOME_YOY"),
                "gross_profit": row.get("GROSS_PROFIT"),
                "gross_profit_yoy": row.get("GROSS_PROFIT_YOY"),
                "net_profit": row.get("HOLDER_PROFIT"),
                "net_profit_yoy": row.get("HOLDER_PROFIT_YOY"),
                "gross_margin": row.get("GROSS_PROFIT_RATIO"),
                "gross_margin_yoy": row.get("GROSS_PROFIT_RATIO_YOY"),
                "net_margin": row.get("NET_PROFIT_RATIO"),
                "net_margin_yoy": row.get("NET_PROFIT_RATIO_YOY"),
                "roe": row.get("ROE_AVG"),
                "roe_yoy": row.get("ROE_YOY"),
                "roa": row.get("ROA"),
                "roa_yoy": row.get("ROA_YOY"),
                "basic_eps": row.get("BASIC_EPS"),
                "eps_yoy": row.get("EPS_YOY"),
                "bps": row.get("BPS"),
                "bps_yoy": row.get("BPS_YOY"),
                "debt_ratio": row.get("DEBT_ASSET_RATIO"),
                "source": "eastmoney_gmainindicator",
            }
        elif not _is_standard_a_share_code(code):
            logger.info(f"[{code}] 非标准A股代码，已跳过季度财务接口")
            return None
        else:
            # A股：使用 akshare 财务摘要
            import akshare as ak
            import pandas as pd

            # 尝试获取季度利润表
            try:
                df = ak.stock_financial_report_sina(stock=code, symbol="利润表")
                if df is None or df.empty:
                    return None

                # 获取最新季度和去年同期
                latest = df.iloc[0]
                report_date = str(latest["报告日"])

                # 找去年同期（4个季度前）
                yoy_row = None
                if len(df) >= 5:
                    yoy_row = df.iloc[4]

                def _parse(val):
                    if pd.isna(val):
                        return None
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return None

                revenue = _parse(latest.get("营业总收入"))
                revenue_yoy = None
                if yoy_row is not None:
                    yoy_revenue = _parse(yoy_row.get("营业总收入"))
                    if revenue and yoy_revenue and yoy_revenue != 0:
                        revenue_yoy = round((revenue / yoy_revenue - 1) * 100, 2)

                net_profit = _parse(latest.get("归属于母公司所有者的净利润"))
                net_profit_yoy = None
                if yoy_row is not None:
                    yoy_np = _parse(yoy_row.get("归属于母公司所有者的净利润"))
                    if net_profit is not None and yoy_np is not None and yoy_np != 0:
                        net_profit_yoy = round((net_profit / yoy_np - 1) * 100, 2)

                # 毛利率需要从财务摘要获取
                fin_df = ak.stock_financial_abstract(symbol=code)
                gross_margin = None
                if fin_df is not None and not fin_df.empty:
                    row = fin_df.set_index("指标")
                    if "毛利率" in row.index:
                        val = row.loc["毛利率"]
                        for col in [report_date, report_date[:6] + "30", report_date[:4] + "1231"]:
                            if col in val.index and pd.notna(val[col]):
                                gross_margin = float(val[col])
                                break

                return {
                    "report_date": report_date,
                    "date_type": "季报",
                    "revenue": revenue,
                    "revenue_yoy": revenue_yoy,
                    "net_profit": net_profit,
                    "net_profit_yoy": net_profit_yoy,
                    "gross_margin": gross_margin,
                    "gross_margin_yoy": None,
                    "basic_eps": _parse(latest.get("基本每股收益")),
                    "source": "akshare_sina",
                }
            except Exception as e:
                logger.warning(f"[{code}] A股季度财务数据获取失败: {e}")
                return None
    except Exception as e:
        logger.warning(f"[{code}] 最新季度财务数据获取失败: {e}")
        return None


def industry_fwd_pe(stock_name: str) -> Optional[float]:
    """计算竞争对手 Forward PE 均值作为行业参考。"""
    competitors = COMPETITOR_MAP.get(stock_name, [])
    if not competitors:
        return None
    fwd_pes = []
    for comp in competitors:
        code = COMPETITOR_CODES.get(comp)
        if not code:
            continue
        c_quote = fetch_tencent_quote(code)
        c_consensus = fetch_consensus_eps(code)
        if c_quote and c_consensus and c_consensus.get("eps_current"):
            price = c_quote.get("price", 0)
            eps = c_consensus["eps_current"]
            if price and eps:
                fwd_pes.append(price / eps)
    if not fwd_pes:
        return None
    return sum(fwd_pes) / len(fwd_pes)


def fetch_index_bars(client, symbol: str, market: str = "std", days: int = 60):
    """获取指数日K数据。兼容 mootdx 两种 API 签名。"""
    if client is None:
        logger.warning("mootdx client 未初始化，无法获取指数数据")
        return None
    try:
        try:
            df = client.index_bars(symbol=symbol, market=market, frequency="9", offset=days)
        except TypeError:
            df = client.index_bars(symbol=symbol, frequency="9", offset=days)
        if df is None or df.empty:
            return None
        df = df.reset_index()
        if "datetime" in df.columns:
            df["date"] = pd.to_datetime(df["datetime"])
        elif "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception as e:
        logger.warning(f"获取指数 {symbol} 数据失败: {e}")
        return None
