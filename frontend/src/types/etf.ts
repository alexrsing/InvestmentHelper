export interface ETFResponse {
  ticker: string;
  name: string | null;
  description: string | null;
  expense_ratio: number | null;
  aum: number | null;
  inception_date: string | null;
  current_price: number | null;
  created_at: string;
  updated_at: string;
}

export interface ETFHistoryItem {
  date: string;
  open_price: number;
  high_price: number;
  low_price: number;
  close_price: number;
  adjusted_close: number | null;
  volume: number;
}

export interface ETFHistoryResponse {
  ticker: string;
  history: ETFHistoryItem[];
  total_records: number;
}

export interface ETFHistoryQueryParams {
  start_date?: string;
  end_date?: string;
  limit?: number;
}

export interface ErrorResponse {
  detail: string;
  error_code?: string;
}
