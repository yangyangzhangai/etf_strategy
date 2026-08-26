from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from etf_timing.data.provider import Record


class AktoolsProvider:
    """Optional HTTP adapter for a separately deployed AKTools service."""

    name = "aktools/akshare"

    def __init__(self, base_url: str, timeout_seconds: float = 35) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _call(self, function: str, **params: str) -> list[Record]:
        query = urlencode(params)
        url = f"{self.base_url}/api/public/{function}"
        if query:
            url = f"{url}?{query}"
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "ETF-Timing/0.2"},
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            payload: Any = json.load(response)
        if not isinstance(payload, list):
            raise ValueError(f"AKTools returned a non-list payload for {function}")
        return [{str(key): value for key, value in row.items()} for row in payload]

    def market_spot(self) -> list[Record]:
        return self._call("stock_zh_a_spot_em")

    def industries(self) -> list[Record]:
        return self._call("stock_board_industry_name_em")

    def etf_spot(self) -> list[Record]:
        return self._call("fund_etf_spot_em")

    def etf_history(self, symbol: str, start_date: str, end_date: str) -> list[Record]:
        return self._call(
            "fund_etf_hist_em",
            symbol=str(symbol).zfill(6),
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
