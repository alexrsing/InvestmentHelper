export interface Holding {
  ticker: string;
  name: string;
  shares: number;
  avgCost: number;
  currentPrice: number;
  value: number;
  gain: number;
  gainPercent: number;
  allocation: number;
}

export interface PortfolioSummary {
  totalValue: number;
  dailyChange: number;
  dailyChangePercent: number;
  totalGain: number;
  totalGainPercent: number;
}

export interface PerformancePeriod {
  label: string;
  returnPercent: number;
}

export interface AllocationSlice {
  name: string;
  ticker: string;
  value: number;
  percent: number;
  color: string;
}

export interface Portfolio {
  summary: PortfolioSummary;
  holdings: Holding[];
  allocation: AllocationSlice[];
  performance: PerformancePeriod[];
}
