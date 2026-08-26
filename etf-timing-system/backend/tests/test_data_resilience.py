from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from etf_timing.config import Settings
from etf_timing.data.cache import SQLiteCache
from etf_timing.data.free_etf_provider import (
    FreeEtfProvider,
    parse_sina_quotes,
    parse_tencent_quotes,
)
from etf_timing.data.gateway import DataGateway
from etf_timing.data.mootdx_provider import MootdxProvider
from etf_timing.data.sample_provider import SampleProvider
from etf_timing.services.import_service import ImportService


class FailingProvider(SampleProvider):
    name = "failing-primary"

    def etf_spot(self):
        raise ConnectionError("primary unavailable")


def settings(tmp_path: Path) -> Settings:
    return Settings(data_mode="auto", cache_db=tmp_path / "cache.sqlite3", cors_origins=())


def test_gateway_switches_provider_and_records_source(tmp_path: Path) -> None:
    primary = FailingProvider()
    fallback = SampleProvider()
    gateway = DataGateway(SQLiteCache(tmp_path / "cache.sqlite3"), primary, fallback, "auto")

    dataset = gateway.load(
        key="test:fallback",
        ttl_seconds=60,
        live_loader=primary.etf_spot,
        sample_loader=fallback.etf_spot,
        live_loaders=[
            (primary.name, primary.etf_spot),
            ("real-fallback", fallback.etf_spot),
        ],
    )

    assert dataset.meta["status"] == "live"
    assert dataset.meta["source"] == "real-fallback"
    assert "已切换" in dataset.meta["message"]
    assert gateway.source_health()[primary.name]["failures"] == 1


def test_excel_template_import_is_persisted(tmp_path: Path) -> None:
    cache = SQLiteCache(tmp_path / "cache.sqlite3")
    service = ImportService(cache, settings(tmp_path))

    content = service.template("history")
    result = service.import_file("history.xlsx", content, "history", "510300")

    assert result["rows"] == 1
    imported = cache.get_import("etf:history:510300")
    assert imported[0]["日期"] == "2026-08-24"
    assert cache.get("etf:history:510300").source == "manual-upload/history.xlsx"


def test_mootdx_history_is_normalized(monkeypatch) -> None:
    provider = MootdxProvider()

    class FakeClient:
        closed = False

        def bars(self, **kwargs):
            if kwargs["start"]:
                return pd.DataFrame()
            return pd.DataFrame(
                [
                    {
                        "datetime": "2026-08-22 15:00:00",
                        "open": 4.1,
                        "close": 4.2,
                        "high": 4.3,
                        "low": 4.0,
                        "vol": 100,
                        "amount": 420,
                    },
                    {
                        "datetime": date(2026, 8, 25),
                        "open": 4.2,
                        "close": 4.1,
                        "high": 4.25,
                        "low": 4.05,
                        "vol": 110,
                        "amount": 451,
                    },
                ]
            )

        def close(self):
            self.closed = True

    client = FakeClient()
    monkeypatch.setattr(provider, "_client", lambda server=None: client)

    rows = provider.etf_history("510300", "20260801", "20260825")

    assert len(rows) == 2
    assert rows[1]["日期"] == "2026-08-25"
    assert rows[1]["涨跌幅"] < 0
    assert client.closed is True


def test_sina_quote_payload_is_normalized() -> None:
    payload = (
        'var hq_str_sh510300="沪深300ETF,4.601,4.627,4.616,4.639,4.587,'
        '4.615,4.616,745256800,3435989271.000,0,0,0,0,0,0,0,0,0,0,0,0,'
        '0,0,0,0,0,0,0,0,2026-08-25,15:34:59,00";\n'
    )

    rows = parse_sina_quotes(payload)

    assert rows["510300"]["最新价"] == 4.616
    assert rows["510300"]["成交额"] == 3435989271
    assert rows["510300"]["数据日期"] == "2026-08-25"
    assert rows["510300"]["行情源"] == "新浪财经"


def test_tencent_quote_payload_is_normalized() -> None:
    values = [""] * 40
    values[0] = "1"
    values[1] = "沪深300ETF华泰柏瑞"
    values[2] = "510300"
    values[3] = "4.616"
    values[4] = "4.627"
    values[5] = "4.601"
    values[6] = "7452568"
    values[30] = "20260825161454"
    values[33] = "4.639"
    values[34] = "4.587"
    values[35] = "4.616/7452568/3435989271"
    payload = f'v_sh510300="{"~".join(values)}";\n'

    rows = parse_tencent_quotes(payload)

    assert rows["510300"]["最新价"] == 4.616
    assert rows["510300"]["成交量"] == 745256800
    assert rows["510300"]["成交额"] == 3435989271
    assert rows["510300"]["行情源"] == "腾讯证券"


def test_free_provider_merges_quote_nav_and_exchange_shares(monkeypatch) -> None:
    provider = FreeEtfProvider()
    monkeypatch.setattr(
        provider,
        "_fetch_ths_catalog",
        lambda: [
            {
                "代码": "510300",
                "名称": "沪深300ETF",
                "单位净值": 4.62,
                "净值日期": "2026-08-25",
                "申购状态": "开放",
                "赎回状态": "开放",
            }
        ],
    )
    monkeypatch.setattr(
        provider,
        "_fetch_sina_quotes",
        lambda symbols: {
            symbol: {
                "代码": symbol,
                "名称": "测试ETF",
                "最新价": 4.616,
                "成交额": 3435989271,
                "数据日期": "2026-08-25",
                "行情源": "新浪财经",
            }
            for symbol in symbols
        },
    )
    monkeypatch.setattr(
        provider,
        "_fetch_exchange_shares",
        lambda: {"510300": (9_000_000_000, "2026-08-24")},
    )

    rows = provider.etf_spot()
    row = next(item for item in rows if item["代码"] == "510300")

    assert row["最新价"] == 4.616
    assert row["单位净值"] == 4.62
    assert row["最新份额"] == 9_000_000_000
    assert row["份额日期"] == "2026-08-24"
    assert "IOPV实时估值" not in row


def test_free_provider_sina_history_is_normalized(monkeypatch) -> None:
    provider = FreeEtfProvider()

    class FakeAkshare:
        @staticmethod
        def fund_etf_hist_sina(symbol: str):
            assert symbol == "sh510300"
            return pd.DataFrame(
                [
                    {
                        "date": date(2026, 8, 22),
                        "open": 4.1,
                        "high": 4.3,
                        "low": 4.0,
                        "close": 4.2,
                        "volume": 100,
                        "amount": 420,
                    },
                    {
                        "date": date(2026, 8, 25),
                        "open": 4.2,
                        "high": 4.25,
                        "low": 4.05,
                        "close": 4.1,
                        "volume": 110,
                        "amount": 451,
                    },
                ]
            )

    monkeypatch.setattr(provider, "_ak", lambda: FakeAkshare())

    rows = provider.etf_history("510300", "20260801", "20260825")

    assert len(rows) == 2
    assert rows[1]["日期"] == "2026-08-25"
    assert rows[1]["涨跌幅"] < 0


def test_free_provider_market_and_industry_frames_are_normalized(monkeypatch) -> None:
    provider = FreeEtfProvider()

    class FakeAkshare:
        @staticmethod
        def stock_zh_a_spot():
            return pd.DataFrame(
                [
                    {
                        "代码": "sh600000",
                        "名称": "浦发银行",
                        "最新价": 10.5,
                        "涨跌幅": -1.2,
                        "成交量": 100,
                        "成交额": 1_050,
                    }
                ]
            )

        @staticmethod
        def stock_board_industry_summary_ths():
            return pd.DataFrame(
                [
                    {
                        "序号": 1,
                        "板块": "银行",
                        "涨跌幅": -0.5,
                        "上涨家数": 10,
                        "下跌家数": 20,
                        "领涨股": "浦发银行",
                        "领涨股-涨跌幅": 1.0,
                    }
                ]
            )

    monkeypatch.setattr(provider, "_ak", lambda: FakeAkshare())

    market = provider.market_spot()
    industries = provider.industries()

    assert market[0]["代码"] == "600000"
    assert market[0]["行情源"] == "新浪财经"
    assert industries[0]["板块名称"] == "银行"
    assert industries[0]["上涨家数"] == 10


def test_free_provider_index_history_and_valuation_are_normalized(monkeypatch) -> None:
    provider = FreeEtfProvider()

    class FakeAkshare:
        @staticmethod
        def stock_zh_index_daily(symbol: str):
            assert symbol == "sh000300"
            return pd.DataFrame(
                [
                    {
                        "date": date(2026, 8, 24),
                        "open": 4500,
                        "high": 4600,
                        "low": 4490,
                        "close": 4550,
                        "volume": 100,
                    },
                    {
                        "date": date(2026, 8, 25),
                        "open": 4550,
                        "high": 4570,
                        "low": 4520,
                        "close": 4540,
                        "volume": 110,
                    },
                ]
            )

        @staticmethod
        def stock_zh_index_value_csindex(symbol: str):
            assert symbol == "000300"
            return pd.DataFrame(
                [{"日期": date(2026, 8, 25), "市盈率2": 14.5, "股息率2": 2.3}]
            )

    monkeypatch.setattr(provider, "_ak", lambda: FakeAkshare())

    history = provider.index_history("000300", "20260801", "20260825")
    valuation = provider.index_valuation("000300")

    assert history[-1]["收盘"] == 4540
    assert history[-1]["涨跌幅"] < 0
    assert valuation[0]["市盈率2"] == 14.5
