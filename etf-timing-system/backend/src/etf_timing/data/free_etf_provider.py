from __future__ import annotations

import re
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Any
from urllib.request import Request, urlopen

from etf_timing.data.akshare_provider import _scalar, _timed_call
from etf_timing.data.provider import Record

CORE_ETFS = {
    "510300": "沪深300ETF",
    "510500": "中证500ETF",
    "512100": "中证1000ETF",
    "588000": "科创50ETF",
    "159915": "创业板ETF",
    "512880": "证券ETF",
}

SINA_QUOTE_URL = "https://hq.sinajs.cn/list={}"
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q={}"
SSE_SCALE_URL = "https://query.sse.com.cn/commonQuery.do"
SZSE_SCALE_URL = "https://fund.szse.cn/api/report/ShowReport"
QUOTE_PATTERN = re.compile(r'^var hq_str_(?:sh|sz)(\d{6})="(.*)";$')


def _number(value: Any) -> float | None:
    try:
        result = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return result


def _market_symbol(symbol: str) -> str:
    symbol = str(symbol).zfill(6)
    return f"{'sh' if symbol.startswith('5') else 'sz'}{symbol}"


def _iso_timestamp(trade_date: str, trade_time: str) -> str | None:
    if not trade_date:
        return None
    try:
        return datetime.fromisoformat(f"{trade_date}T{trade_time}+08:00").isoformat()
    except ValueError:
        return trade_date


def parse_sina_quotes(payload: str) -> dict[str, Record]:
    """Parse Sina's documented quote wire format into canonical raw fields."""
    quotes: dict[str, Record] = {}
    for line in payload.splitlines():
        matched = QUOTE_PATTERN.match(line.strip())
        if not matched:
            continue
        symbol, raw_values = matched.groups()
        values = raw_values.split(",")
        if len(values) < 32 or not values[0]:
            continue
        previous_close = _number(values[2])
        price = _number(values[3])
        change_pct = None
        if price is not None and previous_close not in {None, 0}:
            change_pct = (price / previous_close - 1) * 100
        trade_date, trade_time = values[30], values[31]
        quotes[symbol] = {
            "代码": symbol,
            "名称": values[0],
            "开盘": _number(values[1]),
            "昨收": previous_close,
            "最新价": price,
            "最高": _number(values[4]),
            "最低": _number(values[5]),
            "涨跌幅": change_pct,
            "成交量": _number(values[8]),
            "成交额": _number(values[9]),
            "数据日期": trade_date,
            "更新时间": _iso_timestamp(trade_date, trade_time),
            "行情源": "新浪财经",
        }
    return quotes


def parse_tencent_quotes(payload: str) -> dict[str, Record]:
    quotes: dict[str, Record] = {}
    for line in payload.splitlines():
        if '="' not in line:
            continue
        values = line.split('="', 1)[1].rsplit('"', 1)[0].split("~")
        if len(values) < 38 or not values[1] or not values[2]:
            continue
        symbol = values[2].zfill(6)
        price = _number(values[3])
        previous_close = _number(values[4])
        change_pct = None
        if price is not None and previous_close not in {None, 0}:
            change_pct = (price / previous_close - 1) * 100
        timestamp = values[30]
        trade_date = (
            f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
            if len(timestamp) >= 8
            else ""
        )
        trade_time = (
            f"{timestamp[8:10]}:{timestamp[10:12]}:{timestamp[12:14]}"
            if len(timestamp) >= 14
            else ""
        )
        volume = _number(values[6])
        amount_parts = values[35].split("/") if len(values) > 35 else []
        quotes[symbol] = {
            "代码": symbol,
            "名称": values[1],
            "开盘": _number(values[5]),
            "昨收": previous_close,
            "最新价": price,
            "最高": _number(values[33]),
            "最低": _number(values[34]),
            "涨跌幅": change_pct,
            "成交量": volume * 100 if volume is not None else None,
            "成交额": _number(amount_parts[2]) if len(amount_parts) >= 3 else None,
            "数据日期": trade_date,
            "更新时间": _iso_timestamp(trade_date, trade_time),
            "行情源": "腾讯证券",
        }
    return quotes


class FreeEtfProvider:
    """No-key ETF stack: Sina quotes/history, THS NAV, SSE/SZSE shares."""

    name = "free/sina-tencent+ths+sse-szse"

    @staticmethod
    def _ak() -> Any:
        import akshare as ak

        return ak

    @staticmethod
    def _requests() -> Any:
        import requests

        return requests

    def market_spot(self) -> list[Record]:
        try:
            frame = _timed_call(lambda: self._ak().stock_zh_a_spot(), 35)
            source = "新浪财经"
        except Exception:
            frame = _timed_call(lambda: self._ak().stock_zh_a_spot_tx(), 35)
            source = "腾讯证券"

        rows: list[Record] = []
        for raw in frame.to_dict(orient="records"):
            if source == "新浪财经":
                code = str(raw.get("代码") or "")
                if code[:2].isalpha():
                    code = code[2:]
                rows.append(
                    {
                        "代码": code.zfill(6),
                        "名称": _scalar(raw.get("名称")),
                        "最新价": _scalar(raw.get("最新价")),
                        "涨跌幅": _scalar(raw.get("涨跌幅")),
                        "成交量": _scalar(raw.get("成交量")),
                        "成交额": _scalar(raw.get("成交额")),
                        "行情源": source,
                    }
                )
            else:
                code = str(raw.get("code") or "")
                if code[:2].isalpha():
                    code = code[2:]
                turnover_wan = _number(raw.get("turnover"))
                rows.append(
                    {
                        "代码": code.zfill(6),
                        "名称": _scalar(raw.get("name")),
                        "最新价": _number(raw.get("zxj")),
                        "涨跌幅": _number(raw.get("zdf")),
                        "成交量": _number(raw.get("volume")),
                        "成交额": turnover_wan * 10_000 if turnover_wan is not None else None,
                        "行情源": source,
                    }
                )
        return rows

    def industries(self) -> list[Record]:
        frame = _timed_call(lambda: self._ak().stock_board_industry_summary_ths(), 15)
        rows: list[Record] = []
        for raw in frame.to_dict(orient="records"):
            rows.append(
                {
                    "板块代码": str(raw.get("序号") or ""),
                    "板块名称": _scalar(raw.get("板块")),
                    "涨跌幅": _scalar(raw.get("涨跌幅")),
                    "上涨家数": _scalar(raw.get("上涨家数")),
                    "下跌家数": _scalar(raw.get("下跌家数")),
                    "领涨股票": _scalar(raw.get("领涨股")),
                    "领涨股票-涨跌幅": _scalar(raw.get("领涨股-涨跌幅")),
                    "行业源": "同花顺",
                }
            )
        return rows

    def index_history(self, symbol: str, start_date: str, end_date: str) -> list[Record]:
        exchange_symbol = "sz399006" if symbol == "399006" else f"sh{symbol.zfill(6)}"
        try:
            frame = _timed_call(
                lambda: self._ak().stock_zh_index_daily(symbol=exchange_symbol), 20
            )
            amount_column = "volume"
        except Exception:
            frame = _timed_call(
                lambda: self._ak().stock_zh_index_daily_tx(symbol=exchange_symbol), 20
            )
            amount_column = "amount"

        rows: list[Record] = []
        for raw in sorted(
            frame.to_dict(orient="records"), key=lambda item: str(item.get("date"))
        ):
            trade_date = str(_scalar(raw.get("date")) or "")[:10]
            compact = trade_date.replace("-", "")
            if start_date <= compact <= end_date:
                rows.append(
                    {
                        "日期": trade_date,
                        "开盘": _number(raw.get("open")),
                        "收盘": _number(raw.get("close")),
                        "最高": _number(raw.get("high")),
                        "最低": _number(raw.get("low")),
                        "成交量": _number(raw.get(amount_column)),
                        "成交额": None,
                    }
                )
        previous_close: float | None = None
        for row in rows:
            close = _number(row.get("收盘"))
            row["涨跌幅"] = (
                (close / previous_close - 1) * 100
                if close is not None and previous_close not in {None, 0}
                else None
            )
            if close is not None:
                previous_close = close
        return rows

    def index_valuation(self, symbol: str) -> list[Record]:
        frame = _timed_call(
            lambda: self._ak().stock_zh_index_value_csindex(symbol=symbol.zfill(6)), 15
        )
        return [
            {str(key): _scalar(value) for key, value in raw.items()}
            for raw in frame.to_dict(orient="records")
        ]

    def _fetch_ths_catalog(self) -> list[Record]:
        frame = _timed_call(lambda: self._ak().fund_etf_spot_ths(), 20)
        records: list[Record] = []
        for raw in frame.to_dict(orient="records"):
            symbol = str(raw.get("基金代码") or "").split(".")[0].zfill(6)
            if not symbol.strip("0"):
                continue
            records.append(
                {
                    "代码": symbol,
                    "名称": _scalar(raw.get("基金名称")) or CORE_ETFS.get(symbol, symbol),
                    "单位净值": _scalar(raw.get("当前-单位净值")),
                    "净值日期": _scalar(raw.get("最新-交易日")),
                    "申购状态": _scalar(raw.get("申购状态")),
                    "赎回状态": _scalar(raw.get("赎回状态")),
                    "基金类型": _scalar(raw.get("基金类型")),
                }
            )
        return records

    @staticmethod
    def _fallback_catalog() -> list[Record]:
        return [{"代码": symbol, "名称": name} for symbol, name in CORE_ETFS.items()]

    @staticmethod
    def _sina_quote_chunk(symbols: list[str]) -> dict[str, Record]:
        query = ",".join(_market_symbol(symbol) for symbol in symbols)
        request = Request(
            SINA_QUOTE_URL.format(query),
            headers={
                "Referer": "https://finance.sina.com.cn/",
                "User-Agent": "Mozilla/5.0 (compatible; ETF-Timing-Dashboard/0.3)",
            },
        )
        with urlopen(request, timeout=12) as response:
            payload = response.read().decode("gbk", errors="replace")
        return parse_sina_quotes(payload)

    @staticmethod
    def _tencent_quote_chunk(symbols: list[str]) -> dict[str, Record]:
        query = ",".join(_market_symbol(symbol) for symbol in symbols)
        request = Request(
            TENCENT_QUOTE_URL.format(query),
            headers={"User-Agent": "Mozilla/5.0 (compatible; ETF-Timing-Dashboard/0.3)"},
        )
        with urlopen(request, timeout=12) as response:
            payload = response.read().decode("gbk", errors="replace")
        return parse_tencent_quotes(payload)

    @staticmethod
    def _chunks(symbols: list[str]) -> list[list[str]]:
        return [symbols[index : index + 150] for index in range(0, len(symbols), 150)]

    def _fetch_sina_quotes(self, symbols: list[str]) -> dict[str, Record]:
        chunks = self._chunks(symbols)
        quotes: dict[str, Record] = {}
        errors: list[Exception] = []
        with ThreadPoolExecutor(max_workers=min(4, len(chunks) or 1)) as executor:
            futures = [executor.submit(self._sina_quote_chunk, chunk) for chunk in chunks]
            for future in as_completed(futures):
                try:
                    quotes.update(future.result())
                except Exception as exc:
                    errors.append(exc)
        missing = [symbol for symbol in symbols if symbol not in quotes]
        fallback_chunks = self._chunks(missing)
        if fallback_chunks:
            with ThreadPoolExecutor(max_workers=min(4, len(fallback_chunks))) as executor:
                futures = [
                    executor.submit(self._tencent_quote_chunk, chunk)
                    for chunk in fallback_chunks
                ]
                for future in as_completed(futures):
                    try:
                        quotes.update(future.result())
                    except Exception as exc:
                        errors.append(exc)
        if not quotes:
            error_name = type(errors[-1]).__name__ if errors else "EmptyResponse"
            raise ConnectionError(f"Sina returned no ETF quotes ({error_name})")
        return quotes

    def _fetch_sse_shares(self) -> dict[str, tuple[float, str]]:
        requests = self._requests()
        headers = {
            "Referer": "https://www.sse.com.cn/",
            "User-Agent": "Mozilla/5.0 (compatible; ETF-Timing-Dashboard/0.3)",
        }
        params = {
            "isPagination": "true",
            "pageHelp.pageSize": "10000",
            "pageHelp.pageNo": "1",
            "pageHelp.beginPage": "1",
            "pageHelp.cacheSize": "1",
            "pageHelp.endPage": "1",
            "sqlId": "COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L",
        }
        rows: list[dict[str, Any]] = []
        for days_back in range(10):
            stat_date = date.today() - timedelta(days=days_back)
            params["STAT_DATE"] = stat_date.isoformat()
            response = requests.get(SSE_SCALE_URL, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            rows = response.json().get("result") or []
            if rows:
                break
        result: dict[str, tuple[float, str]] = {}
        for row in rows:
            shares = _number(row.get("TOT_VOL"))
            symbol = str(row.get("SEC_CODE") or "").zfill(6)
            if shares is not None and symbol.strip("0"):
                result[symbol] = (shares * 10_000, str(row.get("STAT_DATE") or "")[:10])
        return result

    def _fetch_szse_shares(self) -> dict[str, tuple[float, str]]:
        requests = self._requests()
        response = requests.get(
            SZSE_SCALE_URL,
            params={"SHOWTYPE": "xlsx", "CATALOGID": "1000_lf", "TABKEY": "tab1"},
            headers={
                "Referer": "https://fund.szse.cn/marketdata/fundslist/index.html",
                "User-Agent": "Mozilla/5.0 (compatible; ETF-Timing-Dashboard/0.3)",
            },
            timeout=20,
        )
        response.raise_for_status()
        import pandas as pd

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            frame = pd.read_excel(
                BytesIO(response.content), engine="openpyxl", dtype={"基金代码": str}
            )
        share_column = "当前规模(份)" if "当前规模(份)" in frame.columns else "基金份额"
        result: dict[str, tuple[float, str]] = {}
        for row in frame.to_dict(orient="records"):
            symbol = str(row.get("基金代码") or "").split(".")[0].zfill(6)
            shares = _number(row.get(share_column))
            if shares is not None and symbol.strip("0"):
                result[symbol] = (shares, date.today().isoformat())
        return result

    def _fetch_exchange_shares(self) -> dict[str, tuple[float, str]]:
        shares: dict[str, tuple[float, str]] = {}
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self._fetch_sse_shares),
                executor.submit(self._fetch_szse_shares),
            ]
            for future in as_completed(futures):
                try:
                    shares.update(future.result())
                except Exception:
                    # Quotes remain useful when an exchange disclosure is temporarily unavailable.
                    continue
        return shares

    def etf_spot(self) -> list[Record]:
        try:
            catalog = self._fetch_ths_catalog()
        except Exception:
            catalog = self._fallback_catalog()

        catalog_by_symbol = {str(row["代码"]): dict(row) for row in catalog}
        for symbol, name in CORE_ETFS.items():
            catalog_by_symbol.setdefault(symbol, {"代码": symbol, "名称": name})

        symbols = list(catalog_by_symbol)
        with ThreadPoolExecutor(max_workers=2) as executor:
            quote_future = executor.submit(self._fetch_sina_quotes, symbols)
            share_future = executor.submit(self._fetch_exchange_shares)
            quotes = quote_future.result()
            shares = share_future.result()

        rows: list[Record] = []
        for symbol, catalog_row in catalog_by_symbol.items():
            quote = quotes.get(symbol)
            if quote is None:
                continue
            row = {**catalog_row, **quote}
            if symbol in shares:
                row["最新份额"], row["份额日期"] = shares[symbol]
            rows.append(row)
        return rows

    def etf_history(self, symbol: str, start_date: str, end_date: str) -> list[Record]:
        market_symbol = _market_symbol(symbol)
        frame = _timed_call(lambda: self._ak().fund_etf_hist_sina(symbol=market_symbol), 20)
        rows: list[Record] = []
        previous_close: float | None = None
        raw_rows = sorted(frame.to_dict(orient="records"), key=lambda row: str(row.get("date")))
        for raw in raw_rows:
            trade_date = str(_scalar(raw.get("date")) or "")[:10]
            compact = trade_date.replace("-", "")
            if not (start_date <= compact <= end_date):
                continue
            close = _number(raw.get("close"))
            change_pct = None
            if close is not None and previous_close not in {None, 0}:
                change_pct = (close / previous_close - 1) * 100
            rows.append(
                {
                    "日期": trade_date,
                    "开盘": _number(raw.get("open")),
                    "收盘": close,
                    "最高": _number(raw.get("high")),
                    "最低": _number(raw.get("low")),
                    "成交量": _number(raw.get("volume")),
                    "成交额": _number(raw.get("amount")),
                    "涨跌幅": change_pct,
                }
            )
            if close is not None:
                previous_close = close
        return rows
