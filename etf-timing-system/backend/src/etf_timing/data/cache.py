from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")


def now_shanghai() -> datetime:
    return datetime.now(tz=SHANGHAI)


@dataclass(frozen=True, slots=True)
class CacheRecord:
    payload: Any
    fetched_at: datetime
    expires_at: datetime
    source: str

    @property
    def is_fresh(self) -> bool:
        return self.expires_at >= now_shanghai()


class SQLiteCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    source TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS etf_share_snapshots (
                    symbol TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    shares REAL,
                    price REAL,
                    discount_rate REAL,
                    source TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY (symbol, trade_date)
                );

                CREATE TABLE IF NOT EXISTS imported_datasets (
                    dataset_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    row_count INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_etf_share_snapshots_symbol_date
                ON etf_share_snapshots(symbol, trade_date DESC);
                """
            )
            self._connection.execute("PRAGMA optimize")

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def get(self, key: str) -> CacheRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload, fetched_at, expires_at, source FROM cache_entries "
                "WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return CacheRecord(
            payload=json.loads(row[0]),
            fetched_at=datetime.fromisoformat(row[1]),
            expires_at=datetime.fromisoformat(row[2]),
            source=row[3],
        )

    def set(self, key: str, payload: Any, ttl_seconds: int, source: str) -> CacheRecord:
        fetched_at = now_shanghai()
        expires_at = fetched_at + timedelta(seconds=ttl_seconds)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO cache_entries(cache_key, payload, fetched_at, expires_at, source)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    fetched_at = excluded.fetched_at,
                    expires_at = excluded.expires_at,
                    source = excluded.source
                """,
                (key, encoded, fetched_at.isoformat(), expires_at.isoformat(), source),
            )
        return CacheRecord(payload, fetched_at, expires_at, source)

    def set_import(self, key: str, payload: Any, source: str) -> None:
        imported_at = now_shanghai()
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        row_count = len(payload) if isinstance(payload, list) else 1
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO imported_datasets(dataset_key, payload, imported_at, source, row_count)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(dataset_key) DO UPDATE SET
                    payload = excluded.payload,
                    imported_at = excluded.imported_at,
                    source = excluded.source,
                    row_count = excluded.row_count
                """,
                (key, encoded, imported_at.isoformat(), source, row_count),
            )

    def get_import(self, key: str) -> list[dict[str, Any]]:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload FROM imported_datasets WHERE dataset_key = ?", (key,)
            ).fetchone()
        return json.loads(row[0]) if row else []

    def list_imports(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT dataset_key, imported_at, source, row_count
                FROM imported_datasets
                ORDER BY imported_at DESC
                """
            ).fetchall()
        return [
            {"dataset": row[0], "importedAt": row[1], "source": row[2], "rows": row[3]}
            for row in rows
        ]

    def record_etf_spot(self, rows: list[dict[str, Any]], source: str) -> None:
        recorded_at = now_shanghai()
        with self._lock, self._connection:
            for row in rows:
                symbol = str(row.get("代码") or "").zfill(6)
                if not symbol.strip("0"):
                    continue
                trade_date = str(
                    row.get("份额日期") or row.get("数据日期") or recorded_at.date().isoformat()
                )[:10]
                self._connection.execute(
                    """
                    INSERT INTO etf_share_snapshots(
                        symbol, trade_date, shares, price, discount_rate, source, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, trade_date) DO UPDATE SET
                        shares = excluded.shares,
                        price = excluded.price,
                        discount_rate = excluded.discount_rate,
                        source = excluded.source,
                        recorded_at = excluded.recorded_at
                    """,
                    (
                        symbol,
                        trade_date,
                        row.get("最新份额"),
                        row.get("最新价"),
                        row.get("基金折价率"),
                        source,
                        recorded_at.isoformat(),
                    ),
                )

    def share_history(self, symbol: str, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT trade_date, shares, price, discount_rate, source
                FROM etf_share_snapshots
                WHERE symbol = ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (symbol.zfill(6), limit),
            ).fetchall()
        return [
            {
                "date": row[0],
                "shares": row[1],
                "price": row[2],
                "discountRatePct": row[3],
                "source": row[4],
            }
            for row in rows
        ]
