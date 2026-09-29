"""Vercel FastAPI service entrypoint.

The production function filesystem is read-only except for ``/tmp``.  Keep the
SQLite cache there and disable the raw-TCP TongdaXin fallback in serverless
deployments.  Local development continues to use ``etf_timing.main:app``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import gettempdir


def _load_app():
    # Vercel installs third-party dependencies from pyproject.toml, but does not
    # install this service's own ``src``-layout package into site-packages.
    # Add it explicitly so the serverless entrypoint can import etf_timing.
    source_dir = Path(__file__).resolve().parent / "src"
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))

    scratch_db = Path(gettempdir()) / "etf-timing" / "cache.sqlite3"
    os.environ.setdefault("ETF_CACHE_DB", str(scratch_db))
    os.environ.setdefault("ETF_MOOTDX_ENABLED", "false")

    from etf_timing.main import app

    return app


app = _load_app()
