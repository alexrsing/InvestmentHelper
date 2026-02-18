import type { ETFResponse } from '../../types/etf';

function fmtCurrency(n: number | null): string {
  if (n == null) return 'N/A';
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}

function fmtAUM(n: number | null): string {
  if (n == null) return 'N/A';
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return fmtCurrency(n);
}

export default function ETFDetailCard({ etf }: { etf: ETFResponse }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 sm:p-5">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 mb-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">{etf.ticker}</h2>
          {etf.name && <p className="text-sm text-gray-600">{etf.name}</p>}
        </div>
        <div className="text-left sm:text-right">
          <p className="text-2xl font-bold text-gray-900">{fmtCurrency(etf.current_price)}</p>
        </div>
      </div>

      {etf.description && (
        <p className="text-sm text-gray-600 mb-4">{etf.description}</p>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-gray-500">Expense Ratio</p>
          <p className="font-semibold text-gray-900">
            {etf.expense_ratio != null ? `${etf.expense_ratio.toFixed(2)}%` : 'N/A'}
          </p>
        </div>
        <div>
          <p className="text-gray-500">AUM</p>
          <p className="font-semibold text-gray-900">{fmtAUM(etf.aum)}</p>
        </div>
        <div>
          <p className="text-gray-500">Inception</p>
          <p className="font-semibold text-gray-900">
            {etf.inception_date
              ? new Date(etf.inception_date).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                })
              : 'N/A'}
          </p>
        </div>
      </div>
    </div>
  );
}
