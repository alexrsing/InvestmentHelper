import { useState, useCallback } from 'react';
import type { ETFResponse } from '../types/etf';
import { getETF } from '../api/etfApi';
import { getMockETF } from '../mocks/etfData';

export function useETF() {
  const [etf, setETF] = useState<ETFResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchETF = useCallback(async (ticker: string) => {
    setLoading(true);
    setError(null);
    setETF(null);

    try {
      const data = await getETF(ticker);
      setETF(data);
    } catch {
      // Fall back to mock data if API is unreachable
      const mock = getMockETF(ticker);
      if (mock) {
        setETF(mock);
        setError(null);
      } else {
        setError(`ETF "${ticker.toUpperCase()}" not found`);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const clear = useCallback(() => {
    setETF(null);
    setError(null);
  }, []);

  return { etf, loading, error, fetchETF, clear };
}
