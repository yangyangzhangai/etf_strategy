from __future__ import annotations

from typing import Any, Protocol

Record = dict[str, Any]


class MarketDataProvider(Protocol):
    name: str

    def market_spot(self) -> list[Record]: ...

    def industries(self) -> list[Record]: ...

    def etf_spot(self) -> list[Record]: ...

    def etf_history(self, symbol: str, start_date: str, end_date: str) -> list[Record]: ...

