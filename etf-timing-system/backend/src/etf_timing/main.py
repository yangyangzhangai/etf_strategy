from __future__ import annotations

import importlib.util
from io import BytesIO
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from etf_timing.config import Settings
from etf_timing.data.akshare_provider import AkshareProvider
from etf_timing.data.aktools_provider import AktoolsProvider
from etf_timing.data.cache import SQLiteCache
from etf_timing.data.free_etf_provider import FreeEtfProvider
from etf_timing.data.gateway import DataGateway
from etf_timing.data.mootdx_provider import MootdxProvider
from etf_timing.data.sample_provider import SampleProvider
from etf_timing.services.etf_service import ETFService
from etf_timing.services.import_service import ImportService
from etf_timing.services.market_service import MarketService

settings = Settings.from_env()
cache = SQLiteCache(settings.cache_db)
free_provider = FreeEtfProvider()
eastmoney_provider = AkshareProvider()
sample_provider = SampleProvider()
aktools_provider = AktoolsProvider(settings.aktools_base_url) if settings.aktools_base_url else None
mootdx_provider = MootdxProvider(settings.mootdx_server) if settings.mootdx_enabled else None
gateway = DataGateway(cache, free_provider, sample_provider, settings.data_mode)
market_extras = tuple(
    provider for provider in (eastmoney_provider, aktools_provider) if provider is not None
)
etf_extras = tuple(
    provider
    for provider in (eastmoney_provider, aktools_provider, mootdx_provider)
    if provider is not None
)
market_service = MarketService(
    gateway, free_provider, sample_provider, settings, extra_live_providers=market_extras
)
etf_service = ETFService(
    gateway, free_provider, sample_provider, settings, extra_live_providers=etf_extras
)
import_service = ImportService(cache, settings)

app = FastAPI(
    title="ETF Timing Data API",
    version="0.3.0",
    description="Data collection and display only. No scores, forecasts or trade signals.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health() -> dict:
    return {
        "status": "ok",
        "dataMode": settings.data_mode,
        "version": "0.3.0",
        "providers": {
            "freeData": {
                "enabled": True,
                "role": "market-etf-primary",
                "components": [
                    "sina-tencent-quotes-history",
                    "ths-nav-industries",
                    "sse-szse-shares",
                ],
            },
            "akshare": {"enabled": True, "role": "eastmoney-fallback"},
            "aktools": {"enabled": aktools_provider is not None, "role": "optional-http"},
            "mootdx": {
                "enabled": settings.mootdx_enabled,
                "installed": importlib.util.find_spec("mootdx") is not None,
                "role": "etf-fallback",
            },
            "manualUpload": {"enabled": True, "role": "last-resort"},
        },
        "sourceActivity": gateway.source_health(),
        "imports": cache.list_imports(),
    }


@app.get("/api/v1/market/overview")
def market_overview(refresh: bool = False) -> dict:
    return market_service.overview(refresh=refresh)


@app.get("/api/v1/etfs")
def list_etfs(
    query: str = "",
    limit: int = Query(default=50, ge=1, le=200),
    refresh: bool = False,
) -> dict:
    return etf_service.list_etfs(query=query, limit=limit, refresh=refresh)


@app.get("/api/v1/etfs/{symbol}/dashboard")
def etf_dashboard(symbol: str, refresh: bool = False) -> dict:
    if not symbol.isdigit() or len(symbol) > 6:
        raise HTTPException(status_code=422, detail="ETF symbol must be a numeric code")
    try:
        return etf_service.dashboard(symbol, refresh=refresh)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/etfs/{symbol}/history")
def etf_history(symbol: str, refresh: bool = False) -> dict:
    if not symbol.isdigit() or len(symbol) > 6:
        raise HTTPException(status_code=422, detail="ETF symbol must be a numeric code")
    return etf_service.history(symbol, refresh=refresh)


@app.post("/api/v1/imports/etf")
async def import_etf_file(
    file: Annotated[UploadFile, File()],
    dataset: Annotated[str, Form()] = "history",
    symbol: Annotated[str, Form()] = "510300",
) -> dict:
    if not symbol.isdigit() or len(symbol) > 6:
        raise HTTPException(status_code=422, detail="ETF symbol must be a numeric code")
    content = await file.read(settings.upload_max_bytes + 1)
    try:
        return import_service.import_file(file.filename or "upload.xlsx", content, dataset, symbol)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/imports/template")
def import_template(dataset: str = Query(default="history", pattern="^(history|spot)$")):
    try:
        content = import_service.template(dataset)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    filename = f"etf-{dataset}-template.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
