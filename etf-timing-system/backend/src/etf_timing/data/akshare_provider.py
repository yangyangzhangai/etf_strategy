from __future__ import annotations

import math
import queue
import threading
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from etf_timing.data.provider import Record


def _scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    try:
        if math.isnan(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    return value


def _records(frame: Any, code_columns: tuple[str, ...] = ("代码", "板块代码")) -> list[Record]:
    records: list[Record] = []
    for raw in frame.to_dict(orient="records"):
        item = {str(key): _scalar(value) for key, value in raw.items()}
        for column in code_columns:
            if column in item and item[column] is not None:
                item[column] = str(item[column]).split(".")[0].zfill(6)
        records.append(item)
    return records


def _timed_call(loader: Callable[[], Any], timeout_seconds: float) -> Any:
    """Bound a blocking upstream call without creating request concurrency."""
    result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def run() -> None:
        try:
            result_queue.put((True, loader()))
        except Exception as exc:  # AKShare exposes many upstream exception types
            result_queue.put((False, exc))

    worker = threading.Thread(target=run, daemon=True, name="akshare-provider")
    worker.start()
    worker.join(timeout_seconds)
    if worker.is_alive():
        raise TimeoutError(f"AKShare call exceeded {timeout_seconds:.0f}s")
    succeeded, value = result_queue.get_nowait()
    if succeeded:
        return value
    raise value


class AkshareProvider:
    """Thin adapter around documented AKShare interfaces.

    This is intentionally the only module that imports AKShare. Upstream column
    changes are isolated here instead of leaking into the service layer.
    """

    name = "akshare/eastmoney"

    @staticmethod
    def _ak() -> Any:
        import akshare as ak

        return ak

    def market_spot(self) -> list[Record]:
        frame = _timed_call(lambda: self._ak().stock_zh_a_spot_em(), 20)
        return _records(frame, code_columns=("代码",))

    def industries(self) -> list[Record]:
        frame = _timed_call(lambda: self._ak().stock_board_industry_name_em(), 15)
        return _records(frame)

    def etf_spot(self) -> list[Record]:
        frame = _timed_call(lambda: self._ak().fund_etf_spot_em(), 15)
        return _records(frame, code_columns=("代码",))

    def etf_history(self, symbol: str, start_date: str, end_date: str) -> list[Record]:
        frame = _timed_call(
            lambda: self._ak().fund_etf_hist_em(
                symbol=str(symbol).zfill(6),
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            ),
            18,
        )
        return _records(frame, code_columns=())
