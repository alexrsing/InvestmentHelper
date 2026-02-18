import { useState, useEffect } from 'react';
import type { Portfolio } from '../types/portfolio';
import { mockPortfolio } from '../mocks/portfolioData';

export function usePortfolio() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Using mock data since backend portfolio service is a stub
    const timer = setTimeout(() => {
      setPortfolio(mockPortfolio);
      setLoading(false);
    }, 300);
    return () => clearTimeout(timer);
  }, []);

  return { portfolio, loading, error, setError };
}
