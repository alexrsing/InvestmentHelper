import type { PortfolioSummary } from '../../types/portfolio';
import StatCard from '../common/StatCard';

function fmt(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}

function pct(n: number): string {
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}

export default function PortfolioSummaryCard({ summary }: { summary: PortfolioSummary }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <StatCard
        label="Total Value"
        value={fmt(summary.totalValue)}
      />
      <StatCard
        label="Daily Change"
        value={fmt(summary.dailyChange)}
        subValue={pct(summary.dailyChangePercent)}
        trend={summary.dailyChange >= 0 ? 'up' : 'down'}
      />
      <StatCard
        label="Total Return"
        value={fmt(summary.totalGain)}
        subValue={pct(summary.totalGainPercent)}
        trend={summary.totalGain >= 0 ? 'up' : 'down'}
      />
    </div>
  );
}
