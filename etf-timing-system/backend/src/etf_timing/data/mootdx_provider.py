from __future__ import annotations

from datetime import date, datetime
from typing import Any

from etf_timing.data.provider import Record

WATCHLIST = {
    "510300": "沪深300ETF",
    "510500": "中证500ETF",
    "512100": "中证1000ETF",
    "588000": "科创50ETF",
    "159915": "创业板ETF",
    "512880": "证券ETF",
}

DEFAULT_SERVERS = (
    ("110.41.147.114", 7709),
    ("124.70.176.52", 7709),
    ("121.36.54.217", 7709),
)


def _value(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row and row[name] is not None:
            value = row[name]
            return value.item() if hasattr(value, "item") else value
    return None


def _date_text(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    return str(value or "")[:10]


class MootdxProvider:
    """TDX fallback for watchlist quotes and unadjusted daily ETF bars."""

    name = "mootdx/tdx-unadjusted"

    def __init__(self, server: str | None = None, timeout_seconds: int = 3) -> None:
        self.server = server
        self.timeout_seconds = timeout_seconds

    def _servers(self) -> tuple[tuple[str, int], ...]:
        if not self.server:
            return DEFAULT_SERVERS
        host, separator, port = self.server.partition(":")
        if not separator or not host or not port.isdigit():
            raise ValueError("ETF_MOOTDX_SERVER must use host:port format")
        return ((host, int(port)),)

    def _client(self, server: tuple[str, int] | None = None) -> Any:
        from mootdx.quotes import Quotes

        selected = server or self._servers()[0]
        kwargs: dict[str, Any] = {
            "market": "std",
            "heartbeat": False,
            "timeout": self.timeout_seconds,
            "server": selected,
        }
        return Quotes.factory(**kwargs)

    def market_spot(self) -> list[Record]:
        raise NotImplementedError("mootdx fallback is intentionally limited to the ETF watchlist")

    def industries(self) -> list[Record]:
        raise NotImplementedError("mootdx does not expose the required industry breadth fields")

    def etf_spot(self) -> list[Record]:
        symbols = list(WATCHLIST)
        raw_rows: list[dict[str, Any]] = []
        errors: list[str] = []
        for server in self._servers():
            client = None
            try:
                client = self._client(server)
                frame = client.quotes(symbol=symbols)
                raw_rows = frame.to_dict(orient="records") if frame is not None else []
                if raw_rows:
                    break
                errors.append(f"{server[0]}:empty")
            except Exception as exc:
                errors.append(f"{server[0]}:{type(exc).__name__}")
            finally:
                if client is not None:
                    client.close()
        if not raw_rows:
            raise ConnectionError(f"No mootdx quote server returned data ({', '.join(errors)})")
        rows: list[Record] = []
        for index, raw in enumerate(raw_rows):
            fallback_symbol = symbols[index] if index < len(symbols) else ""
            symbol = str(_value(raw, "code", "symbol") or fallback_symbol).zfill(6)
            if not symbol.strip("0"):
                continue
            price = _value(raw, "price", "close")
            previous = _value(raw, "last_close", "pre_close")
            change = None
            if price is not None and previous not in {None, 0}:
                change = (float(price) / float(previous) - 1) * 100
            rows.append(
                {
                    "代码": symbol,
                    "名称": WATCHLIST.get(symbol, symbol),
                    "最新价": price,
                    "涨跌幅": change,
                    "成交额": _value(raw, "amount"),
                    "成交量": _value(raw, "vol", "volume"),
                    "数据日期": date.today().isoformat(),
                    "更新时间": datetime.now().astimezone().isoformat(),
                }
            )
        return rows

    def etf_history(self, symbol: str, start_date: str, end_date: str) -> list[Record]:
        collected: dict[str, Record] = {}
        errors: list[str] = []
        for server in self._servers():
            client = None
            try:
                client = self._client(server)
                for start in (0, 800, 1600):
                    frame = client.bars(
                        symbol=str(symbol).zfill(6), frequency=9, start=start, offset=800
                    )
                    raw_rows = frame.to_dict(orient="records") if frame is not None else []
                    if not raw_rows:
                        break
                    for raw in raw_rows:
                        trade_date = _date_text(_value(raw, "datetime", "date"))
                        compact = trade_date.replace("-", "")
                        if start_date <= compact <= end_date:
                            collected[trade_date] = {
                                "日期": trade_date,
                                "开盘": _value(raw, "open"),
                                "收盘": _value(raw, "close"),
                                "最高": _value(raw, "high"),
                                "最低": _value(raw, "low"),
                                "成交量": _value(raw, "vol", "volume"),
                                "成交额": _value(raw, "amount"),
                            }
                    if len(raw_rows) < 800:
                        break
                if collected:
                    break
                errors.append(f"{server[0]}:empty")
            except Exception as exc:
                errors.append(f"{server[0]}:{type(exc).__name__}")
            finally:
                if client is not None:
                    client.close()

        if not collected:
            raise ConnectionError(f"No mootdx history server returned data ({', '.join(errors)})")

        rows = [collected[key] for key in sorted(collected)]
        previous_close: float | None = None
        for row in rows:
            close = float(row["收盘"]) if row.get("收盘") is not None else None
            row["涨跌幅"] = (
                (close / previous_close - 1) * 100
                if close is not None and previous_close not in {None, 0}
                else None
            )
            if close is not None:
                previous_close = close
        return rows
