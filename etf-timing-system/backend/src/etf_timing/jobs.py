from __future__ import annotations

import json
from typing import Any

WATCHLIST = ("510300", "510500", "512100", "588000", "159915", "512880")


def run_daily_refresh() -> dict[str, Any]:
    """InStock-style close-of-day batch: fetch once, persist, then serve cache."""
    from etf_timing.main import etf_service, market_service

    results: dict[str, Any] = {"market": None, "etfs": None, "dashboards": {}}
    try:
        market = market_service.overview(refresh=True)
        results["market"] = market["meta"]["market"]
    except Exception as exc:  # batch continues so one source cannot block all datasets
        results["market"] = {"status": "error", "error": type(exc).__name__}
    try:
        etfs = etf_service.list_etfs(limit=200, refresh=True)
        results["etfs"] = etfs["meta"]
    except Exception as exc:
        results["etfs"] = {"status": "error", "error": type(exc).__name__}
    for symbol in WATCHLIST:
        try:
            dashboard = etf_service.dashboard(symbol, refresh=True)
            results["dashboards"][symbol] = {
                "spot": dashboard["meta"]["spot"],
                "history": dashboard["meta"]["history"],
            }
        except Exception as exc:
            results["dashboards"][symbol] = {
                "status": "error",
                "error": type(exc).__name__,
            }
    return results


def main() -> None:
    print(json.dumps(run_daily_refresh(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
