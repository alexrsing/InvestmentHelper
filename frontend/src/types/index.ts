export interface Recommendation {
  signal: string;
  shares_to_trade: number;
  target_position_value: number;
  current_position_value: number;
  penetration_depth: number;
}

export interface Research {
  sentiment: string;
  summary: string;
  researched_at: string;
}

export interface DecisionStatus {
  action: string;
  shares: number;
  date: string;
}

export interface ETFPosition {
  ticker: string;
  name: string | null;
  current_price: number | null;
  open_price: number | null;
  risk_range_low: number | null;
  risk_range_high: number | null;
  shares: number;
  recommendation: Recommendation | null;
  research: Research | null;
  decision_status: DecisionStatus | null;
}

export interface PortfolioSummary {
  total_value: number;
  initial_value: number;
  percent_change: number;
  cash_balance: number;
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
  min_position_pct: number;
}

export interface TradeRequest {
  ticker: string;
  action: "accepted" | "declined";
  shares: number;
  signal: "Buy" | "Sell";
}

export interface TradeResponse {
  ticker: string;
  signal: string;
  action: string;
  shares: number;
  price: number;
  position_before: number;
  position_after: number;
  cash_before: number;
  cash_after: number;
  date: string;
  created_at: string;
}

export interface TradeHistoryItem {
  ticker: string;
  signal: string;
  action: string;
  shares: number;
  price: number;
  position_before: number;
  position_after: number;
  cash_before: number;
  cash_after: number;
  date: string;
  created_at: string;
}

export interface TradeHistoryResponse {
  trades: TradeHistoryItem[];
}
