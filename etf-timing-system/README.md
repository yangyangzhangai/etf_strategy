# ETF 择时系统

面向主观操盘者的 A 股 ETF 数据观察工具。当前里程碑只负责数据采集、标准化、缓存和渐进式展示，不生成评分、预测或交易命令。

## 当前范围

- 市场层：全 A 涨跌分布、成交额、上涨/下跌家数、行业板块扩散情况。
- ETF 层：ETF 实时行情、IOPV/折溢价、份额快照、历史价格和核心原始指标。
- 展示层：市场总览、ETF 切换、核心数字常驻、分类详情点击展开。
- 数据质量：每个接口返回来源、更新时间、新鲜度和降级原因。

明确不做：分类评分、综合分、买卖信号、历史收益预测、Expected Value、Opportunity Ranking、自动交易。

## 技术结构

```text
etf-timing-system/
├─ frontend/
│  ├─ app/                    # Next.js / React 看板
│  └─ lib/                    # 前端 API 类型与示例回退数据
├─ backend/
│  ├─ main.py                 # Vercel FastAPI 服务入口
│  ├─ src/etf_timing/
│  │  ├─ data/                  # 免费组合源、AKShare、mootdx、SQLite 缓存
│  │  ├─ services/              # 市场与 ETF 数据组织、原始指标计算
│  │  └─ main.py                # FastAPI 只读 API
│  └─ tests/
├─ docs/                        # 架构、任务、规范与数据字典
└─ vercel.json                 # 单项目的前后端 Services 路由
```

## 本地启动

1. 创建后端环境并安装依赖：

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   ```

2. 启动后端：

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn etf_timing.main:app --app-dir backend/src --reload
   ```

3. 新终端启动前端：

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

默认 `ETF_DATA_MODE=auto`。ETF 数据链路依次尝试：

```text
新鲜缓存 → 新浪/腾讯+同花顺+交易所 → 东方财富 → AKTools → mootdx → 人工导入
          → 陈旧缓存 → 示例数据
```

主链无需 API Key：新浪提供全 A 与 ETF 实时行情及 ETF 未复权日线，腾讯补齐新浪未返回的实时行情，同花顺提供行业摘要、ETF 单位净值与申赎状态，上交所/深交所官方披露提供份额。东方财富、AKTools 和 mootdx 降级为备用。所有切换都会写入响应的 `meta.source/status/message`。

### Excel/CSV 兜底

看板顶部“真实数据接入”可直接下载模板并上传：

- ETF 日线历史：至少包含 `日期、收盘、最高、最低`；
- ETF 行情/份额：至少包含 `代码、最新价`；
- 支持 `.xlsx`、UTF-8 CSV 和 GB18030 CSV；
- 文件通过校验后写入 SQLite，同时保留文件名、导入时间和行数。

人工文件是备用源，不需要每天上传。正常情况下每日批量刷新会继续优先尝试免费公开数据。

### 收盘后批量刷新

参考 InStock 的“收盘后集中采集、网站主要读本地库”方式，项目提供了独立批任务：

```powershell
.\.venv\Scripts\python.exe -m etf_timing.jobs
```

建议用 Windows 任务计划程序在交易日 17:35 调用。任务会刷新全 A、ETF 总表和六只自选 ETF 历史；单个数据源失败不会中断其他标的。

详细说明见 [架构](docs/ARCHITECTURE.md)、[任务拆分](docs/PROJECT_TASKS.md)、[代码规范](docs/CODE_STANDARDS.md) 和 [数据字典](docs/DATA_CATALOG.md)。

## Vercel 单项目部署

`vercel.json` 使用 Vercel Services 在同一个项目中同时构建 `frontend/` 的
Next.js 看板和 `backend/` 的 FastAPI 服务。`/api/v1/*` 路由到后端，其他路径
路由到前端，因此线上不需要 `NEXT_PUBLIC_ETF_API_BASE_URL` 或 CORS 环境变量。

Vercel 函数只有 `/tmp` 可写，线上 SQLite 会自动放在
`/tmp/etf-timing/cache.sqlite3`。它是临时缓存，Excel 导入和历史缓存若需永久保留，
需在后续版本改用持久化数据库。

## 数据源说明

公开网页数据和通达信节点均没有 SLA。系统禁止高频轮询：ETF 行情默认缓存 5 分钟，行业数据 15 分钟，日线数据 6 小时；前端刷新优先命中缓存。新浪与 mootdx 历史均为未复权数据，页面会显示实际来源；分红、拆分等除权事件后需另行处理连续价格口径。

## InStock 完整系统参考

`reference/instock/compose.yaml` 保留了独立运行 InStock 的容器配置，访问端口为 `9988`。它只用于观察成熟系统的采集、定时任务和数据库组织，不和本项目共用数据库，也不把自动交易模块接入本系统。
