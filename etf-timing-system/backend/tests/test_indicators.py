from etf_timing.data.sample_provider import SampleProvider
from etf_timing.services.indicators import build_indicators


def test_build_indicators_returns_core_observations() -> None:
    provider = SampleProvider()
    history = provider.etf_history("510300", "20200101", "20300101")

    result = build_indicators(history, history)

    assert result["availability"] == "available"
    assert result["observations"] > 1_000
    assert result["currentDrawdownPct"] <= 0
    assert 0 <= result["drawdownPercentile"] <= 100
    assert 0 <= result["rsi14"] <= 100
    assert result["relativeReturn20Pct"] == 0
    assert len(result["history"]) == 260


def test_build_indicators_marks_short_history() -> None:
    result = build_indicators(
        [{"日期": "2026-01-01", "收盘": 1.0, "最高": 1.1, "最低": 0.9}]
    )

    assert result == {"availability": "insufficient_history", "observations": 1}

