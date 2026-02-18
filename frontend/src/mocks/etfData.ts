import type { ETFResponse, ETFHistoryItem } from '../types/etf';

export const mockETFs: Record<string, ETFResponse> = {
  SPY: {
    ticker: 'SPY',
    name: 'SPDR S&P 500 ETF Trust',
    description: 'Tracks the S&P 500 index, one of the most popular benchmarks for US large-cap stocks.',
    expense_ratio: 0.0945,
    aum: 560000000000,
    inception_date: '1993-01-22T00:00:00Z',
    current_price: 587.42,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2026-02-18T00:00:00Z',
  },
  QQQ: {
    ticker: 'QQQ',
    name: 'Invesco QQQ Trust',
    description: 'Tracks the Nasdaq-100 Index, which includes 100 of the largest non-financial companies listed on Nasdaq.',
    expense_ratio: 0.20,
    aum: 280000000000,
    inception_date: '1999-03-10T00:00:00Z',
    current_price: 485.21,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2026-02-18T00:00:00Z',
  },
  VOO: {
    ticker: 'VOO',
    name: 'Vanguard S&P 500 ETF',
    description: 'Tracks the S&P 500 index with one of the lowest expense ratios available.',
    expense_ratio: 0.03,
    aum: 420000000000,
    inception_date: '2010-09-07T00:00:00Z',
    current_price: 512.34,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2026-02-18T00:00:00Z',
  },
};

function generateMockHistory(ticker: string, days: number): ETFHistoryItem[] {
  const basePrice = mockETFs[ticker]?.current_price ?? 100;
  const items: ETFHistoryItem[] = [];
  const now = new Date();

  for (let i = days; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    if (date.getDay() === 0 || date.getDay() === 6) continue;

    const drift = (Math.random() - 0.48) * 0.02;
    const prevClose = items.length > 0 ? items[items.length - 1].close_price : basePrice * 0.95;
    const open = prevClose * (1 + drift);
    const high = open * (1 + Math.random() * 0.015);
    const low = open * (1 - Math.random() * 0.015);
    const close = low + Math.random() * (high - low);

    items.push({
      date: date.toISOString().split('T')[0],
      open_price: Math.round(open * 100) / 100,
      high_price: Math.round(high * 100) / 100,
      low_price: Math.round(low * 100) / 100,
      close_price: Math.round(close * 100) / 100,
      adjusted_close: Math.round(close * 100) / 100,
      volume: Math.round(10000000 + Math.random() * 50000000),
    });
  }

  return items;
}

export function getMockETF(ticker: string): ETFResponse | null {
  return mockETFs[ticker.toUpperCase()] ?? null;
}

export function getMockHistory(ticker: string): ETFHistoryItem[] {
  return generateMockHistory(ticker.toUpperCase(), 90);
}
