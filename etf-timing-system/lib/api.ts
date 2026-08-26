import type { ETFDashboard, ETFListItem, HealthStatus, ImportResult, MarketOverview } from './types';

const baseUrl = process.env.NEXT_PUBLIC_ETF_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1';

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${path}`);
  }
  return response.json() as Promise<T>;
}

export function getMarket(refresh = false) {
  return request<MarketOverview>(`/market/overview${refresh ? '?refresh=true' : ''}`);
}

export async function getETFs(refresh = false, query = ''): Promise<ETFListItem[]> {
  const queryString = query ? `&query=${encodeURIComponent(query)}` : '';
  const result = await request<{ items: ETFListItem[] }>(
    `/etfs?limit=${query ? 20 : 80}${queryString}${refresh ? '&refresh=true' : ''}`,
  );
  return result.items;
}

export function getETFDashboard(symbol: string, refresh = false) {
  return request<ETFDashboard>(
    `/etfs/${encodeURIComponent(symbol)}/dashboard${refresh ? '?refresh=true' : ''}`,
  );
}

export function getHealth() {
  return request<HealthStatus>('/health');
}

export function getImportTemplateUrl(dataset: 'history' | 'spot') {
  return `${baseUrl}/imports/template?dataset=${dataset}`;
}

export async function importETFFile(
  file: File,
  dataset: 'history' | 'spot',
  symbol: string,
) {
  const body = new FormData();
  body.append('file', file);
  body.append('dataset', dataset);
  body.append('symbol', symbol);
  const response = await fetch(`${baseUrl}/imports/etf`, { method: 'POST', body });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `导入失败：HTTP ${response.status}`);
  }
  return response.json() as Promise<ImportResult>;
}
