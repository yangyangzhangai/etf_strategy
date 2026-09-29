'use client';

import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { getETFDashboard, getETFs, getHealth, getImportTemplateUrl, getMarket, importETFFile } from '../lib/api';
import type { DatasetMeta, ETFDashboard, ETFListItem, HealthStatus, MarketOverview } from '../lib/types';

const DISCOVERY_PRESETS: ETFListItem[] = [
  ['510300', '沪深300ETF'],
  ['510500', '中证500ETF'],
  ['512100', '中证1000ETF'],
  ['588000', '科创50ETF'],
  ['159915', '创业板ETF'],
  ['512880', '证券ETF'],
].map(([symbol, name]) => ({
  symbol,
  name,
  price: null,
  changePct: null,
  iopv: null,
  nav: null,
  discountRatePct: null,
  turnoverAmount: null,
  turnoverRatePct: null,
  latestShares: null,
  mainNetInflow: null,
}));

function formatNumber(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return value.toLocaleString('zh-CN', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function formatPct(value: number | null | undefined, digits = 1, signed = false) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return `${signed && value > 0 ? '+' : ''}${formatNumber(value, digits)}%`;
}

function formatMoney(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  const absolute = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (absolute >= 1e12) return `${sign}${(absolute / 1e12).toFixed(2)}万亿`;
  if (absolute >= 1e8) return `${sign}${(absolute / 1e8).toFixed(2)}亿`;
  if (absolute >= 1e4) return `${sign}${(absolute / 1e4).toFixed(1)}万`;
  return `${sign}${absolute.toFixed(0)}`;
}

function formatTimestamp(value?: string | null) {
  if (!value) return '尚未取得';
  try {
    return new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(new Date(value));
  } catch {
    return '时间异常';
  }
}

function isUsable(meta?: DatasetMeta | null) {
  return Boolean(meta && meta.status !== 'sample');
}

function SourceState({ meta }: { meta?: DatasetMeta | null }) {
  if (!meta || meta.status === 'sample') {
    return <span className="source-state source-missing"><i />数据源暂不可用</span>;
  }
  const label = meta.status === 'live' ? '实时数据' : meta.status === 'cached' ? '有效缓存' : '陈旧缓存';
  return <span className={`source-state source-${meta.status}`} title={meta.source}><i />{label}</span>;
}

function CoreFinding({ label, definition, value, context, formula, emphasis = false }: {
  label: string;
  definition?: string;
  value: string;
  context: string;
  formula?: string;
  emphasis?: boolean;
}) {
  return (
    <article className={`core-finding ${emphasis ? 'core-finding-emphasis' : ''}`}>
      <span className="finding-label">{label}{definition ? `（${definition}）` : ''}</span>
      <strong>{value}</strong>
      <p>{context}</p>
      {formula && <small className="finding-formula">算法：{formula}</small>}
    </article>
  );
}

type Evidence = { label: string; value: string };
type AppView = 'market' | 'pool' | 'detail' | 'research';

function CategoryCard({
  title,
  direction,
  evidence,
  detailEvidence,
  interpretation,
  source = '来源随数据字段记录',
  unavailable = false,
}: {
  title: string;
  direction: string;
  evidence: Evidence[];
  detailEvidence?: Evidence[];
  interpretation: string;
  source?: string;
  unavailable?: boolean;
}) {
  const details = detailEvidence ?? evidence;
  return (
    <details className="category-card">
      <summary>
        <div className="category-head">
          <div>
            <span className="category-direction">{direction}</span>
            <h3>{title}</h3>
          </div>
          <span className={`score-reserved ${unavailable ? 'score-missing' : ''}`}>
            {unavailable ? '数据待接入' : '评分待定义'}
          </span>
        </div>
        <div className="evidence-row">
          {evidence.map((item) => (
            <span className="evidence" key={`${title}-${item.label}`}>
              <small>{item.label}</small><b>{item.value}</b>
            </span>
          ))}
        </div>
        <p className="category-comment">{interpretation}</p>
        <span className="drill-hint">展开原始数据、口径与来源</span>
      </summary>
      <div className="category-detail">
        <div className="detail-grid">
          {details.map((item) => (
            <div key={`detail-${title}-${item.label}`}><span>{item.label}</span><strong>{item.value}</strong></div>
          ))}
        </div>
        <div className="detail-foot">
          <p>当前阶段只展示已取得的数据。评分构成和历史研究将在公式确认后接入，不用示例数字填充。</p>
          <span>{source}</span>
        </div>
      </div>
    </details>
  );
}

function buildLinePath(values: number[], width = 680, height = 190) {
  if (values.length < 2) return '';
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  return values.map((value, index) => {
    const x = (index / (values.length - 1)) * width;
    const y = height - ((value - min) / range) * height;
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(' ');
}

function HistoryPanel({ dashboard }: { dashboard: ETFDashboard | null }) {
  const rows = dashboard?.core.history?.slice(-160) ?? [];
  const pricePath = buildLinePath(rows.map((row) => row.close));
  const drawdownPath = buildLinePath(rows.map((row) => row.drawdownPct), 680, 72);
  if (!rows.length) {
    return (
      <div className="history-panel history-empty">
        <div><span>价格与回撤历史</span><small>核心趋势图</small></div>
        <strong>历史序列暂不可用</strong>
        <p>接入真实复权行情后显示价格曲线、水下回撤和本轮回撤位置。</p>
      </div>
    );
  }
  return (
    <div className="history-panel">
      <div className="chart-title"><span>价格与回撤历史</span><small>最近 {rows.length} 个交易日</small></div>
      <svg className="price-line-chart" viewBox="0 0 680 210" role="img" aria-label="ETF价格历史曲线">
        <path className="chart-grid-line" d="M 0 52.5 H 680 M 0 105 H 680 M 0 157.5 H 680" />
        <path className="price-path" d={pricePath} />
      </svg>
      <div className="underwater-label"><span>水下回撤</span><b>{formatPct(dashboard?.core.currentDrawdownPct, 1)}</b></div>
      <svg className="drawdown-chart" viewBox="0 0 680 80" role="img" aria-label="ETF水下回撤曲线">
        <path className="drawdown-path" d={drawdownPath} />
      </svg>
      <div className="chart-axis"><span>{rows[0]?.date}</span><span>{rows.at(-1)?.date}</span></div>
    </div>
  );
}

function RelativeGauge({ value }: { value: number | null | undefined }) {
  const available = value !== null && value !== undefined && Number.isFinite(value);
  const position = available ? Math.max(4, Math.min(96, 50 + value * 3.5)) : 50;
  return (
    <div className="relative-gauge">
      <div className="gauge-title"><span>相对沪深300强弱</span><small>20日相对收益</small></div>
      <div className="gauge-labels"><span>明显偏弱</span><span>中性</span><span>明显偏强</span></div>
      <div className="gauge-track"><i className={available ? '' : 'unavailable'} style={{ left: `${position}%` }} /></div>
      <strong>{available ? formatPct(value, 1, true) : '—'}</strong>
      <p>{available ? '这是相对表现，不代表绝对位置高低；需与回撤和内部宽度共同阅读。' : '基准与ETF同步历史尚不可用，暂不形成相对强弱指针。'}</p>
    </div>
  );
}

function ResearchMetric({ label, description }: { label: string; description: string }) {
  return <div className="research-metric"><span>{label}</span><strong>—</strong><small>{description}</small></div>;
}

function marketInterpretation(market: MarketOverview | null) {
  if (!market) return '尚未取得可用于决策的实时数据，暂不形成市场扩散判断。';
  const { advancers, decliners, downMoreThan5Pct } = market.summary;
  if (advancers <= 0 || decliners <= 0) return '涨跌截面样本不足，暂不形成市场扩散判断。';
  return `下跌家数约为上涨家数的 ${(decliners / advancers).toFixed(1)} 倍，跌幅超过5%的股票有 ${downMoreThan5Pct} 只；这是市场宽度的直接证据，不等同于买入结论。`;
}

export default function Home() {
  const [view, setView] = useState<AppView>('market');
  const [marketRaw, setMarketRaw] = useState<MarketOverview | null>(null);
  const [etfs, setEtfs] = useState<ETFListItem[]>(DISCOVERY_PRESETS);
  const [watchlist, setWatchlist] = useState<ETFListItem[]>([]);
  const [selected, setSelected] = useState('510300');
  const [dashboardRaw, setDashboardRaw] = useState<ETFDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [horizon, setHorizon] = useState(20);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [importDataset, setImportDataset] = useState<'history' | 'spot'>('history');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const [searchText, setSearchText] = useState('');
  const [searchResults, setSearchResults] = useState<ETFListItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchMessage, setSearchMessage] = useState<string | null>(null);
  const [marketLoading, setMarketLoading] = useState(false);
  const [marketMessage, setMarketMessage] = useState<string | null>(null);

  const market = useMemo(
    () => (marketRaw && isUsable(marketRaw.meta.market) ? marketRaw : null),
    [marketRaw],
  );
  const dashboard = useMemo(
    () => (dashboardRaw && dashboardRaw.etf.symbol === selected ? dashboardRaw : null),
    [dashboardRaw, selected],
  );
  const selectedItem = useMemo(
    () => [...watchlist, ...etfs].find((item) => item.symbol === selected) ?? DISCOVERY_PRESETS[0],
    [etfs, selected, watchlist],
  );
  const poolItems = useMemo(
    () => watchlist.map((saved) => etfs.find((item) => item.symbol === saved.symbol) ?? saved),
    [etfs, watchlist],
  );
  const selectedInPool = poolItems.some((item) => item.symbol === selected);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        const saved = localStorage.getItem('etf-timing-watchlist');
        if (saved) {
          const items = JSON.parse(saved) as ETFListItem[];
          setWatchlist(items);
          if (items[0]) setSelected(items[0].symbol);
        }
      } catch {
        localStorage.removeItem('etf-timing-watchlist');
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    Promise.allSettled([getMarket(), getETFs(), getHealth()]).then(([marketResult, etfResult, healthResult]) => {
      if (marketResult.status === 'fulfilled') setMarketRaw(marketResult.value);
      if (etfResult.status === 'fulfilled' && etfResult.value.length) setEtfs(etfResult.value);
      if (healthResult.status === 'fulfilled') setHealth(healthResult.value);
    });
  }, []);

  useEffect(() => {
    let active = true;
    getETFDashboard(selected)
      .then((result) => active && setDashboardRaw(result))
      .catch(() => active && setDashboardRaw(null));
    return () => { active = false; };
  }, [selected]);

  async function refreshAll() {
    setLoading(true);
    const [marketResult, etfResult, dashboardResult] = await Promise.allSettled([
      getMarket(true),
      getETFs(true),
      getETFDashboard(selected, true),
    ]);
    if (marketResult.status === 'fulfilled') setMarketRaw(marketResult.value);
    if (etfResult.status === 'fulfilled' && etfResult.value.length) setEtfs(etfResult.value);
    if (dashboardResult.status === 'fulfilled') setDashboardRaw(dashboardResult.value);
    setLoading(false);
  }

  function saveWatchlist(items: ETFListItem[]) {
    setWatchlist(items);
    localStorage.setItem('etf-timing-watchlist', JSON.stringify(items));
  }

  function addToWatchlist(item: ETFListItem) {
    const next = watchlist.some((saved) => saved.symbol === item.symbol)
      ? watchlist
      : [...watchlist, item];
    saveWatchlist(next);
    setSearchMessage(`已加入自选ETF池：${item.name} · ${item.symbol}`);
  }

  function removeFromWatchlist(symbol: string) {
    const next = watchlist.filter((item) => item.symbol !== symbol);
    saveWatchlist(next);
    if (selected === symbol) setSelected(next[0]?.symbol ?? '510300');
  }

  function changeView(next: AppView) {
    setView(next);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function openETFDetail(item: ETFListItem) {
    setSelected(item.symbol);
    setView('detail');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function searchETF(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = searchText.trim();
    if (!query) {
      setSearchMessage('请输入 ETF 代码或名称，例如 510300、红利、科创50。');
      return;
    }
    setSearching(true);
    setSearchMessage('正在查询已联网同步的同花顺 ETF 目录与新浪/腾讯行情…');
    try {
      const results = await getETFs(false, query);
      setSearchResults(results);
      setSearchMessage(results.length ? `找到 ${results.length} 个匹配标的，请点击“加入观察”。` : '没有找到匹配 ETF，请换代码或简称。');
    } catch {
      setSearchResults([]);
      setSearchMessage('联网搜索失败；请确认本地数据服务正在运行，或稍后重试。');
    } finally {
      setSearching(false);
    }
  }

  async function refreshMarket() {
    setMarketLoading(true);
    setMarketMessage('正在采集全 A、行业、沪深300历史与中证官方估值，通常需要 20–40 秒…');
    try {
      const result = await getMarket(true);
      setMarketRaw(result);
      setMarketMessage(`采集完成：${result.summary.totalCount} 只股票、${result.industries.all.length} 个行业；指数数据截至 ${result.index.core.historyEnd ?? '未知日期'}。`);
    } catch {
      setMarketMessage('采集失败。页面会继续保留上一次真实缓存，请检查数据服务后重试。');
    } finally {
      setMarketLoading(false);
    }
  }

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!importFile) {
      setImportMessage('请先选择 .xlsx 或 .csv 文件。');
      return;
    }
    setImporting(true);
    setImportMessage(null);
    try {
      const result = await importETFFile(importFile, importDataset, selected);
      setImportMessage(`已导入 ${result.rows} 行，数据已写入本地数据库。`);
      const [dashboardResult, etfResult, healthResult] = await Promise.all([
        getETFDashboard(selected),
        getETFs(),
        getHealth(),
      ]);
      setDashboardRaw(dashboardResult);
      if (etfResult.length) setEtfs(etfResult);
      setHealth(healthResult);
    } catch (error) {
      setImportMessage(error instanceof Error ? error.message : '导入失败，请检查文件格式。');
    } finally {
      setImporting(false);
    }
  }

  const dashboardMatches = dashboardRaw?.etf.symbol === selected;
  const etfMeta = dashboardMatches ? dashboardRaw?.meta.spot : null;
  const core = dashboardRaw && dashboardMatches && isUsable(dashboardRaw.meta.history) ? dashboardRaw.core : null;
  const spot = dashboardRaw && dashboardMatches && isUsable(dashboardRaw.meta.spot) ? dashboardRaw.etf : null;
  const capital = dashboardRaw && dashboardMatches && isUsable(dashboardRaw.meta.spot) ? dashboardRaw.capital : null;
  const breadth = dashboardRaw && dashboardMatches && isUsable(dashboardRaw.meta.history) ? dashboardRaw.internalBreadth : null;
  const marketCore = market?.index.core;
  const valuation = market?.index.valuation;
  const headerMeta = view === 'market' ? marketRaw?.meta.market : etfMeta;
  const headerContext = view === 'market'
    ? { layer: '第一层 · 固定视角', title: '市场环境 · 沪深300与全A' }
    : view === 'pool'
      ? { layer: '第二层 · 自选池', title: `我的ETF池 · ${watchlist.length}只` }
      : view === 'detail'
        ? { layer: '第二层 · ETF详情', title: `${selectedItem.name} · ${selected}` }
        : { layer: '第三层 · 历史参考', title: `${selectedItem.name} · ${selected}` };

  return (
    <main>
      <header className="app-header">
        <div className="brand-block">
          <span className="brand-mark">ETF</span>
          <div><h1>ETF择时系统</h1><p>空仓等待市场大幅回调 · 数据观察驾驶舱</p></div>
        </div>
        <div className="header-controls">
          <div className="current-symbol"><span>{headerContext.layer}</span><strong>{headerContext.title}</strong></div>
          <div className="data-freshness"><SourceState meta={headerMeta} /><small>更新 {formatTimestamp(headerMeta?.asOf)}</small></div>
          <button type="button" onClick={view === 'market' ? refreshMarket : refreshAll} disabled={loading || marketLoading}>{loading || marketLoading ? '更新中' : view === 'market' ? '更新市场数据' : '更新ETF数据'}</button>
        </div>
      </header>

      <nav className="decision-path" aria-label="三层业务结构">
        <button type="button" className={`path-step ${view === 'market' ? 'active' : ''}`} onClick={() => changeView('market')}><b>01</b><span><strong>市场环境</strong><small>固定市场视角，不随ETF改变</small></span></button>
        <span className="path-connector" />
        <button type="button" className={`path-step ${view === 'pool' || view === 'detail' ? 'active' : ''}`} onClick={() => changeView('pool')}><b>02</b><span><strong>ETF自选池</strong><small>池内排名、单只详情与管理</small></span></button>
        <span className="path-connector" />
        <button type="button" className={`path-step ${view === 'research' ? 'active' : ''} ${selectedInPool ? '' : 'path-disabled'}`} onClick={() => selectedInPool && changeView('research')} disabled={!selectedInPool}><b>03</b><span><strong>历史统计参考</strong><small>{selectedInPool ? `${selectedItem.name} · 公式待定义` : '先从自选池选择一只ETF'}</small></span></button>
      </nav>

      {view === 'pool' && <>
      <section className="etf-selector" aria-labelledby="etf-selector-title">
        <div className="selector-heading">
          <div><span>管理自选池</span><h2 id="etf-selector-title">查找并加入ETF</h2><p>只有你主动加入的标的才进入本系统的每日观察、详情分析和未来推荐排名。</p></div>
          <SourceState meta={etfMeta} />
        </div>
        <form className="etf-search" onSubmit={searchETF}>
          <label htmlFor="etf-search-input">ETF代码或名称</label>
          <input id="etf-search-input" value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="例如：510300、红利、科创50、证券" />
          <button type="submit" disabled={searching}>{searching ? '正在联网采集…' : '联网搜索 ETF'}</button>
        </form>
        {searchMessage && <p className="search-message" role="status">{searchMessage}</p>}
        {searchResults.length > 0 && (
          <div className="search-results">
            {searchResults.map((item) => (
              <article key={`search-${item.symbol}`}>
                <div className="result-main"><strong>{item.name}</strong><span>{item.symbol} · {formatNumber(item.price, 3)} · {formatPct(item.changePct, 2, true)}</span></div>
                <button className="add-watch" type="button" onClick={() => addToWatchlist(item)}>{watchlist.some((saved) => saved.symbol === item.symbol) ? '已在池中' : '+ 加入自选池'}</button>
              </article>
            ))}
          </div>
        )}
        <div className="preset-row"><span>常见宽基</span>{DISCOVERY_PRESETS.map((item) => <button type="button" key={`preset-${item.symbol}`} onClick={() => addToWatchlist(etfs.find((candidate) => candidate.symbol === item.symbol) ?? item)}>{item.name}<small>{item.symbol}</small></button>)}</div>
      </section>

      <div className="phase-note"><strong>当前阶段：数据采集与展示</strong><span>评分、AI分析和历史预测保留产品位置，但不生成模拟结果，也不输出交易命令。</span></div>

      <details className="data-operations">
        <summary>
          <div><strong>真实数据接入</strong><span>主源、备用源与人工兜底</span></div>
          <div className="provider-summary">
            <span className="provider-ready">新浪 + 同花顺主源</span>
            <span className={health?.providers.mootdx.installed ? 'provider-ready' : 'provider-warn'}>
              mootdx {health?.providers.mootdx.installed ? '已就绪' : '待安装'}
            </span>
            <span className="provider-ready">Excel/CSV 可导入</span>
          </div>
        </summary>
        <div className="operations-body">
          <div className="source-pipeline" aria-label="数据源优先级">
            <div><b>1</b><span><strong>免费组合源</strong><small>新浪行情/日线 · 同花顺净值 · 交易所份额</small></span></div>
            <i>→</i>
            <div><b>2</b><span><strong>东方财富 / AKTools</strong><small>{health?.providers.aktools.enabled ? 'HTTP 服务已配置' : '自动备用'}</small></span></div>
            <i>→</i>
            <div><b>3</b><span><strong>mootdx</strong><small>通达信 ETF 行情/未复权历史备用</small></span></div>
            <i>→</i>
            <div><b>4</b><span><strong>Excel / CSV</strong><small>所有接口失效时最终兜底</small></span></div>
          </div>
          <form className="import-form" onSubmit={submitImport}>
            <div className="import-copy">
              <strong>导入 {selectedItem.name} · {selected}</strong>
              <span>支持 Excel（.xlsx）和 CSV；系统校验字段后写入 SQLite，并记录文件来源。</span>
            </div>
            <label><span>数据类型</span><select value={importDataset} onChange={(event) => setImportDataset(event.target.value as 'history' | 'spot')}><option value="history">ETF 日线历史</option><option value="spot">ETF 行情/份额</option></select></label>
            <label className="file-field"><span>选择文件</span><input type="file" accept=".xlsx,.csv" onChange={(event) => setImportFile(event.target.files?.[0] ?? null)} /></label>
            <a className="template-link" href={getImportTemplateUrl(importDataset)}>下载模板</a>
            <button type="submit" disabled={importing}>{importing ? '导入中' : '校验并导入'}</button>
          </form>
          {importMessage && <p className="import-message" role="status">{importMessage}</p>}
          {health?.imports?.[0] && <p className="last-import">最近导入：{health.imports[0].dataset} · {health.imports[0].rows} 行 · {formatTimestamp(health.imports[0].importedAt)}</p>}
        </div>
      </details>
      </>}

      <div className="page-shell">
        {view === 'pool' && (
          <section className="layer-section pool-layer" aria-labelledby="pool-title">
            <div className="layer-heading">
              <div className="layer-index">第二层</div>
              <div>
                <h2 id="pool-title">我的ETF自选池</h2>
                <p>只有加入这个池子的ETF才进入系统的每日观察范围。以后评分公式启用后，这里会按推荐指数从高到低自动排序。</p>
              </div>
              <span className="pool-count">{poolItems.length} 只标的</span>
            </div>

            <div className="pool-ranking-note">
              <strong>每日推荐排名</strong>
              <span>当前评分公式尚未确定，因此不生成分数、不做伪排序；现阶段按加入顺序展示。</span>
            </div>

            {poolItems.length === 0 ? (
              <div className="pool-empty">
                <strong>自选池还是空的</strong>
                <p>在上方搜索ETF并点击“加入自选池”，它才会进入后续详情、统计和推荐排名。</p>
              </div>
            ) : (
              <div className="pool-grid">
                {poolItems.map((item, index) => (
                  <article className="pool-card" key={`pool-${item.symbol}`}>
                    <div className="pool-card-rank"><span>当前顺序</span><strong>{String(index + 1).padStart(2, '0')}</strong></div>
                    <div className="pool-card-main">
                      <span>{item.symbol}</span>
                      <h3>{item.name}</h3>
                      <div className="pool-quote"><strong>{formatNumber(item.price, 3)}</strong><b className={(item.changePct ?? 0) > 0 ? 'positive' : (item.changePct ?? 0) < 0 ? 'negative' : ''}>{formatPct(item.changePct, 2, true)}</b></div>
                    </div>
                    <div className="pool-score">
                      <span>买入时机推荐指数</span>
                      <strong>—</strong>
                      <small>评分公式待定义</small>
                    </div>
                    <div className="pool-card-actions">
                      <button type="button" className="primary-action" onClick={() => openETFDetail(item)}>查看ETF详情</button>
                      <button type="button" className="quiet-action" onClick={() => removeFromWatchlist(item.symbol)}>移出池子</button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        {view === 'market' && (
        <section className="layer-section" id="market-layer">
          <div className="layer-heading">
            <div className="layer-index">第一层</div>
            <div><h2>市场环境</h2><p>全 A 截面用于观察当天扩散，沪深300最近六年日线用于计算市场回撤、RSI和波动率。</p></div>
            <div className="layer-actions"><SourceState meta={marketRaw?.meta.market} /><button type="button" onClick={refreshMarket} disabled={marketLoading}>{marketLoading ? '采集中…' : '重新采集市场数据'}</button></div>
          </div>
          {marketMessage && <p className="collection-message" role="status">{marketMessage}</p>}

          <div className="market-index-strip">
            <div><span>市场基准</span><strong>{market?.index.name ?? '沪深300指数'}</strong><small>代码 000300</small></div>
            <div><span>最新收盘</span><strong>{formatNumber(market?.index.close, 2)}</strong><small>新浪指数日线</small></div>
            <div><span>滚动市盈率 PE</span><strong>{formatNumber(valuation?.peTtm, 2)}</strong><small>中证指数官网 · {valuation?.date ?? '待采集'}</small></div>
            <div><span>近期PE分位</span><strong>{formatPct(valuation?.peRecentPercentile, 1)}</strong><small>仅比较官方最近 {valuation?.peObservations ?? 0} 个披露日</small></div>
            <div><span>股息率</span><strong>{formatPct(valuation?.dividendYieldPct, 2)}</strong><small>中证计算用股本口径</small></div>
          </div>

          <div className="core-findings-grid market-findings">
            <CoreFinding label="当前回撤" definition="距六年滚动高点的跌幅" value={formatPct(marketCore?.currentDrawdownPct, 1)} context={`沪深300 · ${marketCore?.observations ?? 0} 个交易日样本`} formula="当前收盘 ÷ 历史最高收盘 − 1" emphasis />
            <CoreFinding label="回撤历史分位" definition="当前回撤有多极端" value={formatPct(marketCore?.drawdownPercentile, 1)} context="越接近100%，当前回撤在历史中越严重" formula="历史上回撤严重度≤当前值的天数占比" emphasis />
            <CoreFinding label="RSI14" definition="14日涨跌动能，0–100" value={formatNumber(marketCore?.rsi14, 1)} context="低于30常称超卖，高于70常称超买；不代表必然反转" formula="100 − 100 ÷ (1 + 14日平均上涨÷平均下跌)" />
            <CoreFinding label="RV20历史分位" definition="20日波动有多异常" value={formatPct(marketCore?.realizedVolatilityPercentile, 1)} context={`当前RV20 ${formatPct(marketCore?.realizedVolatility20Pct, 1)}`} formula="20日对数收益标准差年化后，与近五年比较" />
            <CoreFinding label="上涨 / 下跌家数" definition="全A当日扩散" value={market ? `${formatNumber(market.summary.advancers)} / ${formatNumber(market.summary.decliners)}` : '—'} context={market ? `跌幅≥5%：${formatNumber(market.summary.downMoreThan5Pct)}只` : '全A实时截面暂不可用'} formula="逐只股票按当日涨跌幅正负计数" />
            <CoreFinding label="全A成交额" definition="当日市场流动性" value={formatMoney(market?.summary.turnoverAmount)} context={market ? `${formatNumber(market.summary.totalCount)}只股票有效样本` : '全A实时截面暂不可用'} formula="有效股票成交额逐只求和" />
          </div>

          <div className="section-subhead">
            <div><h3>市场六维观察</h3><p>复杂信息压缩成分类卡；首页只留关键证据，点击查看完整原始指标。</p></div>
            <span>6 个分类 · 原思维导图完整保留</span>
          </div>

          <div className="category-grid">
            <CategoryCard title="沪深300估值" direction="PE越低、股息率越高通常代表估值更便宜" unavailable={!valuation?.peTtm} evidence={[{ label: '滚动PE', value: formatNumber(valuation?.peTtm, 2) }, { label: '近期PE分位', value: formatPct(valuation?.peRecentPercentile, 1) }, { label: '股息率', value: formatPct(valuation?.dividendYieldPct, 2) }]} detailEvidence={[{ label: '滚动市盈率', value: formatNumber(valuation?.peTtm, 2) }, { label: '近期PE分位', value: formatPct(valuation?.peRecentPercentile, 1) }, { label: '官方样本数', value: formatNumber(valuation?.peObservations) }, { label: '股息率', value: formatPct(valuation?.dividendYieldPct, 2) }, { label: '披露日期', value: valuation?.date ?? '—' }, { label: 'PB', value: '官方接口本次未返回' }]} interpretation="数据直接来自中证指数官网。近期PE分位只比较接口返回的最近披露日，不冒充长期历史分位。" source="中证指数有限公司 · 000300" />
            <CategoryCard title="沪深300趋势" direction="分别观察短、中期收益与均线偏离" unavailable={!marketCore} evidence={[{ label: '20日收益', value: formatPct(marketCore?.return20Pct, 2, true) }, { label: '60日收益', value: formatPct(marketCore?.return60Pct, 2, true) }, { label: '120日收益', value: formatPct(marketCore?.return120Pct, 2, true) }]} detailEvidence={[{ label: '5日收益', value: formatPct(marketCore?.return5Pct, 2, true) }, { label: '20日收益', value: formatPct(marketCore?.return20Pct, 2, true) }, { label: '60日收益', value: formatPct(marketCore?.return60Pct, 2, true) }, { label: '120日收益', value: formatPct(marketCore?.return120Pct, 2, true) }, { label: '距MA60', value: formatPct(marketCore?.ma60DistancePct, 1, true) }, { label: '距MA60标准差', value: marketCore?.ma60DistanceZScore != null ? `${formatNumber(marketCore.ma60DistanceZScore, 2)}σ` : '—' }]} interpretation="趋势数据来自沪深300每日收盘序列；它描述当前方向，不判断是否应该买入。" source="新浪财经 · 沪深300日线" />
            <CategoryCard title="压力扩散" direction="跌幅较大的股票越多、波动率越高，压力越广" evidence={[{ label: '跌幅≥5%', value: market ? `${formatNumber(market.summary.downMoreThan5Pct)}只` : '—' }, { label: '涨幅≥5%', value: market ? `${formatNumber(market.summary.upMoreThan5Pct)}只` : '—' }, { label: '涨跌中位数', value: formatPct(market?.summary.medianChangePct, 2, true) }]} detailEvidence={[{ label: '跌幅≥5%家数', value: market ? formatNumber(market.summary.downMoreThan5Pct) : '—' }, { label: '涨幅≥5%家数', value: market ? formatNumber(market.summary.upMoreThan5Pct) : '—' }, { label: '全A涨跌中位数', value: formatPct(market?.summary.medianChangePct, 2, true) }, { label: '当前RV20', value: formatPct(marketCore?.realizedVolatility20Pct, 1) }, { label: 'RV20历史分位', value: formatPct(marketCore?.realizedVolatilityPercentile, 1) }]} interpretation={market ? `全A有 ${market.summary.downMoreThan5Pct} 只股票跌幅超过5%；和波动率一起看，避免只看指数点位。` : '实时截面暂不可用。'} />
            <CategoryCard title="市场宽度健康度" direction="越高代表内部结构越健康" evidence={[{ label: '上涨家数', value: market ? formatNumber(market.summary.advancers) : '—' }, { label: '下跌家数', value: market ? formatNumber(market.summary.decliners) : '—' }, { label: 'MA60上方', value: '—' }]} detailEvidence={[{ label: '上涨家数', value: market ? formatNumber(market.summary.advancers) : '—' }, { label: '下跌家数', value: market ? formatNumber(market.summary.decliners) : '—' }, { label: '平盘家数', value: market ? formatNumber(market.summary.flat) : '—' }, { label: 'MA20上方比例', value: '—' }, { label: 'MA60上方比例', value: '—' }, { label: 'MA120上方比例', value: '—' }, { label: '创新高/新低', value: '—' }, { label: 'A/D线', value: '—' }, { label: 'McClellan', value: '—' }, { label: '平均相关性', value: '—' }]} interpretation={marketInterpretation(market)} />
            <CategoryCard title="流动性健康度" direction="越高代表交易流动性越充足" evidence={[{ label: '全A成交额', value: market ? formatMoney(market.summary.turnoverAmount) : '—' }, { label: '成交额分位', value: '—' }, { label: '换手率', value: '—' }]} detailEvidence={[{ label: '全A成交额', value: market ? formatMoney(market.summary.turnoverAmount) : '—' }, { label: '成交额历史分位', value: '—' }, { label: '全A换手率', value: '—' }, { label: 'Amihud ILLIQ', value: '—' }, { label: '买卖价差', value: '—' }, { label: '冲击成本', value: '—' }, { label: '涨跌停成交结构', value: '—' }]} interpretation={market ? '当前成交额已取得，但只有结合自身历史分位、换手率与冲击成本，才能判断流动性是否异常。' : '成交、换手与冲击成本数据不足，暂不形成流动性判断。'} />
            <CategoryCard title="市场资金状态" direction="越高代表逆势承接越明显" unavailable evidence={[{ label: '融资余额变化', value: '—' }, { label: '宽基ETF份额', value: '—' }, { label: '融资买入占比', value: '—' }]} detailEvidence={[{ label: '融资余额1日变化', value: '—' }, { label: '融资余额5日变化', value: '—' }, { label: '融资买入占比', value: '—' }, { label: '宽基ETF份额5日变化', value: '—' }, { label: '宽基ETF份额20日变化', value: '—' }, { label: '基金申赎', value: '—' }, { label: '可用资金流指标', value: '—' }]} interpretation="融资与宽基ETF份额历史尚未接入；资金流指标只作为承接证据，不直接解释为聪明钱。" />
          </div>
        </section>
        )}

        {view === 'detail' && (
        <section className="layer-section etf-layer" id="etf-layer">
          <div className="layer-heading">
            <div className="layer-index">第二层 · 详情</div>
            <div>
              <h2>{spot?.name ?? selectedItem.name} · ETF状态</h2>
              <p>在固定市场环境背景下，单独观察这只ETF的位置、回撤、波动和资金情况。</p>
            </div>
            <div className="layer-actions detail-nav-actions">
              <SourceState meta={etfMeta} />
              <div><button type="button" className="quiet-action" onClick={() => changeView('pool')}>← 返回ETF池</button><button type="button" onClick={() => changeView('research')}>查看历史参考统计 →</button></div>
            </div>
          </div>

          <div className="detail-score-context">
            <div><span>市场环境</span><strong>固定读取第一层数据</strong><small>不会因切换ETF而改变市场口径</small></div>
            <div><span>ETF状态评分</span><strong>—</strong><small>公式待定义</small></div>
            <div><span>综合推荐指数</span><strong>—</strong><small>市场环境分 + ETF状态分，权重待定义</small></div>
          </div>

          <div className="instrument-strip">
            <div className="instrument-identity"><span>{spot?.symbol ?? selected}</span><strong>{formatNumber(spot?.price, 3)}</strong></div>
            <div><span>当日涨跌</span><strong className={(spot?.changePct ?? 0) > 0 ? 'positive' : (spot?.changePct ?? 0) < 0 ? 'negative' : ''}>{formatPct(spot?.changePct, 2, true)}</strong></div>
            <div><span>单位净值</span><strong>{formatNumber(spot?.nav, 4)}</strong></div>
            <div><span>折溢价</span><strong>{formatPct(spot?.discountRatePct, 2, true)}</strong></div>
            <div><span>成交额</span><strong>{formatMoney(spot?.turnoverAmount)}</strong></div>
            <div><span>换手率</span><strong>{formatPct(spot?.turnoverRatePct, 2)}</strong></div>
          </div>

          <div className="core-findings-grid etf-findings">
            <CoreFinding label="当前回撤" definition="距六年滚动高点的跌幅" value={formatPct(core?.currentDrawdownPct, 1)} context={core ? `${core.observations} 个交易日样本；数值越负，离高点越远` : '真实历史行情暂不可用'} formula="当前收盘 ÷ 历史最高收盘 − 1" emphasis />
            <CoreFinding label="回撤历史分位" definition="当前回撤有多极端" value={formatPct(core?.drawdownPercentile, 1)} context={core?.drawdownPercentile != null ? `当前回撤严重度高于约 ${formatPct(core.drawdownPercentile, 1)} 的历史交易日` : '比较ETF自身历史回撤分布'} formula="历史回撤严重度不超过当前值的天数占比" emphasis />
            <CoreFinding label="RSI14" definition="14日涨跌动能，0–100" value={formatNumber(core?.rsi14, 1)} context="低于30常称超卖，高于70常称超买；它和回撤分位不是同一算法" formula="100 − 100 ÷ (1 + 14日平均上涨÷平均下跌)" />
            <CoreFinding label="20日实现波动率" definition="过去20日波动，年化" value={formatPct(core?.realizedVolatility20Pct, 1)} context={`与近五年相比位于 ${formatPct(core?.realizedVolatilityPercentile, 1)} 分位`} formula="20日对数收益标准差 × √252" />
            <CoreFinding label="ATR14 / 价格" definition="14日平均真实波幅占价格比例" value={formatPct(core?.atr14Pct, 2)} context={`与近五年相比位于 ${formatPct(core?.atrPercentile, 1)} 分位`} formula="14日真实波幅均值 ÷ 最新收盘价" />
            <CoreFinding label="距MA60标准差" definition="偏离60日均线的异常程度" value={core?.ma60DistanceZScore != null ? `${formatNumber(core.ma60DistanceZScore, 2)}σ` : '—'} context={`当前价格距离MA60 ${formatPct(core?.ma60DistancePct, 1, true)}`} formula="当前均线偏离减近252日均值，再除以标准差" />
          </div>

          <div className="history-insight-grid">
            <HistoryPanel dashboard={dashboard && isUsable(dashboard.meta.history) ? dashboard : null} />
            <div className="insight-side">
              <RelativeGauge value={core?.relativeReturn20Pct} />
              <div className="reading-note">
                <span>阅读顺序</span>
                <ol>
                  <li>先看回撤深度与历史分位</li>
                  <li>再看波动率冲击与均线异常偏离</li>
                  <li>最后核对份额、内部宽度和交易质量</li>
                </ol>
                <p>这套顺序只组织证据，不判断是否已经见底。</p>
              </div>
            </div>
          </div>

          <div className="section-subhead">
            <div><h3>ETF九维观察</h3><p>每张卡保留方向语义、关键原始数据和一句解释；评分公式后续单独讨论。</p></div>
            <span>9 个分类 · 点击展开完整指标</span>
          </div>

          <div className="category-grid etf-category-grid">
            <CategoryCard title="标的指数估值吸引力" direction="越高代表估值越有吸引力" unavailable evidence={[{ label: 'PE历史分位', value: '—' }, { label: 'PB历史分位', value: '—' }, { label: '股息率', value: '—' }]} detailEvidence={[{ label: 'PE历史分位', value: '—' }, { label: 'PB历史分位', value: '—' }, { label: '股息率', value: '—' }, { label: '成分股估值中位数', value: '—' }, { label: '破净比例', value: '—' }, { label: '亏损股比例', value: '—' }]} interpretation="指数估值数据尚未接入，暂不以ETF价格高低代替估值判断。" />
            <CategoryCard title="不同周期收益" direction="补充核心指标，不重复展示回撤分位和RSI" evidence={[{ label: '5日收益', value: formatPct(core?.return5Pct, 2, true) }, { label: '20日收益', value: formatPct(core?.return20Pct, 2, true) }, { label: '60日收益', value: formatPct(core?.return60Pct, 2, true) }]} detailEvidence={[{ label: '5日收益', value: formatPct(core?.return5Pct, 2, true) }, { label: '20日收益', value: formatPct(core?.return20Pct, 2, true) }, { label: '60日收益', value: formatPct(core?.return60Pct, 2, true) }, { label: '120日收益', value: formatPct(core?.return120Pct, 2, true) }, { label: '20日相对沪深300', value: formatPct(core?.relativeReturn20Pct, 2, true) }]} interpretation="不同周期收益用于辨别短期反弹和中期趋势，不重复列出上方已经解释过的回撤分位与RSI14。" />
            <CategoryCard title="波动率冲击度" direction="越高代表当前波动越极端" evidence={[{ label: 'RV20分位', value: formatPct(core?.realizedVolatilityPercentile, 1) }, { label: 'ATR分位', value: formatPct(core?.atrPercentile, 1) }, { label: 'RV20', value: formatPct(core?.realizedVolatility20Pct, 1) }]} detailEvidence={[{ label: '20日实现波动率', value: formatPct(core?.realizedVolatility20Pct, 1) }, { label: 'RV20历史分位', value: formatPct(core?.realizedVolatilityPercentile, 1) }, { label: 'ATR14/价格', value: formatPct(core?.atr14Pct, 2) }, { label: 'ATR历史分位', value: formatPct(core?.atrPercentile, 1) }, { label: 'RV5 / RV60', value: '—' }, { label: '下行半方差', value: '—' }]} interpretation={core?.realizedVolatilityPercentile != null ? `20日实现波动率处于自身历史${formatPct(core.realizedVolatilityPercentile, 1)}分位，说明当前是否属于波动率冲击可直接与自身历史比较。` : '实现波动率和ATR历史分位暂不可用。'} />
            <CategoryCard title="相对强弱" direction="-100偏弱 / +100偏强" evidence={[{ label: '20日相对收益', value: formatPct(core?.relativeReturn20Pct, 1, true) }, { label: '5日相对收益', value: '—' }, { label: '60日相对收益', value: '—' }]} detailEvidence={[{ label: '5日相对沪深300', value: '—' }, { label: '20日相对沪深300', value: formatPct(core?.relativeReturn20Pct, 1, true) }, { label: '60日相对沪深300', value: '—' }, { label: '120日相对沪深300', value: '—' }, { label: '同类ETF相对收益', value: '—' }, { label: 'Beta调整超额', value: '—' }]} interpretation="相对强弱只说明与基准相比的表现，不替代绝对回撤和历史位置。" />
            <CategoryCard title="ETF份额与资金状态" direction="越高代表逆势承接越明显" evidence={[{ label: '5日份额变化', value: formatPct(capital?.shareChange5dPct, 2, true) }, { label: '20日份额变化', value: formatPct(capital?.shareChange20dPct, 2, true) }, { label: '折溢价', value: formatPct(capital?.discountRatePct, 2, true) }]} detailEvidence={[{ label: '最新份额', value: formatMoney(capital?.latestShares) }, { label: '1日份额变化', value: formatPct(capital?.shareChange1dPct, 2, true) }, { label: '5日份额变化', value: formatPct(capital?.shareChange5dPct, 2, true) }, { label: '20日份额变化', value: formatPct(capital?.shareChange20dPct, 2, true) }, { label: '折溢价', value: formatPct(capital?.discountRatePct, 2, true) }, { label: '主力净流入', value: formatMoney(capital?.mainNetInflow) }, { label: '历史快照数', value: formatNumber(capital?.snapshotsAvailable) }, { label: 'AUM价格/份额拆分', value: '—' }]} interpretation={capital?.shareChange5dPct != null ? `价格变化期间5日份额变化为${formatPct(capital.shareChange5dPct, 2, true)}；申购赎回只作为资金行为证据，不解释为聪明钱。` : '份额历史需要逐日累积，当前不足以判断资金是否持续逆势申购。'} />
            <CategoryCard title="内部市场宽度健康度" direction="越高代表成分股结构越健康" unavailable={!breadth || breadth.availability !== 'available'} evidence={[{ label: 'MA20上方', value: formatPct(breadth?.ma20AbovePct, 1) }, { label: 'MA60上方', value: formatPct(breadth?.ma60AbovePct, 1) }, { label: '创20日新低', value: formatPct(breadth?.newLow20Pct, 1) }]} detailEvidence={[{ label: 'MA20上方比例', value: formatPct(breadth?.ma20AbovePct, 1) }, { label: 'MA60上方比例', value: formatPct(breadth?.ma60AbovePct, 1) }, { label: 'MA120上方比例', value: formatPct(breadth?.ma120AbovePct, 1) }, { label: '创20日新低比例', value: formatPct(breadth?.newLow20Pct, 1) }, { label: '上涨家数占比', value: '—' }, { label: '成分股RSI分布', value: '—' }, { label: 'Breadth Divergence', value: '—' }]} interpretation={breadth?.availability === 'available' ? '成分股均线宽度已取得；若指数创新低而新低个股比例收缩，将单独提示宽度背离。' : '指数逐时点成分股和成分股历史底座尚未完成，当前不伪造内部宽度。'} />
            <CategoryCard title="量价与技术状态" direction="展示异常程度，不判断止跌" evidence={[{ label: '成交额', value: formatMoney(spot?.turnoverAmount) }, { label: '距MA60', value: core?.ma60DistanceZScore != null ? `${formatNumber(core.ma60DistanceZScore, 2)}σ` : '—' }, { label: '20日收益', value: formatPct(core?.return20Pct, 2, true) }]} detailEvidence={[{ label: '成交额', value: formatMoney(spot?.turnoverAmount) }, { label: '换手率', value: formatPct(spot?.turnoverRatePct, 2) }, { label: '距MA60标准差', value: core?.ma60DistanceZScore != null ? `${formatNumber(core.ma60DistanceZScore, 2)}σ` : '—' }, { label: '距MA60百分比', value: formatPct(core?.ma60DistancePct, 1, true) }, { label: '布林%B', value: '—' }, { label: '量价背离', value: '—' }, { label: '均线斜率', value: '—' }]} interpretation="标准化均线偏离用于识别异常位置；量价背离和布林带数据尚未接入。" />
            <CategoryCard title="关键位置" direction="越高代表更接近历史支持区域" evidence={[{ label: '距52周低点', value: '—' }, { label: '距MA250', value: '—' }, { label: '当前回撤', value: formatPct(core?.currentDrawdownPct, 1) }]} detailEvidence={[{ label: '距52周低点', value: '—' }, { label: '距区间下沿', value: '—' }, { label: '距MA250', value: '—' }, { label: '滚动支撑位', value: '—' }, { label: '箱体位置', value: '—' }, { label: '成交密集区距离', value: '—' }]} interpretation="关键位置模块保留支撑、箱体和长期均线距离，但第一版不把图形形态包装成买入信号。" />
            <CategoryCard title="交易质量" direction="越高代表交易与跟踪质量越好" evidence={[{ label: '成交额', value: formatMoney(spot?.turnoverAmount) }, { label: '单位净值', value: formatNumber(spot?.nav, 4) }, { label: '申赎状态', value: spot?.subscriptionStatus && spot?.redemptionStatus ? `${spot.subscriptionStatus}/${spot.redemptionStatus}` : '—' }]} detailEvidence={[{ label: '成交额', value: formatMoney(spot?.turnoverAmount) }, { label: '换手率', value: formatPct(spot?.turnoverRatePct, 2) }, { label: '单位净值', value: formatNumber(spot?.nav, 4) }, { label: '净值日期', value: spot?.navDate ?? '—' }, { label: 'IOPV', value: formatNumber(spot?.iopv, 4) }, { label: '折溢价', value: formatPct(spot?.discountRatePct, 2, true) }, { label: '申购状态', value: spot?.subscriptionStatus ?? '—' }, { label: '赎回状态', value: spot?.redemptionStatus ?? '—' }]} interpretation="成交价来自新浪，单位净值及申赎状态来自同花顺；IOPV缺失时不以单位净值代替。" />
          </div>
        </section>
        )}

        {view === 'research' && (
        <section className="layer-section research-layer" id="research-layer">
          <div className="layer-heading">
            <div className="layer-index">第三层</div>
            <div><h2>{selectedItem.name} · 历史参考统计</h2><p>这是从单只ETF详情进入的统计支线；只提供指定持有期的条件概率、上行与下行空间。</p></div>
            <div className="layer-actions research-nav-actions"><span className="stage-badge">公式待定义</span><div><button type="button" className="quiet-action" onClick={() => changeView('detail')}>← 返回ETF详情</button><button type="button" className="quiet-action" onClick={() => changeView('pool')}>返回ETF池</button></div></div>
          </div>

          <div className="horizon-bar">
            <div><strong>参考期限</strong><span>界面可切换，当前不计算结果</span></div>
            <div className="horizon-options" role="group" aria-label="选择统计持有期">
              {[{ days: 3, label: '3天' }, { days: 5, label: '1周' }, { days: 10, label: '半个月' }, { days: 15, label: '3周' }, { days: 20, label: '1个月' }].map((item) => (
                <button key={item.days} type="button" className={horizon === item.days ? 'selected' : ''} onClick={() => setHorizon(item.days)}>{item.label}<small>{item.days}个交易日</small></button>
              ))}
            </div>
          </div>

          <div className="research-lock-note"><span>计算尚未启用</span><p>选择了 {horizon} 个交易日。以下区域只固定最终产品结构，不显示演示胜率、模拟收益或虚构置信区间。</p></div>

          <div className="research-grid">
            <ResearchMetric label="正收益概率" description="历史条件概率与置信区间" />
            <ResearchMetric label="Expected Value" description="扣除交易成本后的条件均值" />
            <ResearchMetric label="中位数收益" description="降低极端样本对均值的扭曲" />
            <ResearchMetric label="预期上行" description="正收益样本及75%/90%分位" />
            <ResearchMetric label="预期下行" description="负收益均值、10%分位与ES" />
            <ResearchMetric label="MAE / MFE" description="持有期最大不利/有利波动" />
          </div>

          <div className="third-layer-grid">
            <article className="future-module">
              <div><span>AI辅助分析</span><b>结构已保留</b></div>
              <p>后续固定按“数据事实、有利证据、不利证据、冲突证据、历史参考”输出，所有文字都必须追溯到前两层数据。</p>
              <div className="future-tags"><span>数据事实</span><span>有利证据</span><span>不利证据</span><span>冲突证据</span></div>
            </article>
            <article className="future-module">
              <div><span>Historical Twin</span><b>方法待验证</b></div>
              <p>展示相似状态集合、有效样本数、相似度和置信区间；不会寻找一个“最像的历史日期”冒充预测。</p>
              <div className="future-tags"><span>有效样本</span><span>区块Bootstrap</span><span>相似度</span></div>
            </article>
            <article className="future-module">
              <div><span>Opportunity Ranking</span><b>弱排序</b></div>
              <p>只比较当前Risk/Reward，不预测哪个ETF长期最强；保留进攻、均衡、防守和Pareto四种视角。</p>
              <div className="future-tags"><span>进攻</span><span>均衡</span><span>防守</span><span>Pareto</span></div>
            </article>
          </div>
        </section>
        )}

        <footer className="product-boundary">
          <strong>系统边界</strong>
          <span>不判断基本面</span><span>不负责止跌确认</span><span>不输出买卖命令</span><span>不承诺收益</span>
          <p>人类与AI读取同一套数据；AI负责整理证据和统计参考，人类负责最终判断与交易。</p>
        </footer>
      </div>
    </main>
  );
}
