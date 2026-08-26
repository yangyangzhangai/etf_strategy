from pathlib import Path

from etf_timing.config import Settings
from etf_timing.data.cache import SQLiteCache
from etf_timing.data.gateway import DataGateway
from etf_timing.data.sample_provider import SampleProvider
from etf_timing.services.etf_service import ETFService
from etf_timing.services.market_service import MarketService


def build_services(tmp_path: Path) -> tuple[MarketService, ETFService]:
    settings = Settings(data_mode="sample", cache_db=tmp_path / "cache.sqlite3", cors_origins=())
    provider = SampleProvider()
    gateway = DataGateway(SQLiteCache(settings.cache_db), provider, provider, "sample")
    return (
        MarketService(gateway, provider, provider, settings),
        ETFService(gateway, provider, provider, settings),
    )


def test_market_overview_is_raw_and_traceable(tmp_path: Path) -> None:
    market, _ = build_services(tmp_path)

    result = market.overview()

    assert result["summary"]["totalCount"] == 600
    counted = (
        result["summary"]["advancers"]
        + result["summary"]["decliners"]
        + result["summary"]["flat"]
    )
    assert counted == 600
    assert len(result["distribution"]) == 8
    assert result["breadthHistory"]["availability"] == "not_collected"
    assert result["meta"]["market"]["status"] == "sample"
    assert result["index"]["symbol"] == "000300"
    assert result["index"]["core"]["availability"] == "available"


def test_etf_dashboard_contains_no_score_or_forecast(tmp_path: Path) -> None:
    _, etfs = build_services(tmp_path)

    result = etfs.dashboard("510300")

    assert result["etf"]["symbol"] == "510300"
    assert result["core"]["drawdownPercentile"] is not None
    assert result["internalBreadth"]["availability"] == "not_collected"
    assert "score" not in result
    assert "forecast" not in result
