import { useState, type FormEvent } from 'react';

const TICKER_PATTERN = /^[A-Za-z]{1,10}$/;

export default function ETFSearchBar({
  onSearch,
  loading,
}: {
  onSearch: (ticker: string) => void;
  loading: boolean;
}) {
  const [input, setInput] = useState('');
  const [validationError, setValidationError] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim().toUpperCase();
    if (!trimmed) {
      setValidationError('Enter a ticker symbol');
      return;
    }
    if (!TICKER_PATTERN.test(trimmed)) {
      setValidationError('Ticker must be 1-10 letters only');
      return;
    }
    setValidationError('');
    onSearch(trimmed);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2">
      <div className="flex-1">
        <input
          type="text"
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            setValidationError('');
          }}
          placeholder="Enter ETF ticker (e.g. SPY, QQQ, VOO)"
          className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          disabled={loading}
          autoFocus
        />
        {validationError && (
          <p className="text-xs text-red-500 mt-1">{validationError}</p>
        )}
      </div>
      <button
        type="submit"
        disabled={loading}
        className="px-6 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
      >
        {loading ? 'Searching...' : 'Search'}
      </button>
    </form>
  );
}
