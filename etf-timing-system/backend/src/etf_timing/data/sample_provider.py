from __future__ import annotations

import math
from datetime import date, timedelta

from etf_timing.data.provider import Record

ETF_ROWS = [
    ("510300", "沪深300ETF", 3.912, -1.82, 3.918, -0.15, 31_280_000_000),
    ("510500", "中证500ETF", 5.426, -2.76, 5.435, -0.17, 17_460_000_000),
    ("512100", "中证1000ETF", 2.184, -3.41, 2.190, -0.27, 11_530_000_000),
    ("588000", "科创50ETF", 0.894, -3.88, 0.897, -0.33, 9_870_000_000),
    ("159915", "创业板ETF", 1.872, -3.15, 1.877, -0.27, 14_110_000_000),
    ("512880", "证券ETF", 0.832, -4.26, 0.834, -0.24, 22_760_000_000),
    ("512170", "医疗ETF", 0.356, -2.20, 0.357, -0.28, 18_920_000_000),
    ("512690", "酒ETF", 0.621, -2.97, 0.623, -0.32, 8_340_000_000),
]


class SampleProvider:
    name = "bundled-sample"

    def market_spot(self) -> list[Record]:
        rows: list[Record] = []
        for index in range(600):
            wave = math.sin(index * 0.37) * 3.1 + math.cos(index * 0.11) * 1.7
            shock = -4.2 if index % 17 == 0 else 0.0
            change = max(-10.0, min(10.0, wave + shock - 0.7))
            rows.append(
                {
                    "代码": str(600000 + index).zfill(6),
                    "名称": f"示例股票{index + 1}",
                    "最新价": round(8 + (index % 37) * 0.41, 2),
                    "涨跌幅": round(change, 2),
                    "成交额": float(28_000_000 + (index % 83) * 2_700_000),
                    "换手率": round(0.4 + (index % 19) * 0.21, 2),
                    "60日涨跌幅": round(math.sin(index * 0.07) * 18, 2),
                    "年初至今涨跌幅": round(math.cos(index * 0.04) * 24, 2),
                }
            )
        return rows

    def industries(self) -> list[Record]:
        names = [
            "银行",
            "保险",
            "证券",
            "半导体",
            "医疗服务",
            "白酒",
            "汽车整车",
            "计算机设备",
            "光伏设备",
            "房地产开发",
            "消费电子",
            "电池",
        ]
        rows: list[Record] = []
        for index, name in enumerate(names):
            change = round(math.sin(index * 0.83) * 3.7 - 0.8, 2)
            up = max(1, int(22 + change * 4 + index % 5))
            down = max(1, 48 - up)
            rows.append(
                {
                    "板块代码": f"BK{1000 + index}",
                    "板块名称": name,
                    "涨跌幅": change,
                    "上涨家数": up,
                    "下跌家数": down,
                    "换手率": round(1.2 + index * 0.19, 2),
                    "领涨股票": f"{name}示例股",
                    "领涨股票-涨跌幅": round(change + 3.2, 2),
                }
            )
        return rows

    def etf_spot(self) -> list[Record]:
        today = date.today().isoformat()
        return [
            {
                "代码": symbol,
                "名称": name,
                "最新价": price,
                "涨跌幅": change,
                "IOPV实时估值": iopv,
                "基金折价率": discount,
                "成交额": 420_000_000 + index * 135_000_000,
                "换手率": round(1.1 + index * 0.36, 2),
                "最新份额": shares,
                "主力净流入-净额": -58_000_000 + index * 13_000_000,
                "数据日期": today,
                "更新时间": f"{today}T15:00:00+08:00",
            }
            for index, (symbol, name, price, change, iopv, discount, shares) in enumerate(ETF_ROWS)
        ]

    def etf_history(self, symbol: str, start_date: str, end_date: str) -> list[Record]:
        base_map = {row[0]: row[2] for row in ETF_ROWS}
        target = base_map.get(symbol, 1.0)
        total = 1_260
        start = date.today() - timedelta(days=int(total * 1.48))
        values: list[float] = []
        current = target * 0.84
        for index in range(total):
            cycle = math.sin(index * 0.027) * 0.004 + math.cos(index * 0.009) * 0.002
            drawdown_shock = -0.016 if index > total - 35 and index % 4 == 0 else 0.0
            current = max(target * 0.42, current * (1 + 0.00035 + cycle + drawdown_shock))
            values.append(current)
        scale = target / values[-1]

        rows: list[Record] = []
        day = start
        value_index = 0
        while value_index < total:
            if day.weekday() < 5:
                close = values[value_index] * scale
                previous = values[value_index - 1] * scale if value_index else close
                open_price = previous * (1 + math.sin(value_index * 0.19) * 0.004)
                high = max(open_price, close) * 1.009
                low = min(open_price, close) * 0.991
                rows.append(
                    {
                        "日期": day.isoformat(),
                        "开盘": round(open_price, 4),
                        "收盘": round(close, 4),
                        "最高": round(high, 4),
                        "最低": round(low, 4),
                        "成交量": 180_000_000 + (value_index % 31) * 5_000_000,
                        "成交额": round(close * (180_000_000 + (value_index % 31) * 5_000_000), 2),
                        "涨跌幅": round((close / previous - 1) * 100, 2) if previous else 0,
                        "换手率": round(0.7 + (value_index % 17) * 0.08, 2),
                    }
                )
                value_index += 1
            day += timedelta(days=1)
        return rows

