import { apiFetch } from './client';
import type { ETFResponse, ETFHistoryResponse, ETFHistoryQueryParams } from '../types/etf';

const BASE = '/api/v1/etfs';

export async function getETF(ticker: string): Promise<ETFResponse> {
  return apiFetch<ETFResponse>(`${BASE}/${encodeURIComponent(ticker)}`);
}

export async function getETFHistory(
  ticker: string,
  params?: ETFHistoryQueryParams,
): Promise<ETFHistoryResponse> {
  const searchParams = new URLSearchParams();
  if (params?.start_date) searchParams.set('start_date', params.start_date);
  if (params?.end_date) searchParams.set('end_date', params.end_date);
  if (params?.limit) searchParams.set('limit', String(params.limit));

  const qs = searchParams.toString();
  const url = `${BASE}/${encodeURIComponent(ticker)}/history${qs ? `?${qs}` : ''}`;
  return apiFetch<ETFHistoryResponse>(url);
}
