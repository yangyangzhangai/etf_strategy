"""Vercel FastAPI service entrypoint.

The production function filesystem is read-only except for ``/tmp``.  Keep the
SQLite cache there and disable the raw-TCP TongdaXin fallback in serverless
deployments.  Local development continues to use ``etf_timing.main:app``.
"""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import gettempdir


def _load_app():
    scratch_db = Path(gettempdir()) / "etf-timing" / "cache.sqlite3"
    os.environ.setdefault("ETF_CACHE_DB", str(scratch_db))
    os.environ.setdefault("ETF_MOOTDX_ENABLED", "false")

    from etf_timing.main import app

    return app


app = _load_app()
