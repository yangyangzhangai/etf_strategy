from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from etf_timing.config import Settings
from etf_timing.data.gateway import DataGateway, Dataset
from etf_timing.data.provider import MarketDataProvider
from etf_timing.services.indicators import build_indicators, number, rounded


class ETFService:
    def __init__(
        self,
        gateway: DataGateway,
        live_provider: MarketDataProvider,
        sample_provider: MarketDataProvider,
        settings: Settings,
        extra_live_providers: tuple[MarketDataProvider, ...] = (),
    ) -> None:
        self.gateway = gateway
        self.live = live_provider
        self.sample = sample_provider
        self.settings = settings
        self.live_providers = (live_provider, *extra_live_providers)

    def _loaders(self, method: str, *args: str) -> list[tuple[str, Any]]:
        loaders: list[tuple[str, Any]] = []
        for provider in self.live_providers:
            loader = getattr(provider, method)
            loaders.append((provider.name, lambda loader=loader, args=args: loader(*args)))
        return loaders

    def _manual_loader(self, key: str) -> list[dict[str, Any]]:
        return self.gateway.cache.get_import(key)

    def _spot(self, refresh: bool = False) -> Dataset:
        dataset = self.gateway.load(
            key="etf:spot",
            ttl_seconds=self.settings.etf_spot_ttl_seconds,
            live_loader=self.live.etf_spot,
            sample_loader=self.sample.etf_spot,
            refresh=refresh,
            live_loaders=[
                *self._loaders("etf_spot"),
                ("manual-upload", lambda: self._manual_loader("etf:spot")),
            ],
        )
        self.gateway.cache.record_etf_spot(dataset.data, dataset.meta["source"])
        return dataset

    def _history(self, symbol: str, refresh: bool = False) -> Dataset:
        end = date.today()
        start = end - timedelta(days=365 * 6)
        start_date = start.strftime("%Y%m%d")
        end_date = end.strftime("%Y%m%d")
        return self.gateway.load(
            key=f"etf:history:{symbol}",
            ttl_seconds=self.settings.history_ttl_seconds,
            live_loader=lambda: self.live.etf_history(symbol, start_date, end_date),
            sample_loader=lambda: self.sample.etf_history(symbol, start_date, end_date),
            refresh=refresh,
            live_loaders=[
                *self._loaders("etf_history", symbol, start_date, end_date),
                (
                    "manual-upload",
                    lambda: self._manual_loader(f"etf:history:{symbol}"),
                ),
            ],
        )

    @staticmethod
    def _spot_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "symbol": str(row.get("代码") or "").zfill(6),
            "name": row.get("名称"),
            "price": rounded(number(row.get("最新价")), 4),
            "changePct": rounded(number(row.get("涨跌幅"))),
            "iopv": rounded(number(row.get("IOPV实时估值")), 4),
            "nav": rounded(number(row.get("单位净值")), 4),
            "navDate": str(row.get("净值日期") or "")[:10] or None,
            "discountRatePct": rounded(number(row.get("基金折价率"))),
            "turnoverAmount": rounded(number(row.get("成交额")), 0),
            "turnoverRatePct": rounded(number(row.get("换手率"))),
            "latestShares": rounded(number(row.get("最新份额")), 0),
            "mainNetInflow": rounded(number(row.get("主力净流入-净额")), 0),
            "dataDate": str(row.get("数据日期") or "")[:10] or None,
            "updatedAt": row.get("更新时间"),
            "subscriptionStatus": row.get("申购状态"),
            "redemptionStatus": row.get("赎回状态"),
            "shareDate": str(row.get("份额日期") or "")[:10] or None,
            "quoteSource": row.get("行情源"),
        }

    def list_etfs(self, query: str = "", limit: int = 50, refresh: bool = False) -> dict[str, Any]:
        dataset = self._spot(refresh)
        normalized = [self._spot_row(row) for row in dataset.data]
        if query:
            needle = query.strip().lower()
            normalized = [
                row
                for row in normalized
                if needle in row["symbol"].lower() or needle in str(row["name"]).lower()
            ]
        normalized.sort(
            key=lambda row: row["turnoverAmount"] if row["turnoverAmount"] is not None else -1,
            reverse=True,
        )
        return {"items": normalized[:limit], "total": len(normalized), "meta": dataset.meta}

    @staticmethod
    def _share_change(history: list[dict[str, Any]], offset: int) -> float | None:
        if len(history) <= offset:
            return None
        latest = number(history[0].get("shares"))
        previous = number(history[offset].get("shares"))
        if latest is None or previous in {None, 0}:
            return None
        return (latest / previous - 1) * 100

    def dashboard(self, symbol: str, refresh: bool = False) -> dict[str, Any]:
        symbol = symbol.zfill(6)
        spot_dataset = self._spot(refresh)
        spot_raw = next(
            (row for row in spot_dataset.data if str(row.get("代码") or "").zfill(6) == symbol),
            None,
        )
        if spot_raw is None:
            raise LookupError(f"ETF {symbol} not found")

        history_dataset = self._history(symbol, refresh)
        benchmark_dataset = (
            history_dataset if symbol == "510300" else self._history("510300", refresh=False)
        )
        indicators = build_indicators(history_dataset.data, benchmark_dataset.data)
        share_history = self.gateway.cache.share_history(symbol, limit=30)

        return {
            "etf": self._spot_row(spot_raw),
            "core": indicators,
            "capital": {
                "latestShares": rounded(number(spot_raw.get("最新份额")), 0),
                "shareChange1dPct": rounded(self._share_change(share_history, 1)),
                "shareChange5dPct": rounded(self._share_change(share_history, 5)),
                "shareChange20dPct": rounded(self._share_change(share_history, 20)),
                "discountRatePct": rounded(number(spot_raw.get("基金折价率"))),
                "mainNetInflow": rounded(number(spot_raw.get("主力净流入-净额")), 0),
                "snapshotsAvailable": len(share_history),
                "history": share_history,
            },
            "internalBreadth": {
                "availability": "not_collected",
                "ma20AbovePct": None,
                "ma60AbovePct": None,
                "ma120AbovePct": None,
                "newLow20Pct": None,
                "message": "需要指数逐日成分股与成分股历史底座；本阶段不伪造该数据。",
            },
            "meta": {
                "spot": spot_dataset.meta,
                "history": history_dataset.meta,
                "benchmark": benchmark_dataset.meta,
            },
        }

    def history(self, symbol: str, refresh: bool = False) -> dict[str, Any]:
        dataset = self._history(symbol.zfill(6), refresh)
        return {"symbol": symbol.zfill(6), "items": dataset.data, "meta": dataset.meta}
