from __future__ import annotations

import statistics
from datetime import date, timedelta
from functools import partial
from typing import Any

from etf_timing.config import Settings
from etf_timing.data.gateway import DataGateway
from etf_timing.data.provider import MarketDataProvider
from etf_timing.services.indicators import (
    build_indicators,
    number,
    percentile_rank,
    rounded,
)


class MarketService:
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
            if hasattr(provider, method):
                loaders.append((provider.name, partial(getattr(provider, method), *args)))
        return loaders

    def overview(self, refresh: bool = False) -> dict[str, Any]:
        market = self.gateway.load(
            key="market:spot",
            ttl_seconds=self.settings.market_ttl_seconds,
            live_loader=self.live.market_spot,
            sample_loader=self.sample.market_spot,
            refresh=refresh,
            live_loaders=self._loaders("market_spot"),
        )
        industries = self.gateway.load(
            key="market:industries",
            ttl_seconds=self.settings.industry_ttl_seconds,
            live_loader=self.live.industries,
            sample_loader=self.sample.industries,
            refresh=refresh,
            live_loaders=self._loaders("industries"),
        )

        end = date.today()
        start = end - timedelta(days=365 * 6)
        start_date = start.strftime("%Y%m%d")
        end_date = end.strftime("%Y%m%d")
        index_history = self.gateway.load(
            key="market:index:000300:history",
            ttl_seconds=self.settings.history_ttl_seconds,
            live_loader=lambda: self.live.index_history("000300", start_date, end_date),
            sample_loader=lambda: self.sample.etf_history("510300", start_date, end_date),
            refresh=refresh,
            live_loaders=self._loaders("index_history", "000300", start_date, end_date),
        )
        index_valuation = self.gateway.load(
            key="market:index:000300:valuation",
            ttl_seconds=self.settings.history_ttl_seconds,
            live_loader=lambda: self.live.index_valuation("000300"),
            sample_loader=lambda: [{"数据状态": "unavailable"}],
            refresh=refresh,
            live_loaders=self._loaders("index_valuation", "000300"),
        )

        changes = [
            value for row in market.data if (value := number(row.get("涨跌幅"))) is not None
        ]
        turnovers = [
            value for row in market.data if (value := number(row.get("成交额"))) is not None
        ]
        buckets = [
            ("≤ -7%", lambda value: value <= -7),
            ("-7% ~ -5%", lambda value: -7 < value <= -5),
            ("-5% ~ -3%", lambda value: -5 < value <= -3),
            ("-3% ~ 0%", lambda value: -3 < value < 0),
            ("0% ~ 3%", lambda value: 0 <= value < 3),
            ("3% ~ 5%", lambda value: 3 <= value < 5),
            ("5% ~ 7%", lambda value: 5 <= value < 7),
            ("≥ 7%", lambda value: value >= 7),
        ]
        distribution = [
            {"label": label, "count": sum(1 for change in changes if predicate(change))}
            for label, predicate in buckets
        ]

        normalized_industries = []
        for row in industries.data:
            normalized_industries.append(
                {
                    "code": row.get("板块代码"),
                    "name": row.get("板块名称"),
                    "changePct": rounded(number(row.get("涨跌幅"))),
                    "advancers": int(number(row.get("上涨家数")) or 0),
                    "decliners": int(number(row.get("下跌家数")) or 0),
                    "turnoverRatePct": rounded(number(row.get("换手率"))),
                    "leader": row.get("领涨股票"),
                    "leaderChangePct": rounded(number(row.get("领涨股票-涨跌幅"))),
                }
            )
        normalized_industries.sort(
            key=lambda row: row["changePct"] if row["changePct"] is not None else -999,
            reverse=True,
        )

        index_core = build_indicators(index_history.data)
        valuation_rows = [
            row
            for row in index_valuation.data
            if number(row.get("市盈率2") or row.get("市盈率1")) is not None
        ]
        valuation_rows.sort(key=lambda row: str(row.get("日期")), reverse=True)
        latest_valuation = valuation_rows[0] if valuation_rows else {}
        pe_values = [
            value
            for row in valuation_rows
            if (value := number(row.get("市盈率2") or row.get("市盈率1"))) is not None
        ]
        latest_pe = pe_values[0] if pe_values else None

        return {
            "summary": {
                "totalCount": len(changes),
                "advancers": sum(1 for value in changes if value > 0),
                "decliners": sum(1 for value in changes if value < 0),
                "flat": sum(1 for value in changes if value == 0),
                "medianChangePct": rounded(statistics.median(changes) if changes else None),
                "turnoverAmount": rounded(sum(turnovers), 0),
                "downMoreThan5Pct": sum(1 for value in changes if value <= -5),
                "upMoreThan5Pct": sum(1 for value in changes if value >= 5),
            },
            "distribution": distribution,
            "industries": {
                "leaders": normalized_industries[:6],
                "laggards": list(reversed(normalized_industries[-6:])),
                "all": normalized_industries,
            },
            "breadthHistory": {
                "availability": "not_collected",
                "message": "MA20/60/120 市场宽度需要全 A 逐日历史底座，本阶段不做高并发临时抓取。",
            },
            "index": {
                "symbol": "000300",
                "name": "沪深300指数",
                "close": index_core.get("history", [{}])[-1].get("close")
                if index_core.get("history")
                else None,
                "core": index_core,
                "valuation": {
                    "date": str(latest_valuation.get("日期") or "")[:10] or None,
                    "peTtm": rounded(latest_pe),
                    "peRecentPercentile": rounded(
                        percentile_rank(pe_values, latest_pe)
                        if latest_pe is not None
                        else None
                    ),
                    "peObservations": len(pe_values),
                    "dividendYieldPct": rounded(
                        number(latest_valuation.get("股息率2") or latest_valuation.get("股息率1"))
                    ),
                },
            },
            "meta": {
                "market": market.meta,
                "industries": industries.meta,
                "indexHistory": index_history.meta,
                "indexValuation": index_valuation.meta,
            },
        }
