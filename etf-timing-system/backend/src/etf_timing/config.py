from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    data_mode: str
    cache_db: Path
    cors_origins: tuple[str, ...]
    aktools_base_url: str | None = None
    mootdx_enabled: bool = True
    mootdx_server: str | None = None
    upload_max_bytes: int = 8_000_000
    market_ttl_seconds: int = 300
    etf_spot_ttl_seconds: int = 300
    industry_ttl_seconds: int = 900
    history_ttl_seconds: int = 21_600

    @classmethod
    def from_env(cls) -> Settings:
        mode = os.getenv("ETF_DATA_MODE", "auto").strip().lower()
        if mode not in {"auto", "live", "sample"}:
            raise ValueError("ETF_DATA_MODE must be one of: auto, live, sample")

        cache_path = Path(os.getenv("ETF_CACHE_DB", "backend/data/cache.sqlite3"))
        origins = tuple(
            item.strip()
            for item in os.getenv(
                "ETF_API_CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000,"
                "http://localhost:5173,http://127.0.0.1:5173",
            ).split(",")
            if item.strip()
        )
        aktools_url = os.getenv("ETF_AKTOOLS_BASE_URL", "").strip().rstrip("/") or None
        mootdx_enabled = os.getenv("ETF_MOOTDX_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        mootdx_server = os.getenv("ETF_MOOTDX_SERVER", "").strip() or None
        upload_max_bytes = int(os.getenv("ETF_UPLOAD_MAX_BYTES", "8000000"))
        return cls(
            data_mode=mode,
            cache_db=cache_path,
            cors_origins=origins,
            aktools_base_url=aktools_url,
            mootdx_enabled=mootdx_enabled,
            mootdx_server=mootdx_server,
            upload_max_bytes=upload_max_bytes,
        )
