from __future__ import annotations

import math
import statistics
from collections.abc import Iterable
from typing import Any


def number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def rounded(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def percentile_rank(values: Iterable[float], current: float) -> float | None:
    valid = sorted(item for item in values if math.isfinite(item))
    if not valid:
        return None
    count = sum(1 for item in valid if item <= current)
    return count / len(valid) * 100


def rolling_mean(values: list[float], window: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if window <= 0:
        return result
    running = 0.0
    for index, value in enumerate(values):
        running += value
        if index >= window:
            running -= values[index - window]
        if index >= window - 1:
            result[index] = running / window
    return result


def period_return(values: list[float], periods: int) -> float | None:
    if len(values) <= periods or values[-periods - 1] == 0:
        return None
    return (values[-1] / values[-periods - 1] - 1) * 100


def _rolling_realized_volatility(closes: list[float], window: int = 20) -> list[float]:
    log_returns = [math.log(closes[index] / closes[index - 1]) for index in range(1, len(closes))]
    result: list[float] = []
    for end in range(window, len(log_returns) + 1):
        sample = log_returns[end - window : end]
        if len(sample) >= 2:
            result.append(statistics.stdev(sample) * math.sqrt(252) * 100)
    return result


def _rolling_atr_pct(
    highs: list[float], lows: list[float], closes: list[float], window: int = 14
) -> list[float]:
    true_ranges: list[float] = []
    for index, (high, low) in enumerate(zip(highs, lows, strict=True)):
        previous_close = closes[index - 1] if index else closes[index]
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))

    result: list[float] = []
    for end in range(window, len(true_ranges) + 1):
        close = closes[end - 1]
        if close:
            result.append(statistics.fmean(true_ranges[end - window : end]) / close * 100)
    return result


def _rsi14(closes: list[float]) -> float | None:
    if len(closes) < 15:
        return None
    changes = [closes[index] - closes[index - 1] for index in range(len(closes) - 14, len(closes))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = statistics.fmean(gains)
    average_loss = statistics.fmean(losses)
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100 - 100 / (1 + relative_strength)


def _ma_distance(closes: list[float], window: int = 60) -> tuple[float | None, float | None]:
    means = rolling_mean(closes, window)
    distances = [
        close / mean - 1
        for close, mean in zip(closes, means, strict=True)
        if mean is not None and mean != 0
    ]
    if not distances:
        return None, None
    current = distances[-1]
    reference = distances[-252:]
    if len(reference) < 20:
        return current * 100, None
    deviation = statistics.stdev(reference)
    z_score = (current - statistics.fmean(reference)) / deviation if deviation else 0.0
    return current * 100, z_score


def build_indicators(
    history: list[dict[str, Any]], benchmark_history: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    prepared: list[dict[str, Any]] = []
    for row in history:
        close = number(row.get("收盘"))
        high = number(row.get("最高"))
        low = number(row.get("最低"))
        if close is None or high is None or low is None:
            continue
        prepared.append(
            {
                "date": str(row.get("日期")),
                "close": close,
                "high": high,
                "low": low,
                "changePct": number(row.get("涨跌幅")),
                "turnoverAmount": number(row.get("成交额")),
            }
        )
    prepared.sort(key=lambda item: item["date"])
    if len(prepared) < 20:
        return {"availability": "insufficient_history", "observations": len(prepared)}

    closes = [row["close"] for row in prepared]
    highs = [row["high"] for row in prepared]
    lows = [row["low"] for row in prepared]

    drawdowns: list[float] = []
    peak = closes[0]
    for close in closes:
        peak = max(peak, close)
        drawdowns.append(close / peak - 1)
    severities = [-value for value in drawdowns]
    current_severity = severities[-1]

    realized_volatility = _rolling_realized_volatility(closes)
    realized_reference = realized_volatility[-1_260:]
    atr_values = _rolling_atr_pct(highs, lows, closes)
    atr_reference = atr_values[-1_260:]
    ma_distance_pct, ma_distance_z_score = _ma_distance(closes)

    benchmark_return = None
    if benchmark_history:
        benchmark_closes = [
            value
            for row in sorted(benchmark_history, key=lambda item: str(item.get("日期")))
            if (value := number(row.get("收盘"))) is not None
        ]
        benchmark_return = period_return(benchmark_closes, 20)
    return_20 = period_return(closes, 20)

    history_series = [
        {
            "date": prepared[index]["date"],
            "close": rounded(prepared[index]["close"], 4),
            "changePct": rounded(prepared[index]["changePct"]),
            "drawdownPct": rounded(drawdowns[index] * 100),
            "turnoverAmount": rounded(prepared[index]["turnoverAmount"], 0),
        }
        for index in range(max(0, len(prepared) - 260), len(prepared))
    ]

    return {
        "availability": "available",
        "observations": len(prepared),
        "historyStart": prepared[0]["date"],
        "historyEnd": prepared[-1]["date"],
        "currentDrawdownPct": rounded(drawdowns[-1] * 100),
        "drawdownPercentile": rounded(percentile_rank(severities, current_severity)),
        "rsi14": rounded(_rsi14(closes)),
        "realizedVolatility20Pct": rounded(
            realized_volatility[-1] if realized_volatility else None
        ),
        "realizedVolatilityPercentile": rounded(
            percentile_rank(realized_reference, realized_volatility[-1])
            if realized_volatility
            else None
        ),
        "atr14Pct": rounded(atr_values[-1] if atr_values else None),
        "atrPercentile": rounded(
            percentile_rank(atr_reference, atr_values[-1]) if atr_values else None
        ),
        "ma60DistancePct": rounded(ma_distance_pct),
        "ma60DistanceZScore": rounded(ma_distance_z_score),
        "return5Pct": rounded(period_return(closes, 5)),
        "return20Pct": rounded(return_20),
        "return60Pct": rounded(period_return(closes, 60)),
        "return120Pct": rounded(period_return(closes, 120)),
        "relativeReturn20Pct": rounded(
            return_20 - benchmark_return
            if return_20 is not None and benchmark_return is not None
            else None
        ),
        "history": history_series,
    }
