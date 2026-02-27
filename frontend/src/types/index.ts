export interface ETFPosition {
  ticker: string;
  name: string | null;
  current_price: number | null;
  open_price: number | null;
  risk_range_low: number | null;
  risk_range_high: number | null;
  shares: number;
  recommendation: string | null;
}

export interface PortfolioSummary {
  total_value: number;
  initial_value: number;
  percent_change: number;
  positions: ETFPosition[];
}

export interface ETFHistoryItem {
  date: string;
  open_price: number;
  high_price: number;
  low_price: number;
  close_price: number;
  adjusted_close: number | null;
  volume: number;
  risk_range_low?: number;
  risk_range_high?: number;
}

export interface ETFHistoryResponse {
  ticker: string;
  history: ETFHistoryItem[];
  total_records: number;
}

export interface TradingRules {
  max_position_pct: number;
}
