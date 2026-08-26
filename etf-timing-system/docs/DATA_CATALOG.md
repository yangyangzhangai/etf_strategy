# 第一阶段数据字典

## 市场层

| 字段 | 含义 | 来源/公式 |
|---|---|---|
| `totalCount` | 全 A 有效行情数量 | 新浪全 A 截面，腾讯备用 |
| `advancers/decliners/flat` | 涨/跌/平家数 | 当日涨跌幅符号 |
| `medianChangePct` | 个股涨跌幅中位数 | 全 A 截面 |
| `turnoverAmount` | 全 A 成交额合计，元 | 全 A 截面 |
| `distribution` | `≤-7/-7~-5/.../≥7%` 家数 | 全 A 截面 |
| `industries` | 行业涨跌幅、上涨/下跌家数 | 同花顺行业摘要 |

“≥9.5%家数”只是截面阈值统计，不命名为涨停家数，避免 5%、10%、20%、30% 不同涨跌停制度造成误读。

## ETF 层

| 字段 | 含义 | 来源/公式 |
|---|---|---|
| `price/changePct` | 最新价/当日涨跌幅 | 新浪行情，腾讯备用 |
| `nav/navDate` | 单位净值与净值日期 | 同花顺公开基金页 |
| `subscriptionStatus/redemptionStatus` | 申购/赎回状态 | 同花顺公开基金页 |
| `iopv/discountRatePct` | IOPV 与折溢价 | 免费主链暂不提供，不以单位净值代替 |
| `latestShares/shareDate` | 最新份额与披露日 | 上交所/深交所官方披露 |
| `currentDrawdownPct` | 当前收盘相对历史滚动高点回撤 | 新浪未复权日线 |
| `drawdownPercentile` | 当前回撤严重度在自身历史回撤中的百分位 | 日线全样本 |
| `rsi14` | 最近 14 日简单平均涨跌 RSI | 未复权日线 |
| `realizedVolatility20Pct` | 20 日对数收益年化波动率 | `std(log return) × √252` |
| `realizedVolatilityPercentile` | RV20 在近 5 年滚动 RV20 中的百分位 | 日线 |
| `atr14Pct` | ATR14 / 最新收盘 | 日线 |
| `atrPercentile` | ATR14% 在近 5 年历史中的百分位 | 日线 |
| `ma60DistancePct` | 最新收盘相对 MA60 偏离 | 日线 |
| `ma60DistanceZScore` | MA60 偏离在近 252 个观测中的 z-score | 日线 |
| `relativeReturn20Pct` | ETF 20 日收益减沪深300ETF 20 日收益 | ETF 与 510300 日线 |
| `shareChange5d/20d` | 本系统份额日快照变化 | 首次运行后逐日积累 |

内部市场宽度字段保留为 `availability=not_collected`，直到指数成分股逐日历史底座完成。
