import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Callable, Any
from datetime import datetime, timedelta

import pandas as pd

try:
    from technical_ohlcv_cache import normalize_ohlcv_frame
except ImportError:
    from .technical_ohlcv_cache import normalize_ohlcv_frame

try:
    from mootdx.quotes import Quotes
except ImportError:
    Quotes = None

try:
    import stockstats
except ImportError:
    stockstats = None

logger = logging.getLogger(__name__)

_BAIDU_PAE_HEADERS = {
    "Host": "finance.pae.baidu.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0",
    "Accept": "application/vnd.finance-web.v1+json",
    "Origin": "https://gushitong.baidu.com",
    "Referer": "https://gushitong.baidu.com/",
}


def _baidu_fund_flow_history(code: str, days: int = 20) -> list[dict]:
    """百度股市通个股资金流向（日级，最近 N 交易日）。"""
    import requests
    url = (
        f"https://finance.pae.baidu.com/vapi/v1/fundsortlist"
        f"?code={code}&market=ab&pn=0&rn={days}"
        f"&finClientType=pc"
    )
    try:
        r = requests.get(url, headers=_BAIDU_PAE_HEADERS, timeout=10)
        d = r.json()
        if str(d.get("ResultCode", -1)) != "0":
            return []
        rows = []
        for item in d.get("Result", {}).get("list", []):
            rows.append({
                "date": item.get("showtime", ""),
                "close": item.get("closepx", ""),
                "change_pct": item.get("ratio", ""),
                "super_net_in": item.get("superNetIn", ""),
                "large_net_in": item.get("largeNetIn", ""),
                "medium_net_in": item.get("mediumNetIn", ""),
                "small_net_in": item.get("littleNetIn", ""),
                "main_in": item.get("extMainIn", ""),
            })
        return rows
    except Exception as e:
        logger.info(f"可选数据源 百度资金流向 不可用，已跳过: {e}")
        return []


def _baidu_concept_blocks(code: str) -> dict:
    """百度股市通概念板块归属。"""
    import requests
    url = (
        f"https://finance.pae.baidu.com/api/getrelatedblock"
        f"?code={code}&market=ab"
        f"&typeCode=all&finClientType=pc"
    )
    try:
        r = requests.get(url, headers=_BAIDU_PAE_HEADERS, timeout=10)
        d = r.json()
        if str(d.get("ResultCode", -1)) != "0":
            return {}
        result = {"industry": [], "concept": [], "region": [], "concept_tags": []}
        for block in d.get("Result", []):
            block_type = block.get("type", "")
            for item in block.get("list", []):
                entry = {
                    "name": item.get("name", ""),
                    "change_pct": item.get("increase", ""),
                    "desc": item.get("desc", ""),
                }
                if "行业" in block_type:
                    result["industry"].append(entry)
                elif "概念" in block_type:
                    result["concept"].append(entry)
                    result["concept_tags"].append(entry["name"])
                elif "地域" in block_type:
                    result["region"].append(entry)
        return result
    except Exception as e:
        logger.info(f"可选数据源 百度概念板块 不可用，已跳过: {e}")
        return {}


class AkshareHelper:
    """
    akshare 调用包装器，带限速、重试、失败降级。

    使用方式:
        helper = AkshareHelper()
        df = helper.call(ak.stock_financial_abstract, symbol='300661')
    """

    def __init__(self, delay_sec: float = 1.5, max_retries: int = 3):
        self.delay_sec = delay_sec
        self.max_retries = max_retries
        self._last_call_time = 0.0

    def call(
        self,
        func: Callable,
        *args,
        optional: bool = False,
        source_name: str | None = None,
        fallback_name: str | None = None,
        **kwargs,
    ) -> Any:
        """
        带限速和重试地调用 akshare 函数。
        返回函数结果，或在所有重试失败后返回 None。
        """
        label = source_name or getattr(func, "__name__", "akshare")
        # 限速：确保两次调用间隔至少 delay_sec
        elapsed = time.time() - self._last_call_time
        if elapsed < self.delay_sec:
            time.sleep(self.delay_sec - elapsed)

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self._last_call_time = time.time()
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                err_name = type(e).__name__
                if "RemoteDisconnected" in err_name or "ConnectionError" in err_name or "Connection aborted" in str(e):
                    wait = attempt * 2  # 2s, 4s, 6s
                    log = logger.info if optional else logger.warning
                    log(f"akshare 调用 {label} 失败 (attempt {attempt}/{self.max_retries}): {e}")
                    if attempt < self.max_retries:
                        logger.info(f"等待 {wait}s 后重试...")
                        time.sleep(wait)
                else:
                    # 非网络错误，不重试
                    log = logger.info if optional else logger.warning
                    log(f"akshare 调用 {label} 失败 (非网络错误): {e}")
                    break

        if optional:
            if fallback_name:
                logger.info(f"可选数据源 {label} 不可用，已交给 {fallback_name}: {last_error}")
            else:
                logger.info(f"可选数据源 {label} 不可用，已跳过: {last_error}")
        else:
            logger.error(f"akshare 调用 {label} 最终失败: {last_error}")
        return None


class TechnicalCollector:
    """采集技术指标数据（mootdx + stockstats）"""

    def __init__(self):
        self.client = None
        self._mootdx_initialized = False

    def _get_mootdx_client(self):
        if self.client is not None:
            return self.client
        if getattr(self, "_mootdx_initialized", False) or Quotes is None:
            return None
        self._mootdx_initialized = True
        try:
            self.client = Quotes.factory(market="std")
        except Exception as e:
            logger.warning(f"mootdx 初始化失败: {e}")
        return self.client

    def fetch_kline(self, code: str, market: int | str = 0, days: int = 120, adjustment: str | None = None) -> Optional[pd.DataFrame]:
        """
        获取日K线数据。
        优先级：1) akshare qfq  2) mootdx raw
        Args:
            adjustment: "qfq"=强制akshare前复权, "raw"=强制mootdx原始, None=自动优先qfq
        """
        # --- Priority 1: akshare qfq (unless raw explicitly requested) ---
        if ak is not None and adjustment != "raw":
            helper = AkshareHelper()
            if market == "hk":
                df = helper.call(
                    ak.stock_hk_hist,
                    symbol=code,
                    period="daily",
                    start_date=(datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d"),
                )
            else:
                prefix = "SZ" if market == 0 else "SH"
                symbol = f"{prefix}{code}"
                df = helper.call(
                    ak.stock_zh_a_hist,
                    symbol=symbol,
                    period="daily",
                    start_date=(datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d"),
                    adjust="qfq",
                    optional=True,
                    source_name="akshare stock_zh_a_hist",
                    fallback_name="mootdx raw" if adjustment is None else None,
                )
            normalized = normalize_ohlcv_frame(
                df, source="akshare_hk" if market == "hk" else "akshare",
                adjustment="raw" if market == "hk" else "qfq", limit=days,
            )
            if normalized is not None:
                return normalized

        if market == "hk":
            logger.warning(f"{code} 港股日K获取失败，跳过 mootdx A股回退")
            return None
        if adjustment == "qfq":
            return None

        # --- Priority 2: mootdx raw ---
        client = self._get_mootdx_client()
        if client is None:
            logger.error("mootdx 客户端未初始化")
            return None
        try:
            df = client.bars(symbol=code, frequency=9, start=0, offset=days)
        except Exception as e:
            logger.warning(f"获取 {code} 日K失败: {e}")
            return None
        return normalize_ohlcv_frame(
            df, source="mootdx", adjustment="raw", limit=days,
        )

    def fetch_weekly_kline(
        self, code: str, market: int | str = 0, weeks: int = 72,
        source: str | None = None, adjustment: str | None = None,
    ) -> Optional[pd.DataFrame]:
        """
        获取与日线来源/复权方式一致的周K线数据。
        """
        prefer_mootdx = source == "mootdx" or (source is None and market != "hk")
        if prefer_mootdx:
            client = self._get_mootdx_client()
            try:
                df = client.bars(symbol=code, frequency=5, start=0, offset=weeks) if client else None
            except Exception as e:
                logger.warning(f"mootdx 周线获取失败: {e}")
                df = None
            normalized = normalize_ohlcv_frame(
                df, source="mootdx", adjustment="raw", limit=weeks,
            )
            if normalized is not None or source == "mootdx":
                return normalized

        if ak is None:
            logger.warning("akshare 未安装，无法获取周线数据")
            return None

        helper = AkshareHelper()
        df = None
        if market == 0 or market == 1:
            prefix = "SZ" if market == 0 else "SH"
            symbol = f"{prefix}{code}"
            df = helper.call(
                ak.stock_zh_a_hist,
                symbol=symbol,
                period="weekly",
                start_date="20200101",
                adjust="qfq",
                optional=True,
                source_name="akshare stock_zh_a_hist weekly",
            )
        else:
            df = helper.call(
                ak.stock_hk_hist,
                symbol=code,
                period="weekly",
                start_date="20200101",
                optional=True,
                source_name="akshare stock_hk_hist weekly",
            )

        if df is None or df.empty:
            return None

        return normalize_ohlcv_frame(
            df, source="akshare_hk" if market == "hk" else "akshare",
            adjustment="raw" if market == "hk" else (adjustment or "qfq"), limit=weeks,
        )

    def _compute_indicators_legacy(self, df: pd.DataFrame, code: str | None = None) -> Dict:
        """
        计算技术指标（优先使用 technical_analyzer，回退到 stockstats）。
        Args:
            df: 日K DataFrame
            code: 股票代码，用于 technical_analyzer 的市场/板块共振映射
        Returns:
            Dict with latest indicator values + resonance + patterns + levels
        """
        # 仅保留 stockstats 兼容回退，避免在主 analyzer 失败后再次计算目标价。
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

            # 从原始 DataFrame 计算额外量化指标（不依赖 stockstats）
            if len(df) >= 22:
                latest_close = float(df["close"].iloc[-1])
                month_ago_close = float(df["close"].iloc[-22])
                result["monthly_return_pct"] = round((latest_close - month_ago_close) / month_ago_close * 100, 2)

            if len(df) >= 20 and "amount" in df.columns:
                # amount 通常为元，转换为亿元
                avg_amount = float(df["amount"].tail(20).mean())
                result["avg_amount_yi"] = round(avg_amount / 100000000, 2)
            elif len(df) >= 20 and "volume" in df.columns:
                # 若只有 volume（股），用 close * volume 估算成交额
                avg_vol = float(df["volume"].tail(20).mean())
                avg_close = float(df["close"].tail(20).mean())
                result["avg_amount_yi"] = round(avg_vol * avg_close / 100000000, 2)

            # Remove None values for cleaner JSON
            return {k: v for k, v in result.items() if v is not None}
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
            return {}

    def _run_technical_analyzer(
        self, df_daily, df_weekly=None, code=None, market=None, cache_dir=None,
    ):
        try:
            from .reporter.technical_analyzer import analyze
        except ImportError:
            from reporter.technical_analyzer import analyze
        quote = {
            "code": code or getattr(df_daily, "attrs", {}).get("code"),
            "market": market,
            "is_hk": market == "hk",
            "adjustment": getattr(df_daily, "attrs", {}).get("adjustment", "raw"),
            "data_source": getattr(df_daily, "attrs", {}).get("data_source", "unknown"),
            "technical_ohlcv_cache_dir": cache_dir,
            "index_cache_enabled": market != "hk",
        }
        return analyze(df_daily, df_weekly=df_weekly, quote=quote)

    def build_technical_payload(
        self,
        df_daily: pd.DataFrame,
        df_weekly: pd.DataFrame | None = None,
        code: str | None = None,
        market: int | str | None = None,
        cache_dir=None,
    ) -> Dict:
        """Build the sole technical payload and calculate the target once."""
        if df_daily is None or df_daily.empty:
            return {}
        try:
            result = self._run_technical_analyzer(
                df_daily, df_weekly, code, market, cache_dir=cache_dir,
            )
        except Exception as exc:
            logger.warning(f"technical_analyzer 失败，回退到 stockstats: {exc}")
            result = {}
        if not result or not result.get("indicators"):
            indicators = self._compute_indicators_legacy(df_daily, code=code)
            return {
                "indicators": indicators,
                "price_target": None,
                "patterns": [],
                "levels": {},
            }

        indicators = dict(result.get("indicators", {}))
        resonance = dict(result.get("resonance", {}) or {})
        target = result.get("price_target")
        try:
            from .reporter.technical_state_machine import ensure_technical_judgment
        except ImportError:
            from reporter.technical_state_machine import ensure_technical_judgment
        resonance["judgment"] = ensure_technical_judgment(
            resonance.get("judgment"), resonance=resonance,
            price_target=target, indicators=indicators,
            daily_data=df_daily, market=market,
        )
        indicators["_resonance"] = resonance
        indicators["_patterns"] = result.get("patterns", [])
        indicators["_levels"] = result.get("levels", {})
        return {
            "indicators": indicators,
            "price_target": target,
            "patterns": result.get("patterns", []),
            "levels": result.get("levels", {}),
            "market": market,
            "code": code,
        }

    def compute_indicators(self, df: pd.DataFrame, code: str | None = None, market: int | str | None = None) -> Dict:
        """Compatibility wrapper returning only the builder's flat indicators."""
        payload = self.build_technical_payload(df, code=code, market=market)
        return payload.get("indicators", {})

    def build_collection_payload(
        self, df_daily: pd.DataFrame, df_weekly: pd.DataFrame | None = None, *,
        code: str, market: int | str = 0, fetched_at: str | None = None,
        data_source: str | None = None, include_optional: bool = False,
        cache_dir=None,
    ) -> Dict:
        source = data_source or df_daily.attrs.get("data_source", "unknown")
        if data_source:
            df_daily = df_daily.copy()
            df_daily.attrs["data_source"] = data_source
        try:
            technical = self.build_technical_payload(
                df_daily, df_weekly=df_weekly, code=code, market=market,
                cache_dir=cache_dir,
            )
        except Exception as e:
            logger.warning(f"价格目标分析失败: {e}")
            technical = {}
        return {
            "code": code, "market": market, "days": len(df_daily),
            "adjustment": df_daily.attrs.get("adjustment", "raw"),
            "data_source": source, "indicators": technical.get("indicators", {}),
            "price_target": technical.get("price_target"),
            "daily_data": df_daily.to_dict(orient="list"),
            "weekly_data": df_weekly.to_dict(orient="list") if df_weekly is not None else {},
            "technical": technical,
            "fund_flow": _baidu_fund_flow_history(code, days=5) if include_optional else [],
            "concept_blocks": _baidu_concept_blocks(code) if include_optional else {},
            "fetched_at": fetched_at or datetime.now().astimezone().isoformat(),
        }

    def collect(
        self, code: str, market: int | str = 0, days: int = 120,
        adjustment: str | None = None, cache_dir=None,
    ) -> Dict:
        """一键采集技术指标（含日线+周线+价格目标）"""
        df_daily = self.fetch_kline(code, market, days, adjustment=adjustment)
        if df_daily is None or df_daily.empty:
            return {}
        # --- 周线、指标、判断与价格目标统一由一个 builder 完成 ---
        try:
            df_weekly = self.fetch_weekly_kline(
                code, market, weeks=72,
                source=df_daily.attrs.get("data_source"),
                adjustment=df_daily.attrs.get("adjustment"),
            )
        except Exception as e:
            logger.warning(f"周线数据获取失败，保留日线分析: {e}")
            df_weekly = None
        return self.build_collection_payload(
            df_daily, df_weekly, code=code, market=market, include_optional=True,
            cache_dir=cache_dir,
        )


import ssl
import urllib.request
from datetime import datetime, timedelta


try:
    import akshare as ak
except ImportError:
    ak = None


class ReportCollector:
    """采集券商研报数据（东财 reportapi，直接 HTTP 调用，不依赖 akshare）"""

    REPORT_API = "https://reportapi.eastmoney.com/report/list"
    PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
    UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

    def __init__(self):
        self.session = None

    def _get_session(self):
        import requests
        if self.session is None:
            self.session = requests.Session()
            self.session.headers.update({"User-Agent": self.UA, "Referer": "https://data.eastmoney.com/"})
        return self.session

    def collect(self, code: str, months: int = 4) -> list:
        """
        采集近 N 个月的研报
        Returns:
            List of dicts: [{title, institution, author, rating, target_price, summary, date, url}]
        """
        import requests
        import time

        try:
            all_records = []
            for page in range(1, 6):
                params = {
                    "industryCode": "*", "pageSize": "100", "industry": "*",
                    "rating": "*", "ratingChange": "*",
                    "beginTime": "2000-01-01", "endTime": "2030-01-01",
                    "pageNo": str(page), "fields": "", "qType": "0",
                    "orgCode": "", "code": code, "rcode": "",
                    "p": str(page), "pageNum": str(page), "pageNumber": str(page),
                }
                resp = requests.get(self.REPORT_API, params=params, headers={"User-Agent": self.UA, "Referer": "https://data.eastmoney.com/"}, timeout=30)
                data = resp.json()
                rows = data.get("data") or []
                if not rows:
                    break
                all_records.extend(rows)
                if page >= (data.get("TotalPage", 1) or 1):
                    break
                time.sleep(0.3)

            cutoff = datetime.now() - timedelta(days=months * 30)
            reports = []
            for r in all_records:
                pub_date = r.get("publishDate", "")
                try:
                    if pub_date:
                        pd_date = datetime.strptime(pub_date[:10], "%Y-%m-%d")
                        if pd_date < cutoff:
                            continue
                except Exception:
                    continue

                info_code = r.get("infoCode", "")
                pdf_url = self.PDF_TPL.format(info_code=info_code) if info_code else ""

                reports.append({
                    "title": str(r.get("title", "")),
                    "institution": str(r.get("orgSName", "")),
                    "author": "",
                    "rating": str(r.get("emRatingName", "")),
                    "target_price": "",
                    "summary": "",
                    "date": pub_date[:10] if pub_date else "",
                    "url": pdf_url,
                })

            return reports[:20]
        except Exception as e:
            logger.error(f"采集 {code} 研报失败: {e}")
            return []


class AnnouncementCollector:
    """采集公司公告数据（巨潮/akshare）"""

    def __init__(self):
        self.helper = AkshareHelper()

    def collect(self, code: str, months: int = 3) -> list:
        if ak is None:
            logger.warning("akshare 未安装，跳过公告采集")
            return []

        df = self.helper.call(ak.stock_individual_notice_report, code)
        if df is None or df.empty:
            return []

        announcements = []
        cutoff = datetime.now() - timedelta(days=months * 30)
        important_types = ["定期报告", "重大事项", "股权激励", "增减持", "并购", "关联交易"]

        for _, row in df.iterrows():
            try:
                pub_date = pd.to_datetime(row.get("公告日期", ""))
                if pub_date < cutoff:
                    continue
            except Exception:
                continue

            ann_type = str(row.get("公告类型", ""))
            announcements.append({
                "title": str(row.get("公告标题", "")),
                "type": ann_type,
                "date": str(row.get("公告日期", "")),
                "content": "",  # No content field available
                "url": str(row.get("网址", "")),
                "is_important": any(t in ann_type for t in important_types),
            })

        announcements.sort(key=lambda x: (not x["is_important"], x["date"]), reverse=True)
        return announcements[:15]


class FundFlowCollector:
    """采集资金流向数据（东方财富 / akshare）"""

    def __init__(self):
        self.helper = AkshareHelper()

    def collect(self, code: str, days: int = 7) -> list:
        """采集资金流向，当前环境下 API 可能被限制，返回空列表并记录警告"""
        if ak is None:
            logger.warning("akshare 未安装，跳过资金流向采集")
            return []
        market = "sz" if code.startswith(("00", "30")) else "sh"
        df = self.helper.call(
            ak.stock_individual_fund_flow,
            stock=code,
            market=market,
            optional=True,
            source_name="akshare stock_individual_fund_flow",
        )
        if df is None or df.empty:
            return []
        # akshare returns data in reverse chronological order
        df = df.head(days)
        results = []
        for _, row in df.iterrows():
            results.append({
                "date": str(row.get("日期", "")),
                "main_inflow": float(row.get("主力净流入", 0)),
                "retail_inflow": float(row.get("小单净流入", 0)),
                "large_order_pct": float(row.get("超大单净流入", 0)),
            })
        return results


class NewsCollector:
    """采集个股新闻（akshare）"""

    def __init__(self):
        self.helper = AkshareHelper()

    def collect(self, code: str, days: int = 30) -> list:
        if ak is None:
            return []
        df = self.helper.call(ak.stock_news_em, symbol=code)
        if df is None or df.empty:
            return []
        cutoff = datetime.now() - timedelta(days=days)
        results = []
        for _, row in df.iterrows():
            try:
                pub_date = pd.to_datetime(row.get("发布时间", ""))
                if pub_date < cutoff:
                    continue
            except Exception:
                continue
            results.append({
                "title": str(row.get("新闻标题", "")),
                "summary": str(row.get("新闻内容", ""))[:300],
                "source": str(row.get("文章来源", "")),
                "date": str(row.get("发布时间", "")),
                "url": str(row.get("新闻链接", "")),
            })
        return results[:20]


import requests
import time
import os


class ZhihuCollector:
    """
    采集知乎内容（知乎开发者平台 API）
    - 关键词搜索（如：圣邦股份、模拟芯片）
    - 指定博主文章搜索
    - 自动筛选股市/宏观经济相关内容

    ⚠️ 知乎API每日限量1000次，本采集器已内置限流保护
    """

    BASE_URL = "https://developer.zhihu.com/api/v1/content/zhihu_search"
    WEB_SEARCH_URL = "https://developer.zhihu.com/api/v1/content/global_search"
    DAILY_LIMIT = 1000  # 知乎API日限额

    # 股市/宏观经济相关关键词（用于初步过滤）
    STOCK_MACRO_KEYWORDS = [
        "股票", "股市", "A股", "港股", "美股", "大盘", "指数", "板块",
        "投资", "估值", "PE", "PB", "财报", "营收", "利润", "净利润", "毛利率",
        "业绩", "研报", "券商", "基金", "持仓", "牛市", "熊市", "上涨", "下跌",
        "涨幅", "跌幅", "主力", "散户", "机构", "北向资金", "回购", "分红",
        "市值", "股东", "减持", "增持", "IPO", "退市", "成交量", "成交额",
        "换手率", "市盈率", "市净率", "ROE", "EPS", "年报", "季报", "中报",
        "宏观经济", "GDP", "CPI", "PPI", "通胀", "通缩", "利率", "降息", "加息",
        "央行", "美联储", "货币政策", "财政政策", "降准", "量化宽松", "QE",
        "经济周期", "复苏", "衰退", "PMI", "制造业", "汇率", "人民币", "美元",
        "关税", "贸易", "能源", "原油", "黄金", "大宗商品", "房地产", "楼市",
        "房价", "国债", "地方债", "消费", "内需", "外需", "双循环",
        "半导体", "芯片", "模拟芯片", "集成电路", "国产替代", "涨价", "周期",
        "光模块", "AI芯片", "车规级", "德州仪器", "TI", "ADI", "思瑞浦", "纳芯微",
        "杰华特", "艾为电子",
    ]

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ZHIHU_API_KEY")
        if not self.api_key:
            logger.warning("ZHIHU_API_KEY 未设置，ZhihuCollector 将不可用")
        self._request_count = 0
        self._cache = {}  # query -> (timestamp, results)
        self._cache_ttl = 3600  # 缓存1小时

    def _check_limit(self) -> bool:
        """检查是否超出日限额"""
        if self._request_count >= self.DAILY_LIMIT:
            logger.warning(f"知乎API日限额已达 ({self.DAILY_LIMIT})，跳过本次请求")
            return False
        return True

    def _request(self, query: str, limit: int = 5, endpoint: str = None) -> list:
        """发起知乎搜索请求（带缓存和限流）

        Args:
            query: 搜索关键词
            limit: 返回条数
            endpoint: 自定义端点，默认使用 BASE_URL（站内搜索）
        """
        if not self.api_key:
            return []

        if not self._check_limit():
            return []

        url = endpoint or self.BASE_URL
        cache_key = f"{url}::{query}"

        # 检查缓存
        now = time.time()
        if cache_key in self._cache:
            cached_time, cached_results = self._cache[cache_key]
            if now - cached_time < self._cache_ttl:
                logger.info(f"知乎搜索 '{query}' 命中缓存")
                return cached_results

        try:
            self._request_count += 1
            ts = int(now)
            resp = requests.get(
                url,
                params={"Query": query, "limit": limit},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Request-Timestamp": str(ts),
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("Code") != 0:
                logger.warning(f"知乎API返回错误: {data.get('Message')}")
                return []

            items = data.get("Data", {}).get("Items", [])
            results = []
            for item in items:
                results.append({
                    "title": str(item.get("Title", "")),
                    "content_type": str(item.get("ContentType", "")),
                    "content_id": str(item.get("ContentID", "")),
                    "content_text": str(item.get("ContentText", ""))[:800],
                    "url": str(item.get("Url", "")),
                    "comment_count": int(item.get("CommentCount", 0)),
                    "vote_up_count": int(item.get("VoteUpCount", 0)),
                    "author_name": str(item.get("AuthorName", "")),
                    "author_badge": str(item.get("AuthorBadgeText", "")),
                    "edit_time": int(item.get("EditTime", 0)),
                    "authority_level": str(item.get("AuthorityLevel", "")),
                    "ranking_score": float(item.get("RankingScore", 0)),
                    "source": "知乎",
                })

            # 写入缓存
            self._cache[cache_key] = (now, results)
            return results
        except Exception as e:
            logger.error(f"知乎搜索失败 [{query}]: {e}")
            return []

    @staticmethod
    def _infer_platform(url: str) -> str:
        """通过 URL 域名推断来源平台"""
        if not url:
            return "未知来源"
        url_lower = url.lower()
        if "mp.weixin.qq.com" in url_lower:
            return "微信公众号"
        if "36kr.com" in url_lower:
            return "36氪"
        if "caixin.com" in url_lower:
            return "财新网"
        if "wallstreetcn.com" in url_lower:
            return "华尔街见闻"
        if "cls.cn" in url_lower:
            return "财联社"
        if "zhuanlan.zhihu.com" in url_lower or "zhihu.com" in url_lower:
            return "知乎"
        if "sohu.com" in url_lower:
            return "搜狐"
        if "163.com" in url_lower or "netease.com" in url_lower:
            return "网易"
        if "sina.com.cn" in url_lower or "sina.com" in url_lower:
            return "新浪"
        if "huanqiu.com" in url_lower:
            return "环球网"
        if "cs.com.cn" in url_lower:
            return "中证网"
        if "cninfo.com.cn" in url_lower:
            return "巨潮资讯"
        if "eastmoney.com" in url_lower:
            return "东方财富"
        if "stcn.com" in url_lower:
            return "证券时报"
        # 提取域名作为兜底
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            return domain
        except Exception:
            return "未知来源"

    def search_web(self, keywords: list, limit_per_kw: int = 5) -> list:
        """
        调用知乎全网搜索 API（global_search）
        策略：与 search_keywords 一致，但端点不同
        Returns: 合并去重后的全网文章列表
        """
        all_items = []
        seen_ids = set()
        for kw in keywords:
            items = self._request(kw, limit=limit_per_kw, endpoint=self.WEB_SEARCH_URL)
            for item in items:
                cid = item.get("content_id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    item["search_keyword"] = kw
                    item["_source_type"] = "web"
                    item["source_platform"] = self._infer_platform(item.get("url", ""))
                    all_items.append(item)
            logger.info(f"知乎全网搜索 '{kw}' 获取 {len(items)} 条结果")
        return all_items

    def _is_stock_macro_related(self, text: str) -> bool:
        """基于关键词判断内容是否与股市/宏观经济相关"""
        text_lower = text.lower()
        for kw in self.STOCK_MACRO_KEYWORDS:
            if kw.lower() in text_lower:
                return True
        return False

    def search_keywords(self, keywords: list, limit_per_kw: int = 5) -> list:
        """
        按关键词搜索知乎内容
        Returns: 合并去重后的文章列表
        """
        all_items = []
        seen_ids = set()
        for kw in keywords:
            items = self._request(kw, limit=limit_per_kw)
            for item in items:
                cid = item.get("content_id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    item["search_keyword"] = kw
                    all_items.append(item)
            logger.info(f"知乎搜索 '{kw}' 获取 {len(items)} 条结果")
        return all_items

    def search_authors(self, author_names: list, limit_per_author: int = 3) -> list:
        """
        搜索指定博主的文章
        策略：先用博主名搜索，然后筛选出该博主的内容
        """
        all_items = []
        seen_ids = set()
        for name in author_names:
            items = self._request(name, limit=limit_per_author * 2)
            author_items = [
                item for item in items
                if name.lower() in item.get("author_name", "").lower()
            ]
            for item in author_items[:limit_per_author]:
                cid = item.get("content_id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    item["search_keyword"] = f"博主:{name}"
                    all_items.append(item)
            logger.info(f"知乎博主 '{name}' 获取 {len(author_items)} 条结果")
        return all_items

    def collect(self, stock_name: str = None, keywords: list = None,
                author_names: list = None, limit: int = 5,
                use_curator: bool = True) -> Dict:
        """
        一键采集知乎内容，自动分类为【报告相关】和【知识沉淀】
        注意：默认每关键词5条、每博主3条，以控制API用量

        Args:
            use_curator: 是否启用 ContentQualityGate 进行统一质量评估（默认True）

        Returns:
            {
                "report_items": [...],      # 高质量内容（进入报告）
                "knowledge_items": [...],   # 未采纳内容（知识沉淀）
                "total": N,
                "api_calls": N,             # 知乎API消耗次数
                "gate_stats": {...},        # 质量门统计（若启用）
            }
        """
        start_count = self._request_count

        # 默认关键词
        default_keywords = [stock_name] if stock_name else []
        search_keywords = list(set((keywords or []) + default_keywords))

        # 默认关注博主
        default_authors = ["Deep Van", "奥特之父", "MR.Dang", "羊村里最快的羊"]
        search_authors = author_names or default_authors

        # 搜索（站内 + 全网）
        kw_items = self.search_keywords(search_keywords, limit_per_kw=limit)
        author_items = self.search_authors(search_authors, limit_per_author=min(limit, 3))
        web_items = self.search_web(search_keywords, limit_per_kw=limit)

        all_items = kw_items + author_items + web_items
        api_calls = self._request_count - start_count

        # 去重
        seen_ids = set()
        unique_items = []
        for item in all_items:
            cid = item.get("content_id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                unique_items.append(item)

        # 是否启用 ContentQualityGate 进行统一质量评估
        gate_stats = None
        if use_curator:
            try:
                from .content_quality_gate import ContentQualityGate
                gate = ContentQualityGate()
                quality_results = gate.process_zhihu_items(unique_items)

                report_items = []
                knowledge_items = []
                for result in quality_results:
                    item = result.item.extra
                    item["_quality_gate"] = {
                        "passed_hard_gate": result.passed_hard_gate,
                        "quality_score": result.quality_score,
                        "action": result.action,
                        "reasons": result.reasons,
                    }
                    if result.action == "keep":
                        report_items.append(item)
                    else:
                        knowledge_items.append(item)

                gate_stats = {
                    "total": len(unique_items),
                    "hard_passed": sum(1 for r in quality_results if r.passed_hard_gate),
                    "keep": len(report_items),
                    "demote": sum(1 for r in quality_results if r.action == "demote"),
                    "discard": sum(1 for r in quality_results if r.action == "discard"),
                }
                logger.info(
                    f"知乎采集+质量门完成: 共 {len(unique_items)} 条 "
                    f"(站内 {len(kw_items)} + 博主 {len(author_items)} + 全网 {len(web_items)}), "
                    f"报告纳入 {len(report_items)} 条, 知识沉淀 {len(knowledge_items)} 条, "
                    f"知乎API {api_calls} 次"
                )
            except Exception as e:
                logger.warning(f"ContentQualityGate 启用失败，回退到关键词分类: {e}")
                # 回退：简单关键词分类
                report_items = []
                knowledge_items = []
                for item in unique_items:
                    text = item.get("title", "") + " " + item.get("content_text", "")
                    if self._is_stock_macro_related(text):
                        item["relevance"] = "股市/宏观经济"
                        report_items.append(item)
                    else:
                        item["relevance"] = "知识沉淀"
                        knowledge_items.append(item)
        else:
            # 不使用 quality gate：简单关键词分类
            report_items = []
            knowledge_items = []
            for item in unique_items:
                text = item.get("title", "") + " " + item.get("content_text", "")
                if self._is_stock_macro_related(text):
                    item["relevance"] = "股市/宏观经济"
                    report_items.append(item)
                else:
                    item["relevance"] = "知识沉淀"
                    knowledge_items.append(item)

            logger.info(
                f"知乎采集完成: 共 {len(unique_items)} 条 "
                f"(站内 {len(kw_items)} + 博主 {len(author_items)} + 全网 {len(web_items)}), "
                f"报告相关 {len(report_items)} 条, 知识沉淀 {len(knowledge_items)} 条, "
                f"消耗API {api_calls} 次 (今日累计 {self._request_count}/{self.DAILY_LIMIT})"
            )

        # === ZhihuCurator 增强层 ===
        # 在 ContentQualityGate 之后，对 report_items 进行 LLM 精编 + 时效判断
        curator_stats = None
        if use_curator and report_items:
            try:
                from .zhihu_curator import ZhihuCurator
                curator = ZhihuCurator()
                curator_result = curator.curate(report_items)

                # 最终 report_items = Curator 筛选后的高质量内容
                curated_report = curator_result.get("report_items", [])
                curated_knowledge = curator_result.get("knowledge_items", [])
                curator_stats = curator_result.get("stats", {})

                # 将 Curator 淘汰的内容并入 knowledge_items
                # (ContentQualityGate 原来的 knowledge_items + Curator 淘汰的)
                knowledge_items = knowledge_items + curated_knowledge

                # 更新 report_items
                report_items = curated_report

                logger.info(
                    f"ZhihuCurator 增强层完成: gate后 {curator_stats.get('total', 0)} 条 → "
                    f"L1粗筛 {curator_stats.get('l1_passed', 0)} → "
                    f"L2评估 {curator_stats.get('l2_evaluated', 0)} → "
                    f"L3纳入 {curator_stats.get('l3_included', 0)} 条"
                )
            except Exception as e:
                logger.warning(f"ZhihuCurator 增强层启用失败，保留 ContentQualityGate 结果: {e}")

        result = {
            "report_items": report_items,
            "knowledge_items": knowledge_items,
            "total": len(unique_items),
            "api_calls": api_calls,
        }
        if gate_stats:
            result["gate_stats"] = gate_stats
        if curator_stats:
            result["curator_stats"] = curator_stats
        return result
