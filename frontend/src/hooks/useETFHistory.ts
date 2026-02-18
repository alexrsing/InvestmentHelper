import { useState, useCallback } from 'react';
import type { ETFHistoryItem } from '../types/etf';
import { getETFHistory } from '../api/etfApi';
import { getMockHistory } from '../mocks/etfData';

export function useETFHistory() {
  const [history, setHistory] = useState<ETFHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async (ticker: string) => {
    setLoading(true);
    setError(null);
    setHistory([]);

    try {
      const data = await getETFHistory(ticker, { limit: 200 });
      setHistory(data.history);
    } catch {
      // Fall back to mock data
      const mock = getMockHistory(ticker);
      if (mock.length > 0) {
        setHistory(mock);
        setError(null);
      } else {
        setError('Could not load history');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const clear = useCallback(() => {
    setHistory([]);
    setError(null);
  }, []);

  return { history, loading, error, fetchHistory, clear };
}
