export type DataStatus = 'live' | 'cached' | 'stale' | 'sample';

export type ProviderHealth = {
  enabled: boolean;
  installed?: boolean;
  role: string;
};

export type HealthStatus = {
  status: string;
  dataMode: string;
  version: string;
  providers: {
    freeData: ProviderHealth & { components?: string[] };
    akshare: ProviderHealth;
    aktools: ProviderHealth;
    mootdx: ProviderHealth;
    manualUpload: ProviderHealth;
  };
  sourceActivity: Record<string, {
    successes: number;
    failures: number;
    lastSuccessAt?: string | null;
    lastErrorAt?: string | null;
    lastError?: string | null;
  }>;
  imports: Array<{
    dataset: string;
    importedAt: string;
    source: string;
    rows: number;
  }>;
};

export type ImportResult = {
  status: 'imported';
  dataset: 'history' | 'spot';
  symbol: string;
  rows: number;
  source: string;
};

export type DatasetMeta = {
  source: string;
  status: DataStatus;
  asOf: string;
  expiresAt: string;
  message?: string | null;
};

export type Industry = {
  code: string;
  name: string;
  changePct: number | null;
  advancers: number;
  decliners: number;
  turnoverRatePct: number | null;
  leader?: string | null;
  leaderChangePct?: number | null;
};

export type MarketOverview = {
  summary: {
    totalCount: number;
    advancers: number;
    decliners: number;
    flat: number;
    medianChangePct: number | null;
    turnoverAmount: number | null;
    downMoreThan5Pct: number;
    upMoreThan5Pct: number;
  };
  distribution: Array<{ label: string; count: number }>;
  industries: {
    leaders: Industry[];
    laggards: Industry[];
    all: Industry[];
  };
  breadthHistory: { availability: string; message: string };
  index: {
    symbol: string;
    name: string;
    close: number | null;
    core: ETFDashboard['core'];
    valuation: {
      date: string | null;
      peTtm: number | null;
      peRecentPercentile: number | null;
      peObservations: number;
      dividendYieldPct: number | null;
    };
  };
  meta: {
    market: DatasetMeta;
    industries: DatasetMeta;
    indexHistory: DatasetMeta;
    indexValuation: DatasetMeta;
  };
};

export type ETFListItem = {
  symbol: string;
  name: string;
  price: number | null;
  changePct: number | null;
  iopv: number | null;
  nav: number | null;
  navDate?: string | null;
  discountRatePct: number | null;
  turnoverAmount: number | null;
  turnoverRatePct: number | null;
  latestShares: number | null;
  mainNetInflow: number | null;
  dataDate?: string | null;
  updatedAt?: string | null;
  subscriptionStatus?: string | null;
  redemptionStatus?: string | null;
  shareDate?: string | null;
  quoteSource?: string | null;
};

export type ETFDashboard = {
  etf: ETFListItem;
  core: {
    availability: string;
    observations: number;
    historyStart?: string;
    historyEnd?: string;
    currentDrawdownPct?: number | null;
    drawdownPercentile?: number | null;
    rsi14?: number | null;
    realizedVolatility20Pct?: number | null;
    realizedVolatilityPercentile?: number | null;
    atr14Pct?: number | null;
    atrPercentile?: number | null;
    ma60DistancePct?: number | null;
    ma60DistanceZScore?: number | null;
    return5Pct?: number | null;
    return20Pct?: number | null;
    return60Pct?: number | null;
    return120Pct?: number | null;
    relativeReturn20Pct?: number | null;
    history?: Array<{
      date: string;
      close: number;
      changePct: number | null;
      drawdownPct: number;
      turnoverAmount: number | null;
    }>;
  };
  capital: {
    latestShares: number | null;
    shareChange1dPct: number | null;
    shareChange5dPct: number | null;
    shareChange20dPct: number | null;
    discountRatePct: number | null;
    mainNetInflow: number | null;
    snapshotsAvailable: number;
    history: Array<{
      date: string;
      shares: number | null;
      price: number | null;
      discountRatePct: number | null;
      source: string;
    }>;
  };
  internalBreadth: {
    availability: string;
    ma20AbovePct: number | null;
    ma60AbovePct: number | null;
    ma120AbovePct: number | null;
    newLow20Pct: number | null;
    message: string;
  };
  meta: { spot: DatasetMeta; history: DatasetMeta; benchmark: DatasetMeta };
};
